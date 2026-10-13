"""
Online scope tests: do the README's scope tables match what Atlassian enforces?

Atlassian offers no API to mint tokens, so you create them once, by hand, in the
token form at id.atlassian.com, and list them in tests/scope_tokens.json (see
scope_tokens.example.json; `python3 scripts/scope_lab.py` prints the scopes to tick):

    [{"name": "readonly", "set": "readonly", "token": "..."},
     {"name": "just-comments", "scopes": ["read:comment:jira", ...], "token": "..."}]

For every token and every action, the test predicts from scope_data.py whether
the call should be allowed (every endpoint it needs has all its scopes in the
token), runs it, and fails on a mismatch in either direction:

* predicted allowed, got a scope error  -> the README is missing a scope
* predicted denied, got through         -> the README lists a scope the call does not need

Other failures (a project that forbids the call, a missing feature) are reported
as inconclusive, not as mismatches.

    python3 -m pytest tests/test_live_scopes.py -m live -rs
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import jirav2.operations as operations_module
from jirav2.scope_data import ENDPOINT_SCOPES
from jirav2.scopes import scope_sets
from live_support import ConnectorError, ENV, LABEL, is_scope_error, needs_site, runner

pytestmark = [pytest.mark.live, needs_site]

TOKENS_FILE = Path(__file__).parent / 'scope_tokens.json'
# Parallel probes per token. Atlassian rate-limits (429); the client retries, and any that still
# fail are reported as inconclusive rather than as a mismatch. Lower it if you see many.
WORKERS = int(os.environ.get('JIRA_LIVE_WORKERS', '6'))

GET_ISSUE = 'GET /rest/api/3/issue/{issueIdOrKey}'
PUT_ISSUE = 'PUT /rest/api/3/issue/{issueIdOrKey}'
DELETE_ISSUE = 'DELETE /rest/api/3/issue/{issueIdOrKey}'
GET_TRANSITIONS = 'GET /rest/api/3/issue/{issueIdOrKey}/transitions'
POST_TRANSITIONS = 'POST /rest/api/3/issue/{issueIdOrKey}/transitions'
COMMENT = '/rest/api/3/issue/{issueIdOrKey}/comment'
DESK = '/rest/servicedeskapi/servicedesk/{serviceDeskId}'
USERS = 'GET /rest/api/3/users/search'
ISSUETYPE = 'GET /rest/api/3/issuetype'


def _entries():
    if not TOKENS_FILE.exists():
        return []
    return json.loads(TOKENS_FILE.read_text())


ENTRIES = _entries()


def token_scopes(entry):
    family = entry.get('family', 'granular')
    if 'scopes' in entry:
        return family, set(entry['scopes'])
    return family, set(scope_sets()[entry['set']][family])


def predicted_allowed(endpoints, family, scopes):
    for key in endpoints:
        needed = ENDPOINT_SCOPES[key][family]
        # An endpoint with no scopes in this family cannot be reached with this family at all.
        if not needed or not set(needed) <= scopes:
            return False
    return True


class Probes(object):
    """One minimal call per action, plus the endpoints that call needs."""

    def __init__(self, site):
        self.site = site

    # Fixtures are made with the unrestricted token (the thing under test is the scoped one).
    # Reads and harmless edits share one issue/comment/request for the whole session; only the
    # destructive actions (delete, status change) get a fresh one.
    def issue(self):
        return self.site.shared('issue', self.site.new_issue)

    def issue2(self):
        return self.site.shared('issue2', self.site.new_issue)

    def fresh_issue(self):
        return self.site.new_issue()

    def comment(self):
        key = self.issue()
        return key, self.site.shared('comment', lambda: self.site.jira(
            'add_comment', issue_key=key, comment='scope probe')['id'])

    def fresh_comment(self):
        key = self.issue()
        return key, self.site.jira('add_comment', issue_key=key, comment='scope probe')['id']

    def transition_name(self):
        key = self.fresh_issue()
        options = self.site.jira('get_transitions', issue_key=key)['transitions']
        return (key, options[0]['to']['name']) if options else (key, None)

    def request_type(self):
        desk = self.site.desk
        for candidate in self.site.jira('list_request_types', service_desk_id=desk['id'])['values']:
            fields = self.site.jira('get_request_type_fields', service_desk_id=desk['id'],
                                    request_type_id=candidate['id'])['requestTypeFields']
            if {f['fieldId'] for f in fields if f.get('required')} <= {'summary', 'description'}:
                return candidate
        return None

    def request(self):
        def make():
            made = self.site.jira('create_customer_request', service_desk_id=self.site.desk['id'],
                                  request_type_id=self.request_type()['id'], summary='scope probe request',
                                  description='scope probe')
            self.site.created.append(made['issueKey'])
            return made['issueKey']
        return self.site.shared('request', make)

    def queue(self):
        queues = self.site.jira('list_queues', service_desk_id=self.site.desk['id'])['values']
        return queues[0]['id'] if queues else None

    def table(self):
        s = self.site
        jsm = bool(s.desk)
        desk_id = s.desk['id'] if jsm else None
        t = {
            'create_ticket': (['POST /rest/api/3/issue'], lambda: dict(
                project_key=s.project, issue_type_id=s.issue_type['id'], ticket_summary='scope probe', labels=LABEL)),
            'get_ticket_details': ([GET_ISSUE], lambda: dict(issue_key=self.issue())),
            'update_ticket': ([PUT_ISSUE], lambda: dict(issue_key=self.issue(), summary='scope probe update')),
            'delete_ticket': ([DELETE_ISSUE], lambda: dict(issue_key=self.fresh_issue())),
            'get_transitions': ([GET_TRANSITIONS], lambda: dict(issue_key=self.issue())),
            'assign_issue': (['PUT /rest/api/3/issue/{issueIdOrKey}/assignee'],
                             lambda: dict(issue_key=self.issue(), accountId=s.account_id)),
            'get_changelog': (['GET /rest/api/3/issue/{issueIdOrKey}/changelog'],
                              lambda: dict(issue_key=self.issue())),
            'add_worklog': (['POST /rest/api/3/issue/{issueIdOrKey}/worklog'],
                            lambda: dict(issue_key=self.issue(), time_spent='1m')),
            'add_comment': (['POST ' + COMMENT], lambda: dict(issue_key=self.issue(), comment='scope probe')),
            'get_comments': (['GET ' + COMMENT], lambda: dict(issue_key=self.issue())),
            'add_remote_link': (['POST /rest/api/3/issue/{issueIdOrKey}/remotelink'], lambda: dict(
                issue_key=self.issue(), url='https://example.com/scope', title='scope probe')),
            'list_link_types': (['GET /rest/api/3/issueLinkType'], lambda: {}),
            'validate_jql_query': (['POST /rest/api/3/jql/parse'],
                                   lambda: dict(jql_query='project is not EMPTY')),
            'list_tickets': (['POST /rest/api/3/search/jql'], lambda: dict(
                jql_query='project = "%s" AND labels = "%s"' % (s.project, LABEL), maxResults=1)),
            'list_projects': (['GET /rest/api/3/project/search'], lambda: dict(maxResults=1)),
            'get_project': (['GET /rest/api/3/project/{projectIdOrKey}'], lambda: dict(project_key=s.project)),
            'search_users': ([USERS], lambda: dict(maxResults=1)),
            'get_user_details': (['GET /rest/api/3/user'], lambda: dict(accountId=s.account_id)),
            'list_issue_types': ([ISSUETYPE], lambda: {}),
            'get_create_metadata': (['GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}'],
                                    lambda: dict(project_key=s.project, issue_type_id=s.issue_type['id'])),
            'list_priorities': (['GET /rest/api/3/priority/search'], lambda: {}),
            'list_fields': (['GET /rest/api/3/field'], lambda: {}),
            'get_project_options': (['GET /rest/api/3/project/search'], lambda: {}),
            'get_issue_type_options': ([ISSUETYPE], lambda: {}),
            'get_issue_type_id_options': ([ISSUETYPE], lambda: {}),
            'get_link_type_options': (['GET /rest/api/3/issueLinkType'], lambda: {}),
            'get_user_options': ([USERS], lambda: {}),
            'get_transition_options': ([GET_TRANSITIONS], lambda: dict(issue_key=self.issue())),
            'get_transition_id_options': ([GET_TRANSITIONS], lambda: dict(issue_key=self.issue())),
        }
        return t, jsm, desk_id

    # probes that need two-step fixtures, built separately so a missing feature skips only them
    def extra(self):
        s = self.site
        t = {
            'update_comment': (['PUT ' + COMMENT + '/{id}'], lambda: self._comment_call(
                lambda key, cid: dict(issue_key=key, comment_id=cid, comment='scope probe edit'))),
            'delete_comment': (['DELETE ' + COMMENT + '/{id}'], lambda: self._comment_call(
                lambda key, cid: dict(issue_key=key, comment_id=cid), fresh=True)),
            'set_status': ([GET_TRANSITIONS, POST_TRANSITIONS], self._status_call),
            'link_issues': (['POST /rest/api/3/issueLink'], lambda: dict(
                link_type=s.jira('list_link_types')['issueLinkTypes'][0]['name'],
                inward_issue=self.issue(), outward_issue=self.issue2())),
        }
        return t

    def _comment_call(self, build, fresh=False):
        key, comment_id = self.fresh_comment() if fresh else self.comment()
        return build(key, comment_id)

    def _status_call(self):
        key, name = self.transition_name()
        if name is None:
            raise ConnectorError('no transition available on a new issue')
        return dict(issue_key=key, status=name)

    def jsm(self):
        s = self.site
        desk = s.desk['id']
        return {
            'list_service_desks': (['GET /rest/servicedeskapi/servicedesk'], lambda: {}),
            'get_service_desk_options': (['GET /rest/servicedeskapi/servicedesk'], lambda: {}),
            'list_request_types': (['GET ' + DESK + '/requesttype'], lambda: dict(service_desk_id=desk)),
            'get_request_type_fields': (['GET ' + DESK + '/requesttype/{requestTypeId}/field'], lambda: dict(
                service_desk_id=desk, request_type_id=self.request_type()['id'])),
            'create_customer_request': (['POST /rest/servicedeskapi/request'], lambda: dict(
                service_desk_id=desk, request_type_id=self.request_type()['id'], summary='scope probe request',
                description='scope probe')),
            'get_customer_request': (['GET /rest/servicedeskapi/request/{issueIdOrKey}'],
                                     lambda: dict(issue_key=self.request())),
            'add_request_comment': (['POST /rest/servicedeskapi/request/{issueIdOrKey}/comment'], lambda: dict(
                issue_key=self.request(), comment='scope probe')),
            'list_queues': (['GET ' + DESK + '/queue'], lambda: dict(service_desk_id=desk)),
            'list_queue_issues': (['GET ' + DESK + '/queue/{queueId}/issue'], lambda: dict(
                service_desk_id=desk, queue_id=self.queue())),
        }


def _probe_table(site):
    probes = Probes(site)
    table, has_jsm, _ = probes.table()
    table.update(probes.extra())
    if has_jsm and probes.request_type() is not None:
        table.update(probes.jsm())
    return table, probes


def test_every_action_has_a_scope_probe_or_a_reason(site):
    """Every action is either probed here or is the generic call (whose scopes depend on the endpoint)."""
    from jirav2.scopes import OPERATION_ENDPOINTS
    table, _ = _probe_table(site)
    jsm_skipped = {op for op in OPERATION_ENDPOINTS if 'servicedeskapi' in ' '.join(OPERATION_ENDPOINTS[op] or [])}
    missing = set(OPERATION_ENDPOINTS) - set(table) - {'execute_api_request', 'submit_file'} - jsm_skipped
    assert not missing, 'no scope probe for %s' % sorted(missing)


def test_the_probe_endpoints_are_declared_by_the_actions(site):
    """A probe must only need endpoints the action declares, or the prediction would be wrong."""
    from jirav2.scopes import OPERATION_ENDPOINTS
    table, _ = _probe_table(site)
    for op, (endpoints, _build) in table.items():
        assert set(endpoints) <= set(OPERATION_ENDPOINTS[op]), (op, endpoints)


@pytest.mark.skipif(not ENTRIES, reason='tests/scope_tokens.json not found; see scope_tokens.example.json')
@pytest.mark.parametrize('entry', ENTRIES, ids=[e['name'] for e in ENTRIES] or None)
def test_scopes_match_what_atlassian_enforces(site, entry, monkeypatch, tmp_path):
    family, scopes = token_scopes(entry)
    config = {'server_url': ENV['JIRA_LIVE_SERVER'], 'username': entry.get('email') or ENV.get('JIRA_LIVE_USER', ''),
              'token': entry['token'], 'scoped': True, 'verify_ssl': True}
    scoped = runner(config)

    local = tmp_path / 'probe.txt'
    local.write_text('scope probe')
    monkeypatch.setattr(operations_module, '_get_file_data', lambda kind, value: ('probe.txt', str(local)))

    table, probes = _probe_table(site)
    table['submit_file'] = (['POST /rest/api/3/issue/{issueIdOrKey}/attachments'],
                            lambda: dict(issue_key=probes.issue(), path='Attachment ID', value='x'))

    def probe(op):
        """-> (op, verdict, detail); verdict is agreed | mismatch | inconclusive."""
        endpoints, build = table[op]
        expected = predicted_allowed(endpoints, family, scopes)
        try:
            params = build()
        except ConnectorError as err:
            return op, 'inconclusive', 'could not build the probe (%s)' % str(err)[:80]
        try:
            result = scoped(op, **params)
            observed = 'allowed'
            # Only issues this probe created get cleaned up (a project's "key" must never be deleted).
            created = {'create_ticket': 'key', 'create_customer_request': 'issueKey'}.get(op)
            if created and isinstance(result, dict) and result.get(created):
                site.created.append(result[created])
        except ConnectorError as err:
            if is_scope_error(err):
                observed = 'denied'
            else:
                return op, 'inconclusive', str(err)[:120]
        if (observed == 'allowed') == expected:
            return op, 'agreed', ''
        if expected:
            needed = sorted({s for k in endpoints for s in ENDPOINT_SCOPES[k][family]} - scopes)
            return op, 'mismatch', 'predicted ALLOWED but Atlassian denied it. Token lacks %s' % (needed,)
        return op, 'mismatch', ('predicted DENIED but it went through. Scopes the README demands for it are '
                                'not all required (%s)' % sorted({s for k in endpoints for s in ENDPOINT_SCOPES[k][family]}))

    # Shared fixtures are created once, up front and in parallel, so the probes do not queue behind them.
    # Probes are independent network calls, so a thread pool (not async) is all the speed-up needed.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = sorted(pool.map(probe, sorted(table)))
    mismatches = ['%s: %s' % (op, detail) for op, verdict, detail in results if verdict == 'mismatch']
    inconclusive = ['%s: %s' % (op, detail) for op, verdict, detail in results if verdict == 'inconclusive']
    agreed = sum(1 for _, verdict, _ in results if verdict == 'agreed')
    summary = '%d of %d actions agreed; %d inconclusive' % (agreed, len(table), len(inconclusive))
    if inconclusive:
        print('\ninconclusive for token %r:\n  %s' % (entry['name'], '\n  '.join(inconclusive)))
    assert not mismatches, '%s\n  %s' % (summary, '\n  '.join(mismatches))

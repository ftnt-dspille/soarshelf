"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""
import json
import os
import re
from datetime import datetime
from urllib.parse import quote, unquote, urlparse

from connectors.core.connector import ConnectorError, get_logger

from .adf import adf_to_text, to_adf
from .client import GATEWAY_HOST, JiraClient

logger = get_logger('jirav2')

API = '/rest/api/3'
JSM = '/rest/servicedeskapi'
MAX_FETCH_ALL = 1000
ORDER_BY = re.compile(r'\border\s+by\b', re.I)


# ---------------------------------------------------------------------------
# parameter helpers
# ---------------------------------------------------------------------------

def _blank(value):
    if isinstance(value, str):
        return not value.strip()
    return value is None or value == [] or value == {}


def _require(params, *names):
    for name in names:
        if _blank(params.get(name)):
            raise ConnectorError('Parameter "%s" is required.' % name)


def _ident(value, name='id'):
    """URL-encode a key or id before it goes into a path."""
    value = str(value if value is not None else '').strip()
    if not value:
        raise ConnectorError('Parameter "%s" is required.' % name)
    return quote(value, safe='')


def _json_param(value, name):
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            value = json.loads(value)
        except ValueError:
            raise ConnectorError('Parameter "%s" must be valid JSON.' % name)
    return value


def _dict_param(value, name):
    value = _json_param(value, name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConnectorError('Parameter "%s" must be a JSON object.' % name)
    return value


def _list_param(value):
    if _blank(value):
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(',') if part.strip()]


def _ok(**extra):
    result = {'status': 'Success'}
    result.update(extra)
    return result


def _jira_time(value):
    """ISO-8601 (with Z or an offset) to Jira's 2025-01-31T10:00:00.000+0000."""
    text = str(value).strip().replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ConnectorError('"%s" is not an ISO-8601 date and time.' % value)
    if parsed.tzinfo is None:
        return parsed.strftime('%Y-%m-%dT%H:%M:%S.000+0000')
    return parsed.strftime('%Y-%m-%dT%H:%M:%S.000%z')


def _page(params):
    return {'startAt': params.get('startAt'), 'maxResults': params.get('maxResults')}


def _browse_url(client, key):
    if urlparse(client.server).hostname == GATEWAY_HOST or client.scoped:
        return None
    return '%s/browse/%s' % (client.server, key)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def check_health(config):
    me = JiraClient(config).request('GET', API + '/myself')
    if not me.get('accountId'):
        raise ConnectorError('Connected, but Jira did not identify the calling user. '
                             'Check the username and API token.')
    logger.info('Connected to Jira as %s', me.get('displayName'))
    return True


# ---------------------------------------------------------------------------
# issues
# ---------------------------------------------------------------------------

def _issue_type(params):
    if params.get('issue_type_id'):
        return {'id': str(params['issue_type_id']).strip()}
    if params.get('issue_type'):
        return {'name': str(params['issue_type']).strip()}
    raise ConnectorError('Specify Issue Type (name) or Issue Type ID.')


def create_ticket(config, params):
    _require(params, 'project_key', 'ticket_summary')
    extra = _dict_param(params.get('other_fields'), 'other_fields')
    fields = {
        'project': {'key': str(params['project_key']).strip()},
        'summary': params['ticket_summary'],
    }
    if 'issuetype' not in extra:
        fields['issuetype'] = _issue_type(params)
    if not _blank(params.get('ticket_description')):
        fields['description'] = to_adf(params['ticket_description'])
    if params.get('priority'):
        fields['priority'] = {'name': params['priority']}
    if params.get('labels'):
        fields['labels'] = _list_param(params['labels'])
    if params.get('assignee_account_id'):
        fields['assignee'] = {'accountId': params['assignee_account_id']}
    if params.get('parent'):
        fields['parent'] = {'key': str(params['parent']).strip()}
    # other_fields wins, so it can set a custom field or override a name with an id.
    fields.update(extra)
    client = JiraClient(config)
    created = client.request('POST', API + '/issue', json_body={'fields': fields})
    url = _browse_url(client, created.get('key'))
    if url:
        created['browse_url'] = url
    if params.get('include_details') and created.get('key'):
        created['issue'] = client.request('GET', '%s/issue/%s' % (API, _ident(created['key'])))
    return created


def get_ticket_details(config, params):
    _require(params, 'issue_key')
    query = {'fields': ','.join(_list_param(params.get('fields'))),
             'expand': ','.join(_list_param(params.get('expand')))}
    issue = JiraClient(config).request('GET', '%s/issue/%s' % (API, _ident(params['issue_key'])),
                                       params=query)
    if params.get('include_text'):
        issue['description_text'] = adf_to_text((issue.get('fields') or {}).get('description')).strip()
    return issue


def update_ticket(config, params):
    _require(params, 'issue_key')
    key = _ident(params['issue_key'])
    fields = {}
    if not _blank(params.get('summary')):
        fields['summary'] = params['summary']
    if not _blank(params.get('description')):
        fields['description'] = to_adf(params['description'])
    if params.get('priority'):
        fields['priority'] = {'name': params['priority']}
    if params.get('labels'):
        fields['labels'] = _list_param(params['labels'])
    fields.update(_dict_param(params.get('other_fields'), 'other_fields'))
    body = {}
    if fields:
        body['fields'] = fields
    if not _blank(params.get('comment')):
        body['update'] = {'comment': [{'add': {'body': to_adf(params['comment'])}}]}
    status = params.get('status')
    if not body and not status:
        raise ConnectorError('Nothing to update: set at least one field, a comment or a status.')
    client = JiraClient(config)
    if body:
        query = {} if params.get('notify_users', True) else {'notifyUsers': 'false'}
        client.request('PUT', '%s/issue/%s' % (API, key), params=query, json_body=body)
    transition = None
    if status:
        transition = _transition(client, key, status=status)
    return _ok(issue_key=params['issue_key'], transition=transition)


def delete_ticket(config, params):
    _require(params, 'issue_key')
    delete_subtasks = 'true' if params.get('delete_subtask') else 'false'
    JiraClient(config).request('DELETE', '%s/issue/%s' % (API, _ident(params['issue_key'])),
                               params={'deleteSubtasks': delete_subtasks})
    return _ok(issue_key=params['issue_key'])


def _transitions(client, key):
    return client.request('GET', '%s/issue/%s/transitions' % (API, key)).get('transitions') or []


def _transition(client, key, status=None, transition_id=None, resolution=None, comment=None):
    options = _transitions(client, key)
    chosen = None
    if transition_id:
        chosen = next((t for t in options if str(t.get('id')) == str(transition_id)), None)
    elif status:
        wanted = str(status).strip().lower()
        chosen = next((t for t in options
                       if str((t.get('to') or {}).get('name', '')).lower() == wanted), None) \
            or next((t for t in options if str(t.get('name', '')).lower() == wanted), None)
    if chosen is None:
        available = ', '.join('%s (to %s)' % (t.get('name'), (t.get('to') or {}).get('name'))
                              for t in options) or 'none'
        raise ConnectorError('No transition matches "%s" from the issue\'s current status. '
                             'Available: %s.' % (transition_id or status, available))
    body = {'transition': {'id': str(chosen['id'])}}
    if resolution:
        body['fields'] = {'resolution': {'name': resolution}}
    if comment:
        body['update'] = {'comment': [{'add': {'body': to_adf(comment)}}]}
    client.request('POST', '%s/issue/%s/transitions' % (API, key), json_body=body)
    return {'id': chosen['id'], 'name': chosen.get('name'), 'to': (chosen.get('to') or {}).get('name')}


def set_status(config, params):
    _require(params, 'issue_key')
    if _blank(params.get('status')) and _blank(params.get('transition_id')):
        raise ConnectorError('Specify Status or Transition ID.')
    client = JiraClient(config)
    applied = _transition(client, _ident(params['issue_key']), status=params.get('status'),
                          transition_id=params.get('transition_id'),
                          resolution=params.get('resolution'), comment=params.get('comment'))
    return _ok(issue_key=params['issue_key'], transition=applied)


def get_transitions(config, params):
    _require(params, 'issue_key')
    client = JiraClient(config)
    return {'transitions': _transitions(client, _ident(params['issue_key']))}


def assign_issue(config, params):
    _require(params, 'issue_key')
    # "-1" assigns the project's default assignee; null unassigns.
    account = params.get('accountId')
    JiraClient(config).request('PUT', '%s/issue/%s/assignee' % (API, _ident(params['issue_key'])),
                               json_body={'accountId': account if not _blank(account) else None})
    return _ok(issue_key=params['issue_key'], accountId=account or None)


def get_changelog(config, params):
    _require(params, 'issue_key')
    return JiraClient(config).request(
        'GET', '%s/issue/%s/changelog' % (API, _ident(params['issue_key'])), params=_page(params))


def add_worklog(config, params):
    _require(params, 'issue_key', 'time_spent')
    body = {'timeSpent': params['time_spent']}
    if not _blank(params.get('comment')):
        body['comment'] = to_adf(params['comment'])
    if params.get('started'):
        body['started'] = _jira_time(params['started'])
    return JiraClient(config).request(
        'POST', '%s/issue/%s/worklog' % (API, _ident(params['issue_key'])), json_body=body)


# ---------------------------------------------------------------------------
# comments, attachments, links
# ---------------------------------------------------------------------------

def add_comment(config, params):
    _require(params, 'issue_key', 'comment')
    body = {'body': to_adf(params['comment'])}
    if params.get('internal'):
        # JSM: marks the comment internal (agents only) instead of customer-visible.
        body['properties'] = [{'key': 'sd.public.comment', 'value': {'internal': True}}]
    return JiraClient(config).request(
        'POST', '%s/issue/%s/comment' % (API, _ident(params['issue_key'])), json_body=body)


def get_comments(config, params):
    _require(params, 'issue_key')
    query = _page(params)
    query['orderBy'] = params.get('orderBy')
    result = JiraClient(config).request(
        'GET', '%s/issue/%s/comment' % (API, _ident(params['issue_key'])), params=query)
    if params.get('include_text'):
        for comment in result.get('comments') or []:
            comment['body_text'] = adf_to_text(comment.get('body')).strip()
    return result


def update_comment(config, params):
    _require(params, 'issue_key', 'comment_id', 'comment')
    return JiraClient(config).request(
        'PUT', '%s/issue/%s/comment/%s' % (API, _ident(params['issue_key']), _ident(params['comment_id'])),
        json_body={'body': to_adf(params['comment'])})


def delete_comment(config, params):
    _require(params, 'issue_key', 'comment_id')
    JiraClient(config).request(
        'DELETE', '%s/issue/%s/comment/%s' % (API, _ident(params['issue_key']), _ident(params['comment_id'])))
    return _ok(issue_key=params['issue_key'], comment_id=params['comment_id'])


def _get_file_data(iri_type, iri):
    """Resolve a FortiSOAR attachment id or file IRI to (file name, local path)."""
    from connectors.cyops_utilities.builtins import download_file_from_cyops
    try:
        file_name = None
        if iri_type == 'Attachment ID':
            from integrations.crudhub import make_request
            if not str(iri).startswith('/api/3/attachments/'):
                iri = '/api/3/attachments/%s' % iri
            attachment = make_request(iri, 'GET')
            file_iri = attachment['file']['@id']
            file_name = attachment['file']['filename']
        else:
            file_iri = iri
        downloaded = download_file_from_cyops(file_iri)
        file_name = file_name or downloaded['filename']
        return file_name, os.path.join('/tmp', downloaded['cyops_file_path'])
    except Exception as err:
        logger.exception(str(err))
        raise ConnectorError('Could not load the FortiSOAR file "%s": %s' % (iri, err))


def submit_file(config, params):
    _require(params, 'issue_key', 'value')
    file_name, file_path = _get_file_data(params.get('path') or 'Attachment ID', params['value'])
    with open(file_path, 'rb') as handle:
        content = handle.read()
    result = JiraClient(config).request(
        'POST', '%s/issue/%s/attachments' % (API, _ident(params['issue_key'])),
        files={'file': (file_name, content)}, headers={'X-Atlassian-Token': 'no-check'})
    return result


def add_remote_link(config, params):
    _require(params, 'issue_key', 'url', 'title')
    body = {'object': {'url': params['url'], 'title': params['title']}}
    return JiraClient(config).request(
        'POST', '%s/issue/%s/remotelink' % (API, _ident(params['issue_key'])), json_body=body)


def link_issues(config, params):
    _require(params, 'link_type', 'inward_issue', 'outward_issue')
    body = {'type': {'name': params['link_type']},
            'inwardIssue': {'key': str(params['inward_issue']).strip()},
            'outwardIssue': {'key': str(params['outward_issue']).strip()}}
    if not _blank(params.get('comment')):
        body['comment'] = {'body': to_adf(params['comment'])}
    JiraClient(config).request('POST', API + '/issueLink', json_body=body)
    return _ok(link_type=params['link_type'], inward_issue=params['inward_issue'],
               outward_issue=params['outward_issue'])


def list_link_types(config, params):
    return JiraClient(config).request('GET', API + '/issueLinkType')


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def _with_window(jql, start_time):
    """AND an `updated >=` window onto a JQL string, keeping any ORDER BY last."""
    if not start_time:
        return jql
    stamp = datetime.fromisoformat(str(start_time).strip().replace('Z', '+00:00'))
    clause = 'updated >= "%s"' % stamp.strftime('%Y-%m-%d %H:%M')
    parts = ORDER_BY.split(jql, maxsplit=1)
    condition = parts[0].strip()
    order = ' ORDER BY ' + parts[1].strip() if len(parts) > 1 else ''
    condition = '(%s) AND %s' % (condition, clause) if condition else clause
    return condition + order


def list_tickets(config, params):
    _require(params, 'jql_query')
    try:
        jql = _with_window(params['jql_query'], params.get('start_time'))
    except ValueError:
        raise ConnectorError('"%s" is not an ISO-8601 date and time.' % params.get('start_time'))
    body = {'jql': jql, 'fields': _list_param(params.get('fields')) or ['*navigable']}
    if params.get('expand'):
        body['expand'] = ','.join(_list_param(params['expand']))
    client = JiraClient(config)
    page_size = int(params.get('maxResults') or 50)
    body['maxResults'] = page_size
    if not params.get('fetch_all'):
        if params.get('nextPageToken'):
            body['nextPageToken'] = params['nextPageToken']
        return client.request('POST', API + '/search/jql', json_body=body)
    cap = int(params.get('max_total') or MAX_FETCH_ALL)
    issues, token = [], params.get('nextPageToken')
    while True:
        if token:
            body['nextPageToken'] = token
        page = client.request('POST', API + '/search/jql', json_body=body)
        issues.extend(page.get('issues') or [])
        token = page.get('nextPageToken')
        if not token or page.get('isLast') or len(issues) >= cap:
            break
    return {'issues': issues[:cap], 'total': len(issues[:cap]), 'jql': jql,
            'truncated': bool(token) and len(issues) >= cap}


def validate_jql_query(config, params):
    _require(params, 'jql_query')
    return JiraClient(config).request(
        'POST', API + '/jql/parse', params={'validation': 'strict'},
        json_body={'queries': [params['jql_query']]})


# ---------------------------------------------------------------------------
# projects, users, metadata
# ---------------------------------------------------------------------------

def list_projects(config, params):
    client = JiraClient(config)
    query = {'query': params.get('query'), 'startAt': params.get('startAt'),
             'maxResults': params.get('maxResults')}
    if params.get('fetch_all'):
        values = client.paginate_offset(API + '/project/search', query, limit=MAX_FETCH_ALL)
        return {'values': values, 'total': len(values)}
    return client.request('GET', API + '/project/search', params=query)


def get_project(config, params):
    _require(params, 'project_key')
    return JiraClient(config).request('GET', '%s/project/%s' % (API, _ident(params['project_key'])))


def search_users(config, params):
    # /user/search matches a name or email prefix and needs a query; with none,
    # /users/search lists every user on the site.
    query = params.get('query')
    path = '/user/search' if not _blank(query) else '/users/search'
    users = JiraClient(config).request(
        'GET', API + path,
        params={'query': query, 'startAt': params.get('startAt'), 'maxResults': params.get('maxResults')})
    return {'users': users, 'total': len(users) if isinstance(users, list) else 0}


def get_user_details(config, params):
    _require(params, 'accountId')
    return JiraClient(config).request('GET', API + '/user', params={'accountId': params['accountId']})


def list_issue_types(config, params):
    client = JiraClient(config)
    if params.get('project_key'):
        result = client.request(
            'GET', '%s/issue/createmeta/%s/issuetypes' % (API, _ident(params['project_key'])),
            params=_page(params))
        return {'issueTypes': result.get('issueTypes') or result.get('values') or [],
                'total': result.get('total')}
    return {'issueTypes': client.request('GET', API + '/issuetype')}


def get_create_metadata(config, params):
    _require(params, 'project_key', 'issue_type_id')
    return JiraClient(config).request(
        'GET', '%s/issue/createmeta/%s/issuetypes/%s' % (
            API, _ident(params['project_key']), _ident(params['issue_type_id'])),
        params=_page(params))


def list_priorities(config, params):
    return JiraClient(config).request('GET', API + '/priority/search', params=_page(params))


def list_fields(config, params):
    return {'fields': JiraClient(config).request('GET', API + '/field')}


# ---------------------------------------------------------------------------
# Jira Service Management
# ---------------------------------------------------------------------------

def _jsm_page(params):
    return {'start': params.get('start'), 'limit': params.get('limit')}


def list_service_desks(config, params):
    return JiraClient(config).request('GET', JSM + '/servicedesk', params=_jsm_page(params))


def list_request_types(config, params):
    _require(params, 'service_desk_id')
    query = _jsm_page(params)
    query['searchQuery'] = params.get('search_query')
    return JiraClient(config).request(
        'GET', '%s/servicedesk/%s/requesttype' % (JSM, _ident(params['service_desk_id'])), params=query)


def get_request_type_fields(config, params):
    _require(params, 'service_desk_id', 'request_type_id')
    return JiraClient(config).request(
        'GET', '%s/servicedesk/%s/requesttype/%s/field' % (
            JSM, _ident(params['service_desk_id']), _ident(params['request_type_id'])))


def create_customer_request(config, params):
    _require(params, 'service_desk_id', 'request_type_id', 'summary')
    values = {'summary': params['summary']}
    # The JSM request API takes description as wiki-markup text, not ADF.
    if not _blank(params.get('description')):
        values['description'] = params['description']
    values.update(_dict_param(params.get('request_field_values'), 'request_field_values'))
    body = {'serviceDeskId': str(params['service_desk_id']), 'requestTypeId': str(params['request_type_id']),
            'requestFieldValues': values}
    if params.get('raise_on_behalf_of'):
        body['raiseOnBehalfOf'] = params['raise_on_behalf_of']
    participants = _list_param(params.get('request_participants'))
    if participants:
        body['requestParticipants'] = participants
    return JiraClient(config).request('POST', JSM + '/request', json_body=body)


def get_customer_request(config, params):
    _require(params, 'issue_key')
    return JiraClient(config).request(
        'GET', '%s/request/%s' % (JSM, _ident(params['issue_key'])),
        params={'expand': ','.join(_list_param(params.get('expand')))})


def add_request_comment(config, params):
    _require(params, 'issue_key', 'comment')
    return JiraClient(config).request(
        'POST', '%s/request/%s/comment' % (JSM, _ident(params['issue_key'])),
        json_body={'body': params['comment'], 'public': bool(params.get('public', True))})


def list_queues(config, params):
    _require(params, 'service_desk_id')
    query = _jsm_page(params)
    if params.get('include_count'):
        query['includeCount'] = 'true'
    return JiraClient(config).request(
        'GET', '%s/servicedesk/%s/queue' % (JSM, _ident(params['service_desk_id'])), params=query)


def list_queue_issues(config, params):
    _require(params, 'service_desk_id', 'queue_id')
    return JiraClient(config).request(
        'GET', '%s/servicedesk/%s/queue/%s/issue' % (
            JSM, _ident(params['service_desk_id']), _ident(params['queue_id'])),
        params=_jsm_page(params))


# ---------------------------------------------------------------------------
# dropdown populators ("apiOperation" sources, hidden in info.json)
#
# The step editor calls these with only the connector config and renders the
# result as dropdown options, so a playbook author picks a name while the
# playbook stores the stable key or id.
# ---------------------------------------------------------------------------

def get_project_options(config, params):
    client = JiraClient(config)
    projects = client.paginate_offset(API + '/project/search', {'maxResults': 100}, limit=MAX_FETCH_ALL)
    options = [{'title': '%s (%s)' % (p.get('name'), p.get('key')), 'value': p.get('key')} for p in projects]
    return sorted(options, key=lambda o: o['title'].lower())


def _issue_types(config, project_key=None):
    """Issue types: the project's own when a project is chosen, else every type on the site."""
    client = JiraClient(config)
    if not _blank(project_key):
        result = client.request(
            'GET', '%s/issue/createmeta/%s/issuetypes' % (API, _ident(project_key)), params={'maxResults': 200})
        items = result.get('issueTypes') or result.get('values') or []
    else:
        items = client.request('GET', API + '/issuetype') or []
    seen, unique = set(), []
    for item in items:
        if item.get('name') not in seen:
            seen.add(item.get('name'))
            unique.append(item)
    return unique


def _dependent(config, params, parent, build):
    """Run a populator that needs a sibling parameter (the editor passes the form's values).

    Until the parent is chosen, or when it is an unresolved expression like
    {{vars.x}}, the dropdown is simply empty rather than an error. A parent that
    does not exist (404) or is malformed (400) is empty too. Authentication and
    permission failures (401/403) are NOT swallowed: a token missing a scope
    must show up as an error, not as a silently empty list.
    """
    if _blank(params.get(parent)) or '{{' in str(params.get(parent)):
        return []
    try:
        return build()
    except ConnectorError as err:
        if 'HTTP 401' in str(err) or 'HTTP 403' in str(err):
            raise
        logger.info('Dropdown for %s=%s left empty: %s', parent, params.get(parent), err)
        return []


def get_issue_type_options(config, params):
    def build():
        return sorted(({'title': t['name'] + (' (sub-task)' if t.get('subtask') else ''), 'value': t['name']}
                       for t in _issue_types(config, params.get('project_key'))),
                      key=lambda o: o['title'].lower())
    if _blank(params.get('project_key')):
        return build()
    return _dependent(config, params, 'project_key', build)


def get_issue_type_id_options(config, params):
    def build():
        return sorted(({'title': '%s [%s]' % (t['name'], t['id']), 'value': str(t['id'])}
                       for t in _issue_types(config, params.get('project_key'))),
                      key=lambda o: o['title'].lower())
    if _blank(params.get('project_key')):
        return build()
    return _dependent(config, params, 'project_key', build)


def _paged_values(client, path, page_size=100):
    items, start = [], 0
    while len(items) < MAX_FETCH_ALL:
        page = client.request('GET', path, params={'start': start, 'limit': page_size})
        batch = page.get('values') or []
        items.extend(batch)
        if page.get('isLastPage', True) or not batch:
            break
        start += len(batch)
    return items


def get_request_type_options(config, params):
    def build():
        types = _paged_values(JiraClient(config),
                              '%s/servicedesk/%s/requesttype' % (JSM, _ident(params['service_desk_id'])))
        return [{'title': t.get('name'), 'value': str(t['id'])} for t in types]
    return _dependent(config, params, 'service_desk_id', build)


def get_queue_options(config, params):
    def build():
        queues = _paged_values(JiraClient(config), '%s/servicedesk/%s/queue' % (JSM, _ident(params['service_desk_id'])))
        return [{'title': q.get('name'), 'value': str(q['id'])} for q in queues]
    return _dependent(config, params, 'service_desk_id', build)


def get_transition_options(config, params):
    """Target status names reachable from the issue's current status."""
    def build():
        found = _transitions(JiraClient(config), _ident(params['issue_key']))
        return [{'title': '%s (via %s)' % ((t.get('to') or {}).get('name'), t.get('name')),
                 'value': (t.get('to') or {}).get('name')} for t in found]
    return _dependent(config, params, 'issue_key', build)


def get_transition_id_options(config, params):
    def build():
        found = _transitions(JiraClient(config), _ident(params['issue_key']))
        return [{'title': '%s -> %s [%s]' % (t.get('name'), (t.get('to') or {}).get('name'), t['id']),
                 'value': str(t['id'])} for t in found]
    return _dependent(config, params, 'issue_key', build)


def get_link_type_options(config, params):
    types = JiraClient(config).request('GET', API + '/issueLinkType').get('issueLinkTypes') or []
    return [{'title': '%s (%s / %s)' % (t['name'], t.get('inward'), t.get('outward')), 'value': t['name']}
            for t in types]


def get_user_options(config, params):
    client = JiraClient(config)
    users, start = [], 0
    while len(users) < MAX_FETCH_ALL:
        batch = client.request('GET', API + '/users/search',
                               params={'startAt': start, 'maxResults': 100}) or []
        users.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    options = []
    for user in users:
        if user.get('accountType') not in (None, 'atlassian') or user.get('active') is False:
            continue
        label = user.get('displayName') or user['accountId']
        if user.get('emailAddress'):
            label += ' (%s)' % user['emailAddress']
        options.append({'title': label, 'value': user['accountId']})
    return sorted(options, key=lambda o: o['title'].lower())


def get_service_desk_options(config, params):
    desks = JiraClient(config).request('GET', JSM + '/servicedesk', params={'limit': 100}).get('values') or []
    return [{'title': '%s (%s)' % (d.get('projectName'), d.get('projectKey')), 'value': str(d['id'])}
            for d in desks]


# ---------------------------------------------------------------------------
# generic API call
# ---------------------------------------------------------------------------

def _climbs_out(endpoint):
    """True when the path, after percent-decoding, holds a `..` segment or a backslash."""
    path = endpoint.split('?')[0]
    for _ in range(3):  # a doubly encoded %252e%252e decodes in two rounds
        if '\\' in path or '..' in path.split('/'):
            return True
        decoded = unquote(path)
        if decoded == path:
            return False
        path = decoded
    return True


def execute_api_request(config, params):
    """Call any Jira or JSM REST endpoint with the connector's credentials."""
    _require(params, 'endpoint')
    endpoint = str(params['endpoint']).strip()
    parsed = urlparse(endpoint)
    # Credentials go to the configured site only: never to a host named in a playbook.
    if parsed.scheme or parsed.netloc or _climbs_out(endpoint):
        raise ConnectorError('Endpoint must be a path on the configured site, '
                             'e.g. /rest/api/3/myself - not a full URL.')
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    method = (params.get('method') or 'GET').upper()
    content_type = params.get('content_type')
    if _blank(content_type) or content_type == 'None':
        content_type = 'application/json'
    payload = _json_param(params.get('payload'), 'payload')
    query = _dict_param(params.get('query_params'), 'query_params')
    kwargs = {}
    if not _blank(payload):
        if 'json' in content_type.lower():
            kwargs['json_body'] = payload
        else:
            kwargs['data'] = payload if isinstance(payload, str) else json.dumps(payload)
            kwargs['headers'] = {'Content-Type': content_type}
    return JiraClient(config).request(method, endpoint, params=query, **kwargs)


operations = {
    'create_ticket': create_ticket,
    'get_ticket_details': get_ticket_details,
    'update_ticket': update_ticket,
    'delete_ticket': delete_ticket,
    'set_status': set_status,
    'get_transitions': get_transitions,
    'assign_issue': assign_issue,
    'get_changelog': get_changelog,
    'add_worklog': add_worklog,
    'add_comment': add_comment,
    'get_comments': get_comments,
    'update_comment': update_comment,
    'delete_comment': delete_comment,
    'submit_file': submit_file,
    'add_remote_link': add_remote_link,
    'link_issues': link_issues,
    'list_link_types': list_link_types,
    'list_tickets': list_tickets,
    'validate_jql_query': validate_jql_query,
    'list_projects': list_projects,
    'get_project': get_project,
    'search_users': search_users,
    'get_user_details': get_user_details,
    'list_issue_types': list_issue_types,
    'get_create_metadata': get_create_metadata,
    'list_priorities': list_priorities,
    'list_fields': list_fields,
    'list_service_desks': list_service_desks,
    'list_request_types': list_request_types,
    'get_request_type_fields': get_request_type_fields,
    'create_customer_request': create_customer_request,
    'get_customer_request': get_customer_request,
    'add_request_comment': add_request_comment,
    'list_queues': list_queues,
    'list_queue_issues': list_queue_issues,
    'execute_api_request': execute_api_request,
    'get_project_options': get_project_options,
    'get_issue_type_options': get_issue_type_options,
    'get_issue_type_id_options': get_issue_type_id_options,
    'get_link_type_options': get_link_type_options,
    'get_user_options': get_user_options,
    'get_service_desk_options': get_service_desk_options,
    'get_request_type_options': get_request_type_options,
    'get_queue_options': get_queue_options,
    'get_transition_options': get_transition_options,
    'get_transition_id_options': get_transition_id_options,
}

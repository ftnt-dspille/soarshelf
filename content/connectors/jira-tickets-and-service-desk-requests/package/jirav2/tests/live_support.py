"""
Shared plumbing for the online tests (test_live.py, test_live_scopes.py).

Credentials come from the environment or tests/.env (git-ignored), never from
the command line:

    JIRA_LIVE_SERVER   https://yourcompany.atlassian.net
    JIRA_LIVE_USER     the account email
    JIRA_LIVE_TOKEN    an UNRESTRICTED API token (the functional tests and the
                       scope tests' fixtures use it)
    JIRA_LIVE_PROJECT  optional: a project key you accept test issues in.
                       Empty means "find any project where an issue can be created".

Everything the tests create carries the label `jirav2-live-test` and is
deleted afterwards; a sweep at session end removes leftovers of crashed runs.
"""
import itertools
import json
import os
import threading
from pathlib import Path

import pytest

from jirav2 import client as client_module
from jirav2.connector import JiraV2

LABEL = 'jirav2-live-test'
ENV_FILE = Path(__file__).parent / '.env'
CACHE_FILE = Path(__file__).parent / '.live-cache.json'
ConnectorError = client_module.ConnectorError
_counter = itertools.count(1)


def load_env():
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith('JIRA_LIVE_')})
    return values


ENV = load_env()
HAVE_SITE = bool(ENV.get('JIRA_LIVE_SERVER') and ENV.get('JIRA_LIVE_TOKEN'))
needs_site = pytest.mark.skipif(
    not HAVE_SITE, reason='set JIRA_LIVE_SERVER, JIRA_LIVE_USER and JIRA_LIVE_TOKEN (tests/.env) to run online tests')


def admin_config():
    return {'server_url': ENV['JIRA_LIVE_SERVER'], 'username': ENV.get('JIRA_LIVE_USER', ''),
            'token': ENV['JIRA_LIVE_TOKEN'], 'verify_ssl': True}


def runner(config):
    connector = JiraV2()
    return lambda operation, **params: connector.execute(config, operation, params)


def is_scope_error(err):
    text = str(err)
    return 'HTTP 401' in text and 'scope' in text.lower()


class Site(object):
    """What the test site looks like, discovered once, plus a factory for throwaway issues."""

    # fields a test issue may require and that we can fill in ourselves
    FILLABLE = {'summary', 'project', 'issuetype', 'reporter', 'description', 'labels', 'priority'}

    def __init__(self):
        self.config = admin_config()
        self.jira = runner(self.config)
        self.created = []
        self.me = self.jira('execute_api_request', endpoint='/rest/api/3/myself')
        self.account_id = self.me['accountId']
        self.projects = self.jira('list_projects', fetch_all=True)['values']
        self._lock = threading.Lock()
        self._shared = {}
        cached = self._load_cache()
        if cached:
            self.project, self.issue_type, self.desk = cached
        else:
            self.project, self.issue_type = self._pick_project()
            self.desk = self._first_desk()
            self._save_cache()

    # -- discovery cache: picking a project creates and deletes an issue, so remember the answer ----

    def _cache_key(self):
        return '%s|%s|%s' % (self.config['server_url'], self.config['username'], ENV.get('JIRA_LIVE_PROJECT', ''))

    def _load_cache(self):
        try:
            entry = json.loads(CACHE_FILE.read_text()).get(self._cache_key())
            if entry and any(p['key'] == entry['project'] for p in self.projects):
                return entry['project'], entry['issue_type'], entry.get('desk')
        except (OSError, ValueError, KeyError):
            pass
        return None

    def _save_cache(self):
        try:
            data = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
        except (OSError, ValueError):
            data = {}
        data[self._cache_key()] = {'project': self.project, 'issue_type': self.issue_type, 'desk': self.desk}
        CACHE_FILE.write_text(json.dumps(data, indent=1))

    def shared(self, name, factory):
        """Create a fixture once per session (thread-safe) and hand the same one to every caller."""
        with self._lock:
            if name not in self._shared:
                self._shared[name] = factory()
            return self._shared[name]

    # -- discovery ---------------------------------------------------------

    def _candidate_projects(self):
        wanted = ENV.get('JIRA_LIVE_PROJECT')
        if wanted:
            return [p for p in self.projects if p['key'] == wanted] or [{'key': wanted}]
        # Plain software/business projects first: JSM projects want request types.
        return sorted(self.projects, key=lambda p: p.get('projectTypeKey') == 'service_desk')

    def _creatable_type(self, project_key):
        types = self.jira('list_issue_types', project_key=project_key)['issueTypes']
        # Standard-level types (Task, Bug, Story) first: an Epic cannot parent a sub-task.
        for issue_type in sorted(types, key=lambda t: t.get('hierarchyLevel', 0) != 0):
            if issue_type.get('subtask'):
                continue
            meta = self.jira('get_create_metadata', project_key=project_key, issue_type_id=issue_type['id'])
            fields = meta.get('fields') or meta.get('values') or []
            required = {f['fieldId'] for f in fields if f.get('required')}
            if required <= self.FILLABLE:
                return issue_type
        return None

    def _pick_project(self):
        for project in self._candidate_projects():
            try:
                issue_type = self._creatable_type(project['key'])
                if issue_type is None:
                    continue
                probe = self.jira('create_ticket', project_key=project['key'], issue_type_id=issue_type['id'],
                                  ticket_summary='jirav2 live probe', labels=LABEL)
                self.jira('delete_ticket', issue_key=probe['key'])
                return project['key'], issue_type
            except ConnectorError:
                continue
        return None, None

    def _first_desk(self):
        try:
            desks = self.jira('list_service_desks')['values']
        except ConnectorError:
            return None
        return desks[0] if desks else None

    # -- fixtures ----------------------------------------------------------

    def new_issue(self, **extra):
        """Create a throwaway issue with the unrestricted token; deleted at session end."""
        assert self.project, 'no project on this site accepts a test issue'
        params = {'project_key': self.project, 'issue_type_id': self.issue_type['id'], 'labels': LABEL,
                  'ticket_summary': 'jirav2 live test #%d (safe to delete)' % next(_counter),
                  'ticket_description': 'created by the jirav2 online tests'}
        params.update(extra)
        key = self.jira('create_ticket', **params)['key']
        self.created.append(key)
        return key

    def forget(self, key):
        if key in self.created:
            self.created.remove(key)

    def cleanup(self):
        for key in list(self.created):
            try:
                self.jira('delete_ticket', issue_key=key, delete_subtask=True)
            except ConnectorError:
                pass
        self.created.clear()
        if self.project:
            try:
                leftovers = self.jira('list_tickets', fetch_all=True, fields='summary',
                                      jql_query='project = "%s" AND labels = "%s"' % (self.project, LABEL))
                for issue in leftovers['issues']:
                    self.jira('delete_ticket', issue_key=issue['key'], delete_subtask=True)
            except ConnectorError:
                pass


_SITE = []


def get_site():
    if not _SITE:
        _SITE.append(Site())
    return _SITE[0]

"""JQL search, projects, users and create metadata."""
import pytest

from jirav2 import client as client_module
from jirav2.operations import _with_window

ConnectorError = client_module.ConnectorError
SEARCH = '/rest/api/3/search/jql'


# -- list_tickets ----------------------------------------------------------

@pytest.mark.op('list_tickets')
def test_list_tickets_basic(fake, run):
    fake.on('POST', SEARCH, {'issues': [{'key': 'SEC-1'}], 'isLast': True})
    out = run('list_tickets', jql_query='project = SEC')
    assert fake.only().json == {'jql': 'project = SEC', 'fields': ['*navigable'], 'maxResults': 50}
    assert out['issues'][0]['key'] == 'SEC-1'


@pytest.mark.op('list_tickets')
def test_list_tickets_does_not_require_a_project_clause(fake, run):
    """v1 refused any JQL without 'project = X'."""
    fake.on('POST', SEARCH, {'issues': []})
    run('list_tickets', jql_query='assignee = currentUser() AND resolution = Unresolved')
    assert fake.only().json['jql'].startswith('assignee')


@pytest.mark.op('list_tickets')
def test_list_tickets_fields_expand_paging(fake, run):
    fake.on('POST', SEARCH, {'issues': [], 'nextPageToken': 'tok2'})
    out = run('list_tickets', jql_query='project = SEC', fields='summary, status', expand='changelog',
              maxResults=10, nextPageToken='tok1')
    body = fake.only().json
    assert body['fields'] == ['summary', 'status']
    assert body['expand'] == 'changelog'
    assert body['maxResults'] == 10 and body['nextPageToken'] == 'tok1'
    assert out['nextPageToken'] == 'tok2'


@pytest.mark.op('list_tickets')
def test_list_tickets_updated_since_is_parenthesised(fake, run):
    """v1 appended 'and created >= x or updated >= y' with no parentheses."""
    fake.on('POST', SEARCH, {'issues': []})
    run('list_tickets', jql_query='project = SEC OR project = OPS', start_time='2025-10-12T14:05:33.000Z')
    assert fake.only().json['jql'] == '(project = SEC OR project = OPS) AND updated >= "2025-10-12 14:05"'


@pytest.mark.op('list_tickets')
def test_list_tickets_bad_start_time_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='ISO-8601'):
        run('list_tickets', jql_query='project = SEC', start_time='last week')
    assert not fake.calls


@pytest.mark.op('list_tickets')
def test_list_tickets_fetch_all_follows_the_token(fake, run):
    fake.on_sequence('POST', SEARCH, [
        (200, {'issues': [{'key': 'A'}, {'key': 'B'}], 'nextPageToken': 't2'}),
        (200, {'issues': [{'key': 'C'}], 'isLast': True})])
    out = run('list_tickets', jql_query='project = SEC', fetch_all=True, maxResults=2)
    assert [i['key'] for i in out['issues']] == ['A', 'B', 'C']
    assert out['total'] == 3 and out['truncated'] is False
    assert fake.calls[1].json['nextPageToken'] == 't2'


@pytest.mark.op('list_tickets')
def test_list_tickets_fetch_all_stops_at_max_total(fake, run):
    fake.on('POST', SEARCH, {'issues': [{'key': 'A'}, {'key': 'B'}], 'nextPageToken': 'more'})
    out = run('list_tickets', jql_query='project = SEC', fetch_all=True, max_total=3)
    assert out['total'] == 3 and out['truncated'] is True
    assert len(fake.calls) == 2


@pytest.mark.parametrize('jql, expected', [
    ('project = A', '(project = A) AND updated >= "2025-01-02 03:04"'),
    ('project = A ORDER BY created DESC', '(project = A) AND updated >= "2025-01-02 03:04" ORDER BY created DESC'),
    ('project = A order  by key', '(project = A) AND updated >= "2025-01-02 03:04" ORDER BY key'),
    ('ORDER BY created', 'updated >= "2025-01-02 03:04" ORDER BY created'),
])
def test_with_window(jql, expected):
    assert _with_window(jql, '2025-01-02T03:04:05Z') == expected


def test_with_window_without_a_start_time_changes_nothing():
    assert _with_window('project = A', None) == 'project = A'


# -- validate_jql_query ----------------------------------------------------

@pytest.mark.op('validate_jql_query')
def test_validate_jql_query(fake, run):
    fake.on('POST', '/rest/api/3/jql/parse', {'queries': [{'query': 'project = SEC', 'errors': []}]})
    out = run('validate_jql_query', jql_query='project = SEC')
    call = fake.only()
    assert call.json == {'queries': ['project = SEC']}
    assert call.params == {'validation': 'strict'}
    assert out['queries'][0]['errors'] == []


@pytest.mark.op('validate_jql_query')
def test_validate_jql_query_reports_errors_in_the_result(fake, run):
    fake.on('POST', '/rest/api/3/jql/parse', {'queries': [{'query': 'bad', 'errors': ['Field bad does not exist']}]})
    assert run('validate_jql_query', jql_query='bad')['queries'][0]['errors']


# -- projects --------------------------------------------------------------

@pytest.mark.op('list_projects')
def test_list_projects(fake, run):
    fake.on('GET', '/rest/api/3/project/search', {'values': [{'key': 'SEC'}], 'total': 1})
    out = run('list_projects', query='sec', startAt=0, maxResults=20)
    assert fake.only().params == {'query': 'sec', 'startAt': 0, 'maxResults': 20}
    assert out['values'] == [{'key': 'SEC'}]


@pytest.mark.op('list_projects')
def test_list_projects_fetch_all(fake, run):
    fake.on_sequence('GET', '/rest/api/3/project/search', [
        (200, {'values': [{'key': 'A'}], 'isLast': False}), (200, {'values': [{'key': 'B'}], 'isLast': True})])
    out = run('list_projects', fetch_all=True)
    assert [p['key'] for p in out['values']] == ['A', 'B'] and out['total'] == 2


@pytest.mark.op('list_projects')
def test_list_projects_empty_site_is_an_empty_list_not_an_error(fake, run):
    fake.on('GET', '/rest/api/3/project/search', {'values': [], 'total': 0})
    assert run('list_projects')['values'] == []


@pytest.mark.op('get_project')
def test_get_project(fake, run):
    fake.on('GET', '/rest/api/3/project/SEC', {'key': 'SEC', 'name': 'Security'})
    assert run('get_project', project_key='SEC')['name'] == 'Security'


# -- users -----------------------------------------------------------------

@pytest.mark.op('search_users')
def test_search_users_with_a_query_uses_user_search(fake, run):
    fake.on('GET', '/rest/api/3/user/search', [{'accountId': 'a1'}])
    out = run('search_users', query='sam')
    assert fake.only().params == {'query': 'sam'}
    assert out == {'users': [{'accountId': 'a1'}], 'total': 1}


@pytest.mark.op('search_users')
def test_search_users_without_a_query_lists_everyone(fake, run):
    fake.on('GET', '/rest/api/3/users/search', [{'accountId': 'a1'}, {'accountId': 'a2'}])
    out = run('search_users', startAt=0, maxResults=10)
    assert fake.only().path == '/rest/api/3/users/search'
    assert out['total'] == 2


@pytest.mark.op('get_user_details')
def test_get_user_details(fake, run):
    fake.on('GET', '/rest/api/3/user', {'accountId': 'a1', 'displayName': 'Sam'})
    assert run('get_user_details', accountId='a1')['displayName'] == 'Sam'
    assert fake.only().params == {'accountId': 'a1'}


# -- metadata --------------------------------------------------------------

@pytest.mark.op('list_issue_types')
def test_list_issue_types_for_the_site(fake, run):
    fake.on('GET', '/rest/api/3/issuetype', [{'id': '1', 'name': 'Task'}])
    assert run('list_issue_types')['issueTypes'] == [{'id': '1', 'name': 'Task'}]


@pytest.mark.op('list_issue_types')
def test_list_issue_types_for_a_project(fake, run):
    fake.on('GET', '/rest/api/3/issue/createmeta/ETSP/issuetypes',
            {'issueTypes': [{'id': '10341', 'name': '[System] Service request'}], 'total': 1})
    out = run('list_issue_types', project_key='ETSP')
    assert out == {'issueTypes': [{'id': '10341', 'name': '[System] Service request'}], 'total': 1}


@pytest.mark.op('get_create_metadata')
def test_get_create_metadata(fake, run):
    fake.on('GET', '/rest/api/3/issue/createmeta/ETSP/issuetypes/10341',
            {'fields': [{'fieldId': 'summary', 'required': True}]})
    out = run('get_create_metadata', project_key='ETSP', issue_type_id='10341', maxResults=200)
    assert out['fields'][0]['required'] is True
    assert fake.only().params == {'maxResults': 200}


@pytest.mark.op('get_create_metadata')
def test_get_create_metadata_requires_both(fake, run):
    with pytest.raises(ConnectorError, match='issue_type_id'):
        run('get_create_metadata', project_key='ETSP')


@pytest.mark.op('list_priorities')
def test_list_priorities(fake, run):
    fake.on('GET', '/rest/api/3/priority/search', {'values': [{'name': 'High'}]})
    assert run('list_priorities')['values'] == [{'name': 'High'}]


@pytest.mark.op('list_fields')
def test_list_fields(fake, run):
    fake.on('GET', '/rest/api/3/field', [{'id': 'summary'}, {'id': 'customfield_10010'}])
    assert [f['id'] for f in run('list_fields')['fields']] == ['summary', 'customfield_10010']

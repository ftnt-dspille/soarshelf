"""
Online tests: every action against a real Jira Cloud site.

    cp tests/.env.example tests/.env      # fill in an UNRESTRICTED token, then:
    python3 -m pytest tests/test_live.py -m live -rs

The tests pick a project that accepts a test issue (or use JIRA_LIVE_PROJECT),
label everything `jirav2-live-test` and delete it afterwards. Jira Service
Management tests skip when the site has no service desk. A test that cannot
run for a reason the site explains (for example time tracking switched off)
skips with that reason instead of passing silently.

Each test names the action it proves with a live_op marker (see below);
tests/test_coverage.py fails if an action has no online test.
"""
import pytest

import jirav2.operations as operations_module
from jirav2.connector import JiraV2
from live_support import ConnectorError, LABEL, needs_site

pytestmark = [pytest.mark.live, needs_site]


@pytest.fixture
def jira(site):
    return site.jira


@pytest.fixture
def pairs(site):
    """pairs(populator, **params) -> the {title, value} options behind a dropdown (the editor sees titles only)."""
    from jirav2 import operations as ops
    return lambda name, **params: ops.operations[name].pairs(site.config, params)


@pytest.fixture
def needs_project(site):
    if not site.project:
        pytest.skip('no project on this site accepts a test issue (set JIRA_LIVE_PROJECT)')


def skip_when(err, *phrases):
    text = str(err).lower()
    if any(p in text for p in phrases):
        pytest.skip(str(err)[:200])
    raise err


# -- connection ------------------------------------------------------------

def test_health_check_passes_with_the_configured_account(site):
    assert JiraV2().check_health(site.config) is True


def test_wrong_username_fails_clearly(site):
    """The original connector reported 'make sure you have at least one JIRA project' here."""
    bad = dict(site.config, username='test2')
    with pytest.raises(ConnectorError) as err:
        JiraV2().check_health(bad)
    assert 'HTTP 401' in str(err.value) or 'HTTP 403' in str(err.value), str(err.value)


def test_wrong_token_fails_clearly(site):
    bad = dict(site.config, token='not-a-real-token')
    with pytest.raises(ConnectorError, match='HTTP 40[13]'):
        JiraV2().check_health(bad)


def test_scoped_mode_looks_up_the_cloud_id_and_routes_through_the_gateway(site):
    config = dict(site.config, scoped=True)
    assert JiraV2().check_health(config) is True


def test_bearer_mode_rejects_a_basic_token(site):
    config = dict(site.config, auth_type='Bearer (OAuth 2.0 Access Token)')
    with pytest.raises(ConnectorError, match='HTTP 40[13]'):
        JiraV2().check_health(config)


# -- read-only actions -----------------------------------------------------

@pytest.mark.live_op('list_projects')
def test_list_projects(jira, site):
    page = jira('list_projects', maxResults=1)
    assert 'values' in page
    everything = jira('list_projects', fetch_all=True)
    assert everything['total'] == len(everything['values']) == len(site.projects)


@pytest.mark.live_op('get_project')
def test_get_project(jira, site):
    if not site.projects:
        pytest.skip('site has no projects')
    key = site.projects[0]['key']
    assert jira('get_project', project_key=key)['key'] == key


@pytest.mark.live_op('search_users')
def test_search_users_both_paths(jira, site):
    everyone = jira('search_users')
    assert everyone['total'] >= 1
    name = site.me['displayName'].split()[0]
    assert any(u['accountId'] == site.account_id for u in jira('search_users', query=name)['users'])


@pytest.mark.live_op('get_user_details')
def test_get_user_details(jira, site):
    assert jira('get_user_details', accountId=site.account_id)['accountId'] == site.account_id


@pytest.mark.live_op('list_issue_types')
def test_list_issue_types_site_and_project(jira, site):
    assert jira('list_issue_types')['issueTypes']
    if site.project:
        assert jira('list_issue_types', project_key=site.project)['issueTypes']


@pytest.mark.live_op('get_create_metadata')
def test_get_create_metadata(jira, site, needs_project):
    meta = jira('get_create_metadata', project_key=site.project, issue_type_id=site.issue_type['id'])
    fields = meta.get('fields') or meta.get('values')
    assert any(f['fieldId'] == 'summary' for f in fields)


@pytest.mark.live_op('list_priorities')
def test_list_priorities(jira):
    try:
        assert jira('list_priorities')['values']
    except ConnectorError as err:
        skip_when(err, 'http 403', 'scope', 'administer')


@pytest.mark.live_op('list_fields')
def test_list_fields(jira):
    ids = [f['id'] for f in jira('list_fields')['fields']]
    assert 'summary' in ids


@pytest.mark.live_op('list_link_types')
def test_list_link_types(jira):
    assert jira('list_link_types')['issueLinkTypes']


@pytest.mark.live_op('validate_jql_query')
def test_validate_jql_query_good_and_bad(jira):
    assert jira('validate_jql_query', jql_query='project is not EMPTY')['queries'][0].get('errors') in ([], None)
    assert jira('validate_jql_query', jql_query='nosuchfield = 1')['queries'][0]['errors']


@pytest.mark.live_op('list_tickets')
def test_list_tickets_paths(jira, site, needs_project):
    key = site.new_issue()
    jql = 'project = "%s" AND labels = "%s" ORDER BY created DESC' % (site.project, LABEL)
    page = jira('list_tickets', jql_query=jql, fields='summary,labels')
    assert key in [i['key'] for i in page['issues']]
    windowed = jira('list_tickets', jql_query=jql, start_time='2000-01-01T00:00:00.000Z', maxResults=1)
    assert 'issues' in windowed
    walked = jira('list_tickets', jql_query=jql, fetch_all=True, maxResults=1)
    assert key in [i['key'] for i in walked['issues']]


@pytest.mark.live_op('execute_api_request')
def test_execute_api_request(jira, site):
    assert jira('execute_api_request', endpoint='/rest/api/3/myself')['accountId'] == site.account_id
    parsed = jira('execute_api_request', endpoint='/rest/api/3/jql/parse', method='POST',
                  query_params={'validation': 'strict'}, payload={'queries': ['project is not EMPTY']})
    assert parsed['queries']
    with pytest.raises(ConnectorError, match='HTTP 404'):
        jira('execute_api_request', endpoint='/rest/api/3/issue/NOPE-99999999')


@pytest.mark.live_op('get_project_options')
@pytest.mark.live_op('get_issue_type_options')
@pytest.mark.live_op('get_issue_type_id_options')
@pytest.mark.live_op('get_link_type_options')
@pytest.mark.live_op('get_user_options')
def test_dropdown_populators_return_title_value_pairs(jira, pairs, site):
    for operation in ('get_project_options', 'get_issue_type_options', 'get_issue_type_id_options',
                      'get_link_type_options', 'get_user_options'):
        options = pairs(operation)
        assert options, operation
        assert jira(operation) == [o['title'] for o in options], operation
        assert all(set(o) == {'title', 'value'} and o['title'] and o['value'] for o in options), operation
    assert site.account_id in [o['value'] for o in pairs('get_user_options')]


# -- the issue lifecycle ---------------------------------------------------

@pytest.mark.live_op('create_ticket')
@pytest.mark.live_op('get_ticket_details')
@pytest.mark.live_op('delete_ticket')
def test_create_get_delete_round_trip(jira, site, needs_project):
    created = jira('create_ticket', project_key=site.project, issue_type=site.issue_type['name'],
                   ticket_summary='jirav2 round trip', ticket_description='line one\n\nline two', labels=LABEL,
                   include_details=True)
    key = created['key']
    site.created.append(key)
    assert created['issue']['fields']['summary'] == 'jirav2 round trip'
    details = jira('get_ticket_details', issue_key=key, include_text=True, fields='summary,description')
    assert 'line one' in details['description_text'] and 'line two' in details['description_text']
    jira('delete_ticket', issue_key=key)
    site.forget(key)
    with pytest.raises(ConnectorError, match='HTTP 404'):
        jira('get_ticket_details', issue_key=key)


@pytest.mark.live_op('create_ticket')
def test_create_ticket_with_a_bad_issue_type_names_the_problem(jira, site, needs_project):
    with pytest.raises(ConnectorError, match='HTTP 400'):
        jira('create_ticket', project_key=site.project, issue_type='No Such Type', ticket_summary='x')


@pytest.mark.live_op('create_ticket')
def test_create_ticket_with_assignee_and_other_fields(jira, site, needs_project):
    key = site.new_issue(assignee_account_id=site.account_id, other_fields={'labels': [LABEL, 'extra']})
    fields = jira('get_ticket_details', issue_key=key, fields='assignee,labels')['fields']
    assert fields['assignee']['accountId'] == site.account_id
    assert set(fields['labels']) == {LABEL, 'extra'}


@pytest.mark.live_op('create_ticket')
def test_create_sub_task_under_a_parent(jira, site, needs_project):
    types = jira('list_issue_types', project_key=site.project)['issueTypes']
    sub = next((t for t in types if t.get('subtask')), None)
    if sub is None:
        pytest.skip('the project has no sub-task issue type')
    parent = site.new_issue()
    try:
        child = jira('create_ticket', project_key=site.project, issue_type_id=sub['id'], parent=parent,
                     ticket_summary='jirav2 sub-task', labels=LABEL)
    except ConnectorError as err:
        skip_when(err, 'required', 'cannot be set')
    site.created.append(child['key'])
    assert jira('get_ticket_details', issue_key=child['key'], fields='parent')['fields']['parent']['key'] == parent


@pytest.mark.live_op('update_ticket')
@pytest.mark.live_op('get_changelog')
def test_update_ticket_and_changelog(jira, site, needs_project):
    key = site.new_issue()
    out = jira('update_ticket', issue_key=key, summary='jirav2 updated', description='new text',
               labels='%s,second' % LABEL, comment='from update_ticket')
    assert out['status'] == 'Success'
    fields = jira('get_ticket_details', issue_key=key, fields='summary,labels,comment')['fields']
    assert fields['summary'] == 'jirav2 updated'
    assert 'second' in fields['labels']
    assert fields['comment']['total'] == 1
    items = [i['field'] for h in jira('get_changelog', issue_key=key)['values'] for i in h['items']]
    assert 'summary' in items


@pytest.mark.live_op('get_transitions')
@pytest.mark.live_op('set_status')
@pytest.mark.live_op('update_ticket')
def test_transitions_and_status_changes(jira, site, needs_project):
    key = site.new_issue()
    transitions = jira('get_transitions', issue_key=key)['transitions']
    if not transitions:
        pytest.skip('the workflow offers no transition from the initial status')
    first = transitions[0]
    try:
        out = jira('set_status', issue_key=key, status=first['to']['name'])
    except ConnectorError as err:
        skip_when(err, 'required', 'resolution')
    assert out['transition']['to'] == first['to']['name']
    now = jira('get_ticket_details', issue_key=key, fields='status')['fields']['status']['name']
    assert now == first['to']['name']
    with pytest.raises(ConnectorError, match='Available:'):
        jira('set_status', issue_key=key, status='No Such Status')
    back = jira('get_transitions', issue_key=key)['transitions']
    target = next((t for t in back if t['to']['name'] != first['to']['name']), None)
    if target is not None:
        try:
            jira('update_ticket', issue_key=key, status=target['to']['name'])
        except ConnectorError as err:
            skip_when(err, 'required', 'resolution')


@pytest.mark.live_op('assign_issue')
def test_assign_and_unassign(jira, site, needs_project):
    key = site.new_issue()
    jira('assign_issue', issue_key=key, accountId=site.account_id)
    assignee = jira('get_ticket_details', issue_key=key, fields='assignee')['fields']['assignee']
    assert assignee['accountId'] == site.account_id
    jira('assign_issue', issue_key=key, accountId='')
    assert jira('get_ticket_details', issue_key=key, fields='assignee')['fields']['assignee'] is None


@pytest.mark.live_op('add_comment')
@pytest.mark.live_op('get_comments')
@pytest.mark.live_op('update_comment')
@pytest.mark.live_op('delete_comment')
def test_comment_lifecycle(jira, site, needs_project):
    key = site.new_issue()
    comment = jira('add_comment', issue_key=key, comment='first\n\nsecond paragraph')
    listed = jira('get_comments', issue_key=key, include_text=True)
    assert listed['total'] == 1 and 'second paragraph' in listed['comments'][0]['body_text']
    jira('update_comment', issue_key=key, comment_id=comment['id'], comment='edited')
    assert jira('get_comments', issue_key=key, include_text=True)['comments'][0]['body_text'] == 'edited'
    jira('add_comment', issue_key=key, comment='internal note', internal=True)
    assert jira('get_comments', issue_key=key, orderBy='-created')['total'] == 2
    jira('delete_comment', issue_key=key, comment_id=comment['id'])
    assert jira('get_comments', issue_key=key)['total'] == 1


@pytest.mark.live_op('add_worklog')
def test_add_worklog(jira, site, needs_project):
    key = site.new_issue()
    try:
        log = jira('add_worklog', issue_key=key, time_spent='15m', comment='tested',
                   started='2025-01-02T03:04:05.000Z')
    except ConnectorError as err:
        skip_when(err, 'time tracking', 'work on issues', 'worklog')
    assert log['timeSpent'] == '15m'


@pytest.mark.live_op('add_remote_link')
def test_add_remote_link(jira, site, needs_project):
    key = site.new_issue()
    link = jira('add_remote_link', issue_key=key, url='https://example.com/jirav2', title='jirav2 test link')
    assert link.get('id')
    remote = jira('execute_api_request', endpoint='/rest/api/3/issue/%s/remotelink' % key)
    assert remote[0]['object']['title'] == 'jirav2 test link'


@pytest.mark.live_op('link_issues')
@pytest.mark.live_op('list_link_types')
def test_link_two_issues(jira, site, needs_project):
    first, second = site.new_issue(), site.new_issue()
    link_type = jira('list_link_types')['issueLinkTypes'][0]['name']
    assert jira('link_issues', link_type=link_type, inward_issue=first, outward_issue=second,
                comment='linked by test')['status'] == 'Success'
    links = jira('get_ticket_details', issue_key=first, fields='issuelinks')['fields']['issuelinks']
    assert links


@pytest.mark.live_op('submit_file')
def test_submit_file(jira, site, needs_project, monkeypatch, tmp_path):
    local = tmp_path / 'evidence.txt'
    local.write_text('attached by the jirav2 online tests')
    monkeypatch.setattr(operations_module, '_get_file_data', lambda kind, value: ('evidence.txt', str(local)))
    key = site.new_issue()
    uploaded = jira('submit_file', issue_key=key, path='Attachment ID', value='ignored')
    assert uploaded[0]['filename'] == 'evidence.txt'
    attachments = jira('get_ticket_details', issue_key=key, fields='attachment')['fields']['attachment']
    assert [a['filename'] for a in attachments] == ['evidence.txt']


# -- Jira Service Management -----------------------------------------------

@pytest.fixture
def desk(site):
    if not site.desk:
        pytest.skip('the site has no Jira Service Management service desk')
    return site.desk


@pytest.mark.live_op('list_service_desks')
@pytest.mark.live_op('get_service_desk_options')
def test_service_desks(jira, pairs, desk):
    assert any(d['id'] == desk['id'] for d in jira('list_service_desks')['values'])
    assert str(desk['id']) in [o['value'] for o in pairs('get_service_desk_options')]


@pytest.mark.live_op('list_request_types')
@pytest.mark.live_op('get_request_type_fields')
def test_request_types_and_their_fields(jira, desk):
    types = jira('list_request_types', service_desk_id=desk['id'])['values']
    assert types
    fields = jira('get_request_type_fields', service_desk_id=desk['id'], request_type_id=types[0]['id'])
    assert any(f['fieldId'] == 'summary' for f in fields['requestTypeFields'])


@pytest.mark.live_op('create_customer_request')
@pytest.mark.live_op('get_customer_request')
@pytest.mark.live_op('add_request_comment')
def test_customer_request_lifecycle(jira, site, desk):
    request_type = None
    for candidate in jira('list_request_types', service_desk_id=desk['id'])['values']:
        fields = jira('get_request_type_fields', service_desk_id=desk['id'],
                      request_type_id=candidate['id'])['requestTypeFields']
        if {f['fieldId'] for f in fields if f.get('required')} <= {'summary', 'description'}:
            request_type = candidate
            break
    if request_type is None:
        pytest.skip('every request type has required fields beyond summary and description')
    made = jira('create_customer_request', service_desk_id=desk['id'], request_type_id=request_type['id'],
                summary='jirav2 customer request', description='created by the online tests')
    site.created.append(made['issueKey'])
    fetched = jira('get_customer_request', issue_key=made['issueKey'])
    assert fetched['issueKey'] == made['issueKey']
    assert jira('add_request_comment', issue_key=made['issueKey'], comment='public reply')['public'] is True
    note = jira('add_request_comment', issue_key=made['issueKey'], comment='agent note', public=False)
    assert note['public'] is False


@pytest.mark.live_op('list_queues')
@pytest.mark.live_op('list_queue_issues')
def test_queues(jira, desk):
    queues = jira('list_queues', service_desk_id=desk['id'], include_count=True)['values']
    if not queues:
        pytest.skip('the service desk has no queues')
    page = jira('list_queue_issues', service_desk_id=desk['id'], queue_id=queues[0]['id'], limit=5)
    assert 'values' in page


# -- dependent dropdowns (the editor passes sibling values to the populator) --

@pytest.mark.live_op('get_issue_type_options')
@pytest.mark.live_op('get_issue_type_id_options')
def test_issue_type_dropdowns_follow_the_project(jira, pairs, site, needs_project):
    own = {t['name'] for t in jira('list_issue_types', project_key=site.project)['issueTypes']}
    names = {o['value'] for o in pairs('get_issue_type_options', project_key=site.project)}
    assert names == own
    ids = {o['value'] for o in pairs('get_issue_type_id_options', project_key=site.project)}
    assert str(site.issue_type['id']) in ids
    assert jira('get_issue_type_options', project_key='NOSUCHPROJECT') == []


@pytest.mark.live_op('get_request_type_options')
@pytest.mark.live_op('get_queue_options')
def test_request_type_and_queue_dropdowns_follow_the_service_desk(jira, pairs, desk):
    request_types = pairs('get_request_type_options', service_desk_id=desk['id'])
    assert request_types and all(set(o) == {'title', 'value'} for o in request_types)
    wanted = {str(t['id']) for t in jira('list_request_types', service_desk_id=desk['id'])['values']}
    assert {o['value'] for o in request_types} == wanted
    queues = pairs('get_queue_options', service_desk_id=desk['id'])
    assert {o['value'] for o in queues} == {str(q['id']) for q in jira('list_queues', service_desk_id=desk['id'])['values']}
    assert jira('get_request_type_options') == [] and jira('get_queue_options') == []


@pytest.mark.live_op('get_transition_options')
@pytest.mark.live_op('get_transition_id_options')
def test_transition_dropdowns_follow_the_issue(jira, pairs, site, needs_project):
    key = site.new_issue()
    real = jira('get_transitions', issue_key=key)['transitions']
    assert {o['value'] for o in pairs('get_transition_options', issue_key=key)} == {t['to']['name'] for t in real}
    assert {o['value'] for o in pairs('get_transition_id_options', issue_key=key)} == {str(t['id']) for t in real}
    assert jira('get_transition_options') == []

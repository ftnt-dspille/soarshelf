"""Issue lifecycle: create, read, update, delete, transition, assign, history, time."""
import pytest

from jirav2 import client as client_module

ConnectorError = client_module.ConnectorError
ISSUE = '/rest/api/3/issue'


# -- create_ticket ---------------------------------------------------------

@pytest.mark.op('create_ticket')
def test_create_ticket_sends_the_minimum(fake, run):
    fake.on('POST', ISSUE, {'id': '1', 'key': 'SEC-1', 'self': 'x'}, status=201)
    out = run('create_ticket', project_key='SEC', ticket_summary='Disk full', issue_type='Task')
    assert fake.only().json == {'fields': {'project': {'key': 'SEC'}, 'summary': 'Disk full',
                                           'issuetype': {'name': 'Task'}}}
    assert out['key'] == 'SEC-1'
    assert out['browse_url'] == 'https://example.atlassian.net/browse/SEC-1'


@pytest.mark.op('create_ticket')
def test_create_ticket_sends_every_optional_field(fake, run):
    fake.on('POST', ISSUE, {'key': 'SEC-2'}, status=201)
    run('create_ticket', project_key='SEC', ticket_summary='s', ticket_description='line1\nline2',
        issue_type='Task', priority='High', labels='a, b', assignee_account_id='acc1', parent='SEC-1',
        other_fields='{"customfield_10010": "1/25"}')
    fields = fake.only().json['fields']
    assert fields['priority'] == {'name': 'High'}
    assert fields['labels'] == ['a', 'b']
    assert fields['assignee'] == {'accountId': 'acc1'}
    assert fields['parent'] == {'key': 'SEC-1'}
    assert fields['customfield_10010'] == '1/25'
    assert fields['description']['type'] == 'doc'


@pytest.mark.op('create_ticket')
def test_create_ticket_issue_type_id_wins_over_name(fake, run):
    fake.on('POST', ISSUE, {'key': 'SEC-3'}, status=201)
    run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task', issue_type_id='10341')
    assert fake.only().json['fields']['issuetype'] == {'id': '10341'}


@pytest.mark.op('create_ticket')
def test_create_ticket_other_fields_can_override_issue_type(fake, run):
    fake.on('POST', ISSUE, {'key': 'SEC-3'}, status=201)
    run('create_ticket', project_key='SEC', ticket_summary='s',
        other_fields={'issuetype': {'id': '10343'}})
    assert fake.only().json['fields']['issuetype'] == {'id': '10343'}


@pytest.mark.op('create_ticket')
def test_create_ticket_blank_priority_is_not_sent(fake, run):
    """A JSM project with no Priority field rejects the field outright."""
    fake.on('POST', ISSUE, {'key': 'SEC-4'}, status=201)
    run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task', priority='')
    assert 'priority' not in fake.only().json['fields']


@pytest.mark.op('create_ticket')
def test_create_ticket_without_issue_type_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='Issue Type'):
        run('create_ticket', project_key='SEC', ticket_summary='s')
    assert not fake.calls


@pytest.mark.op('create_ticket')
@pytest.mark.parametrize('missing', ['project_key', 'ticket_summary'])
def test_create_ticket_requires_project_and_summary(fake, run, missing):
    params = {'project_key': 'SEC', 'ticket_summary': 's', 'issue_type': 'Task'}
    del params[missing]
    with pytest.raises(ConnectorError, match=missing):
        run('create_ticket', **params)


@pytest.mark.op('create_ticket')
def test_create_ticket_bad_other_fields_json_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='other_fields'):
        run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task', other_fields='{nope')


@pytest.mark.op('create_ticket')
def test_create_ticket_other_fields_must_be_an_object(fake, run):
    with pytest.raises(ConnectorError, match='JSON object'):
        run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task', other_fields='[1]')


@pytest.mark.op('create_ticket')
def test_create_ticket_include_details_reads_the_issue_back(fake, run):
    fake.on('POST', ISSUE, {'key': 'SEC-5'}, status=201)
    fake.on('GET', ISSUE + '/SEC-5', {'key': 'SEC-5', 'fields': {'status': {'name': 'To Do'}}})
    out = run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task', include_details=True)
    assert out['issue']['fields']['status']['name'] == 'To Do'


@pytest.mark.op('create_ticket')
def test_create_ticket_surfaces_the_jira_error(fake, run):
    fake.on('POST', ISSUE, {'errors': {'issuetype': 'Specify a valid issue type'}}, status=400)
    with pytest.raises(ConnectorError, match='Specify a valid issue type'):
        run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Service Request')


@pytest.mark.op('create_ticket')
def test_create_ticket_has_no_browse_url_through_the_gateway(fake, run, config):
    config['server_url'] = 'https://api.atlassian.com/ex/jira/abc'
    fake.on('POST', ISSUE, {'key': 'SEC-6'}, status=201)
    assert 'browse_url' not in run('create_ticket', project_key='SEC', ticket_summary='s', issue_type='Task')


# -- get_ticket_details ----------------------------------------------------

@pytest.mark.op('get_ticket_details')
def test_get_ticket_details(fake, run):
    fake.on('GET', ISSUE + '/SEC-1', {'key': 'SEC-1', 'fields': {}})
    assert run('get_ticket_details', issue_key='SEC-1')['key'] == 'SEC-1'
    assert fake.only().params == {}


@pytest.mark.op('get_ticket_details')
def test_get_ticket_details_fields_and_expand(fake, run):
    fake.on('GET', ISSUE + '/SEC-1', {'fields': {}})
    run('get_ticket_details', issue_key='SEC-1', fields='summary, status', expand='changelog')
    assert fake.only().params == {'fields': 'summary,status', 'expand': 'changelog'}


@pytest.mark.op('get_ticket_details')
def test_get_ticket_details_include_text(fake, run):
    from jirav2.adf import to_adf
    fake.on('GET', ISSUE + '/SEC-1', {'fields': {'description': to_adf('hello\nthere')}})
    assert run('get_ticket_details', issue_key='SEC-1', include_text=True)['description_text'] == 'hello\nthere'


@pytest.mark.op('get_ticket_details')
def test_get_ticket_details_not_found_explains_visibility(fake, run):
    fake.on('GET', ISSUE + '/SEC-9', {'errorMessages': ['Issue does not exist']}, status=404)
    with pytest.raises(ConnectorError, match='Browse permission'):
        run('get_ticket_details', issue_key='SEC-9')


@pytest.mark.op('get_ticket_details')
def test_issue_key_is_url_encoded_so_it_cannot_change_the_path(fake, run):
    fake.on('GET', ISSUE + '/..%2Fmyself', {'fields': {}})
    run('get_ticket_details', issue_key='../myself')
    assert fake.only().path == ISSUE + '/..%2Fmyself'


@pytest.mark.op('get_ticket_details')
def test_issue_key_is_required(fake, run):
    with pytest.raises(ConnectorError, match='issue_key'):
        run('get_ticket_details', issue_key='  ')


# -- update_ticket ---------------------------------------------------------

@pytest.mark.op('update_ticket')
def test_update_ticket_sends_only_what_was_set(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1', None, status=204)
    out = run('update_ticket', issue_key='SEC-1', summary='new')
    assert fake.only().json == {'fields': {'summary': 'new'}}
    assert out['status'] == 'Success'


@pytest.mark.op('update_ticket')
def test_update_ticket_never_sends_the_project(fake, run):
    """v1 sent project on every update; Jira cannot move an issue that way."""
    fake.on('PUT', ISSUE + '/SEC-1', None, status=204)
    run('update_ticket', issue_key='SEC-1', summary='x', priority='Low', description='d', labels='a')
    assert 'project' not in fake.only().json['fields']


@pytest.mark.op('update_ticket')
def test_update_ticket_comment_goes_in_the_update_block(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1', None, status=204)
    run('update_ticket', issue_key='SEC-1', comment='see this')
    body = fake.only().json
    assert 'fields' not in body
    assert body['update']['comment'][0]['add']['body']['type'] == 'doc'


@pytest.mark.op('update_ticket')
def test_update_ticket_notify_users_false(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1', None, status=204)
    run('update_ticket', issue_key='SEC-1', summary='x', notify_users=False)
    assert fake.only().params == {'notifyUsers': 'false'}


@pytest.mark.op('update_ticket')
def test_update_ticket_status_transitions_after_the_field_update(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1', None, status=204)
    fake.on('GET', ISSUE + '/SEC-1/transitions',
            {'transitions': [{'id': '31', 'name': 'Done it', 'to': {'name': 'Done'}}]})
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    out = run('update_ticket', issue_key='SEC-1', summary='x', status='done')
    assert [c.method for c in fake.calls] == ['PUT', 'GET', 'POST']
    assert fake.calls[2].json == {'transition': {'id': '31'}}
    assert out['transition'] == {'id': '31', 'name': 'Done it', 'to': 'Done'}


@pytest.mark.op('update_ticket')
def test_update_ticket_status_only_skips_the_put(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', {'transitions': [{'id': '5', 'name': 'Go', 'to': {'name': 'Open'}}]})
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    run('update_ticket', issue_key='SEC-1', status='Open')
    assert [c.method for c in fake.calls] == ['GET', 'POST']


@pytest.mark.op('update_ticket')
def test_update_ticket_with_nothing_to_do_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='Nothing to update'):
        run('update_ticket', issue_key='SEC-1')
    assert not fake.calls


# -- delete_ticket ---------------------------------------------------------

@pytest.mark.op('delete_ticket')
def test_delete_ticket(fake, run):
    fake.on('DELETE', ISSUE + '/SEC-1', None, status=204)
    assert run('delete_ticket', issue_key='SEC-1')['status'] == 'Success'
    assert fake.only().params == {'deleteSubtasks': 'false'}


@pytest.mark.op('delete_ticket')
def test_delete_ticket_with_subtasks(fake, run):
    fake.on('DELETE', ISSUE + '/SEC-1', None, status=204)
    run('delete_ticket', issue_key='SEC-1', delete_subtask=True)
    assert fake.only().params == {'deleteSubtasks': 'true'}


@pytest.mark.op('delete_ticket')
def test_delete_ticket_with_subtasks_but_no_flag_surfaces_the_jira_refusal(fake, run):
    fake.on('DELETE', ISSUE + '/SEC-1', {'errorMessages': ['The issue has subtasks']}, status=400)
    with pytest.raises(ConnectorError, match='has subtasks'):
        run('delete_ticket', issue_key='SEC-1')


# -- transitions -----------------------------------------------------------

TRANSITIONS = {'transitions': [
    {'id': '11', 'name': 'Start progress', 'to': {'name': 'In Progress'}},
    {'id': '31', 'name': 'Resolve', 'to': {'name': 'Done'}}]}


@pytest.mark.op('get_transitions')
def test_get_transitions(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    assert [t['id'] for t in run('get_transitions', issue_key='SEC-1')['transitions']] == ['11', '31']


@pytest.mark.op('set_status')
def test_set_status_by_target_status_name_is_case_insensitive(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    out = run('set_status', issue_key='SEC-1', status='in progress')
    assert fake.calls[1].json == {'transition': {'id': '11'}}
    assert out['transition']['to'] == 'In Progress'


@pytest.mark.op('set_status')
def test_set_status_by_transition_name(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    run('set_status', issue_key='SEC-1', status='Resolve')
    assert fake.calls[1].json == {'transition': {'id': '31'}}


@pytest.mark.op('set_status')
def test_set_status_by_transition_id_wins(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    run('set_status', issue_key='SEC-1', status='Done', transition_id='11')
    assert fake.calls[1].json == {'transition': {'id': '11'}}


@pytest.mark.op('set_status')
def test_set_status_with_resolution_and_comment(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    fake.on('POST', ISSUE + '/SEC-1/transitions', None, status=204)
    run('set_status', issue_key='SEC-1', status='Done', resolution='Fixed', comment='shipped')
    body = fake.calls[1].json
    assert body['fields'] == {'resolution': {'name': 'Fixed'}}
    assert body['update']['comment'][0]['add']['body']['type'] == 'doc'


@pytest.mark.op('set_status')
def test_set_status_unknown_lists_what_is_available(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/transitions', TRANSITIONS)
    with pytest.raises(ConnectorError) as err:
        run('set_status', issue_key='SEC-1', status='Nowhere')
    assert 'Start progress (to In Progress)' in str(err.value)
    assert 'Resolve (to Done)' in str(err.value)
    assert fake.paths() == [('GET', ISSUE + '/SEC-1/transitions')]


@pytest.mark.op('set_status')
def test_set_status_needs_a_target(fake, run):
    with pytest.raises(ConnectorError, match='Status or Transition ID'):
        run('set_status', issue_key='SEC-1')


# -- assign ----------------------------------------------------------------

@pytest.mark.op('assign_issue')
def test_assign_issue(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1/assignee', None, status=204)
    out = run('assign_issue', issue_key='SEC-1', accountId='acc1')
    assert fake.only().json == {'accountId': 'acc1'}
    assert out['accountId'] == 'acc1'


@pytest.mark.op('assign_issue')
def test_assign_issue_blank_unassigns(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1/assignee', None, status=204)
    out = run('assign_issue', issue_key='SEC-1', accountId='')
    assert fake.only().json == {'accountId': None}
    assert out['accountId'] is None


@pytest.mark.op('assign_issue')
def test_assign_issue_minus_one_means_default_assignee(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1/assignee', None, status=204)
    run('assign_issue', issue_key='SEC-1', accountId='-1')
    assert fake.only().json == {'accountId': '-1'}


# -- changelog / worklog ---------------------------------------------------

@pytest.mark.op('get_changelog')
def test_get_changelog(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/changelog', {'values': [{'id': '1'}], 'total': 1})
    out = run('get_changelog', issue_key='SEC-1', startAt=10, maxResults=5)
    assert out['values'] == [{'id': '1'}]
    assert fake.only().params == {'startAt': 10, 'maxResults': 5}


@pytest.mark.op('add_worklog')
def test_add_worklog(fake, run):
    fake.on('POST', ISSUE + '/SEC-1/worklog', {'id': '77'}, status=201)
    out = run('add_worklog', issue_key='SEC-1', time_spent='1h 30m', comment='fixed it',
              started='2025-10-12T14:05:00.000Z')
    body = fake.only().json
    assert body['timeSpent'] == '1h 30m'
    assert body['started'] == '2025-10-12T14:05:00.000+0000'
    assert body['comment']['type'] == 'doc'
    assert out['id'] == '77'


@pytest.mark.op('add_worklog')
def test_add_worklog_minimum_and_naive_time(fake, run):
    fake.on('POST', ISSUE + '/SEC-1/worklog', {'id': '78'}, status=201)
    run('add_worklog', issue_key='SEC-1', time_spent='2h', started='2025-10-12T14:05:00')
    assert fake.only().json == {'timeSpent': '2h', 'started': '2025-10-12T14:05:00.000+0000'}


@pytest.mark.op('add_worklog')
def test_add_worklog_bad_time_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='ISO-8601'):
        run('add_worklog', issue_key='SEC-1', time_spent='1h', started='yesterday')
    assert not fake.calls


@pytest.mark.op('add_worklog')
def test_add_worklog_requires_time_spent(fake, run):
    with pytest.raises(ConnectorError, match='time_spent'):
        run('add_worklog', issue_key='SEC-1')

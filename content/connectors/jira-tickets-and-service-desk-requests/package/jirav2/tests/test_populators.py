"""The hidden get_*_options operations that feed the step editor's dropdowns (apiOperation)."""
import pytest


@pytest.mark.op('get_project_options')
def test_project_options_are_name_key_pairs_sorted_by_name(fake, run):
    fake.on('GET', '/rest/api/3/project/search', {'isLast': True, 'values': [
        {'key': 'OPS', 'name': 'Operations'}, {'key': 'ETSP', 'name': 'Enterprise Support'}]})
    assert run('get_project_options') == [
        {'title': 'Enterprise Support (ETSP)', 'value': 'ETSP'},
        {'title': 'Operations (OPS)', 'value': 'OPS'}]


@pytest.mark.op('get_project_options')
def test_project_options_walk_every_page(fake, run):
    fake.on_sequence('GET', '/rest/api/3/project/search', [
        (200, {'isLast': False, 'values': [{'key': 'A', 'name': 'A'}]}),
        (200, {'isLast': True, 'values': [{'key': 'B', 'name': 'B'}]})])
    assert [o['value'] for o in run('get_project_options')] == ['A', 'B']


@pytest.mark.op('get_project_options')
def test_project_options_empty_site(fake, run):
    fake.on('GET', '/rest/api/3/project/search', {'isLast': True, 'values': []})
    assert run('get_project_options') == []


TYPES = [{'id': '10341', 'name': '[System] Service request', 'subtask': False},
         {'id': '10038', 'name': 'Sub-task', 'subtask': True},
         {'id': '99', 'name': 'Sub-task', 'subtask': True},
         {'id': '1', 'name': 'Task', 'subtask': False}]


@pytest.mark.op('get_issue_type_options')
def test_issue_type_options_use_the_name_as_the_value_and_dedupe(fake, run):
    fake.on('GET', '/rest/api/3/issuetype', TYPES)
    assert run('get_issue_type_options') == [
        {'title': '[System] Service request', 'value': '[System] Service request'},
        {'title': 'Sub-task (sub-task)', 'value': 'Sub-task'},
        {'title': 'Task', 'value': 'Task'}]


@pytest.mark.op('get_issue_type_id_options')
def test_issue_type_id_options_use_the_id_as_the_value(fake, run):
    fake.on('GET', '/rest/api/3/issuetype', TYPES)
    options = run('get_issue_type_id_options')
    assert {'title': '[System] Service request [10341]', 'value': '10341'} in options
    assert all(isinstance(o['value'], str) for o in options)


@pytest.mark.op('get_link_type_options')
def test_link_type_options(fake, run):
    fake.on('GET', '/rest/api/3/issueLinkType', {'issueLinkTypes': [
        {'name': 'Blocks', 'inward': 'is blocked by', 'outward': 'blocks'}]})
    assert run('get_link_type_options') == [{'title': 'Blocks (is blocked by / blocks)', 'value': 'Blocks'}]


@pytest.mark.op('get_user_options')
def test_user_options_keep_active_people_only(fake, run):
    fake.on('GET', '/rest/api/3/users/search', [
        {'accountId': 'a1', 'displayName': 'Sam Rivera', 'emailAddress': 'sam@example.com',
         'accountType': 'atlassian', 'active': True},
        {'accountId': 'a2', 'displayName': 'Gone Person', 'accountType': 'atlassian', 'active': False},
        {'accountId': 'a3', 'displayName': 'Some App', 'accountType': 'app', 'active': True},
        {'accountId': 'a4', 'accountType': 'atlassian', 'active': True}])
    assert run('get_user_options') == [
        {'title': 'a4', 'value': 'a4'},
        {'title': 'Sam Rivera (sam@example.com)', 'value': 'a1'}]


@pytest.mark.op('get_user_options')
def test_user_options_page_through_large_sites(fake, run):
    page = [{'accountId': 'u%d' % i, 'displayName': 'U%03d' % i, 'accountType': 'atlassian', 'active': True}
            for i in range(100)]
    fake.on_sequence('GET', '/rest/api/3/users/search', [(200, page), (200, [page[0]])])
    assert len(run('get_user_options')) == 101
    assert [c.params['startAt'] for c in fake.calls] == [0, 100]


@pytest.mark.op('get_service_desk_options')
def test_service_desk_options(fake, run):
    fake.on('GET', '/rest/servicedeskapi/servicedesk', {'values': [
        {'id': 4, 'projectName': 'Enterprise Support', 'projectKey': 'ETSP'}]})
    assert run('get_service_desk_options') == [{'title': 'Enterprise Support (ETSP)', 'value': '4'}]


# -- dependent dropdowns: the editor passes the form's other values ----------

@pytest.mark.op('get_issue_type_options')
def test_issue_type_options_follow_the_chosen_project(fake, run):
    """The project's own types, such as the [System] ones in a service desk, not the whole site's."""
    fake.on('GET', '/rest/api/3/issue/createmeta/ETSP/issuetypes', {'issueTypes': [
        {'id': '10341', 'name': '[System] Service request', 'subtask': False},
        {'id': '10038', 'name': 'Sub-task', 'subtask': True}]})
    assert run('get_issue_type_options', project_key='ETSP') == [
        {'title': '[System] Service request', 'value': '[System] Service request'},
        {'title': 'Sub-task (sub-task)', 'value': 'Sub-task'}]


@pytest.mark.op('get_issue_type_id_options')
def test_issue_type_id_options_follow_the_chosen_project(fake, run):
    fake.on('GET', '/rest/api/3/issue/createmeta/ETSP/issuetypes', {'issueTypes': [
        {'id': '10341', 'name': '[System] Service request'}]})
    assert run('get_issue_type_id_options', project_key='ETSP') == [
        {'title': '[System] Service request [10341]', 'value': '10341'}]


@pytest.mark.op('get_issue_type_options')
def test_issue_type_options_for_an_unreadable_project_are_empty_not_an_error(fake, run):
    fake.on('GET', '/rest/api/3/issue/createmeta/NOPE/issuetypes', {'errorMessages': ['no']}, status=404)
    assert run('get_issue_type_options', project_key='NOPE') == []


@pytest.mark.op('get_issue_type_options')
def test_issue_type_options_ignore_an_unresolved_expression(fake, run):
    fake.on('GET', '/rest/api/3/issuetype', [{'id': '1', 'name': 'Task'}])
    assert run('get_issue_type_options', project_key='{{vars.project}}') == []
    assert not fake.calls


@pytest.mark.op('get_request_type_options')
def test_request_type_options_follow_the_service_desk(fake, run):
    fake.on('GET', '/rest/servicedeskapi/servicedesk/4/requesttype', {'isLastPage': True, 'values': [
        {'id': '25', 'name': 'Get IT help'}, {'id': '26', 'name': 'Report a bug'}]})
    assert run('get_request_type_options', service_desk_id='4') == [
        {'title': 'Get IT help', 'value': '25'}, {'title': 'Report a bug', 'value': '26'}]


@pytest.mark.op('get_request_type_options')
def test_request_type_options_are_empty_until_a_desk_is_chosen(fake, run):
    assert run('get_request_type_options') == []
    assert run('get_request_type_options', service_desk_id='') == []
    assert run('get_request_type_options', service_desk_id='{{vars.desk}}') == []
    assert not fake.calls


@pytest.mark.op('get_request_type_options')
def test_request_type_options_page_through(fake, run):
    fake.on_sequence('GET', '/rest/servicedeskapi/servicedesk/4/requesttype', [
        (200, {'isLastPage': False, 'values': [{'id': '1', 'name': 'A'}]}),
        (200, {'isLastPage': True, 'values': [{'id': '2', 'name': 'B'}]})])
    assert [o['value'] for o in run('get_request_type_options', service_desk_id='4')] == ['1', '2']
    assert [c.params['start'] for c in fake.calls] == [0, 1]


@pytest.mark.op('get_queue_options')
def test_queue_options_follow_the_service_desk(fake, run):
    fake.on('GET', '/rest/servicedeskapi/servicedesk/4/queue', {'isLastPage': True, 'values': [
        {'id': '133', 'name': 'All open'}]})
    assert run('get_queue_options', service_desk_id=4) == [{'title': 'All open', 'value': '133'}]


@pytest.mark.op('get_queue_options')
def test_queue_options_are_empty_until_a_desk_is_chosen(fake, run):
    assert run('get_queue_options') == []
    assert not fake.calls


@pytest.mark.op('get_transition_options')
def test_transition_options_are_the_statuses_the_issue_can_reach(fake, run):
    fake.on('GET', '/rest/api/3/issue/SEC-1/transitions', {'transitions': [
        {'id': '11', 'name': 'Start progress', 'to': {'name': 'In Progress'}},
        {'id': '31', 'name': 'Resolve', 'to': {'name': 'Done'}}]})
    assert run('get_transition_options', issue_key='SEC-1') == [
        {'title': 'In Progress (via Start progress)', 'value': 'In Progress'},
        {'title': 'Done (via Resolve)', 'value': 'Done'}]


@pytest.mark.op('get_transition_options')
def test_transition_options_are_empty_without_an_issue_or_for_a_missing_one(fake, run):
    assert run('get_transition_options') == []
    fake.on('GET', '/rest/api/3/issue/SEC-9/transitions', {'errorMessages': ['gone']}, status=404)
    assert run('get_transition_options', issue_key='SEC-9') == []


@pytest.mark.op('get_transition_id_options')
def test_transition_id_options(fake, run):
    fake.on('GET', '/rest/api/3/issue/SEC-1/transitions', {'transitions': [
        {'id': 31, 'name': 'Resolve', 'to': {'name': 'Done'}}]})
    assert run('get_transition_id_options', issue_key='SEC-1') == [
        {'title': 'Resolve -> Done [31]', 'value': '31'}]
    assert run('get_transition_id_options') == []


@pytest.mark.op('get_transition_id_options')
def test_transition_id_options_for_a_missing_issue_are_empty(fake, run):
    fake.on('GET', '/rest/api/3/issue/SEC-9/transitions', {'errorMessages': ['gone']}, status=404)
    assert run('get_transition_id_options', issue_key='SEC-9') == []


@pytest.mark.op('get_transition_options')
@pytest.mark.parametrize('status', [401, 403])
def test_a_missing_scope_is_an_error_not_an_empty_dropdown(fake, run, status):
    """A denied token must be visible: an empty list would read as 'no transitions'."""
    from jirav2 import client as client_module
    fake.on('GET', '/rest/api/3/issue/SEC-1/transitions', {'code': status, 'message': 'Unauthorized; scope does not match'},
            status=status)
    with pytest.raises(client_module.ConnectorError, match='HTTP %d' % status):
        run('get_transition_options', issue_key='SEC-1')


@pytest.mark.op('get_request_type_options')
def test_request_type_options_surface_a_denied_scope(fake, run):
    from jirav2 import client as client_module
    fake.on('GET', '/rest/servicedeskapi/servicedesk/4/requesttype', {'errorMessage': 'no'}, status=403)
    with pytest.raises(client_module.ConnectorError, match='HTTP 403'):
        run('get_request_type_options', service_desk_id='4')

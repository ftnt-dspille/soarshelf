"""Jira Service Management: service desks, request types, requests, queues."""
import pytest

from jirav2 import client as client_module

ConnectorError = client_module.ConnectorError
JSM = '/rest/servicedeskapi'


@pytest.mark.op('list_service_desks')
def test_list_service_desks(fake, run):
    fake.on('GET', JSM + '/servicedesk', {'values': [{'id': '4', 'projectKey': 'ETSP'}]})
    out = run('list_service_desks', start=0, limit=10)
    assert fake.only().params == {'start': 0, 'limit': 10}
    assert out['values'][0]['projectKey'] == 'ETSP'


@pytest.mark.op('list_request_types')
def test_list_request_types(fake, run):
    fake.on('GET', JSM + '/servicedesk/4/requesttype', {'values': [{'id': '25', 'name': 'Get IT help'}]})
    out = run('list_request_types', service_desk_id='4', search_query='help')
    assert fake.only().params == {'searchQuery': 'help'}
    assert out['values'][0]['id'] == '25'


@pytest.mark.op('list_request_types')
def test_list_request_types_requires_the_desk(fake, run):
    with pytest.raises(ConnectorError, match='service_desk_id'):
        run('list_request_types')


@pytest.mark.op('get_request_type_fields')
def test_get_request_type_fields(fake, run):
    fake.on('GET', JSM + '/servicedesk/4/requesttype/25/field',
            {'requestTypeFields': [{'fieldId': 'summary', 'required': True}]})
    assert run('get_request_type_fields', service_desk_id='4', request_type_id='25')[
        'requestTypeFields'][0]['required'] is True


@pytest.mark.op('create_customer_request')
def test_create_customer_request(fake, run):
    fake.on('POST', JSM + '/request', {'issueId': '1', 'issueKey': 'ETSP-1'}, status=201)
    out = run('create_customer_request', service_desk_id='4', request_type_id='25', summary='VPN down',
              description='cannot connect', raise_on_behalf_of='acc9', request_participants='a1, a2',
              request_field_values='{"customfield_10100": "high"}')
    assert fake.only().json == {
        'serviceDeskId': '4', 'requestTypeId': '25',
        'requestFieldValues': {'summary': 'VPN down', 'description': 'cannot connect',
                               'customfield_10100': 'high'},
        'raiseOnBehalfOf': 'acc9', 'requestParticipants': ['a1', 'a2']}
    assert out['issueKey'] == 'ETSP-1'


@pytest.mark.op('create_customer_request')
def test_create_customer_request_description_is_text_not_adf(fake, run):
    fake.on('POST', JSM + '/request', {'issueKey': 'ETSP-2'}, status=201)
    run('create_customer_request', service_desk_id='4', request_type_id='25', summary='s', description='plain')
    assert fake.only().json['requestFieldValues']['description'] == 'plain'


@pytest.mark.op('create_customer_request')
def test_create_customer_request_minimum(fake, run):
    fake.on('POST', JSM + '/request', {'issueKey': 'ETSP-3'}, status=201)
    run('create_customer_request', service_desk_id=4, request_type_id=25, summary='s')
    assert fake.only().json == {'serviceDeskId': '4', 'requestTypeId': '25', 'requestFieldValues': {'summary': 's'}}


@pytest.mark.op('create_customer_request')
@pytest.mark.parametrize('missing', ['service_desk_id', 'request_type_id', 'summary'])
def test_create_customer_request_requires(fake, run, missing):
    params = {'service_desk_id': '4', 'request_type_id': '25', 'summary': 's'}
    del params[missing]
    with pytest.raises(ConnectorError, match=missing):
        run('create_customer_request', **params)


@pytest.mark.op('get_customer_request')
def test_get_customer_request(fake, run):
    fake.on('GET', JSM + '/request/ETSP-1', {'issueKey': 'ETSP-1', 'currentStatus': {'status': 'Waiting'}})
    out = run('get_customer_request', issue_key='ETSP-1', expand='participant, sla')
    assert fake.only().params == {'expand': 'participant,sla'}
    assert out['currentStatus']['status'] == 'Waiting'


@pytest.mark.op('add_request_comment')
def test_add_request_comment_is_public_by_default(fake, run):
    fake.on('POST', JSM + '/request/ETSP-1/comment', {'id': '9'}, status=201)
    run('add_request_comment', issue_key='ETSP-1', comment='working on it')
    assert fake.only().json == {'body': 'working on it', 'public': True}


@pytest.mark.op('add_request_comment')
def test_add_request_comment_internal(fake, run):
    fake.on('POST', JSM + '/request/ETSP-1/comment', {'id': '9'}, status=201)
    run('add_request_comment', issue_key='ETSP-1', comment='note to self', public=False)
    assert fake.only().json == {'body': 'note to self', 'public': False}


@pytest.mark.op('list_queues')
def test_list_queues(fake, run):
    fake.on('GET', JSM + '/servicedesk/4/queue', {'values': [{'id': '133', 'name': 'All open'}]})
    out = run('list_queues', service_desk_id='4', include_count=True, limit=5)
    assert fake.only().params == {'limit': 5, 'includeCount': 'true'}
    assert out['values'][0]['id'] == '133'


@pytest.mark.op('list_queue_issues')
def test_list_queue_issues(fake, run):
    fake.on('GET', JSM + '/servicedesk/4/queue/133/issue', {'values': [{'key': 'ETSP-1'}]})
    out = run('list_queue_issues', service_desk_id='4', queue_id='133', start=0, limit=25)
    assert fake.only().params == {'start': 0, 'limit': 25}
    assert out['values'][0]['key'] == 'ETSP-1'


@pytest.mark.op('list_queue_issues')
def test_list_queue_issues_requires_a_queue(fake, run):
    with pytest.raises(ConnectorError, match='queue_id'):
        run('list_queue_issues', service_desk_id='4')


@pytest.mark.op('list_queues')
def test_jsm_errors_use_the_errormessage_key(fake, run):
    fake.on('GET', JSM + '/servicedesk/4/queue', {'errorMessage': 'The Service Desk does not exist'}, status=404)
    with pytest.raises(ConnectorError, match='Service Desk does not exist'):
        run('list_queues', service_desk_id='4')

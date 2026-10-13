"""execute_api_request: the escape hatch for endpoints without a dedicated action."""
import pytest

from jirav2 import client as client_module

ConnectorError = client_module.ConnectorError


@pytest.mark.op('execute_api_request')
def test_get_with_query_params(fake, run):
    fake.on('GET', '/rest/api/3/project/search', {'values': []})
    out = run('execute_api_request', endpoint='/rest/api/3/project/search', method='GET',
              query_params={'maxResults': 1, 'query': 'x'})
    assert out == {'values': []}
    assert fake.only().params == {'maxResults': 1, 'query': 'x'}


@pytest.mark.op('execute_api_request')
def test_query_params_as_a_json_string(fake, run):
    fake.on('GET', '/rest/api/3/x', {})
    run('execute_api_request', endpoint='/rest/api/3/x', query_params='{"a": "1"}')
    assert fake.only().params == {'a': '1'}


@pytest.mark.op('execute_api_request')
def test_post_json_payload(fake, run):
    fake.on('POST', '/rest/api/3/issue', {'key': 'SEC-1'}, status=201)
    run('execute_api_request', endpoint='/rest/api/3/issue', method='POST', content_type='application/json',
        payload={'fields': {'summary': 's'}})
    call = fake.only()
    assert call.json == {'fields': {'summary': 's'}}
    assert call.headers['Content-Type'] == 'application/json'


@pytest.mark.op('execute_api_request')
def test_content_type_none_falls_back_to_json(fake, run):
    fake.on('POST', '/rest/api/3/x', {})
    run('execute_api_request', endpoint='/rest/api/3/x', method='POST', content_type='None', payload='{"a": 1}')
    assert fake.only().json == {'a': 1}


@pytest.mark.op('execute_api_request')
def test_form_payload_is_sent_as_data(fake, run):
    fake.on('POST', '/rest/api/3/x', {})
    run('execute_api_request', endpoint='/rest/api/3/x', method='POST',
        content_type='application/x-www-form-urlencoded', payload={'a': 1})
    call = fake.only()
    assert call.json is None and call.data == '{"a": 1}'
    assert call.headers['Content-Type'] == 'application/x-www-form-urlencoded'


@pytest.mark.op('execute_api_request')
def test_endpoint_without_a_leading_slash_is_accepted(fake, run):
    fake.on('GET', '/rest/api/3/myself', {'accountId': 'a'})
    run('execute_api_request', endpoint='rest/api/3/myself')
    assert fake.only().url == 'https://example.atlassian.net/rest/api/3/myself'


@pytest.mark.op('execute_api_request')
def test_method_defaults_to_get_and_is_case_insensitive(fake, run):
    fake.on('DELETE', '/rest/api/3/x', None, status=204)
    run('execute_api_request', endpoint='/rest/api/3/x', method='delete')
    assert fake.only().method == 'DELETE'


@pytest.mark.op('execute_api_request')
def test_jsm_endpoints_work_too(fake, run):
    fake.on('GET', '/rest/servicedeskapi/servicedesk', {'values': []})
    assert run('execute_api_request', endpoint='/rest/servicedeskapi/servicedesk') == {'values': []}


@pytest.mark.op('execute_api_request')
@pytest.mark.parametrize('endpoint', [
    'https://evil.example.com/steal', 'http://evil.example.com', '//evil.example.com/x',
    '/rest/api/3/../../etc', 'ftp://x/y'])
def test_endpoints_that_could_leak_credentials_are_refused(fake, run, endpoint):
    with pytest.raises(ConnectorError, match='path on the configured site'):
        run('execute_api_request', endpoint=endpoint)
    assert not fake.calls


@pytest.mark.op('execute_api_request')
def test_error_status_raises_with_the_jira_message(fake, run):
    fake.on('GET', '/rest/api/3/x', {'errorMessages': ['no such thing']}, status=404)
    with pytest.raises(ConnectorError, match='no such thing'):
        run('execute_api_request', endpoint='/rest/api/3/x')


@pytest.mark.op('execute_api_request')
def test_bad_payload_json_is_refused(fake, run):
    with pytest.raises(ConnectorError, match='payload'):
        run('execute_api_request', endpoint='/rest/api/3/x', method='POST', payload='{nope')


@pytest.mark.op('execute_api_request')
def test_endpoint_is_required(fake, run):
    with pytest.raises(ConnectorError, match='endpoint'):
        run('execute_api_request')

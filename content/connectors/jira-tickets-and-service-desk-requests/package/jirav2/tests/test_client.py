"""Authentication, URL resolution, retries and error reporting."""
import base64

import pytest
import requests

from jirav2 import client as client_module
from jirav2.client import JiraClient, error_details
from jirav2.connector import JiraV2
from jirav2.operations import check_health

from conftest import GATEWAY, SITE, Reply

ConnectorError = client_module.ConnectorError


def test_basic_auth_sends_credentials_not_a_header(fake, config):
    fake.on('GET', '/rest/api/3/myself', {'accountId': 'a1'})
    JiraClient(config).request('GET', '/rest/api/3/myself')
    call = fake.only()
    assert call.auth == ('me@example.com', 'tok')
    assert 'Authorization' not in call.headers
    assert call.url == SITE + '/rest/api/3/myself'
    assert call.timeout == 30 and call.verify is True


def test_bearer_auth_sends_header_and_no_basic(fake, config):
    config.update({'auth_type': 'Bearer (OAuth 2.0 Access Token)', 'token': 'abc'})
    fake.on('GET', '/rest/api/3/myself', {'accountId': 'a1'})
    JiraClient(config).request('GET', '/rest/api/3/myself')
    call = fake.only()
    assert call.headers['Authorization'] == 'Bearer abc'
    assert call.auth is None


def test_server_url_is_normalised(fake, config):
    config['server_url'] = 'example.atlassian.net/'
    fake.on('GET', '/rest/api/3/myself', {})
    JiraClient(config).request('GET', 'rest/api/3/myself')
    assert fake.only().url == SITE + '/rest/api/3/myself'


def test_blank_server_url_is_refused(config):
    config['server_url'] = '  '
    with pytest.raises(ConnectorError, match='Server URL is required'):
        JiraClient(config)


def test_gateway_url_is_used_as_is(fake, config):
    config['server_url'] = GATEWAY
    fake.on('GET', '/rest/api/3/myself', {})
    JiraClient(config).request('GET', '/rest/api/3/myself')
    assert fake.only().url == GATEWAY + '/rest/api/3/myself'


@pytest.mark.parametrize('url', ['https://api.atlassian.com', 'https://api.atlassian.com/',
                                 'https://api.atlassian.com/ex/jira', 'https://api.atlassian.com/ex/jira/'])
def test_bare_gateway_url_gets_a_clear_error_not_a_404(config, url):
    config['server_url'] = url
    with pytest.raises(ConnectorError, match='missing the cloud id'):
        JiraClient(config).base_url


def test_scoped_with_cloud_id_routes_through_the_gateway(fake, config):
    config.update({'scoped': True, 'cloud_id': 'cid-9'})
    fake.on('GET', '/rest/api/3/myself', {})
    JiraClient(config).request('GET', '/rest/api/3/myself')
    assert fake.only().url == 'https://api.atlassian.com/ex/jira/cid-9/rest/api/3/myself'


def test_scoped_without_cloud_id_looks_it_up_once(fake, config, monkeypatch):
    seen = []

    def tenant_info(url, **kwargs):
        seen.append(url)
        return Reply(200, {'cloudId': 'looked-up'})
    monkeypatch.setattr(client_module.requests, 'get', tenant_info)
    config['scoped'] = True
    fake.on('GET', '/rest/api/3/myself', {})
    JiraClient(config).request('GET', '/rest/api/3/myself')
    JiraClient(config).request('GET', '/rest/api/3/myself')
    assert fake.calls[0].url.startswith('https://api.atlassian.com/ex/jira/looked-up/')
    assert seen == [SITE + '/_edge/tenant_info']


def test_failed_cloud_id_lookup_says_how_to_fix_it(config, monkeypatch):
    def boom(url, **kwargs):
        raise requests.exceptions.ConnectionError('down')
    monkeypatch.setattr(client_module.requests, 'get', boom)
    config['scoped'] = True
    with pytest.raises(ConnectorError, match='Cloud ID field'):
        JiraClient(config).base_url


def test_empty_query_params_are_dropped(fake, config):
    fake.on('GET', '/rest/api/3/project/search', {})
    JiraClient(config).request('GET', '/rest/api/3/project/search',
                               params={'query': '', 'startAt': None, 'maxResults': 5})
    assert fake.only().params == {'maxResults': 5}


def test_timeout_setting_is_used_and_bad_values_fall_back(fake, config):
    config['timeout'] = '12'
    fake.on('GET', '/x', {})
    JiraClient(config).request('GET', '/x')
    assert fake.only().timeout == 12
    assert JiraClient(dict(config, timeout='abc')).timeout == 30
    assert JiraClient(dict(config, timeout=-4)).timeout == 30


def test_empty_204_body_decodes_to_empty_dict(fake, config):
    fake.on('PUT', '/x', None, status=204)
    assert JiraClient(config).request('PUT', '/x') == {}


def test_non_json_body_is_returned_as_raw(fake, config):
    fake.on('GET', '/x', text='plain words')
    assert JiraClient(config).request('GET', '/x') == {'raw': 'plain words'}


def test_error_message_carries_jira_details(fake, config):
    fake.on('POST', '/rest/api/3/issue', {'errorMessages': [], 'errors': {'issuetype': 'Specify a valid issue type'}},
            status=400)
    with pytest.raises(ConnectorError) as err:
        JiraClient(config).request('POST', '/rest/api/3/issue', json_body={})
    assert 'HTTP 400 POST /rest/api/3/issue' in str(err.value)
    assert 'issuetype: Specify a valid issue type' in str(err.value)


def test_401_scope_mismatch_points_at_the_scope_table(fake, config):
    fake.on('GET', '/x', {'code': 401, 'message': 'Unauthorized; scope does not match'}, status=401)
    with pytest.raises(ConnectorError, match='missing a scope'):
        JiraClient(config).request('GET', '/x')


def test_401_plain_points_at_username_and_scoped_option(fake, config):
    fake.on('GET', '/x', None, status=401)
    with pytest.raises(ConnectorError, match='email, not the token name'):
        JiraClient(config).request('GET', '/x')


def test_403_and_404_hints(fake, config):
    fake.on('GET', '/a', {'errorMessages': ['nope']}, status=403)
    fake.on('GET', '/b', {'errorMessages': ['gone']}, status=404)
    with pytest.raises(ConnectorError, match='lacks the Jira project or global permission'):
        JiraClient(config).request('GET', '/a')
    with pytest.raises(ConnectorError, match='Browse permission'):
        JiraClient(config).request('GET', '/b')


def test_429_is_retried_with_retry_after(config, monkeypatch):
    waits = []
    monkeypatch.setattr(client_module, '_sleep', waits.append)
    replies = [Reply(429, {}, headers={'Retry-After': '3'}), Reply(200, {'ok': 1})]
    monkeypatch.setattr(client_module.requests, 'request', lambda *a, **k: replies.pop(0))
    assert JiraClient(config).request('GET', '/x') == {'ok': 1}
    assert waits == [3.0]


def test_429_gives_up_after_three_attempts(config, monkeypatch):
    attempts = []

    def always_429(*args, **kwargs):
        attempts.append(1)
        return Reply(429, {'message': 'slow down'})
    monkeypatch.setattr(client_module.requests, 'request', always_429)
    monkeypatch.setattr(client_module, '_sleep', lambda s: None)
    with pytest.raises(ConnectorError, match='HTTP 429'):
        JiraClient(config).request('GET', '/x')
    assert len(attempts) == 3


def test_503_is_retried_for_get_but_not_for_post(config, monkeypatch):
    monkeypatch.setattr(client_module, '_sleep', lambda s: None)
    counts = {'GET': 0, 'POST': 0}

    def flaky(method, url, **kwargs):
        counts[method] += 1
        return Reply(503, {'message': 'busy'})
    monkeypatch.setattr(client_module.requests, 'request', flaky)
    with pytest.raises(ConnectorError):
        JiraClient(config).request('GET', '/x')
    with pytest.raises(ConnectorError):
        JiraClient(config).request('POST', '/x', json_body={})
    assert counts == {'GET': 3, 'POST': 1}


@pytest.mark.parametrize('raised, message', [
    (requests.exceptions.SSLError('bad cert'), 'SSL certificate validation failed'),
    (requests.exceptions.Timeout(), 'timed out after 30s'),
    (requests.exceptions.ConnectionError('refused'), 'Could not connect'),
])
def test_transport_failures_become_connector_errors(config, monkeypatch, raised, message):
    def boom(*args, **kwargs):
        raise raised
    monkeypatch.setattr(client_module.requests, 'request', boom)
    with pytest.raises(ConnectorError, match=message):
        JiraClient(config).request('GET', '/x')


def test_error_details_shapes():
    assert error_details(Reply(400, {'errorMessages': ['a', 'a', 'b']})) == 'a; b'
    assert error_details(Reply(400, {'errorMessage': 'jsm says no'})) == 'jsm says no'
    assert error_details(Reply(400, {'message': {'i18nKey': 'k'}})) == 'k'
    assert error_details(Reply(500, text='<html>boom</html>')) == '<html>boom</html>'
    assert error_details(Reply(400, [1, 2])) == '[1, 2]'


def test_paginate_offset_walks_every_page(fake, config):
    pages = [{'values': [1, 2], 'isLast': False}, {'values': [3], 'isLast': True}]
    fake.on_sequence('GET', '/p', [(200, pages[0]), (200, pages[1])])
    assert JiraClient(config).paginate_offset('/p', {}) == [1, 2, 3]
    assert [c.params['startAt'] for c in fake.calls] == [0, 2]


def test_paginate_offset_honours_limit(fake, config):
    fake.on('GET', '/p', {'values': [1, 2, 3], 'isLast': False})
    assert JiraClient(config).paginate_offset('/p', {}, limit=2) == [1, 2]


# -- health check ----------------------------------------------------------

def test_health_check_uses_myself_only(fake, config):
    fake.on('GET', '/rest/api/3/myself', {'accountId': 'a1', 'displayName': 'Me'})
    assert JiraV2().check_health(config) is True
    assert fake.paths() == [('GET', '/rest/api/3/myself')]


def test_health_check_needs_an_identified_user(fake, config):
    fake.on('GET', '/rest/api/3/myself', {})
    with pytest.raises(ConnectorError, match='did not identify'):
        check_health(config)


def test_health_check_surfaces_the_http_error(fake, config):
    fake.on('GET', '/rest/api/3/myself', None, status=401)
    with pytest.raises(ConnectorError, match='HTTP 401'):
        JiraV2().check_health(config)


def test_health_check_on_a_site_with_no_projects_still_passes(fake, config):
    """The v1 connector failed here with 'make sure you have at least one JIRA project'."""
    fake.on('GET', '/rest/api/3/myself', {'accountId': 'a1'})
    assert JiraV2().check_health(config) is True


def test_unexpected_exceptions_are_wrapped(config, monkeypatch):
    import jirav2.connector as connector_module
    monkeypatch.setitem(connector_module.operations, 'list_fields', lambda c, p: 1 / 0)
    with pytest.raises(ConnectorError, match='list_fields failed'):
        JiraV2().execute(config, 'list_fields', {})


def test_unknown_operation_is_refused(config):
    with pytest.raises(ConnectorError, match='Unsupported operation'):
        JiraV2().execute(config, 'nope', {})


def test_basic_header_value_is_what_atlassian_expects(fake, config):
    """requests builds the header from auth=; assert the pair would encode correctly."""
    fake.on('GET', '/x', {})
    JiraClient(config).request('GET', '/x')
    user, token = fake.only().auth
    assert base64.b64encode(('%s:%s' % (user, token)).encode()).decode() == \
        base64.b64encode(b'me@example.com:tok').decode()

"""Offline tests for the HashiCorp Vault KV connector - no Vault server,
just the loopback fake from conftest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import make_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultkv.operations as ops  # noqa: E402
from vaultkv.connections import ConnectorError, parse_secret_data  # noqa: E402


def test_health(fake, config):
    result = ops.get_health(config, {})
    assert result == {'valid': True, 'policies': ['lab-lab'],
                      'display_name': 'root'}


def test_health_bad_token(fake, config):
    with pytest.raises(ConnectorError):
        make_client(config, token='bad').health()


def test_read_secret_latest(fake, config):
    result = ops.read_secret(config, {'path': 'lab/ai'})
    assert result['version'] == 2
    assert result['data']['api_key'] == 'faig_old'
    assert result['metadata']['version'] == 2


def test_read_secret_missing_raises(fake, config):
    with pytest.raises(ConnectorError):
        ops.read_secret(config, {'path': 'nope/missing'})


def test_write_secret_bumps_version(fake, config):
    result = ops.write_secret(
        config, {'path': 'lab/ai',
                 'secret_data': '{"api_key": "faig_new", "base_url": "https://gw"}'})
    assert result['version'] == 4
    back = ops.read_secret(config, {'path': 'lab/ai'})
    assert back['data']['api_key'] == 'faig_new'
    assert back['version'] == 4


def test_write_secret_replaces_all_fields(fake, config):
    ops.write_secret(config, {'path': 'lab/ai',
                              'secret_data': {'api_key': 'faig_only'}})
    back = ops.read_secret(config, {'path': 'lab/ai'})
    assert back['data'] == {'api_key': 'faig_only'}


def test_write_secret_accepts_dict_and_pairs(fake, config):
    ops.write_secret(config, {'path': 'x/y', 'secret_data': {'a': '1'}})
    assert ops.read_secret(config, {'path': 'x/y'})['data'] == {'a': '1'}
    ops.write_secret(config, {'path': 'x/y', 'secret_data': 'b=2'})
    assert ops.read_secret(config, {'path': 'x/y'})['data'] == {'b': '2'}


def test_list_secrets(fake, config):
    ops.write_secret(config, {'path': 'lab/other', 'secret_data': {'a': '1'}})
    result = ops.list_secrets(config, {'path': 'lab'})
    assert set(result['keys']) == {'ai', 'other'}


def test_delete_secret(fake, config):
    assert ops.delete_secret(config, {'path': 'lab/ai'}) == {
        'path': 'lab/ai', 'deleted': True}
    with pytest.raises(ConnectorError):
        ops.read_secret(config, {'path': 'lab/ai'})


def test_read_specific_version(fake, config):
    result = ops.read_secret(config, {'path': 'lab/ai', 'version': '2'})
    assert result['version'] == 2
    with pytest.raises(ConnectorError):
        ops.read_secret(config, {'path': 'lab/ai', 'version': '1'})


def test_parse_secret_data_variants():
    assert parse_secret_data({'a': 1}) == {'a': 1}
    assert parse_secret_data('{"a": "x"}') == {'a': 'x'}
    assert parse_secret_data('k1=v1,k2=v2') == {'k1': 'v1', 'k2': 'v2'}
    with pytest.raises(ConnectorError):
        parse_secret_data('just-a-string')


def test_operations_dispatch_table_covers_info_json():
    repo = Path(__file__).resolve().parent.parent
    info = json.load(open(repo / 'info.json'))
    for entry in info['operations']:
        assert entry['operation'] in ops.operations, entry['operation']


def test_required_params_rejected(fake, config):
    with pytest.raises(ValueError):
        ops.read_secret(config, {'path': ''})
    with pytest.raises(ValueError):
        ops.write_secret(config, {'path': 'a', 'secret_data': ''})
    with pytest.raises(ValueError):
        ops.delete_secret(config, {'path': None})


# - generic API call ------------------------------------------------------

def test_execute_api_request_reads_with_the_token(fake, config):
    out = ops.execute_api_request(config, {'endpoint': '/v1/secret/data/lab/ai'})
    assert out['data']['data']['base_url'] == 'https://gw'


def test_execute_api_request_adds_v1_and_sends_a_body(fake, config):
    ops.execute_api_request(config, {'endpoint': 'secret/data/new/one', 'method': 'POST',
                                     'request_body': '{"data": {"k": "v"}}'})
    assert fake.store['new/one']['value'] == {'k': 'v'}


def test_execute_api_request_list_verb_and_delete(fake, config):
    assert ops.execute_api_request(config, {'endpoint': '/v1/secret/metadata/', 'method': 'LIST'})['data']['keys'] == ['lab/']
    ops.execute_api_request(config, {'endpoint': '/v1/secret/data/lab/ai', 'method': 'DELETE'})
    assert 'lab/ai' not in fake.store


def test_execute_api_request_passes_query_params(fake, config):
    out = ops.execute_api_request(config, {'endpoint': '/v1/secret/data/lab/ai', 'query_params': {'version': 2}})
    assert out['data']['metadata']['version'] == 2


def test_execute_api_request_uses_the_configured_token(fake, config):
    with pytest.raises(ConnectorError, match='HTTP 403'):
        ops.execute_api_request(dict(config, token='bad'), {'endpoint': '/v1/secret/data/lab/ai'})


@pytest.mark.parametrize('endpoint', [
    'https://evil.example.com/v1/x', '//evil.example.com/v1/x', 'ftp://x/y', '/v1/../etc',
    '/v1/%2e%2e/etc', '/v1/%252e%252e/etc', '/v1/..%5cetc'])
def test_execute_api_request_refuses_anything_that_could_send_the_token_elsewhere(fake, config, endpoint):
    with pytest.raises(ConnectorError, match='path on the configured server'):
        ops.execute_api_request(config, {'endpoint': endpoint})


def test_execute_api_request_validates_input(fake, config):
    with pytest.raises(ConnectorError, match='Endpoint is required'):
        ops.execute_api_request(config, {})
    with pytest.raises(ConnectorError, match='Method must be'):
        ops.execute_api_request(config, {'endpoint': '/v1/sys/health', 'method': 'TRACE'})
    with pytest.raises(ConnectorError, match='valid JSON'):
        ops.execute_api_request(config, {'endpoint': '/v1/sys/health', 'request_body': '{nope'})
    with pytest.raises(ConnectorError, match='JSON object'):
        ops.execute_api_request(config, {'endpoint': '/v1/sys/health', 'request_body': '[1]'})


def test_execute_api_request_does_not_follow_redirects(fake, config, monkeypatch):
    import requests

    class Redirect(object):
        status_code, content, text, headers = 302, b'', '', {'Location': 'http://other.invalid/x'}

    monkeypatch.setattr(requests.Session, 'request', lambda self, *a, **k: (_ for _ in ()).throw(AssertionError) if k.get('allow_redirects', True) else Redirect())
    with pytest.raises(ConnectorError, match='redirect'):
        ops.execute_api_request(config, {'endpoint': '/v1/sys/health'})

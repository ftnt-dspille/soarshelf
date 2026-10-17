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


# --- patch, metadata and find-by-metadata (1.2.0) ---------------------------

def _seed(fake, path, tag=None, value=None, deleted=False):
    fake.store[path] = {'value': value or {'api_key': 'faig_x', 'base_url': 'https://gw'},
                        'version': 1}
    if tag:
        fake.metadata[path] = {'faig_key_id': tag, 'owner': 'ai-team'}
    if deleted:
        fake.deleted.add(path)


def test_patch_secret_changes_only_the_given_fields(fake, config):
    result = ops.patch_secret(config, {'path': 'lab/ai', 'secret_data': '{"api_key": "faig_new"}'})
    assert result['fields'] == ['api_key'] and result['attempts'] == 1
    assert fake.store['lab/ai']['value'] == {'api_key': 'faig_new', 'base_url': 'https://gw',
                                             'model': 'gpt-x'}
    assert result['version'] == fake.store['lab/ai']['version']


def test_patch_secret_sends_a_merge_patch_and_never_reads(fake, config):
    ops.patch_secret(config, {'path': 'lab/ai', 'secret_data': {'api_key': 'faig_new'}})
    assert fake.requests == [('PATCH', '/v1/secret/data/lab/ai')]


def test_patch_secret_retries_a_server_error(fake, config, monkeypatch):
    monkeypatch.setattr('vaultkv.connections.time.sleep', lambda s: None)
    fake.patch_failures = 2
    result = ops.patch_secret(config, {'path': 'lab/ai', 'secret_data': {'api_key': 'faig_new'}})
    assert result['attempts'] == 3
    assert fake.store['lab/ai']['value']['api_key'] == 'faig_new'


def test_patch_secret_gives_up_after_the_retries(fake, config, monkeypatch):
    monkeypatch.setattr('vaultkv.connections.time.sleep', lambda s: None)
    fake.patch_failures = 5
    with pytest.raises(ConnectorError, match='HTTP 503'):
        ops.patch_secret(config, {'path': 'lab/ai', 'secret_data': {'api_key': 'n'}, 'retries': '2'})
    assert len([r for r in fake.requests if r[0] == 'PATCH']) == 3


def test_patch_secret_does_not_retry_a_refusal_or_create_a_secret(fake, config, monkeypatch):
    monkeypatch.setattr('vaultkv.connections.time.sleep', lambda s: pytest.fail('retried'))
    with pytest.raises(ConnectorError, match='only changes an existing secret'):
        ops.patch_secret(config, {'path': 'nope/missing', 'secret_data': {'api_key': 'n'}})
    assert 'nope/missing' not in fake.store
    with pytest.raises(ConnectorError, match='HTTP 403'):
        make_client(config, token='bad').patch_secret('lab/ai', {'api_key': 'n'})


def test_read_metadata_never_returns_the_value(fake, config):
    _seed(fake, 'apps/chat', tag='k1')
    md = ops.read_metadata(config, {'path': 'apps/chat'})
    assert md['custom_metadata'] == {'faig_key_id': 'k1', 'owner': 'ai-team'}
    assert md['current_version'] == 1 and md['current_deleted'] is False
    assert 'faig_x' not in json.dumps(md)


def test_patch_metadata_merges_and_removes_tags(fake, config):
    _seed(fake, 'apps/chat', tag='k1')
    md = ops.patch_metadata(config, {'path': 'apps/chat',
                                     'custom_metadata': '{"faig_rotated_at": "now", "owner": null}'})
    assert md['custom_metadata'] == {'faig_key_id': 'k1', 'faig_rotated_at': 'now'}
    assert fake.store['apps/chat']['version'] == 1          # metadata is not a new version


def test_patch_metadata_requires_an_object(fake, config):
    _seed(fake, 'apps/chat')
    for bad in ('', '[1]', 'nope'):
        with pytest.raises((ConnectorError, ValueError)):
            ops.patch_metadata(config, {'path': 'apps/chat', 'custom_metadata': bad})


def test_find_by_metadata_walks_sub_folders_and_reads_no_values(fake, config):
    _seed(fake, 'apps/chat', tag='k1')
    _seed(fake, 'apps/team-a/bot', tag='k2')
    _seed(fake, 'apps/team-a/deep/agent', tag='k3')
    _seed(fake, 'apps/untagged')
    _seed(fake, 'other/outside', tag='k9')
    result = ops.find_secrets_by_metadata(config, {'path': 'apps', 'metadata_key': 'faig_key_id'})
    assert result['scanned'] == 4
    assert result['by_value'] == {'k1': ['apps/chat'], 'k2': ['apps/team-a/bot'],
                                  'k3': ['apps/team-a/deep/agent']}
    assert result['untagged'] == ['apps/untagged']
    assert 'matches' not in result
    assert not [r for r in fake.requests if '/data/' in r[1]]


def test_find_by_metadata_sorts_values_into_matches_unmatched_conflicts(fake, config):
    _seed(fake, 'apps/chat', tag='k1')
    _seed(fake, 'apps/copy-a', tag='k2')
    _seed(fake, 'apps/copy-b', tag='k2')
    _seed(fake, 'apps/gone', tag='k4', deleted=True)
    result = ops.find_secrets_by_metadata(config, {
        'path': 'apps', 'metadata_key': 'faig_key_id', 'values': '["k1", "k2", "k3", "k4", "k1"]'})
    assert result['matches'] == [{'value': 'k1', 'path': 'apps/chat'}]
    assert result['unmatched'] == ['k3', 'k4']          # a deleted secret is not a match
    assert result['conflicts'] == [{'value': 'k2', 'paths': ['apps/copy-a', 'apps/copy-b']}]
    assert result['deleted'] == ['apps/gone']


def test_find_by_metadata_empty_values_and_missing_prefix(fake, config):
    result = ops.find_secrets_by_metadata(config, {'path': 'nothing-here', 'metadata_key': 'faig_key_id',
                                                   'values': []})
    assert result['scanned'] == 0 and result['matches'] == [] and result['unmatched'] == []
    result = ops.find_secrets_by_metadata(config, {'metadata_key': 'faig_key_id', 'values': 'a, b'})
    assert result['unmatched'] == ['a', 'b']


def test_find_by_metadata_caps_the_walk(fake, config):
    for i in range(5):
        _seed(fake, 'apps/s{0}'.format(i))
    with pytest.raises(ConnectorError, match='More than 3 secrets'):
        ops.find_secrets_by_metadata(config, {'path': 'apps', 'metadata_key': 'k', 'max_paths': '3'})
    with pytest.raises(ConnectorError, match='between 1 and 10000'):
        ops.find_secrets_by_metadata(config, {'path': 'apps', 'metadata_key': 'k', 'max_paths': '0'})


def test_write_create_only_refuses_an_existing_secret(fake, config):
    with pytest.raises(ConnectorError, match='already exists at lab/ai'):
        ops.write_secret(config, {'path': 'lab/ai', 'secret_data': {'api_key': 'n'}, 'create_only': True})
    assert fake.store['lab/ai']['value']['api_key'] == 'faig_old'
    wrote = ops.write_secret(config, {'path': 'apps/new', 'secret_data': {'api_key': 'n'},
                                      'create_only': 'true'})
    assert fake.store['apps/new']['version'] == wrote['version']


def test_read_metadata_missing_ok(fake, config):
    assert ops.read_metadata(config, {'path': 'apps/none', 'missing_ok': True})['exists'] is False
    assert ops.read_metadata(config, {'path': 'lab/ai', 'missing_ok': True})['exists'] is True
    with pytest.raises(ConnectorError):
        ops.read_metadata(config, {'path': 'apps/none'})


BAD_PATHS = ['../sys/policies/acl/x', 'lab/../../sys/mounts', 'lab/./ai', '..', '%2e%2e/sys/mounts',
             '%252e%252e/sys', 'lab\\..\\sys', 'lab/ai?list=true', 'lab/ai#x']


@pytest.mark.parametrize('bad', BAD_PATHS)
def test_a_secret_path_cannot_leave_the_mount(fake, config, bad):
    """Paths come from playbook input (an onboarding API body, a folder to search)."""
    calls = [
        lambda: ops.read_secret(config, {'path': bad}),
        lambda: ops.write_secret(config, {'path': bad, 'secret_data': {'a': 'b'}}),
        lambda: ops.patch_secret(config, {'path': bad, 'secret_data': {'a': 'b'}, 'retries': '0'}),
        lambda: ops.read_metadata(config, {'path': bad, 'missing_ok': True}),
        lambda: ops.patch_metadata(config, {'path': bad, 'custom_metadata': {'a': 'b'}}),
        lambda: ops.find_secrets_by_metadata(config, {'path': bad, 'metadata_key': 'k'}),
        lambda: ops.list_secrets(config, {'path': bad}),
        lambda: ops.delete_secret(config, {'path': bad}),
    ]
    for call in calls:
        with pytest.raises(ConnectorError, match='is not allowed'):
            call()
    assert fake.requests == []


def test_ordinary_paths_still_work(fake, config):
    _seed(fake, 'apps/team-a/my.app-1', tag='k1')
    assert ops.read_metadata(config, {'path': '/apps/team-a/my.app-1'})['custom_metadata']['faig_key_id'] == 'k1'
    assert ops.find_secrets_by_metadata(config, {'path': 'apps/', 'metadata_key': 'faig_key_id'})['scanned'] == 1

"""Live tests for the HashiCorp Vault KV connector against a real Vault.
Opt-in: requires VAULT_ADDR / VAULT_TOKEN (copy tests/.env.example to
tests/.env, or reuse ../fortinet-fortiaigate/tests/.env). Mutating tests
only touch a disposable lab/connector-test path."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from conftest import make_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultkv.operations as ops  # noqa: E402

pytestmark = pytest.mark.live


def _load_env(*paths):
    values = {}
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            values.setdefault(key.strip(), value)
    return values


HERE = Path(__file__).resolve().parent
ENV = _load_env(HERE / '.env',
                HERE.parent.parent / 'fortinet-fortiaigate' / 'tests' / '.env')

TEST_PATH = 'lab/connector-test'


def _env(name):
    return os.environ.get(name) or ENV.get(name)


def _config():
    if not _env('VAULT_ADDR') or not _env('VAULT_TOKEN'):
        pytest.skip('live Vault credentials not configured (tests/.env)')
    return {
        'server': _env('VAULT_ADDR'),
        'token': _env('VAULT_TOKEN'),
        'mount': _env('VAULT_MOUNT') or 'secret',
        'verify_ssl': False,
        'timeout': '30',
    }


def test_live_health():
    result = ops.get_health(_config(), {})
    assert result['valid'] is True
    assert result['policies']


def test_live_read_lab_key():
    path = _env('VAULT_SECRET_PATH') or ''
    if not path:
        pytest.skip('no VAULT_SECRET_PATH configured for the lab secret')
    result = ops.read_secret(_config(), {'path': path.replace('secret/', '', 1)})
    assert result['version'] >= 1
    assert result['data'].get('api_key', '').startswith('faig_')


def test_live_write_read_delete_disposable():
    config = _config()
    wrote = ops.write_secret(config, {'path': TEST_PATH,
                                       'secret_data': '{"probe": "1"}'})
    assert wrote['version'] >= 1
    back = ops.read_secret(config, {'path': TEST_PATH})
    assert back['data'] == {'probe': '1'}
    assert back['version'] == wrote['version']
    ops.delete_secret(config, {'path': TEST_PATH})


def test_live_list_secrets():
    result = ops.list_secrets(_config(), {'path': 'lab'})
    assert isinstance(result['keys'], list)


# --- patch, metadata and find-by-metadata (1.2.0) ---------------------------
# Everything lives under its own top-level folder, so a walk never reaches a
# real secret, and the fixture removes every version and its metadata after.

TREE = 'connector-test-tree'
SEEDED = {
    TREE + '/chat': ('key-1', {'api_key': 'faig_one', 'base_url': 'https://keep.example/v1'}),
    TREE + '/team-a/bot': ('key-2', {'api_key': 'faig_two'}),
    TREE + '/team-a/deep/agent': ('key-3', {'api_key': 'faig_three'}),
    TREE + '/copy-a': ('key-dup', {'api_key': 'faig_dup'}),
    TREE + '/copy-b': ('key-dup', {'api_key': 'faig_dup'}),
    TREE + '/untagged': (None, {'api_key': 'faig_none'}),
    TREE + '/gone': ('key-gone', {'api_key': 'faig_gone'}),
}


@pytest.fixture()
def tree():
    config = _config()
    client = make_client(config)
    for path, (tag, value) in SEEDED.items():
        client.write_secret(path, value)
        if tag:
            client.patch_metadata(path, {'faig_key_id': tag})
    client.delete_secret(TREE + '/gone')               # soft-deletes its current version
    yield config
    for path in client.walk(TREE):
        client.raw('DELETE', '/v1/{0}/metadata/{1}'.format(client.mount, path))
    assert client.walk(TREE) == []


def test_live_find_by_metadata(tree):
    result = ops.find_secrets_by_metadata(tree, {
        'path': TREE, 'metadata_key': 'faig_key_id',
        'values': '["key-1", "key-3", "key-dup", "key-gone", "key-missing"]'})
    assert result['scanned'] == len(SEEDED)
    assert result['untagged'] == [TREE + '/untagged']
    assert result['deleted'] == [TREE + '/gone']
    assert result['matches'] == [{'value': 'key-1', 'path': TREE + '/chat'},
                                 {'value': 'key-3', 'path': TREE + '/team-a/deep/agent'}]
    assert result['unmatched'] == ['key-gone', 'key-missing']
    assert result['conflicts'] == [{'value': 'key-dup', 'paths': [TREE + '/copy-a', TREE + '/copy-b']}]
    assert 'faig_one' not in str(result)                  # no secret value came back


def test_live_patch_secret_keeps_other_fields(tree):
    before = ops.read_secret(tree, {'path': TREE + '/chat'})
    result = ops.patch_secret(tree, {'path': TREE + '/chat', 'secret_data': '{"api_key": "faig_new"}'})
    after = ops.read_secret(tree, {'path': TREE + '/chat'})
    assert result['version'] == after['version'] == before['version'] + 1
    assert after['data'] == {'api_key': 'faig_new', 'base_url': 'https://keep.example/v1'}


def test_live_patch_secret_will_not_create(tree):
    with pytest.raises(ops.ConnectorError, match='only changes an existing secret'):
        ops.patch_secret(tree, {'path': TREE + '/does-not-exist', 'secret_data': {'api_key': 'x'},
                                'retries': '0'})
    assert TREE + '/does-not-exist' not in make_client(tree).walk(TREE)


def test_live_patch_metadata_merges_and_removes(tree):
    md = ops.patch_metadata(tree, {'path': TREE + '/chat',
                                   'custom_metadata': '{"faig_rotated_at": "2000-01-01T00:00:00Z"}'})
    assert md['custom_metadata'] == {'faig_key_id': 'key-1', 'faig_rotated_at': '2000-01-01T00:00:00Z'}
    md = ops.patch_metadata(tree, {'path': TREE + '/chat', 'custom_metadata': '{"faig_rotated_at": null}'})
    assert md['custom_metadata'] == {'faig_key_id': 'key-1'}
    assert ops.read_metadata(tree, {'path': TREE + '/chat'})['current_version'] == 1


POLICY = 'connector-test-rotator'
POLICY_HCL = '''
path "{mount}/metadata/{tree}/*" {{ capabilities = ["read", "list", "patch"] }}
path "{mount}/metadata/{tree}"   {{ capabilities = ["list"] }}
path "{mount}/data/{tree}/*"     {{ capabilities = ["patch"] }}
'''


@pytest.fixture()
def rotator(tree):
    """A token with only the rotation policy: find and update, never read."""
    admin = make_client(tree)
    admin.raw('PUT', '/v1/sys/policies/acl/' + POLICY,
              body={'policy': POLICY_HCL.format(mount=admin.mount, tree=TREE)})
    token = admin.raw('POST', '/v1/auth/token/create',
                      body={'policies': [POLICY], 'ttl': '10m'})['auth']['client_token']
    try:
        yield dict(tree, token=token)
    finally:
        admin.raw('POST', '/v1/auth/token/revoke', body={'token': token})
        admin.raw('DELETE', '/v1/sys/policies/acl/' + POLICY)


def test_live_rotator_token_finds_and_updates_but_cannot_read(rotator):
    found = ops.find_secrets_by_metadata(rotator, {'path': TREE, 'metadata_key': 'faig_key_id',
                                                   'values': ['key-1']})
    assert found['matches'] == [{'value': 'key-1', 'path': TREE + '/chat'}]
    ops.patch_secret(rotator, {'path': TREE + '/chat', 'secret_data': {'api_key': 'faig_rotated'}})
    ops.patch_metadata(rotator, {'path': TREE + '/chat', 'custom_metadata': {'faig_rotated_at': 'now'}})
    with pytest.raises(ops.ConnectorError, match='HTTP 403'):
        ops.read_secret(rotator, {'path': TREE + '/chat'})
    with pytest.raises(ops.ConnectorError, match='HTTP 403'):
        ops.write_secret(rotator, {'path': TREE + '/chat', 'secret_data': {'api_key': 'overwrite'}})
    with pytest.raises(ops.ConnectorError, match='HTTP 403'):
        ops.find_secrets_by_metadata(rotator, {'path': 'lab', 'metadata_key': 'faig_key_id'})
    data = ops.read_secret(dict(rotator, token=_config()['token']), {'path': TREE + '/chat'})['data']
    assert data == {'api_key': 'faig_rotated', 'base_url': 'https://keep.example/v1'}


def test_live_create_only_and_missing_ok(tree):
    path = TREE + '/fresh'
    assert ops.read_metadata(tree, {'path': path, 'missing_ok': True})['exists'] is False
    ops.write_secret(tree, {'path': path, 'secret_data': {'api_key': 'faig_first'}, 'create_only': True})
    with pytest.raises(ops.ConnectorError, match='already exists'):
        ops.write_secret(tree, {'path': path, 'secret_data': {'api_key': 'faig_second'}, 'create_only': True})
    assert ops.read_secret(tree, {'path': path})['data'] == {'api_key': 'faig_first'}
    assert ops.read_metadata(tree, {'path': path, 'missing_ok': True})['exists'] is True


@pytest.mark.parametrize('bad', ['../sys/mounts', '%2e%2e/sys/policies/acl', 'lab/ai?list=true'])
def test_live_a_secret_path_cannot_leave_the_mount(bad):
    with pytest.raises(ops.ConnectorError, match='is not allowed'):
        ops.read_secret(_config(), {'path': bad})
    with pytest.raises(ops.ConnectorError, match='is not allowed'):
        ops.write_secret(_config(), {'path': bad, 'secret_data': {'a': 'b'}, 'create_only': True})

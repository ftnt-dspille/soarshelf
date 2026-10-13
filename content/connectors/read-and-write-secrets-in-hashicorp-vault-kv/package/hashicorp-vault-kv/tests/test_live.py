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

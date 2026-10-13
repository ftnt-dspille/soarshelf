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

"""info.json is consistent with the code and with what the FortiSOAR step editor needs."""
import json
import re
import runpy
from pathlib import Path

import pytest

from jirav2.operations import operations

ROOT = Path(__file__).resolve().parent.parent
INFO = json.load(open(ROOT / 'info.json'))
OPS = {o['operation']: o for o in INFO['operations']}
TYPES = {'text', 'textarea', 'integer', 'checkbox', 'select', 'json', 'datetime', 'password', 'multiselect'}


def test_info_json_is_what_the_generator_produces():
    generated = runpy.run_path(str(ROOT / 'scripts' / 'gen_info.py'))['INFO']
    assert generated == INFO, 'info.json is stale: run python3 scripts/gen_info.py'


def test_info_operations_match_the_code():
    assert set(OPS) == set(operations)
    assert len(INFO['operations']) == len(OPS), 'duplicate operation in info.json'


def test_connector_identity():
    assert INFO['name'] == 'jirav2'
    assert re.match(r'^\d+\.\d+\.\d+$', INFO['version'])
    assert (ROOT / 'images' / INFO['icon_small_name']).exists()
    assert (ROOT / 'images' / INFO['icon_large_name']).exists()


def test_release_notes_cover_the_current_version():
    assert '#### %s' % INFO['version'] in (ROOT / 'release_notes.md').read_text()


@pytest.mark.parametrize('name', sorted(OPS))
def test_operation_definition_is_complete(name):
    op = OPS[name]
    assert op['title'] and op['description'] and op['annotation'] == name
    assert op['enabled'] is True
    seen = set()
    for param in op['parameters']:
        assert param['name'] not in seen, 'duplicate parameter %s' % param['name']
        seen.add(param['name'])
        assert param['type'] in TYPES, param
        assert param['title'] and param['description']
        if param['type'] == 'select' and not param.get('apiOperation'):
            assert param.get('options'), '%s.%s is a select with no options' % (name, param['name'])
            if 'value' in param:
                assert param['value'] in param['options']
        if param.get('apiOperation'):
            assert param['apiOperation'] in OPS, param
            assert OPS[param['apiOperation']].get('visible') is False
            assert not OPS[param['apiOperation']]['parameters'], 'populators receive only the config'


@pytest.mark.parametrize('name', sorted(OPS))
def test_every_required_parameter_is_enforced_by_the_code(name, config, monkeypatch):
    """Leaving a required parameter out must fail fast, before any request."""
    import jirav2.client as client_module
    from conftest import FakeJira
    fake = FakeJira()
    monkeypatch.setattr(client_module.requests, 'request', fake.request)
    required = [p['name'] for p in OPS[name]['parameters'] if p.get('required')]
    for missing in required:
        params = {p: 'x' for p in required if p != missing}
        with pytest.raises(client_module.ConnectorError):
            operations[name](config, params)
        assert not fake.calls, '%s.%s: made a request without a required parameter' % (name, missing)


def test_configuration_fields():
    fields = {f['name']: f for f in INFO['configuration']['fields']}
    assert {'server_url', 'auth_type', 'token', 'scoped', 'cloud_id', 'timeout', 'verify_ssl'} <= set(fields)
    assert fields['token']['type'] == 'password'
    assert fields['auth_type']['value'] in fields['auth_type']['options']


def test_username_only_appears_for_basic_authentication():
    """onchange: the select's option values key the fields shown under it."""
    auth = next(f for f in INFO['configuration']['fields'] if f['name'] == 'auth_type')
    assert set(auth['onchange']) == set(auth['options'])
    basic = auth['onchange']['Basic (Email + API Token)']
    assert [f['name'] for f in basic] == ['username'] and basic[0]['required'] is True
    assert auth['onchange']['Bearer (OAuth 2.0 Access Token)'] == []
    assert 'username' not in [f['name'] for f in INFO['configuration']['fields']]

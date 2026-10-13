"""The scope registry matches the code, so the README permission tables are true."""
import json
from pathlib import Path

from jirav2.operations import operations
from jirav2.scope_data import ENDPOINT_SCOPES
from jirav2.scopes import HEALTH_CHECK, OPERATION_ENDPOINTS, POPULATORS

ROOT = Path(__file__).resolve().parent.parent


def test_every_operation_declares_its_endpoints():
    assert set(OPERATION_ENDPOINTS) == set(operations)


def test_every_declared_endpoint_has_scope_data():
    declared = {key for keys in OPERATION_ENDPOINTS.values() for key in keys or []} | set(HEALTH_CHECK)
    assert declared <= set(ENDPOINT_SCOPES), declared - set(ENDPOINT_SCOPES)


def test_no_scope_data_is_orphaned():
    declared = {key for keys in OPERATION_ENDPOINTS.values() for key in keys or []} | set(HEALTH_CHECK)
    assert set(ENDPOINT_SCOPES) == declared, set(ENDPOINT_SCOPES) - declared


def test_every_endpoint_has_a_classic_or_granular_scope_or_is_documented_as_having_none():
    for key, data in ENDPOINT_SCOPES.items():
        assert data['classic'] or data['granular'], key


def test_priorities_is_the_one_endpoint_without_granular_scopes():
    """The README warns about it; if Atlassian adds granular scopes this fails so the note is dropped."""
    assert [k for k, d in ENDPOINT_SCOPES.items() if not d['granular']] == ['GET /rest/api/3/priority/search']


def test_scope_strings_look_like_scopes():
    for key, data in ENDPOINT_SCOPES.items():
        for scope in data['classic'] + data['granular']:
            assert scope.islower() and ' ' not in scope, (key, scope)


def test_health_check_calls_only_myself():
    assert HEALTH_CHECK == ['GET /rest/api/3/myself']


def test_populators_are_hidden_operations_and_nothing_else_is():
    info = json.load(open(ROOT / 'info.json'))
    hidden = {o['operation'] for o in info['operations'] if o.get('visible') is False}
    assert hidden == set(POPULATORS)


def test_token_plan_fits_the_form_limit_and_covers_every_action():
    """Atlassian's token form caps a token at 50 scopes; the plan must still reach every action."""
    from jirav2.scopes import TOKEN_SCOPE_LIMIT, pack_tokens
    for family in ('granular', 'classic'):
        tokens = pack_tokens(family)
        assert all(len(t['scopes']) <= TOKEN_SCOPE_LIMIT for t in tokens), family
        covered = set().union(*[set(t['actions']) for t in tokens])
        reachable = {op for op, keys in OPERATION_ENDPOINTS.items() if keys}
        missing = reachable - covered
        # The one action with no granular scope at all cannot be covered by a granular token.
        assert missing == ({'list_priorities'} if family == 'granular' else set()), (family, missing)


def test_everything_does_not_fit_one_granular_token():
    """Why a plan is needed at all: if this starts failing, one token could do it and the plan can go."""
    from jirav2.scopes import TOKEN_SCOPE_LIMIT, scope_sets
    assert len(scope_sets()['all']['granular']) > TOKEN_SCOPE_LIMIT

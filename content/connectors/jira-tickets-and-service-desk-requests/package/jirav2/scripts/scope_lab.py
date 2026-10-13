#!/usr/bin/env python3
"""Print the scopes to tick when creating a test token at id.atlassian.com.

    python3 scripts/scope_lab.py                 # the three standard sets
    python3 scripts/scope_lab.py create_ticket   # exactly what one action needs
    python3 scripts/scope_lab.py --json NAME ... # a ready scope_tokens.json entry per action
    python3 scripts/scope_lab.py --plan [classic]# fewest tokens (50-scope cap) that reach every action

Atlassian has no API for minting tokens, so each is made by hand in the token
form (API token with scopes > choose the Jira / Jira Service Management app >
tick the scopes below). Then add it to tests/scope_tokens.json.
"""
import json
import os
import sys
import types

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
_package = types.ModuleType('jirav2')
_package.__path__ = [ROOT]
sys.modules['jirav2'] = _package

from jirav2.scope_data import ENDPOINT_SCOPES  # noqa: E402
from jirav2.scopes import OPERATION_ENDPOINTS, pack_tokens, scope_sets  # noqa: E402


def action_scopes(operation):
    keys = OPERATION_ENDPOINTS.get(operation)
    if keys is None:
        sys.exit('%s: unknown action (or the generic call, whose scopes depend on the endpoint)' % operation)
    classic, granular = set(), set()
    for key in keys:
        classic.update(ENDPOINT_SCOPES[key]['classic'])
        granular.update(ENDPOINT_SCOPES[key]['granular'])
    return sorted(classic), sorted(granular)


def main(argv):
    if '--plan' in argv:
        family = 'classic' if 'classic' in argv else 'granular'
        for token in pack_tokens(family):
            print('== %s (%d scopes, %d actions) ==' % (token['name'], len(token['scopes']), len(token['actions'])))
            print('  scopes : %s' % ', '.join(token['scopes']))
            print('  actions: %s' % ', '.join(token['actions']))
        return
    as_json = '--json' in argv
    names = [a for a in argv if not a.startswith('--')]
    if not names:
        for name, sets in scope_sets().items():
            print('== %s ==' % name)
            print('  granular: %s' % ', '.join(sorted(sets['granular'])))
            print('  classic : %s' % ', '.join(sorted(sets['classic'])))
        return
    entries = []
    for name in names:
        classic, granular = action_scopes(name)
        if as_json:
            entries.append({'name': name, 'family': 'granular', 'scopes': granular, 'token': '<token>'})
        else:
            print('== %s ==' % name)
            print('  granular: %s' % (', '.join(granular) or '(none: classic only)'))
            print('  classic : %s' % ', '.join(classic))
    if as_json:
        print(json.dumps(entries, indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])

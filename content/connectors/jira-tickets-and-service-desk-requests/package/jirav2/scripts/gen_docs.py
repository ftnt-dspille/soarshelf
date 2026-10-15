#!/usr/bin/env python3
"""Regenerate the permission tables inside README.md.

    python3 scripts/gen_docs.py          # rewrite README.md in place
    python3 scripts/gen_docs.py --check  # exit 1 if README.md is out of date

Everything between <!-- BEGIN GENERATED --> and <!-- END GENERATED --> comes
from info.json (titles), scopes.py (which endpoints an operation calls) and
scope_data.py (Atlassian's scopes for each endpoint). tests/test_docs.py runs
--check, so the README cannot drift from the code.
"""
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))

# The checkout directory may have any name; register it as the package `jirav2`.
_package = types.ModuleType('jirav2')
_package.__path__ = [ROOT]
sys.modules['jirav2'] = _package

from jirav2.scope_data import ENDPOINT_SCOPES  # noqa: E402
from jirav2.scopes import HEALTH_CHECK, OPERATION_ENDPOINTS, POPULATORS, scope_sets  # noqa: E402

BEGIN = '<!-- BEGIN GENERATED -->'
END = '<!-- END GENERATED -->'


def code(items):
    return ', '.join('`%s`' % i for i in items) if items else '-'


def union(operation, field):
    found = set()
    for key in OPERATION_ENDPOINTS[operation] or []:
        found.update(ENDPOINT_SCOPES[key][field])
    return sorted(found)


def endpoints_text(operation):
    keys = OPERATION_ENDPOINTS[operation]
    if keys is None:
        return 'whatever endpoint you call'
    return '<br>'.join('`%s`' % k for k in keys)


def render():
    info = json.load(open(os.path.join(ROOT, 'info.json')))
    titles = {o['operation']: o['title'] for o in info['operations']}
    visible = [o['operation'] for o in info['operations'] if o.get('visible', True)]
    out = []

    def line(text=''):
        out.append(text)

    sets = scope_sets()
    health, health_classic = sets['health']['granular'], sets['health']['classic']
    read_granular, read_classic = sets['readonly']['granular'], sets['readonly']['classic']
    all_granular, all_classic = sets['all']['granular'], sets['all']['classic']

    line('### Scope sets to copy')
    line()
    line('Granular scopes are what the Atlassian token form lists; classic scopes are the older coarse ones. '
         'Use one family or the other for a token. Generated from Atlassian\'s OpenAPI specification.')
    line()
    line('| Need | Classic scopes | Granular scopes |')
    line('|---|---|---|')
    line('| **Health check only** | %s | %s |' % (code(sorted(health_classic)), code(sorted(health))))
    line('| **Read-only actions** (every Get/List) | %s | %s |' % (
        code(sorted(read_classic)), code(sorted(read_granular))))
    line('| **Everything in this connector** | %s | %s |' % (
        code(sorted(all_classic)), code(sorted(all_granular))))
    line()
    line('`List Priorities` calls `GET /rest/api/3/priority/search`, which Atlassian only offers under the '
         'classic `manage:jira-configuration` scope: no granular scope exists for it. With a granular-only '
         'token that one action returns a scope error; every other action is unaffected.')
    line()
    line('### Permissions by action')
    line()
    line('A scope lets the token call an endpoint; the account behind the token must *also* hold the Jira '
         'permission (Browse Projects, Create Issues, ...) in the project. The last table below lists the '
         'permission each endpoint needs.')
    line()
    line('| Action | Calls | Classic scope | Granular scopes |')
    line('|---|---|---|---|')
    for op in visible:
        if op == 'execute_api_request':
            line('| %s | %s | depends | depends |' % (titles[op], endpoints_text(op)))
            continue
        line('| %s | %s | %s | %s |' % (titles[op], endpoints_text(op), code(union(op, 'classic')),
                                        code(union(op, 'granular'))))
    line()
    line('### Dropdown helpers')
    line()
    line('Parameters that take a project, user, issue type, link type or service desk are dropdowns filled live '
         'by hidden `get_*_options` actions (the same `apiOperation` mechanism as the FortiAIGate connector). The editor can only show plain text, so each list holds names such as `Operations (OPS)`; the connector turns the picked name back into the key or id when the action runs, and an action can also be given the bare key or id. '
         'They call the same endpoints as the matching read actions, so they need no extra permission:')
    line()
    line('| Helper | Calls | Granular scopes |')
    line('|---|---|---|')
    for op in POPULATORS:
        line('| `%s` | %s | %s |' % (op, endpoints_text(op), code(union(op, 'granular'))))
    line()
    line('### Scopes and Jira permissions by endpoint')
    line()
    line('| Endpoint | Classic scope | Granular scopes | Jira permission the account needs |')
    line('|---|---|---|---|')
    used = set(HEALTH_CHECK)
    for keys in OPERATION_ENDPOINTS.values():
        used.update(keys or [])
    for key in sorted(used, key=lambda k: (k.split(' ', 1)[1], k)):
        data = ENDPOINT_SCOPES[key]
        line('| `%s` | %s | %s | %s |' % (key, code(data['classic']), code(data['granular']),
                                          data['permissions'] or 'Permission to access Jira.'))
    line()
    return '\n'.join(out)


def build(readme):
    start = readme.index(BEGIN) + len(BEGIN)
    end = readme.index(END)
    return readme[:start] + '\n\n' + render() + '\n' + readme[end:]


def main():
    path = os.path.join(ROOT, 'README.md')
    current = open(path).read()
    updated = build(current)
    if '--check' in sys.argv:
        if updated != current:
            print('README.md is out of date: run python3 scripts/gen_docs.py')
            sys.exit(1)
        print('README.md is current')
        return
    with open(path, 'w') as handle:
        handle.write(updated)
    print('README.md updated')


if __name__ == '__main__':
    main()

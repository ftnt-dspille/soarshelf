#!/usr/bin/env python3
"""Regenerate scope_data.py from Atlassian's published OpenAPI specs.

    python3 scripts/gen_scopes.py                 # download the specs
    python3 scripts/gen_scopes.py --spec-dir DIR  # use DIR/jira.json, DIR/jsm.json

scope_data.py is the single source for the permission tables in README.md and
for the scope assertions in tests/. Re-run this when Atlassian changes a scope,
then re-run scripts/gen_docs.py.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

SPECS = {
    'jira': 'https://dac-static.atlassian.com/cloud/jira/platform/swagger-v3.v3.json',
    'jsm': 'https://dac-static.atlassian.com/cloud/jira/service-desk/swagger.v3.json',
}

# (spec, method, path) for every endpoint the connector calls. Keep in step
# with OPERATION_ENDPOINTS in scopes.py; tests/test_scopes.py enforces it.
ENDPOINTS = [
    ('jira', 'get', '/rest/api/3/myself'),
    ('jira', 'post', '/rest/api/3/issue'),
    ('jira', 'get', '/rest/api/3/issue/{issueIdOrKey}'),
    ('jira', 'put', '/rest/api/3/issue/{issueIdOrKey}'),
    ('jira', 'delete', '/rest/api/3/issue/{issueIdOrKey}'),
    ('jira', 'get', '/rest/api/3/issue/{issueIdOrKey}/transitions'),
    ('jira', 'post', '/rest/api/3/issue/{issueIdOrKey}/transitions'),
    ('jira', 'put', '/rest/api/3/issue/{issueIdOrKey}/assignee'),
    ('jira', 'post', '/rest/api/3/issue/{issueIdOrKey}/comment'),
    ('jira', 'get', '/rest/api/3/issue/{issueIdOrKey}/comment'),
    ('jira', 'put', '/rest/api/3/issue/{issueIdOrKey}/comment/{id}'),
    ('jira', 'delete', '/rest/api/3/issue/{issueIdOrKey}/comment/{id}'),
    ('jira', 'post', '/rest/api/3/issue/{issueIdOrKey}/attachments'),
    ('jira', 'post', '/rest/api/3/issue/{issueIdOrKey}/remotelink'),
    ('jira', 'get', '/rest/api/3/issue/{issueIdOrKey}/changelog'),
    ('jira', 'post', '/rest/api/3/issue/{issueIdOrKey}/worklog'),
    ('jira', 'post', '/rest/api/3/issueLink'),
    ('jira', 'get', '/rest/api/3/issueLinkType'),
    ('jira', 'post', '/rest/api/3/search/jql'),
    ('jira', 'post', '/rest/api/3/jql/parse'),
    ('jira', 'get', '/rest/api/3/project/search'),
    ('jira', 'get', '/rest/api/3/project/{projectIdOrKey}'),
    ('jira', 'get', '/rest/api/3/user/search'),
    ('jira', 'get', '/rest/api/3/users/search'),
    ('jira', 'get', '/rest/api/3/user'),
    ('jira', 'get', '/rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes'),
    ('jira', 'get', '/rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}'),
    ('jira', 'get', '/rest/api/3/issuetype'),
    ('jira', 'get', '/rest/api/3/priority/search'),
    ('jira', 'get', '/rest/api/3/field'),
    ('jsm', 'get', '/rest/servicedeskapi/servicedesk'),
    ('jsm', 'get', '/rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype'),
    ('jsm', 'get', '/rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/field'),
    ('jsm', 'post', '/rest/servicedeskapi/request'),
    ('jsm', 'get', '/rest/servicedeskapi/request/{issueIdOrKey}'),
    ('jsm', 'post', '/rest/servicedeskapi/request/{issueIdOrKey}/comment'),
    ('jsm', 'get', '/rest/servicedeskapi/servicedesk/{serviceDeskId}/queue'),
    ('jsm', 'get', '/rest/servicedeskapi/servicedesk/{serviceDeskId}/queue/{queueId}/issue'),
]


def _is_granular(scopes):
    return any(s.count(':') >= 2 for s in scopes)


def _permissions(description):
    m = re.search(r'\*\*\[Permissions\]\([^)]*\) required:?\*\*(.*?)(?:\n\s*\n\*\*|\Z)',
                  description or '', re.S)
    if not m:
        return ''
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', m.group(1))
    text = re.sub(r'\n\s*\*\s+', '; ', text)
    text = re.sub(r'[*_`]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lstrip(':; ').strip()


def _load(spec_dir, name):
    if spec_dir:
        with open(os.path.join(spec_dir, name + '.json')) as fh:
            return json.load(fh)
    with urllib.request.urlopen(SPECS[name], timeout=90) as resp:
        return json.load(resp)


def build(spec_dir=None):
    specs = {name: _load(spec_dir, name) for name in SPECS}
    out = {}
    for name, method, path in ENDPOINTS:
        op = specs[name]['paths'].get(path, {}).get(method)
        if op is None:
            sys.exit('endpoint missing from the %s spec: %s %s' % (name, method.upper(), path))
        classic, granular = [], []
        for entry in op.get('x-atlassian-oauth2-scopes') or []:
            (granular if _is_granular(entry['scopes']) else classic).append(entry['scopes'])
        if not classic:
            # Some endpoints carry their classic scope only in `security`.
            for sec in op.get('security') or []:
                if 'OAuth2' in sec and sec['OAuth2']:
                    classic.append(sec['OAuth2'])
        out['%s %s' % (method.upper(), path)] = {
            'summary': op.get('summary', ''),
            'classic': sorted({s for group in classic for s in group}),
            'granular': sorted({s for group in granular for s in group}),
            'permissions': _permissions(op.get('description')),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec-dir')
    args = ap.parse_args()
    data = build(args.spec_dir)
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, '..', 'scope_data.py')
    lines = ['"""Generated by scripts/gen_scopes.py from Atlassian\'s OpenAPI specs. Do not edit."""',
             '', 'ENDPOINT_SCOPES = {']
    for key in sorted(data):
        lines.append('    %r: {' % key)
        for field in ('summary', 'classic', 'granular', 'permissions'):
            lines.append('        %r: %r,' % (field, data[key][field]))
        lines.append('    },')
    lines.append('}')
    with open(target, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('wrote %s (%d endpoints)' % (os.path.normpath(target), len(data)))


if __name__ == '__main__':
    main()

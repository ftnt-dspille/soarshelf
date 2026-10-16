"""Run the sample playbooks on a live FortiSOAR and check what they produce.

Not collected by pytest (no test_ prefix): it needs a FortiSOAR with jirav2
installed and configured, the fsrpb CLI from fsr-playbook-framework pointed at it
(FSR_BASE_URL / FSR_USERNAME / FSR_PASSWORD in its .env) and pyfsr for cleanup.

    FSRPB_HOME=~/PycharmProjects/fsr-playbook-framework \
    PYFSR_INSTANCE=159 JIRA_PROJECT=KAN \
        python tests/soar_playbooks_check.py

Everything it creates is labelled jirav2-sample and deleted at the end.
"""
import json
import os
import subprocess
import sys

FSRPB_HOME = os.path.expanduser(os.environ.get('FSRPB_HOME', '~/PycharmProjects/fsr-playbook-framework'))
INSTANCE = os.environ.get('PYFSR_INSTANCE', '159')
PROJECT = os.environ.get('JIRA_PROJECT', 'KAN')
COLLECTION = 'Sample - Jira v2 - 1.0.1'
created = []
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def fsrpb(*args):
    return subprocess.run(['uv', 'run', 'fsrpb'] + list(args), cwd=FSRPB_HOME, capture_output=True, text=True, timeout=600)


def run_playbook(name, params):
    out = fsrpb('run-playbook', '%s:%s' % (COLLECTION, name), '--input', json.dumps(params), '--follow')
    text = out.stdout
    start = text.find('{')
    run = json.loads(text[start:]) if start >= 0 else {}
    pk = run.get('@id', '').rstrip('/').split('/')[-1]
    env = json.loads(fsrpb('env', pk).stdout) if pk else {}
    return run.get('status'), env.get('vars', {})


def connector():
    from pyfsr.instances import InstanceRegistry
    client = InstanceRegistry.load().client(INSTANCE)
    return lambda op, **p: client.connectors.execute('jirav2', op, params=p).data


def main():
    jira = connector()
    try:
        status, v = run_playbook('Jira v2 - Create Ticket', {
            'project_key': PROJECT, 'issue_type': 'Task', 'summary': 'jirav2 playbook check',
            'description': 'First paragraph.\n\nSecond paragraph.'})
        key = v.get('issue_key')
        created.append(key)
        check('Create Ticket finished', status == 'finished', status)
        check('Create Ticket returns key, status and link', bool(key) and v.get('issue_status') and
              str(v.get('issue_url', '')).endswith('/browse/%s' % key), '%s %s' % (key, v.get('issue_status')))
        body = jira('get_ticket_details', issue_key=key, fields='description', include_text=True)
        check('description became two ADF paragraphs', len(body['fields']['description']['content']) == 2)

        status, v = run_playbook('Jira v2 - Comment and Transition', {
            'issue_key': key, 'comment': 'moving this along', 'status': 'In Progress'})
        check('Comment and Transition finished', status == 'finished', status)
        check('ticket moved to In Progress', v.get('issue_status') == 'In Progress', str(v.get('issue_status')))
        check('comment id and transitions returned', bool(v.get('comment_id')) and bool(v.get('available_transitions')),
              str(v.get('available_transitions')))

        status, v = run_playbook('Jira v2 - Poll Updated Tickets', {
            'jql_query': 'project = %s AND labels = "jirav2-sample" ORDER BY created DESC' % PROJECT})
        check('Poll Updated Tickets finished', status == 'finished', status)
        check('poll finds the new ticket', key in (v.get('ticket_keys') or []), 'count=%s' % v.get('ticket_count'))

        desk = next((d for d in jira('list_service_desks')['values'] if d.get('projectKey') == os.environ.get('JSM_PROJECT', 'DEMO')), None)
        if desk is None:
            print('SKIP  Open Service Desk Request: no service desk on the site')
        else:
            types = jira('list_request_types', service_desk_id=desk['id'])['values']
            rtype = types[0]
            status, v = run_playbook('Jira v2 - Open Service Desk Request', {
                'service_desk_id': desk['id'], 'request_type_id': rtype['id'],
                'summary': 'jirav2 playbook check', 'description': 'raised by the sample playbook'})
            created.append(v.get('request_key'))
            check('Open Service Desk Request finished', status == 'finished', status)
            check('request key and status returned', bool(v.get('request_key')) and bool(v.get('request_status')),
                  '%s %s' % (v.get('request_key'), v.get('request_status')))
    finally:
        for k in [k for k in created if k]:
            try:
                jira('delete_ticket', issue_key=k, delete_subtask=True)
            except Exception as err:  # noqa: BLE001
                print('cleanup failed for %s: %s' % (k, err))
    print('\n%d checks, %d failed' % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


main()

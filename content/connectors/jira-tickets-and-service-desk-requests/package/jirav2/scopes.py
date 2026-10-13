"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end

Which Atlassian endpoints each operation calls. The scope strings themselves
live in scope_data.py (generated from Atlassian's OpenAPI specs); the README
permission tables are generated from the two together, and tests/test_scopes.py
checks that what an operation really calls matches what is declared here.
"""
from .scope_data import ENDPOINT_SCOPES  # noqa: F401

ISSUE = 'GET /rest/api/3/issue/{issueIdOrKey}'
TRANSITIONS = '/rest/api/3/issue/{issueIdOrKey}/transitions'
COMMENT = '/rest/api/3/issue/{issueIdOrKey}/comment'

HEALTH_CHECK = ['GET /rest/api/3/myself']

# None: the endpoint depends on what the caller passes.
OPERATION_ENDPOINTS = {
    # the GET is only made when "Return Full Issue" is ticked
    'create_ticket': ['POST /rest/api/3/issue', ISSUE],
    'get_ticket_details': [ISSUE],
    'update_ticket': ['PUT /rest/api/3/issue/{issueIdOrKey}', 'GET ' + TRANSITIONS, 'POST ' + TRANSITIONS],
    'delete_ticket': ['DELETE /rest/api/3/issue/{issueIdOrKey}'],
    'set_status': ['GET ' + TRANSITIONS, 'POST ' + TRANSITIONS],
    'get_transitions': ['GET ' + TRANSITIONS],
    'assign_issue': ['PUT /rest/api/3/issue/{issueIdOrKey}/assignee'],
    'get_changelog': ['GET /rest/api/3/issue/{issueIdOrKey}/changelog'],
    'add_worklog': ['POST /rest/api/3/issue/{issueIdOrKey}/worklog'],
    'add_comment': ['POST ' + COMMENT],
    'get_comments': ['GET ' + COMMENT],
    'update_comment': ['PUT ' + COMMENT + '/{id}'],
    'delete_comment': ['DELETE ' + COMMENT + '/{id}'],
    'submit_file': ['POST /rest/api/3/issue/{issueIdOrKey}/attachments'],
    'add_remote_link': ['POST /rest/api/3/issue/{issueIdOrKey}/remotelink'],
    'link_issues': ['POST /rest/api/3/issueLink'],
    'list_link_types': ['GET /rest/api/3/issueLinkType'],
    'list_tickets': ['POST /rest/api/3/search/jql'],
    'validate_jql_query': ['POST /rest/api/3/jql/parse'],
    'list_projects': ['GET /rest/api/3/project/search'],
    'get_project': ['GET /rest/api/3/project/{projectIdOrKey}'],
    'search_users': ['GET /rest/api/3/user/search', 'GET /rest/api/3/users/search'],
    'get_user_details': ['GET /rest/api/3/user'],
    'list_issue_types': ['GET /rest/api/3/issuetype',
                         'GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes'],
    'get_create_metadata': ['GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}'],
    'list_priorities': ['GET /rest/api/3/priority/search'],
    'list_fields': ['GET /rest/api/3/field'],
    'list_service_desks': ['GET /rest/servicedeskapi/servicedesk'],
    'list_request_types': ['GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype'],
    'get_request_type_fields': [
        'GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/field'],
    'create_customer_request': ['POST /rest/servicedeskapi/request'],
    'get_customer_request': ['GET /rest/servicedeskapi/request/{issueIdOrKey}'],
    'add_request_comment': ['POST /rest/servicedeskapi/request/{issueIdOrKey}/comment'],
    'list_queues': ['GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue'],
    'list_queue_issues': ['GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue/{queueId}/issue'],
    'execute_api_request': None,
    # dropdown populators (hidden operations)
    'get_project_options': ['GET /rest/api/3/project/search'],
    # these two read the project's own types when Project Key is set, else the whole site's
    'get_issue_type_options': ['GET /rest/api/3/issuetype',
                               'GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes'],
    'get_issue_type_id_options': ['GET /rest/api/3/issuetype',
                                  'GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes'],
    'get_link_type_options': ['GET /rest/api/3/issueLinkType'],
    'get_user_options': ['GET /rest/api/3/users/search'],
    'get_service_desk_options': ['GET /rest/servicedeskapi/servicedesk'],
    'get_request_type_options': ['GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype'],
    'get_queue_options': ['GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue'],
    'get_transition_options': ['GET ' + TRANSITIONS],
    'get_transition_id_options': ['GET ' + TRANSITIONS],
}

POPULATORS = ('get_project_options', 'get_issue_type_options', 'get_issue_type_id_options',
              'get_link_type_options', 'get_user_options', 'get_service_desk_options',
              'get_request_type_options', 'get_queue_options', 'get_transition_options',
              'get_transition_id_options')


def scope_sets():
    """The three copy-paste scope sets: {name: {'classic': set, 'granular': set}}.

    `health`: what Check Health needs. `readonly`: every GET the connector
    makes. `all`: everything. The README tables and the live scope tests both
    come from here, so they cannot disagree.
    """
    sets = {name: {'classic': set(), 'granular': set()} for name in ('health', 'readonly', 'all')}

    def add(name, key):
        sets[name]['classic'].update(ENDPOINT_SCOPES[key]['classic'])
        sets[name]['granular'].update(ENDPOINT_SCOPES[key]['granular'])

    for key in HEALTH_CHECK:
        add('health', key)
    for keys in OPERATION_ENDPOINTS.values():
        for key in keys or []:
            add('all', key)
            if key.startswith('GET '):
                add('readonly', key)
    return sets


TOKEN_SCOPE_LIMIT = 50  # Atlassian's token form caps a token at 50 scopes


def action_scope_set(operation, family='granular'):
    found = set()
    for key in OPERATION_ENDPOINTS.get(operation) or []:
        found.update(ENDPOINT_SCOPES[key][family])
    return found


def pack_tokens(family='granular', limit=TOKEN_SCOPE_LIMIT):
    """Plan the fewest tokens such that every action's scopes fit inside one of them.

    The token form allows at most `limit` scopes, so the "everything" set cannot
    be one token. Returns [{'name', 'scopes', 'actions'}]: a `health` token, then
    first-fit-decreasing bins of the remaining actions. Every bin also receives
    the other actions whose scopes it happens to cover, so a token's expected
    behaviour is computed from its real scope list by the live scope tests.
    """
    bins = []
    health = set(ENDPOINT_SCOPES[HEALTH_CHECK[0]][family])
    todo = sorted((op for op in OPERATION_ENDPOINTS if OPERATION_ENDPOINTS[op] is not None
                   and action_scope_set(op, family)),
                  key=lambda op: -len(action_scope_set(op, family)))
    for op in todo:
        need = action_scope_set(op, family)
        for entry in bins:
            if len(entry['scopes'] | need) <= limit:
                entry['scopes'] |= need
                break
        else:
            bins.append({'scopes': set(need)})
    tokens = [{'name': 'health', 'scopes': sorted(health)}]
    for index, entry in enumerate(bins, 1):
        tokens.append({'name': 'pack-%d' % index, 'scopes': sorted(entry['scopes'])})
    for token in tokens:
        have = set(token['scopes'])
        token['actions'] = sorted(op for op in OPERATION_ENDPOINTS
                                  if OPERATION_ENDPOINTS[op] is not None
                                  and action_scope_set(op, family) and action_scope_set(op, family) <= have)
    return tokens

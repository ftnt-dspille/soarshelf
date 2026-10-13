#!/usr/bin/env python3
"""Generate info.json (config form + operation parameters) for the connector.

    python3 scripts/gen_info.py

info.json is committed; this script is its source. Edit here, re-run, commit
both. tests/test_info.py checks the result against operations.py and scopes.py.
"""
import json
import os

VERSION = '1.0.0'

SITE = 'the issue key or id, for example SEC-123'


def P(name, title, description, type='text', required=False, value=None, options=None,
      placeholder=None, api=None):
    param = {'name': name, 'title': title, 'type': type, 'editable': True, 'visible': True,
             'required': required, 'description': description, 'tooltip': description}
    if value is not None:
        param['value'] = value
    if options:
        param['options'] = options
    if placeholder:
        param['placeholder'] = placeholder
    if api:
        # Dynamic dropdown: the step editor fills it from this hidden operation.
        param['type'] = 'select'
        param['apiOperation'] = api
    return param


def KEY(desc='Specify the key of the issue, for example SEC-123.'):
    return P('issue_key', 'Issue Key', desc, required=True, placeholder='e.g. SEC-123')


def PAGE(start='startAt', limit='maxResults', default='50'):
    return [P(start, 'Start At', '(Optional) Index of the first result to return. Defaults to 0.',
              'integer'),
            P(limit, 'Max Results', '(Optional) Maximum number of results per page. Defaults to %s.' % default,
              'integer', value=default)]


def OP(operation, title, description, parameters=None, category='investigation'):
    return {'operation': operation, 'title': title, 'description': description,
            'category': category, 'annotation': operation, 'enabled': True, 'visible': True,
            'parameters': parameters or [], 'output_schema': {}}


def POPULATOR(operation, title, description):
    op = OP(operation, title, description)
    op['visible'] = False
    op['output_schema'] = {'type': 'array', 'items': {'type': 'object', 'properties': {}}}
    return op


PROJECT = dict(api='get_project_options')
USER = dict(api='get_user_options')
DESK = dict(api='get_service_desk_options')

CONFIGURATION = [
    P('server_url', 'Server URL',
      'Your Jira Cloud site, for example https://yourcompany.atlassian.net. For a scoped API token '
      'either tick "Scoped API Token" below, or enter https://api.atlassian.com/ex/jira/<cloudId> here.',
      required=True, placeholder='https://yourcompany.atlassian.net'),
    P('auth_type', 'Authentication',
      'Basic: the Atlassian account email as Username and an API token as API Token. Bearer: an OAuth 2.0 '
      'access token, sent as-is; Username is ignored.', 'select', required=True,
      value='Basic (Email + API Token)',
      options=['Basic (Email + API Token)', 'Bearer (OAuth 2.0 Access Token)']),
    P('username', 'Username',
      'The Atlassian account email address the API token was created under (not the token name). '
      'Not used for Bearer authentication.'),
    P('token', 'API Token', 'The API token (Basic) or access token (Bearer).', 'password', required=True),
    P('scoped', 'Scoped API Token',
      'Tick this when the token was created with scopes. Requests are then routed through '
      'https://api.atlassian.com/ex/jira/<cloudId>, which is the only place Atlassian accepts a scoped '
      'token. An unrestricted token does not need it.', 'checkbox', value=False),
    P('cloud_id', 'Cloud ID',
      '(Optional) The site\'s cloud id, used only with "Scoped API Token". Left empty, it is looked up '
      'from <Server URL>/_edge/tenant_info.'),
    P('timeout', 'Timeout (seconds)', 'Seconds to wait for each request. Defaults to 30.', 'integer',
      value='30'),
    P('verify_ssl', 'Verify SSL',
      'Specifies whether the SSL certificate for the server is to be verified or not. By default, this '
      'option is set to True.', 'checkbox', value=True),
]

# Username is only meaningful for Basic authentication, so it appears under the
# Authentication select only when Basic is chosen (FortiSOAR `onchange`).
_auth = next(f for f in CONFIGURATION if f['name'] == 'auth_type')
_user = next(f for f in CONFIGURATION if f['name'] == 'username')
CONFIGURATION.remove(_user)
_user['required'] = True
_auth['onchange'] = {'Basic (Email + API Token)': [_user], 'Bearer (OAuth 2.0 Access Token)': []}

OPERATIONS = [
    OP('create_ticket', 'Create Ticket',
       'Creates an issue. Give the issue type by name or by id. Anything else the project requires (a custom '
       'field, a JSM request type, a reporter) goes in Other Fields.', [
           P('project_key', 'Project Key', 'Key of the project to create the issue in. Pick from the list or enter a key.',
             required=True, placeholder='e.g. SEC', **PROJECT),
           P('ticket_summary', 'Summary', 'The issue summary (title).', required=True),
           P('ticket_description', 'Description',
             '(Optional) Plain text, or an Atlassian Document Format JSON document. Blank lines start a new '
             'paragraph.', 'textarea'),
           P('issue_type', 'Issue Type',
             'Issue type name, exactly as the project spells it. Jira Service Management projects use names '
             'such as "[System] Service request". Use List Issue Types to see them. Ignored when Issue Type '
             'ID is set. The list shows the chosen project\'s own types.', api='get_issue_type_options'),
           P('issue_type_id', 'Issue Type ID', '(Optional) Issue type id, for example 10341. Wins over Issue Type.',
             api='get_issue_type_id_options'),
           P('priority', 'Priority',
             '(Optional) Priority name, for example High. Leave empty when the project has no Priority field.'),
           P('labels', 'Labels', '(Optional) Comma-separated labels, or a JSON list.'),
           P('assignee_account_id', 'Assignee', '(Optional) The assignee. Pick a user or enter an account id.', **USER),
           P('parent', 'Parent Key', '(Optional) Parent issue key. Required for sub-tasks, for example SEC-1.'),
           P('other_fields', 'Other Fields',
             '(Optional) JSON object merged into the issue fields, for example '
             '{"customfield_10010": "1/25", "reporter": {"accountId": "..."}}. It overrides the fields above.',
             'json'),
           P('include_details', 'Return Full Issue',
             'Also fetch the created issue (one extra read) and return it under "issue".', 'checkbox',
             value=False),
       ]),
    OP('get_ticket_details', 'Get Ticket Details', 'Retrieves one issue.', [
        KEY(),
        P('fields', 'Fields', '(Optional) Comma-separated fields to return, for example summary,status.'),
        P('expand', 'Expand', '(Optional) Comma-separated expansions, for example changelog,renderedFields.'),
        P('include_text', 'Include Plain Text',
          'Add description_text, the description flattened from ADF to plain text.', 'checkbox', value=False),
    ]),
    OP('update_ticket', 'Update Ticket',
       'Updates fields, adds a comment and/or moves the issue to a new status. Only the values you set are '
       'sent. The project cannot be changed.', [
           KEY(),
           P('summary', 'Summary', '(Optional) New summary.'),
           P('description', 'Description', '(Optional) New description (plain text or ADF JSON).', 'textarea'),
           P('priority', 'Priority', '(Optional) New priority name.'),
           P('labels', 'Labels', '(Optional) Replaces the labels. Comma-separated or a JSON list.'),
           P('comment', 'Comment', '(Optional) A comment to add.', 'textarea'),
           P('status', 'Status',
             '(Optional) Target status name. The issue is moved with the workflow transition that leads there.',
             api='get_transition_options'),
           P('other_fields', 'Other Fields', '(Optional) JSON object of additional fields to set.', 'json'),
           P('notify_users', 'Notify Users', 'Send Jira notifications for the field changes.', 'checkbox',
             value=True),
       ]),
    OP('delete_ticket', 'Delete Ticket', 'Deletes an issue.', [
        KEY(),
        P('delete_subtask', 'Delete Sub-tasks', 'Also delete the issue\'s sub-tasks.', 'checkbox', value=False),
    ], category='miscellaneous'),
    OP('set_status', 'Set Ticket Status',
       'Moves an issue through its workflow, by target status name or by transition id.', [
           KEY(),
           P('status', 'Status', 'Name of the status to move to, or of the transition. The list shows what the issue can move to now.',
             api='get_transition_options'),
           P('transition_id', 'Transition ID', '(Optional) Transition id. Wins over Status. See Get Transitions.',
             api='get_transition_id_options'),
           P('resolution', 'Resolution', '(Optional) Resolution name, for transitions that require one.'),
           P('comment', 'Comment', '(Optional) A comment to add with the transition.', 'textarea'),
       ]),
    OP('get_transitions', 'Get Transitions', 'Lists the workflow transitions available from the issue\'s status.',
       [KEY()]),
    OP('assign_issue', 'Assign Issue',
       'Assigns the issue. An empty Account ID unassigns it; "-1" assigns the project\'s default assignee.', [
           KEY(),
           P('accountId', 'Assignee', 'The new assignee (an account id). Leave empty to unassign; "-1" assigns the project default.',
             **USER),
       ]),
    OP('get_changelog', 'Get Changelog', 'Retrieves the change history of an issue.', [KEY()] + PAGE()),
    OP('add_worklog', 'Add Worklog', 'Logs time against an issue.', [
        KEY(),
        P('time_spent', 'Time Spent', 'Time in Jira notation, for example 1h 30m.', required=True),
        P('started', 'Started', '(Optional) When the work started. Defaults to now.', 'datetime'),
        P('comment', 'Comment', '(Optional) Work description.', 'textarea'),
    ]),
    OP('add_comment', 'Add Comment', 'Adds a comment to an issue.', [
        KEY(),
        P('comment', 'Comment', 'Comment text (plain text or ADF JSON).', 'textarea', required=True),
        P('internal', 'Internal (JSM)',
          'In a Jira Service Management project, make the comment internal so the customer cannot see it.',
          'checkbox', value=False),
    ]),
    OP('get_comments', 'Get Comments', 'Lists the comments on an issue.', [
        KEY(),
        P('orderBy', 'Order By', '(Optional) Sort order.', 'select', value='created',
          options=['created', '-created']),
        P('include_text', 'Include Plain Text', 'Add body_text to each comment.', 'checkbox', value=False),
    ] + PAGE()),
    OP('update_comment', 'Update Comment', 'Replaces the text of a comment.', [
        KEY(),
        P('comment_id', 'Comment ID', 'Id of the comment.', required=True),
        P('comment', 'Comment', 'New comment text.', 'textarea', required=True),
    ]),
    OP('delete_comment', 'Delete Comment', 'Deletes a comment.', [
        KEY(), P('comment_id', 'Comment ID', 'Id of the comment.', required=True)],
       category='miscellaneous'),
    OP('submit_file', 'Add Attachment', 'Attaches a FortiSOAR file to an issue.', [
        KEY(),
        P('path', 'Reference Type', 'How the file is identified.', 'select', value='Attachment ID',
          options=['Attachment ID', 'File IRI']),
        P('value', 'Reference Value', 'The FortiSOAR attachment id or file IRI.', required=True),
    ]),
    OP('add_remote_link', 'Add Remote Link', 'Adds a web link to an issue.', [
        KEY(),
        P('url', 'URL', 'The link target.', required=True),
        P('title', 'Title', 'The link text.', required=True),
    ]),
    OP('link_issues', 'Link Issues', 'Creates a link between two issues, for example Blocks or Relates.', [
        P('link_type', 'Link Type', 'Link type name. See List Link Types.', required=True,
          placeholder='e.g. Relates', api='get_link_type_options'),
        P('inward_issue', 'Inward Issue', 'Key of the inward issue.', required=True),
        P('outward_issue', 'Outward Issue', 'Key of the outward issue.', required=True),
        P('comment', 'Comment', '(Optional) A comment to add with the link.', 'textarea'),
    ]),
    OP('list_link_types', 'List Link Types', 'Lists the issue link types.'),
    OP('list_tickets', 'List Tickets',
       'Searches with JQL. Jira requires the query to be bounded (for example project = SEC), and interprets '
       'dates in the calling user\'s time zone.', [
           P('jql_query', 'JQL Query', 'The JQL to run. An ORDER BY clause is allowed.', required=True,
             placeholder='e.g. project = SEC AND statusCategory != Done'),
           P('start_time', 'Updated Since',
             '(Optional) Only issues updated at or after this time (ANDed onto the JQL, to the minute).',
             'datetime'),
           P('fields', 'Fields', '(Optional) Comma-separated fields to return. Defaults to all navigable fields.'),
           P('expand', 'Expand', '(Optional) Comma-separated expansions.'),
           P('maxResults', 'Max Results', '(Optional) Page size. Defaults to 50.', 'integer', value='50'),
           P('nextPageToken', 'Next Page Token',
             '(Optional) The nextPageToken from a previous response, to read the next page.'),
           P('fetch_all', 'Fetch All Pages', 'Follow nextPageToken until the results run out or Max Total is hit.',
             'checkbox', value=False),
           P('max_total', 'Max Total', '(Optional) Cap for Fetch All Pages. Defaults to 1000.', 'integer',
             value='1000'),
       ]),
    OP('validate_jql_query', 'Validate JQL Query', 'Checks a JQL string for errors without running it.', [
        P('jql_query', 'JQL Query', 'The JQL to validate.', required=True)]),
    OP('list_projects', 'List Projects', 'Lists the projects the account can browse.', [
        P('query', 'Query', '(Optional) Filter by project name or key.'),
        P('fetch_all', 'Fetch All Pages', 'Read every page (up to 1000 projects).', 'checkbox', value=False),
    ] + PAGE()),
    OP('get_project', 'Get Project', 'Retrieves one project.', [
        P('project_key', 'Project Key', 'The project key or id.', required=True, **PROJECT)]),
    OP('search_users', 'Search Users', 'Finds users by name or email.', [
        P('query', 'Query', '(Optional) Name or email fragment. Empty lists users.')] + PAGE()),
    OP('get_user_details', 'Get User Details', 'Retrieves a user by account id.', [
        P('accountId', 'User', 'The user (an account id).', required=True, **USER)]),
    OP('list_issue_types', 'List Issue Types',
       'Lists issue types: those usable in one project, or every type on the site when no project is given.', [
           P('project_key', 'Project Key', '(Optional) Limit to the types this project allows.', **PROJECT)]),
    OP('get_create_metadata', 'Get Create Metadata',
       'Lists the fields (and which are required) for creating an issue of a type in a project.', [
           P('project_key', 'Project Key', 'The project key or id.', required=True, **PROJECT),
           P('issue_type_id', 'Issue Type ID', 'The issue type id.', required=True,
             api='get_issue_type_id_options')] + PAGE(default='200')),
    OP('list_priorities', 'List Priorities', 'Lists the priorities. Needs the manage:jira-configuration '
       'scope (see README).', PAGE()),
    OP('list_fields', 'List Fields', 'Lists system and custom fields, including custom field ids.'),
    OP('list_service_desks', 'List Service Desks', 'Lists Jira Service Management service desks.', [
        P('start', 'Start', '(Optional) Index of the first result.', 'integer'),
        P('limit', 'Limit', '(Optional) Maximum results.', 'integer')]),
    OP('list_request_types', 'List Request Types', 'Lists the request types of a service desk.', [
        P('service_desk_id', 'Service Desk', 'The service desk (its numeric id).', required=True, **DESK),
        P('search_query', 'Search Query', '(Optional) Filter by name.'),
        P('start', 'Start', '(Optional) Index of the first result.', 'integer'),
        P('limit', 'Limit', '(Optional) Maximum results.', 'integer')]),
    OP('get_request_type_fields', 'Get Request Type Fields',
       'Lists the fields a request type takes, and which are required.', [
           P('service_desk_id', 'Service Desk', 'The service desk (its numeric id).', required=True, **DESK),
           P('request_type_id', 'Request Type', 'The request type (its id). Pick the service desk first.', required=True,
             api='get_request_type_options')]),
    OP('create_customer_request', 'Create Customer Request',
       'Creates a request through the JSM API, so it has a request type and shows in the portal and queues.', [
           P('service_desk_id', 'Service Desk', 'The service desk (its numeric id).', required=True, **DESK),
           P('request_type_id', 'Request Type', 'The request type (its id). Pick the service desk first.', required=True,
             api='get_request_type_options'),
           P('summary', 'Summary', 'The request summary.', required=True),
           P('description', 'Description', '(Optional) Description, as plain or wiki-markup text.', 'textarea'),
           P('request_field_values', 'Request Field Values',
             '(Optional) JSON object of other request fields, keyed by field id.', 'json'),
           P('raise_on_behalf_of', 'Raise On Behalf Of', '(Optional) Account id of the customer.'),
           P('request_participants', 'Participants', '(Optional) Comma-separated participant account ids.')]),
    OP('get_customer_request', 'Get Customer Request', 'Retrieves a request with its portal-side details.', [
        KEY(), P('expand', 'Expand', '(Optional) Comma-separated expansions, for example participant,sla.')]),
    OP('add_request_comment', 'Add Request Comment', 'Comments on a request through the JSM API.', [
        KEY(),
        P('comment', 'Comment', 'Comment text (JSM takes plain or wiki-markup text).', 'textarea', required=True),
        P('public', 'Public', 'Visible to the customer. Untick for an internal note.', 'checkbox', value=True)]),
    OP('list_queues', 'List Queues', 'Lists the queues of a service desk.', [
        P('service_desk_id', 'Service Desk', 'The service desk (its numeric id).', required=True, **DESK),
        P('include_count', 'Include Issue Count', 'Also return the issue count of each queue.', 'checkbox',
          value=False),
        P('start', 'Start', '(Optional) Index of the first result.', 'integer'),
        P('limit', 'Limit', '(Optional) Maximum results.', 'integer')]),
    OP('list_queue_issues', 'List Queue Issues', 'Lists the issues in a queue.', [
        P('service_desk_id', 'Service Desk', 'The service desk (its numeric id).', required=True, **DESK),
        P('queue_id', 'Queue', 'The queue (its id). Pick the service desk first.', required=True, api='get_queue_options'),
        P('start', 'Start', '(Optional) Index of the first result.', 'integer'),
        P('limit', 'Limit', '(Optional) Maximum results.', 'integer')]),
    OP('execute_api_request', 'Execute an API Request',
       'Calls any Jira or Jira Service Management REST endpoint with this configuration\'s credentials. '
       'The scopes needed depend on the endpoint.', [
           P('endpoint', 'Endpoint',
             'A path on the configured site, for example /rest/api/3/project/search. Full URLs are refused so '
             'credentials never leave the configured site.', required=True,
             placeholder='/rest/api/3/myself'),
           P('method', 'Method', 'The HTTP method. Defaults to GET.', 'select', value='GET',
             options=['DELETE', 'GET', 'PATCH', 'POST', 'PUT']),
           P('content_type', 'Content Type', '(Optional) Content-Type of the payload.', 'select',
             value='application/json', options=['None', 'application/json', 'application/x-www-form-urlencoded']),
           P('query_params', 'Query Parameters', '(Optional) Query string parameters, as a JSON object.', 'json'),
           P('payload', 'Payload', '(Optional) The request body.', 'json')]),
    POPULATOR('get_project_options', 'Get Project Options',
              'Populates project dropdowns: every project the account can browse, as Name (KEY) / key pairs.'),
    POPULATOR('get_issue_type_options', 'Get Issue Type Options',
              'Populates issue type dropdowns with the chosen project\'s issue type names (the whole site\'s when no project is chosen).'),
    POPULATOR('get_issue_type_id_options', 'Get Issue Type ID Options',
              'Populates issue type id dropdowns as Name [id] / id pairs, for the chosen project when one is set.'),
    POPULATOR('get_link_type_options', 'Get Link Type Options',
              'Populates link type dropdowns with the issue link type names.'),
    POPULATOR('get_user_options', 'Get User Options',
              'Populates assignee dropdowns with the active people on the site, as Name (email) / account id.'),
    POPULATOR('get_service_desk_options', 'Get Service Desk Options',
              'Populates service desk dropdowns as Project (KEY) / service desk id.'),
    POPULATOR('get_request_type_options', 'Get Request Type Options',
              'Populates request type dropdowns for the chosen service desk. Empty until Service Desk is set.'),
    POPULATOR('get_queue_options', 'Get Queue Options',
              'Populates queue dropdowns for the chosen service desk. Empty until Service Desk is set.'),
    POPULATOR('get_transition_options', 'Get Transition Options',
              'Populates status dropdowns with what the chosen issue can move to now. Empty until Issue Key is set.'),
    POPULATOR('get_transition_id_options', 'Get Transition ID Options',
              'Populates transition id dropdowns for the chosen issue. Empty until Issue Key is set.'),
]

INFO = {
    'name': 'jirav2',
    'label': 'Jira v2',
    'description': 'Create, update, search and transition Jira Cloud issues, and work with Jira Service '
                   'Management requests and queues. Supports scoped API tokens, tests every action offline, '
                   'and ships a generic API call for anything not covered.',
    'publisher': 'Fortinet',
    'cs_approved': False,
    'cs_compatible': True,
    'version': VERSION,
    'category': 'Ticket Management',
    'icon_small_name': 'jira_small.png',
    'icon_large_name': 'jira_large.png',
    'help_online': 'https://github.com/ftnt-dspille/connector-jirav2',
    'configuration': {'fields': CONFIGURATION},
    'operations': OPERATIONS,
}


def main():
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'info.json')
    with open(target, 'w') as handle:
        json.dump(INFO, handle, indent=2)
        handle.write('\n')
    print('wrote %s (%d operations)' % (os.path.normpath(target), len(OPERATIONS)))


if __name__ == '__main__':
    main()

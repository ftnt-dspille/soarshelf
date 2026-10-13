# Jira v2 - FortiSOAR connector

A FortiSOAR connector for **Jira Cloud** and **Jira Service Management**. It
replaces the Fortinet `jira` 2.0.0 connector (it installs alongside it, under
the name `jirav2`) with scoped-token support, JSM actions, live dropdowns, a
generic API call, and an offline test for every action.

## What is better than the original

| | `jira` 2.0.0 | `jirav2` |
|---|---|---|
| Health check | Lists projects, and reports "make sure you have at least one JIRA project" for any empty result or scope problem | Calls `GET /myself`. Passes with zero projects, and names the HTTP status and Jira's own message on failure |
| Scoped API tokens | Not supported (needs `api.atlassian.com/ex/jira/<cloudId>`) | "Scoped API Token" option routes there and looks the cloud id up for you; a bare `https://api.atlassian.com` gets a clear error, not a 404 |
| Bearer / OAuth 2.0 | No | Yes |
| Errors | `Error [Bad Request] ... status [400]` | `HTTP 400 POST /rest/api/3/issue: issuetype: Specify a valid issue type` plus a hint for 401/403/404 |
| Retries | None | `429` (honours `Retry-After`) and `502/503/504` on reads |
| JQL search | Rejects any query without `project = X`; the "updated since" clause had no parentheses | Any bounded JQL; the window is `(your JQL) AND updated >= ...` and keeps `ORDER BY` last; `Fetch All Pages` |
| Create ticket | Issue type by name only; always sends `priority` | By name **or id**; blank priority is not sent; labels, assignee, parent; `Other Fields` overrides |
| Update ticket | Sent `project` on every update | Sends only what you set; comment and status transition in one action |
| Status changes | Silent "invalid status" | Lists the transitions that *are* available |
| Jira Service Management | None | Service desks, request types, create/get request, request comments, queues |
| Dropdowns | None | Project, user, issue type, link type, service desk (`apiOperation`) |
| Generic call | None | `Execute an API Request`: endpoint, method, content type, query parameters, payload |
| Removed | `update_fortisoar` took FortiSOAR credentials as parameters | Gone. Use the FortiSOAR record actions instead |
| Tests | Scaffold only | Every action has offline tests; the permission tables below are checked against them |

## Install

Build the bundle and install it from the connector page (Install > Upload), or
copy it to the appliance as for any connector:

```bash
./scripts/package.sh        # -> dist/jirav2-<version>.tgz
```

## Configure

| Field | Value |
|---|---|
| Server URL | Your site, e.g. `https://yourcompany.atlassian.net` |
| Authentication | `Basic (Email + API Token)` (default) or `Bearer (OAuth 2.0 Access Token)` |
| Username | The Atlassian account **email** the token was created under. Not the token's name |
| API Token | The token |
| Scoped API Token | Tick if the token was created **with scopes** |
| Cloud ID | Optional. Only used with Scoped API Token; empty means look it up |
| Timeout / Verify SSL | Defaults 30 s / on |

Which Server URL?

| Token | Server URL | Scoped API Token |
|---|---|---|
| Unrestricted API token | `https://<site>.atlassian.net` | off |
| Scoped API token | `https://<site>.atlassian.net` | **on** |
| Scoped API token, you know the cloud id | `https://api.atlassian.com/ex/jira/<cloudId>` | off |
| OAuth 2.0 (3LO) access token | `https://api.atlassian.com/ex/jira/<cloudId>` | off, authentication = Bearer |

Find a site's cloud id by opening `https://<site>.atlassian.net/_edge/tenant_info`.

This connector targets Jira **Cloud** (REST API v3). Jira Data Center and
Server speak REST v2 and are not supported.

## Jira Service Management projects

* **Issue type names are the project's own**, e.g. `[System] Service request`,
  `[System] Incident`. `Task` and `Bug` may not exist there. Use the Issue Type
  dropdown, `List Issue Types` (with a project key) or pass the id.
* To create something that appears in the portal and queues, use **Create
  Customer Request** (it takes a request type) rather than Create Ticket. Find
  ids with `List Service Desks` and `List Request Types`.
* Create Ticket can also set the request type through `Other Fields`, as
  `{"customfield_10010": "<serviceDeskId>/<requestTypeId>"}` (the custom field
  number varies by site; `List Fields` shows it).
* If a project has no Priority field, leave Priority empty. Jira rejects the field.
* `Get Create Metadata` shows every field of an issue type and which are required.

## Sample playbooks

The connector ships a collection, `Sample - Jira v2 - 1.0.1`, that FortiSOAR imports with it. Each
playbook takes plain parameters, so it runs from a button, from another playbook, or on its own.

| Playbook | Parameters | What it does |
|---|---|---|
| Jira v2 - Create Ticket | project_key, issue_type, summary, description | Creates a ticket, reads it back, returns `issue_key`, `issue_status`, `issue_url` |
| Jira v2 - Comment and Transition | issue_key, comment, status | Adds a comment, lists the transitions, moves the ticket by status name |
| Jira v2 - Poll Updated Tickets | jql_query | Runs a JQL search with pagination handled, returns `ticket_count` and `ticket_keys` |
| Jira v2 - Open Service Desk Request | service_desk_id, request_type_id, summary, description | Raises a JSM request, adds a public reply, reads it back |

The YAML source is `playbooks/jirav2.yaml`; `scripts/build_playbooks.sh` compiles it to
`playbooks/playbooks.json` with the fsrpb compiler (set `FSRPB_HOME`). To run them against a live
FortiSOAR and check the output, use `tests/soar_playbooks_check.py` (the header lists what it needs).

## Troubleshooting

| Message | Meaning |
|---|---|
| `HTTP 401 ... scope does not match` | A scoped token is missing a scope this action needs. See the scope tables below |
| `HTTP 401 ... Check the username` | Username must be the account email; the token must be pasted without whitespace |
| `Server URL https://api.atlassian.com is missing the cloud id` | Use `.../ex/jira/<cloudId>`, or the site URL with Scoped API Token ticked |
| `HTTP 404` on everything | Wrong Server URL, or a scoped token sent to the site URL instead of the gateway |
| `HTTP 404` on one issue/project | It does not exist **or the account cannot Browse it** (Jira hides it) |
| `HTTP 400 ... issuetype: Specify a valid issue type` | The name is not an issue type of that project. Use the dropdown or an id |
| `No transition matches ... Available: ...` | The workflow has no transition to that status from the current one |
| `Unbounded JQL queries are not allowed` | Add a restriction such as `project = SEC` or `updated >= -30d` |

## Actions

Create / Get / Update / Delete Ticket, Set Ticket Status, Get Transitions, Assign
Issue, Get Changelog, Add Worklog, Add / Get / Update / Delete Comment, Add
Attachment, Add Remote Link, Link Issues, List Link Types, List Tickets (JQL),
Validate JQL Query, List / Get Project, Search Users, Get User Details, List
Issue Types, Get Create Metadata, List Priorities, List Fields; JSM: List
Service Desks, List Request Types, Get Request Type Fields, Create / Get
Customer Request, Add Request Comment, List Queues, List Queue Issues; and
**Execute an API Request**.

Rich text (descriptions, comments) is converted to Atlassian Document Format
for you: pass plain text (blank line = new paragraph) or ADF JSON.

Dates for `List Tickets` and `Add Worklog` are ISO-8601. Jira evaluates JQL
dates in the *calling user's* time zone, to the minute.

## Permissions

<!-- BEGIN GENERATED -->

### Scope sets to copy

Granular scopes are what the Atlassian token form lists; classic scopes are the older coarse ones. Use one family or the other for a token. Generated from Atlassian's OpenAPI specification.

| Need | Classic scopes | Granular scopes |
|---|---|---|
| **Health check only** | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` |
| **Read-only actions** (every Get/List) | `manage:jira-configuration`, `read:jira-user`, `read:jira-work`, `read:servicedesk-request` | `read:application-role:jira`, `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:field-configuration:jira`, `read:field:jira`, `read:group:jira`, `read:issue-link-type:jira`, `read:issue-meta:jira`, `read:issue-security-level:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:issue.changelog:jira`, `read:issue.transition:jira`, `read:issue.vote:jira`, `read:issue:jira`, `read:jql:jira`, `read:project-category:jira`, `read:project-role:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:queue:jira-service-management`, `read:request:jira-service-management`, `read:requesttype:jira-service-management`, `read:servicedesk:jira-service-management`, `read:status:jira`, `read:user.property:jira`, `read:user:jira` |
| **Everything in this connector** | `manage:jira-configuration`, `read:jira-user`, `read:jira-work`, `read:servicedesk-request`, `write:jira-work`, `write:servicedesk-request` | `delete:comment.property:jira`, `delete:comment:jira`, `delete:issue:jira`, `read:application-role:jira`, `read:attachment:jira`, `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:field-configuration:jira`, `read:field.default-value:jira`, `read:field.option:jira`, `read:field:jira`, `read:group:jira`, `read:issue-details:jira`, `read:issue-link-type:jira`, `read:issue-meta:jira`, `read:issue-security-level:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:issue-worklog.property:jira`, `read:issue-worklog:jira`, `read:issue.changelog:jira`, `read:issue.remote-link:jira`, `read:issue.transition:jira`, `read:issue.vote:jira`, `read:issue:jira`, `read:jql:jira`, `read:project-category:jira`, `read:project-role:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:queue:jira-service-management`, `read:request.comment:jira-service-management`, `read:request:jira-service-management`, `read:requesttype:jira-service-management`, `read:servicedesk:jira-service-management`, `read:status:jira`, `read:user.property:jira`, `read:user:jira`, `validate:jql:jira`, `write:attachment:jira`, `write:comment.property:jira`, `write:comment:jira`, `write:issue-link:jira`, `write:issue-worklog.property:jira`, `write:issue-worklog:jira`, `write:issue.property:jira`, `write:issue.remote-link:jira`, `write:issue:jira`, `write:request.comment:jira-service-management`, `write:request:jira-service-management` |

`List Priorities` calls `GET /rest/api/3/priority/search`, which Atlassian only offers under the classic `manage:jira-configuration` scope: no granular scope exists for it. With a granular-only token that one action returns a scope error; every other action is unaffected.

### Permissions by action

A scope lets the token call an endpoint; the account behind the token must *also* hold the Jira permission (Browse Projects, Create Issues, ...) in the project. The last table below lists the permission each endpoint needs.

| Action | Calls | Classic scope | Granular scopes |
|---|---|---|---|
| Create Ticket | `POST /rest/api/3/issue`<br>`GET /rest/api/3/issue/{issueIdOrKey}` | `read:jira-work`, `write:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-security-level:jira`, `read:issue.changelog:jira`, `read:issue.vote:jira`, `read:issue:jira`, `read:status:jira`, `read:user:jira`, `write:attachment:jira`, `write:comment.property:jira`, `write:comment:jira`, `write:issue:jira` |
| Get Ticket Details | `GET /rest/api/3/issue/{issueIdOrKey}` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-security-level:jira`, `read:issue.changelog:jira`, `read:issue.vote:jira`, `read:issue:jira`, `read:status:jira`, `read:user:jira` |
| Update Ticket | `PUT /rest/api/3/issue/{issueIdOrKey}`<br>`GET /rest/api/3/issue/{issueIdOrKey}/transitions`<br>`POST /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:jira-work`, `write:jira-work` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira`, `write:issue.property:jira`, `write:issue:jira` |
| Delete Ticket | `DELETE /rest/api/3/issue/{issueIdOrKey}` | `write:jira-work` | `delete:issue:jira` |
| Set Ticket Status | `GET /rest/api/3/issue/{issueIdOrKey}/transitions`<br>`POST /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:jira-work`, `write:jira-work` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira`, `write:issue.property:jira`, `write:issue:jira` |
| Get Transitions | `GET /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:jira-work` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira` |
| Assign Issue | `PUT /rest/api/3/issue/{issueIdOrKey}/assignee` | `write:jira-work` | `write:issue:jira` |
| Get Changelog | `GET /rest/api/3/issue/{issueIdOrKey}/changelog` | `read:jira-work` | `read:avatar:jira`, `read:issue-meta:jira`, `read:issue.changelog:jira` |
| Add Worklog | `POST /rest/api/3/issue/{issueIdOrKey}/worklog` | `write:jira-work` | `read:avatar:jira`, `read:group:jira`, `read:issue-worklog.property:jira`, `read:issue-worklog:jira`, `read:project-role:jira`, `read:user:jira`, `write:issue-worklog.property:jira`, `write:issue-worklog:jira` |
| Add Comment | `POST /rest/api/3/issue/{issueIdOrKey}/comment` | `write:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira`, `write:comment:jira` |
| Get Comments | `GET /rest/api/3/issue/{issueIdOrKey}/comment` | `read:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira` |
| Update Comment | `PUT /rest/api/3/issue/{issueIdOrKey}/comment/{id}` | `write:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira`, `write:comment:jira` |
| Delete Comment | `DELETE /rest/api/3/issue/{issueIdOrKey}/comment/{id}` | `write:jira-work` | `delete:comment.property:jira`, `delete:comment:jira` |
| Add Attachment | `POST /rest/api/3/issue/{issueIdOrKey}/attachments` | `write:jira-work` | `read:attachment:jira`, `read:avatar:jira`, `read:user:jira`, `write:attachment:jira` |
| Add Remote Link | `POST /rest/api/3/issue/{issueIdOrKey}/remotelink` | `write:jira-work` | `read:issue.remote-link:jira`, `write:issue.remote-link:jira`, `write:issue:jira` |
| Link Issues | `POST /rest/api/3/issueLink` | `write:jira-work` | `write:comment:jira`, `write:issue-link:jira`, `write:issue:jira` |
| List Link Types | `GET /rest/api/3/issueLinkType` | `read:jira-work` | `read:issue-link-type:jira` |
| List Tickets | `POST /rest/api/3/search/jql` | `read:jira-work` | `read:field.default-value:jira`, `read:field.option:jira`, `read:field:jira`, `read:group:jira`, `read:issue-details:jira` |
| Validate JQL Query | `POST /rest/api/3/jql/parse` | `read:jira-work` | `read:field:jira`, `read:jql:jira`, `validate:jql:jira` |
| List Projects | `GET /rest/api/3/project/search` | `read:jira-work` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:user:jira` |
| Get Project | `GET /rest/api/3/project/{projectIdOrKey}` | `read:jira-work` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:user:jira` |
| Search Users | `GET /rest/api/3/user/search`<br>`GET /rest/api/3/users/search` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user.property:jira`, `read:user:jira` |
| Get User Details | `GET /rest/api/3/user` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` |
| List Issue Types | `GET /rest/api/3/issuetype`<br>`GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project:jira` |
| Get Create Metadata | `GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira` |
| List Priorities | `GET /rest/api/3/priority/search` | `manage:jira-configuration` | - |
| List Fields | `GET /rest/api/3/field` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:field:jira`, `read:project-category:jira`, `read:project:jira` |
| List Service Desks | `GET /rest/servicedeskapi/servicedesk` | `read:servicedesk-request` | `read:servicedesk:jira-service-management` |
| List Request Types | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype` | `read:servicedesk-request` | `read:requesttype:jira-service-management` |
| Get Request Type Fields | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/field` | `read:servicedesk-request` | `read:requesttype:jira-service-management` |
| Create Customer Request | `POST /rest/servicedeskapi/request` | `write:servicedesk-request` | `read:request:jira-service-management`, `read:user:jira`, `write:request:jira-service-management` |
| Get Customer Request | `GET /rest/servicedeskapi/request/{issueIdOrKey}` | `read:servicedesk-request` | `read:request:jira-service-management`, `read:user:jira` |
| Add Request Comment | `POST /rest/servicedeskapi/request/{issueIdOrKey}/comment` | `write:servicedesk-request` | `read:request.comment:jira-service-management`, `read:user:jira`, `write:request.comment:jira-service-management` |
| List Queues | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue` | `read:jira-work` | `read:jql:jira`, `read:queue:jira-service-management`, `read:user:jira` |
| List Queue Issues | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue/{queueId}/issue` | `read:jira-work` | `read:issue:jira`, `read:queue:jira-service-management`, `read:user:jira` |
| Execute an API Request | whatever endpoint you call | depends | depends |

### Dropdown helpers

Parameters that take a project, user, issue type, link type or service desk are dropdowns filled live by hidden `get_*_options` actions (the same `apiOperation` mechanism as the FortiAIGate connector). The editor can only show plain text, so each list holds names such as `Operations (OPS)`; the connector turns the picked name back into the key or id when the action runs, and an action can also be given the bare key or id. They call the same endpoints as the matching read actions, so they need no extra permission:

| Helper | Calls | Granular scopes |
|---|---|---|
| `get_project_options` | `GET /rest/api/3/project/search` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:user:jira` |
| `get_issue_type_options` | `GET /rest/api/3/issuetype`<br>`GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project:jira` |
| `get_issue_type_id_options` | `GET /rest/api/3/issuetype`<br>`GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project:jira` |
| `get_link_type_options` | `GET /rest/api/3/issueLinkType` | `read:issue-link-type:jira` |
| `get_user_options` | `GET /rest/api/3/users/search` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` |
| `get_service_desk_options` | `GET /rest/servicedeskapi/servicedesk` | `read:servicedesk:jira-service-management` |
| `get_request_type_options` | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype` | `read:requesttype:jira-service-management` |
| `get_queue_options` | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue` | `read:jql:jira`, `read:queue:jira-service-management`, `read:user:jira` |
| `get_transition_options` | `GET /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira` |
| `get_transition_id_options` | `GET /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira` |

### Scopes and Jira permissions by endpoint

| Endpoint | Classic scope | Granular scopes | Jira permission the account needs |
|---|---|---|---|
| `GET /rest/api/3/field` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:field:jira`, `read:project-category:jira`, `read:project:jira` | None. |
| `POST /rest/api/3/issue` | `write:jira-work` | `read:issue:jira`, `write:attachment:jira`, `write:comment.property:jira`, `write:comment:jira`, `write:issue:jira` | Browse projects and Create issues project permissions for the project in which the issue or subtask is created. |
| `GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira` | Create issues project permission in the requested projects. |
| `GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira` | Create issues project permission in the requested projects. |
| `DELETE /rest/api/3/issue/{issueIdOrKey}` | `write:jira-work` | `delete:issue:jira` | Browse projects and Delete issues project permission for the project containing the issue.; If issue-level security is configured, issue-level security permission to view the issue. |
| `GET /rest/api/3/issue/{issueIdOrKey}` | `read:jira-work` | `read:avatar:jira`, `read:field-configuration:jira`, `read:issue-meta:jira`, `read:issue-security-level:jira`, `read:issue.changelog:jira`, `read:issue.vote:jira`, `read:issue:jira`, `read:status:jira`, `read:user:jira` | Browse projects project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `PUT /rest/api/3/issue/{issueIdOrKey}` | `write:jira-work` | `write:issue:jira` | Browse projects and Edit issues project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `PUT /rest/api/3/issue/{issueIdOrKey}/assignee` | `write:jira-work` | `write:issue:jira` | Browse Projects and Assign Issues project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `POST /rest/api/3/issue/{issueIdOrKey}/attachments` | `write:jira-work` | `read:attachment:jira`, `read:avatar:jira`, `read:user:jira`, `write:attachment:jira` | Browse Projects and Create attachments project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `GET /rest/api/3/issue/{issueIdOrKey}/changelog` | `read:jira-work` | `read:avatar:jira`, `read:issue-meta:jira`, `read:issue.changelog:jira` | Browse projects project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `GET /rest/api/3/issue/{issueIdOrKey}/comment` | `read:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira` | Comments are included in the response where the user has:; Browse projects project permission for the project containing the comment.; If issue-level security is configured, issue-level security permission to view the issue.; If the comment has visibility restrictions, belongs to the group or has the role visibility is role visibility is restricted to. |
| `POST /rest/api/3/issue/{issueIdOrKey}/comment` | `write:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira`, `write:comment:jira` | Browse projects and Add comments project permission for the project that the issue containing the comment is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `DELETE /rest/api/3/issue/{issueIdOrKey}/comment/{id}` | `write:jira-work` | `delete:comment.property:jira`, `delete:comment:jira` | Browse projects project permission for the project that the issue containing the comment is in.; If issue-level security is configured, issue-level security permission to view the issue.; Delete all comments project permission to delete any comment or Delete own comments to delete comment created by the user,; If the comment has visibility restrictions, the user belongs to the group or has the role visibility is restricted to. |
| `PUT /rest/api/3/issue/{issueIdOrKey}/comment/{id}` | `write:jira-work` | `read:avatar:jira`, `read:comment.property:jira`, `read:comment:jira`, `read:group:jira`, `read:project-role:jira`, `read:project:jira`, `read:user:jira`, `write:comment:jira` | Browse projects project permission for the project that the issue containing the comment is in.; If issue-level security is configured, issue-level security permission to view the issue.; Edit all comments project permission to update any comment or Edit own comments to update comment created by the user.; If the comment has visibility restrictions, the user belongs to the group or has the role visibility is restricted to. |
| `POST /rest/api/3/issue/{issueIdOrKey}/remotelink` | `write:jira-work` | `read:issue.remote-link:jira`, `write:issue.remote-link:jira`, `write:issue:jira` | Browse projects and Link issues project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `GET /rest/api/3/issue/{issueIdOrKey}/transitions` | `read:jira-work` | `read:field-configuration:jira`, `read:issue.transition:jira`, `read:status:jira` | Permission to access Jira. |
| `POST /rest/api/3/issue/{issueIdOrKey}/transitions` | `write:jira-work` | `write:issue.property:jira`, `write:issue:jira` | Browse projects and Transition issues project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `POST /rest/api/3/issue/{issueIdOrKey}/worklog` | `write:jira-work` | `read:avatar:jira`, `read:group:jira`, `read:issue-worklog.property:jira`, `read:issue-worklog:jira`, `read:project-role:jira`, `read:user:jira`, `write:issue-worklog.property:jira`, `write:issue-worklog:jira` | Browse projects and Work on issues project permission for the project that the issue is in.; If issue-level security is configured, issue-level security permission to view the issue. |
| `POST /rest/api/3/issueLink` | `write:jira-work` | `write:comment:jira`, `write:issue-link:jira`, `write:issue:jira` | Browse project project permission for all the projects containing the issues to be linked,; Link issues project permission on the project containing the from (outward) issue,; If issue-level security is configured, issue-level security permission to view the issue.; If the comment has visibility restrictions, belongs to the group or has the role visibility is restricted to. |
| `GET /rest/api/3/issueLinkType` | `read:jira-work` | `read:issue-link-type:jira` | Browse projects project permission for a project in the site. |
| `GET /rest/api/3/issuetype` | `read:jira-work` | `read:avatar:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project:jira` | Issue types are only returned as follows:; if the user has the Administer Jira global permission, all issue types are returned.; if the user has the Browse projects project permission for one or more projects, the issue types associated with the projects the user has permission to browse are returned.; if the user is anonymous then they will be able to access projects with the Browse projects for anonymous users; if the user authentication is incorrect they will fall back to anonymous |
| `POST /rest/api/3/jql/parse` | `read:jira-work` | `read:field:jira`, `read:jql:jira`, `validate:jql:jira` | None. |
| `GET /rest/api/3/myself` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` | Permission to access Jira. |
| `GET /rest/api/3/priority/search` | `manage:jira-configuration` | - | Permission to access Jira. |
| `GET /rest/api/3/project/search` | `read:jira-work` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:user:jira` | Projects are returned only where the user has one of:; Browse Projects project permission for the project.; Administer Projects project permission for the project.; Administer Jira global permission. |
| `GET /rest/api/3/project/{projectIdOrKey}` | `read:jira-work` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:issue-type-hierarchy:jira`, `read:issue-type:jira`, `read:project-category:jira`, `read:project-version:jira`, `read:project.component:jira`, `read:project.property:jira`, `read:project:jira`, `read:user:jira` | Browse projects project permission for the project. |
| `POST /rest/api/3/search/jql` | `read:jira-work` | `read:field.default-value:jira`, `read:field.option:jira`, `read:field:jira`, `read:group:jira`, `read:issue-details:jira` | Issues are included in the response where the user has:; Browse projects project permission for the project containing the issue.; If issue-level security is configured, issue-level security permission to view the issue. |
| `GET /rest/api/3/user` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` | Browse users and groups global permission. |
| `GET /rest/api/3/user/search` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user.property:jira`, `read:user:jira` | Browse users and groups global permission. Anonymous calls or calls by users without the required permission return empty search results. |
| `GET /rest/api/3/users/search` | `read:jira-user` | `read:application-role:jira`, `read:avatar:jira`, `read:group:jira`, `read:user:jira` | Browse users and groups global permission. |
| `POST /rest/servicedeskapi/request` | `write:servicedesk-request` | `read:request:jira-service-management`, `read:user:jira`, `write:request:jira-service-management` | Permission to create requests in the specified service desk. |
| `GET /rest/servicedeskapi/request/{issueIdOrKey}` | `read:servicedesk-request` | `read:request:jira-service-management`, `read:user:jira` | Permission to access the specified service desk. |
| `POST /rest/servicedeskapi/request/{issueIdOrKey}/comment` | `write:servicedesk-request` | `read:request.comment:jira-service-management`, `read:user:jira`, `write:request.comment:jira-service-management` | User has Add Comments permission. |
| `GET /rest/servicedeskapi/servicedesk` | `read:servicedesk-request` | `read:servicedesk:jira-service-management` | Any |
| `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue` | `read:jira-work` | `read:jql:jira`, `read:queue:jira-service-management`, `read:user:jira` | service desk's Agent. |
| `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue/{queueId}/issue` | `read:jira-work` | `read:issue:jira`, `read:queue:jira-service-management`, `read:user:jira` | Service desk's agent. |
| `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype` | `read:servicedesk-request` | `read:requesttype:jira-service-management` | Permission to access the service desk. |
| `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/field` | `read:servicedesk-request` | `read:requesttype:jira-service-management` | Permission to view the Service Desk. However, hidden fields would be visible to only Service desk's Administrator. |

<!-- END GENERATED -->

## Tests

Offline, no network (a fake Jira answers every call and records it). These run in CI:

```bash
pip install -r tests/requirements.txt
python3 -m pytest tests
```

Every action has tests (`tests/test_coverage.py` fails if one does not), and each
test checks that the action only calls endpoints declared in `scopes.py`, which is
what the permission tables above are built from.

### Online tests (a real Jira Cloud site)

`tests/test_live.py` runs **every action** against a real site, and
`tests/test_live_scopes.py` checks the permission tables above against what
Atlassian actually enforces. Both skip unless credentials are present.

```bash
cp tests/.env.example tests/.env     # fill in; the file is git-ignored
python3 -m pytest tests/test_live.py -m live -rs
```

Faster: the online tests are network-bound and independent, so they run in parallel with
pytest-xdist (`-n 4`), and the scope probes already run on a thread pool
(`JIRA_LIVE_WORKERS`, default 6). On a real site that took the functional suite from about
4 minutes to about 80 seconds, and the five-token scope run from about 19 minutes to about 1:

```bash
uv run --with pytest --with pytest-xdist --with requests python -m pytest tests/test_live.py tests/test_live_scopes.py -m live -n 4 -rs
```

If you see Atlassian rate-limit (429) errors, lower `-n` or `JIRA_LIVE_WORKERS`: a probe that is
still throttled after the client's retries is reported as inconclusive, not as a mismatch.

* `JIRA_LIVE_TOKEN` must be an **unrestricted** API token: it is used for the
  functional tests and to create the fixtures the scope tests probe with.
* The tests find a project that accepts a test issue (or use
  `JIRA_LIVE_PROJECT`). Everything they create is labelled `jirav2-live-test`
  and deleted afterwards, and a sweep at the end removes leftovers of a crashed
  run. Jira Service Management tests skip when the site has no service desk.
* Credentials go in `tests/.env` or the environment, never on the command line.

### Scope tests

Atlassian has no API for creating tokens (an API token cannot create another),
so make the tokens once by hand and list them in `tests/scope_tokens.json`:

```bash
python3 scripts/scope_lab.py                    # the three standard sets, to tick in the token form
python3 scripts/scope_lab.py create_ticket      # exactly one action's scopes
python3 scripts/scope_lab.py --json set_status  # a ready scope_tokens.json entry
cp tests/scope_tokens.example.json tests/scope_tokens.json    # then edit
python3 -m pytest tests/test_live_scopes.py -m live -rs
```

For each token the test predicts, from the generated scope data, which actions
should be allowed, runs all of them, and fails on a mismatch in either direction:
**allowed-but-denied** means the README is missing a scope; **denied-but-allowed**
means it lists a scope the call does not need. Anything that fails for another
reason (a project that forbids the call) is reported as inconclusive instead.
Three tokens (health, readonly, all) validate the copy-paste sets; extra
one-action tokens pin down individual actions.

## Regenerating generated files

```bash
python3 scripts/gen_info.py     # info.json (config form, parameters)
python3 scripts/gen_scopes.py   # scope_data.py, from Atlassian's OpenAPI specs
python3 scripts/gen_docs.py     # the Permissions section above
python3 scripts/scope_lab.py    # (not generated) prints scopes for creating test tokens
```

## Releasing

Bump `VERSION` in `scripts/gen_info.py`, re-run the generators, add a section to
`release_notes.md`, commit, then tag `vX.Y.Z`. The tag must match `info.json`.
The `release` workflow builds `dist/jirav2-<version>.tgz` and attaches it to a
GitHub release.

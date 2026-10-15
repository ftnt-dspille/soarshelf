#### 1.0.2

- Fixed: the Issue Type, Issue Type ID, Request Type and Queue dropdowns came back empty once you
  picked a Project Key or Service Desk from the list. The step editor hands these dropdowns the
  picked name ("Operations (OPS)"), not its key, and the connector asked Jira for a project of that
  name, got a 404 and showed nothing. The picked name is now turned into its key or id first, as the
  action itself already did. A bare key or id works as before and costs no extra Jira call.
- These four dropdowns now also read the project list (`GET /rest/api/3/project/search`) or the
  service desk list (`GET /rest/servicedeskapi/servicedesk`); the README permission tables list it.

#### 1.0.1

- Fixed: the project, user, issue type, link type, service desk, request type,
  queue and transition dropdowns showed "[object Object]" for every entry in the
  step editor. They now list plain names such as "Operations (OPS)". The picked
  name is turned back into its key or id when the action runs; a bare key or id
  still works, and a title shared by two choices is an error that lists the values.

#### 1.0.0

- First release of the Jira v2 connector.

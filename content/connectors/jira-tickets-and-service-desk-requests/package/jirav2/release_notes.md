#### 1.0.1

- Fixed: the project, user, issue type, link type, service desk, request type,
  queue and transition dropdowns showed "[object Object]" for every entry in the
  step editor. They now list plain names such as "Operations (OPS)". The picked
  name is turned back into its key or id when the action runs; a bare key or id
  still works, and a title shared by two choices is an error that lists the values.

#### 1.0.0

- First release of the Jira v2 connector.

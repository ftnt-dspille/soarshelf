#### What's Improved
- Security alert-related actions now support API versions V1 and V2.
  - Added a new API Version parameter to support API versions V1 and V2. Also added conditional output schema support based on this parameter to the following actions
     - Get All Security Alerts
     - Get Security Alert
     - Update Security Alert
  - Added new parameters `Classification`, `Determination`, `Status`, `Created Date`, `Last Update Date`, `Severity`, `Service Source`, `Limit` and `Offset` to the `Get All Security Alerts` action based on the selected V2 API Version options.
  - Added new parameters `Classification`, `Determination`, `Status`,  to the `Update Security Alert` action based on the selected V2 API Version options.

- Added the following new actions and playbooks
  - Add Comment on Security Alert

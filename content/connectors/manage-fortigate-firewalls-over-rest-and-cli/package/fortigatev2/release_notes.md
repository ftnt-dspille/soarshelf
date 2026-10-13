## 1.0.0

First release of **FortiGate v2** (`fortigatev2`), a fork of Fortinet's `fortigate-firewall` 5.4.0
connector. It installs alongside `fortigate-firewall` rather than replacing it, and keeps every
operation and parameter, so playbooks move over by changing the connector name.

#### What's Fixed (relative to fortigate-firewall 5.4.0)
- Health check no longer fails with a 404 when the configured URL Block Policy is a web filter profile with no URL filter table attached (for example the factory `default` profile). `Block URL` now creates and attaches the URL filter table on first use.
- `Create Service` / `Update Service` work on FortiOS 7.4 and later, where the protocol `TCP/UDP/SCTP` was renamed `TCP/UDP/UDP-Lite/SCTP`.
- ICMP type/code and IP protocol number are now applied by `Create Service` / `Update Service` (FortiOS ignores them when sent with the protocol); ICMP code `0` is no longer dropped.
- `Update Service` no longer resets a service's protocol when the old default protocol value `All` is passed; `Create Service` maps it to `ALL`.
- `Block Application` now always adds applications to a rule whose action is block; previously it used the first rule of the profile even when that rule was a pass or monitor rule.
- `Create Address` accepts a subnet in CIDR (`192.0.2.0/24`) or mask form instead of always appending `/32`.
- `Update Address` honors the IP range and MAC range values entered in the form.
- `Delete Address`, `Get Addresses`, `Delete Address Group` and `Get Address Groups` with the default category now act on the IPv4 table (previously `Delete` hit the IPv6 table).
- `Create Policy` now sets the policy comment (`comments`), and no longer fails when optional fields such as security profiles are left empty.
- `Create User` / `Update User` no longer fail on empty optional fields, send `fortitoken-cloud` for FortiToken Cloud, no longer write `NoneNone` as the SMS phone, and `Update User` sends only FortiOS user fields.
- Object names and policy IDs from operation inputs are escaped as a single REST path segment, so names containing a space, `/`, `?`, `#` or `%` address the right object (previously only `/` was handled, in some operations).
- An invalid API key is now reported as `Unauthorized` instead of an empty error, and an unknown operation name raises a clean error instead of crashing.
- Corrected select defaults in the operation forms (`IPv4` → `IPv4 Address` / `IPv4 Group`, `All` → `ALL`, `IP Pool Configuration` → empty) and the duplicated `start-mac` field in `Update Address`.

## fortigate-firewall 5.4.0 (upstream)

#### What's Improved
- Added following new actions:
  - Get Entries from External Dynamic List
  - Modify Entries in External Dynamic List
- Added a new parameter `Interactive Mode` in the action Execute Command.
- The API key is now being sent in the headers instead of in the query parameters to conform to the latest FortiGate API guidelines.
- Updated output schemas of all actions.

#### What's Fixed
- Fixed an issue where the action Get System Events was failing with the following error:  
  > Log processed None% 
- Fixed an issue where the action `Block IP Address` failed if the policy name provided was an integer.

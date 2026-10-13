# Fortinet FortiGate v2 connector

`fortigatev2` manages a FortiGate firewall from FortiSOAR over the FortiOS REST API:
policies, addresses and address groups, services and service groups, local users,
IP / application / URL blocking, host quarantine, external dynamic lists, system
event logs, and CLI commands over SSH.

It is a fork of Fortinet's `fortigate-firewall` 5.4.0 connector with the bugs found by
live testing against FortiOS 7.6 fixed (see [release_notes.md](release_notes.md)). It has
its own connector name, so it installs **alongside** `fortigate-firewall` instead of
replacing it. Every operation and parameter is unchanged, so a playbook moves over by
switching its connector step to `fortigatev2`.

## Configuration

| Field | Name | Required | Description |
|---|---|---|---|
| Hostname | `address` | yes | IP address or Hostname of the Fortinet FortiGate endpoint server to connect and perform the automated operations |
| API Key | `api_key` | yes | API Key of the Fortinet FortiGate endpoint server to connect and perform the automated operations |
| Port | `port` | yes | Port number used for connecting to the Fortinet FortiGate server |
| Web Filter Profile Name | `url_block_policy` |  | Name of the Web Filter Profile that you have specified on Fortinet FortiGate for blocking or unblocking IP addresses |
| Application Control Profile Name | `app_block_policy` |  | Name of the Application Control Profile that you have specified on Fortinet FortiGate for blocking or unblocking IP addresses |
| VDOM | `vdom` |  | VDOMs, in the CSV or List format, if the VDOM mode is enabled |
| Verify SSL | `verify_ssl` |  | Specifies whether the SSL certificate for the server is to be verified |

The API key belongs to a FortiGate **REST API administrator** (System > Administrators >
Create New > REST API Admin). Give it a read-write admin profile and add the FortiSOAR
appliance's address to its trusted hosts.

*Web Filter Profile Name* and *Application Control Profile Name* name the profiles that the
URL and application blocking operations edit. Both are only needed for those operations.
A web filter profile with no URL filter table attached yet is fine; `Block URL`
creates and attaches one on first use.

## Operations

| Operation | Name | Category |
|---|---|---|
| Block Application | `block_applications` | containment |
| Block IP Address | `block_ip_new` | containment |
| Block IP Address (Deprecated) | `block_ip` | containment |
| Block URL | `block_url` | containment |
| Quarantine Host | `quarantine_host` | containment |
| Unquarantine Host | `unquarantine_host` | containment |
| Create Address | `create_address` | investigation |
| Create Address Group | `create_address_group` | investigation |
| Create Policy | `create_policy` | investigation |
| Create Service | `create_firewall_service` | investigation |
| Create Service Group | `create_service_group` | investigation |
| Create User | `create_user` | investigation |
| Delete Address | `delete_address` | investigation |
| Delete Address Group | `delete_address_group` | investigation |
| Delete Policy | `delete_policy` | investigation |
| Delete Service | `delete_firewall_service` | investigation |
| Delete Service Group | `delete_service_group` | investigation |
| Delete User | `delete_user` | investigation |
| Execute Command | `execute_command` | investigation |
| Execute API Request | `execute_api_request` | miscellaneous |
| Get Address Groups | `get_address_groups` | investigation |
| Get Addresses | `get_addresses` | investigation |
| Get Applications Detail | `get_list_of_applications` | investigation |
| Get Blocked Applications | `get_blocked_applications` | investigation |
| Get Blocked IP Addresses | `get_blocked_ip` | investigation |
| Get Blocked URLs | `get_blocked_urls` | investigation |
| Get Country Names | `get_country_names` | investigation |
| Get Entries from External Dynamic List | `get_entries_from_edl` | investigation |
| Get List of Policies | `get_list_of_policies` | investigation |
| Get Quarantine Hosts | `get_quarantine_hosts` | investigation |
| Get Service Groups | `get_service_groups` | investigation |
| Get Services | `get_firewall_services` | investigation |
| Get System Events | `get_system_events` | investigation |
| Get User Last Login Details | `get_user_list_login_details` | investigation |
| Get Users | `get_users` | investigation |
| Modify Entries in External Dynamic List | `modify_entries_in_edl` | investigation |
| Update Address | `update_address` | investigation |
| Update Address Group | `update_address_group` | investigation |
| Update Policy | `update_policy` | investigation |
| Update Service | `update_firewall_service` | investigation |
| Update Service Group | `update_service_group` | investigation |
| Update User | `update_user` | investigation |
| Unblock Application | `unblock_applications` | remediation |
| Unblock IP Address | `unblock_ip` | remediation |
| Unblock URL | `unblock_url` | remediation |

`Execute API Request` calls any FortiOS REST endpoint (GET, POST, PUT, PATCH, DELETE) on the configured FortiGate with the configured API key; a full URL is refused so the key never leaves that server.

`Execute Command` connects over SSH with the username/password (or private key) given
in the operation, not the API key. It accepts the FortiGate's SSH host key without
checking it (paramiko `AutoAddPolicy`, unchanged from `fortigate-firewall`), so use it only
over a network path you trust between FortiSOAR and the FortiGate.

## FortiOS behavior worth knowing

- **External dynamic lists:** `Modify Entries in External Dynamic List` needs an external
  resource with `update-method push`. A newly created list rejects updates with
  "External resource has not been loaded" for roughly 10 seconds, and pushed entries show
  up in `Get Entries from External Dynamic List` a few seconds after the push.
- **Deleting users:** FortiOS refuses to delete a local user that is still a member of a
  user group. Remove it from its groups first (`Update User` > *User Groups to Remove*).
- **Service protocol `ALL`:** FortiOS accepts `ALL` for a custom service over REST but
  stores its default `TCP/UDP/UDP-Lite/SCTP` protocol.

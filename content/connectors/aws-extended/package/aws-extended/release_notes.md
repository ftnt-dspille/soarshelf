#### 1.0.0

Initial release. A clone of the Fortinet **AWS EC2** connector (`aws` 3.1.2) with
34 operations -- the stock 32 plus two -- that installs alongside the stock
connector and takes its own configuration.

##### What's added

- **`generic_action`** -- call any boto3 *client* method on any AWS service.
  Covers the gaps in the 32 curated operations: there is no list-instances
  (`describe_instance` demands a concrete ID), no describe-subnets, and no
  describe-snapshots, so a playbook that snapshots a volume has no shipped way
  to confirm the snapshot exists on AWS. Optional `paginate` walks every page
  and merges results; optional `read_only` refuses anything that is not a
  `describe_`/`get_`/`list_`/`search_`/`lookup_`/`batch_get_`.
- **`generic_resource_action`** -- call a method on a boto3 *resource* object,
  for the operations only reachable that way (the vendor's own `revoke_egress`
  goes through `ec2.SecurityGroup(...)`).

##### What's fixed

- **`IpProtocol: "-1"` is reachable again.** FortiSOAR's parameter layer retypes
  numeric-looking strings to int before the connector sees them, so `"-1"`
  arrives at boto3 as int `-1` and is rejected by parameter validation. `"tcp"`
  works and `"6"` fails identically, which places the fault in the platform
  rather than the connector -- and the vendor's own placeholder text documents
  `"IpProtocol": "-1"`, so the shipped example is the case that cannot work.

  It matters because `-1` means *all protocols*, and revoking the default
  allow-all egress rule is what turns a security group into a quarantine group.
  Without it a "contained" instance still has open egress.

  Both new operations take `payload` as a JSON **string**, which is the fix
  rather than an accident: the platform cannot retype what it never parsed. The
  four security-group rule operations (`authorize_ingress`, `authorize_egress`,
  `revoke_ingress`, `revoke_egress`) are wrapped so `IpProtocol` is coerced back
  to a string. No vendor function body is edited.

##### Notes

`cs_approved` is false, so the appliance needs the custom-connector gate on
before this will import.

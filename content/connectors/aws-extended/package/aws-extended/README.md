# AWS EC2 (Extended)

A clone of the Fortinet **AWS EC2** connector (`aws` 3.1.2) with two additions.
It installs alongside the stock connector and needs its own configuration.

Live on FortiSOAR 8.0.0: 34 operations, the stock 32 plus two.

## Why it exists

**1. The stock connector cannot send a numeric IpProtocol.** FortiSOAR's
parameter layer retypes numeric-looking strings to int before the connector
sees them, so an `ip_permissions` entry of `{"IpProtocol": "-1"}` reaches boto3
as int `-1` and is rejected by parameter validation:

```
Invalid type for parameter IpPermissions[0].IpProtocol, value: -1,
type: <class 'int'>, valid types: <class 'str'>
```

`"tcp"` works and `"6"` fails identically to `"-1"`, which places the fault in
the platform, not the connector. The vendor's own placeholder text documents
`"IpProtocol": "-1"` -- the shipped example is the case that cannot work.

This matters because **`-1` means "all protocols"**, and revoking the default
allow-all egress rule is what turns a security group into a quarantine group.
Without it, a "contained" instance still has open egress, and containment that
leaves C2 reachable has contained nothing.

**2. There are only 32 curated operations.** There is no list-instances
(`describe_instance` demands a concrete ID), no describe-subnets, no
describe-snapshots, and no IAM key deactivation. That last gap is not academic:
a containment playbook that snapshots a volume and then wants to confirm the
snapshot exists on AWS has no shipped operation to do it with.

## What it adds

| Operation | Purpose |
|---|---|
| `generic_action` | Call any boto3 **client** method on any AWS service. Optional `paginate` walks every page and merges results; optional `read_only` refuses anything that is not a `describe_`/`get_`/`list_`/`search_`/`lookup_`/`batch_get_`. |
| `generic_resource_action` | Call a method on a boto3 **resource** object, for the operations only reachable that way (the vendor's own `revoke_egress` goes through `ec2.SecurityGroup(...)`). |

Both take `payload` as a **JSON string**. That is the fix, not an accident: the
platform cannot retype values it never parsed, so `"-1"` stays a string and an
all-digit identifier stays a string.

The four security-group rule operations (`authorize_ingress`, `authorize_egress`,
`revoke_ingress`, `revoke_egress`) are wrapped so `IpProtocol` is coerced back to
a string. Vendor function bodies are not edited.

## Install

Download the `.tgz` from
[Releases](https://github.com/ftnt-dspille/connector-aws-extended/releases) and
import it from **Content Hub -> Manage -> Add Connector**.

The appliance must have the custom-connector gate on, since this is
`cs_approved: false`:

```python
client.system_settings.set_development_mode(connectors=True)
```

## Configuration

The clone needs its own configuration -- the stock connector's credentials are
encrypted on the appliance and cannot be copied through the API. Same fields as
the stock connector: configuration type, region, access key ID, secret access
key. Keep credentials out of this repository.

`iam-policy.json` in the repository root is a least-privilege policy covering
read, snapshot, security-group and instance-attribute actions. Two actions are
worth calling out because they are the ones a containment workflow silently
lacks and then fails on with `UnauthorizedOperation`:

| Operation | IAM action |
|---|---|
| `snapshot_volume` | `ec2:CreateSnapshot` |
| `add_security_group_to_instance` | `ec2:ModifyInstanceAttribute` |

## Rebuilding against a newer vendor release

`build.py` and `overlay/` are kept in the repository root so this can be rebuilt
when the vendor ships a new AWS connector version, rather than hand-patched.
The overlay is one module plus a short footer appended to `operations.py` that
registers the new operations and wraps the four rule operations; no vendor
function body is edited.

```bash
python3 build.py --from-appliance <pyfsr-alias>   # fetch vendor source, then build
python3 build.py --from-tarball ./aws_3_1_2.tgz
python3 build.py                                   # rebuild from the cached vendor copy
python3 build.py --install <pyfsr-alias>           # build and install
```

## Packaging rules the importer enforces but never reports

Every failure below produces the same message, **even when no connector of that
name exists**:

```
Connector with same name is already active.
```

It is a lie. `SolutionPackController.php` wraps the whole install in
`catch (BadRequestHttpException | \Exception $e)` and rethrows that one string,
discarding the real cause.

The rule that cost the most time: **the package folder must be named exactly
`info.json`'s `name`.** `aws-extended`, not `aws-extended_1_0_0`. The
`<name>_<version>` form (`aws_3_1_2`) is the appliance's *installed* layout, not
the package layout.

`pyfsr.validate_connector_source()` checks this locally, and `pack_connector()`
refuses to build a package that would fail:

```python
from pyfsr import validate_connector_source
validate_connector_source("aws-extended", strict=False)  # [] when clean
```

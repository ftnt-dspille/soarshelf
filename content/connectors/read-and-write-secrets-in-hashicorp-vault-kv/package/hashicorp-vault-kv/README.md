# HashiCorp Vault KV - FortiSOAR connector

A FortiSOAR connector for the HashiCorp Vault KV version 2 secrets engine,
using token authentication. Its raison d'etre is the WRITE: the official
hashicorp-vault connector can only read credentials for FortiSOAR's own
credentials store, while rotation flows need to push a fresh secret INTO
Vault. `write_secret` creates a new KV v2 version, so downstream consumers
watching version changes (for example the lab's `vault-watch.sh`) pick the
new value up automatically.

Operations: get health (token lookup-self), read secret (latest or a
specific version), write secret (new version; replaces all fields - resend
what you want kept), list secrets, delete latest version, and execute API
request: any Vault HTTP API endpoint (GET, POST, PUT, PATCH, DELETE, LIST) called
with the configured token; a full URL is refused so the token never leaves
the configured server.

Since 1.2.0 it can also update a secret without reading it:

- **Update Secret Fields** (`patch_secret`): an HTTP PATCH that changes only
  the fields you send, retried on network and server errors.
- **Get / Update Secret Metadata** (`read_metadata`, `patch_metadata`): the
  secret's custom metadata tags, never its value.
- **Find Secrets by Metadata** (`find_secrets_by_metadata`): Vault cannot
  search, so this walks a folder (and its sub-folders) and reads each
  secret's metadata to find the ones carrying a tag, for example
  `faig_key_id=<uuid>`.

Together they let a rotation playbook run on a token that can find and
update secrets but never read one:

```hcl
path "secret/metadata/apps/*" { capabilities = ["read", "list", "patch"] }
path "secret/metadata/apps"   { capabilities = ["list"] }
path "secret/data/apps/*"     { capabilities = ["patch"] }
```

The live suite proves this against a real Vault: with that policy, find,
patch and metadata updates work, and read, write and any path outside the
folder are refused (403).

## Tests

```
pytest tests/test_offline.py       # loopback fake Vault, no network
cp tests/.env.example tests/.env   # or reuse ../fortinet-fortiaigate/tests/.env
pytest tests/test_live.py -m live  # real Vault; writes touch only the
                                    # disposable lab/connector-test path
```

## Packaging

`scripts/package.sh` builds `dist/hashicorp-vault-kv-<version>.tgz`
(single top-level `hashicorp-vault-kv/` directory). Prefers git-tracked
files, falls back to the working tree excluding tests / scripts / dist /
caches.

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

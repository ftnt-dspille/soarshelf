# hashicorp-vault-kv release notes

## 1.0.1

- Parameter description examples use generic secret paths (no lab-specific
  defaults); no functional changes.

## 1.0.0

- KV version 2 secrets engine operations: read_secret, write_secret,
  list_secrets, delete_secret, plus get_health for the Vault server.
- Token authentication; KV v2 paths resolved as mount + path (the API's
  data/metadata prefixing is handled internally).
- write_secret performs a KV v2 write (a NEW secret version), so playbooks
  can push rotated credentials non-destructively; delete_secret removes
  versions, and read_secret exposes version metadata (created_time,
  destroyed, deleted) alongside the data.
- Typed client (VaultClient), stdlib fake server for the offline suite, and
  opt-in live tests against a real Vault (VAULT_ADDR / VAULT_TOKEN).

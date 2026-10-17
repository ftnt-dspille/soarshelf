# hashicorp-vault-kv release notes

## 1.2.1

- A secret path with a `.` or `..` segment (also percent-encoded), a backslash,
  `?` or `#` is refused before any call. Paths now come from playbook input (an
  onboarding API body, a folder to search), and none of these may reach another
  part of the Vault API with the configured token. Applies to every operation
  that takes a path.

## 1.2.0

- New operation **Update Secret Fields** (`patch_secret`): change only the
  given fields of an existing secret with an HTTP PATCH (a new version; the
  other fields are kept). Needs the `patch` capability, not `read`. Retried on
  network and server errors (default 3 extra attempts); a 403 or a missing
  secret is not retried, and a patch never creates a secret.
- New operations **Get Secret Metadata** and **Update Secret Metadata**: read
  and merge a secret's custom metadata tags (a null value removes a tag)
  without reading its value.
- New operation **Find Secrets by Metadata**: walks a folder and its
  sub-folders, reads each secret's metadata and returns the ones carrying a
  tag. Given values, sorts them into matches (exactly one secret), unmatched
  and conflicts (several). A secret whose latest version is deleted is not a
  match. Stops past Max Secrets (default 1000).
- **Write Secret** takes **Create Only**: Vault check-and-set 0, so the write is
  refused if any secret exists at the path. **Get Secret Metadata** takes
  **Missing Is OK** and answers `exists: false` for a free path.
- A 403 now says the policy may not allow the call on that path, not only
  that the token was rejected.

## 1.1.0

- New operation **Execute API Request**: call any Vault HTTP API endpoint
  (GET, POST, PUT, PATCH, DELETE and LIST) with the configured token. A full
  URL, a `..` segment or a backslash is refused, so the token only goes to the
  configured server.

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

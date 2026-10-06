# Security

## Threats and controls

| Threat | Control | Where |
|---|---|---|
| Malware / code execution | Only playbook JSON and pack zips accepted. Connector code is never hosted (manifest + source link only). Packs with bundled installers or other non-JSON files are blocked (README, LICENSE and a docs folder are ignored, never published). Code steps force human review. Downloads are forced inactive. | `intake.py`, `process.py`, `policy.py`, `sanitize.py` |
| Hostile archives | Path traversal, symlinks, encryption, >100× compression ratio, >2000 entries, >100 MB unpacked all rejected. Archive read in memory, never extracted to disk. | `intake.py` |
| Serving attacker bytes | Every download is re-serialized from parsed content; the uploaded file is never served. `/downloads/*` is `Content-Disposition: attachment` with a sandbox CSP. | `process.py`, `site/static/_headers` |
| Leaked credentials / environment data | Owners, people/team IRIs, connector config links, global variable values and sample data stripped. Token formats and literal secrets block; IPs, emails, internal hosts warn → review. | `sanitize.py`, `checks/secrets.py` |
| Copyright / trademark | Official-content UUID and structure fingerprints, vendor copyright notices and endorsement claims block. Hub snapshot keeps facts only. No vendor branding on the site. | `checks/brand.py`, `hubindex.py` |
| XSS via contributor text | Markdown: raw HTML escaped, links limited to http(s)/mailto/relative, images dropped, DOMPurify in the browser. Step arguments rendered as text only. CSP `script-src 'self'` plus SvelteKit hashes, no third-party origins (fonts self-hosted). | `site/src/lib/markdown.ts`, `svelte.config.js` |
| Clickjacking / sniffing | `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, HSTS, restrictive Permissions-Policy. | `site/static/_headers` |
| Malicious PR weakening the checks | CODEOWNERS on pipeline, CI, policy and headers. CI token is read-only. Actions pinned to commit SHAs. | `.github/` |
| Vulnerable dependencies | `pip-audit` and `pnpm audit --prod` in CI. | `ci.yml` |
| Spam / abuse | GitHub login, account ≥ 30 days, Turnstile on every upload, 3/day for new contributors (20 otherwise) enforced in the same SQL statement that reserves the upload (parallel requests can't race past it), sha256 duplicate rejection, re-uploads of playbooks already on the site rejected (by workflow uuid or step structure, standalone or inside a published pack, for any upload type), a strike for each secret/copyright rejection and suspension at 2. Reporting needs the same account age and standing; reports open an issue at 3. | `worker/src/trust.ts`, `submissions.ts`, `reports.ts`, `pipeline/.../submission.py` |
| Raw uploads becoming public | Uploads go to a private R2 bucket (30-day expiry) and are only read by the Action through the token-protected internal API. Only the pipeline's cleaned output is committed. | `worker/src/submissions.ts`, `internal.ts`, `submission.yml` |
| Session theft / CSRF | Stateless HMAC-signed session cookie (HttpOnly, Secure, SameSite=Lax, 7 days). Every state-changing route checks `Origin`. The GitHub access token is used once at sign-in and never stored. OAuth `state` in a signed cookie; post-login redirect limited to same-site paths. | `worker/src/session.ts`, `auth.ts`, `http.ts` |
| Workflow injection | Only the submission id crosses into GitHub (validated `^[0-9a-f]{32}$`); all other data is fetched by the Action and handled as files. Event fields reach `run:` only through `env:`. PR bodies drop markup and break @mentions, `#` references and anything GitHub would autolink. Report reasons reach issues only inside a code fence longer than any backtick run they contain. | `.github/workflows/submission*.yml`, `pipeline/.../submission.py` |
| Untrusted upload on a runner with write access | The `check` job parses the upload with no write token; the `publish` job holds the App token but only receives the cleaned item, and re-validates its paths, slug and type before committing. | `submission.yml` |
| Impersonation / item takeover | Uploads are credited to the authenticated GitHub login. For pull requests, the `author-gate` (pull_request_target, base-branch code, PR files read with `git show`) requires every changed item to be credited to the PR author on both base and head. Logins can be renamed and re-registered, so trust tiers in `contributors.yaml` are bound to the numeric GitHub id, and items record `author_id`: a reclaimed login gets no tier and can't edit the old owner's items. | `.github/workflows/author-gate.yml`, `pipeline/.../authors.py`, `build.py`, `worker/src/trust.ts` |
| Spoofed status updates | `submission-closed` only acts on PRs opened by the submission App from this repository. The internal API checks a ≥32-character bearer token in constant time and bounds and validates every field it stores. | `submission-closed.yml`, `worker/src/internal.ts` |
| Long-lived credentials | The Worker and Action use GitHub App installation tokens (1 hour, one repository) instead of personal access tokens. | `worker/src/github.ts` |

Known limit: the secret scanner is pattern-based and can't recognise things
like customer names in free text. That is why new contributors are always
reviewed by a person.

Dev-only sign-in (`DEV_LOGIN`) needs both the variable and a localhost
request; it must never be set in production.

## Repository settings to enable

- Branch protection on `main`: require PR, 1 approval, **code owner review**, passing `ci`, no force pushes.
- Actions: "Require approval for all outside collaborators" for workflows from forks.
- Dependabot alerts and security updates; secret scanning with push protection.
- Private vulnerability reporting.

## Reporting

Report a security problem or unwanted content through a private
vulnerability report on the repository, not a public issue.

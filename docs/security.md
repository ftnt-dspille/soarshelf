# Security

## Threats and controls

| Threat | Control | Where |
|---|---|---|
| Malware / code execution | Only playbook JSON and pack zips accepted. Connector code is never hosted (manifest + source link only). Packs with bundled installers are blocked. Code steps force human review. Downloads are forced inactive. | `intake.py`, `process.py`, `policy.py`, `sanitize.py` |
| Hostile archives | Path traversal, symlinks, encryption, >100× compression ratio, >2000 entries, >100 MB unpacked all rejected. Archive read in memory, never extracted to disk. | `intake.py` |
| Serving attacker bytes | Every download is re-serialized from parsed content; the uploaded file is never served. `/downloads/*` is `Content-Disposition: attachment` with a sandbox CSP. | `process.py`, `site/static/_headers` |
| Leaked credentials / environment data | Owners, people/team IRIs, connector config links, global variable values and sample data stripped. Token formats and literal secrets block; IPs, emails, internal hosts warn → review. | `sanitize.py`, `checks/secrets.py` |
| Copyright / trademark | Official-content UUID and structure fingerprints, vendor copyright notices and endorsement claims block. Hub snapshot keeps facts only. No vendor branding on the site. | `checks/brand.py`, `hubindex.py` |
| XSS via contributor text | Markdown: raw HTML escaped, links limited to http(s)/mailto/relative, images dropped, DOMPurify in the browser. Step arguments rendered as text only. CSP `script-src 'self'` plus SvelteKit hashes, no third-party origins (fonts self-hosted). | `site/src/lib/markdown.ts`, `svelte.config.js` |
| Clickjacking / sniffing | `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, HSTS, restrictive Permissions-Policy. | `site/static/_headers` |
| Malicious PR weakening the checks | CODEOWNERS on pipeline, CI, policy and headers. CI token is read-only. Actions pinned to commit SHAs. | `.github/` |
| Vulnerable dependencies | `pip-audit` and `pnpm audit --prod` in CI. | `ci.yml` |
| Spam / abuse (phase 2) | GitHub login, account ≥ 30 days, Turnstile, per-tier rate limits, duplicate-hash rejection, strikes, report-to-unpublish. | `docs/plan.md` |

Known limit: the secret scanner is pattern-based and can't recognise things
like customer names in free text. That is why new contributors are always
reviewed by a person.

## Repository settings to enable

- Branch protection on `main`: require PR, 1 approval, **code owner review**, passing `ci`, no force pushes.
- Actions: "Require approval for all outside collaborators" for workflows from forks.
- Dependabot alerts and security updates; secret scanning with push protection.
- Private vulnerability reporting.

## Reporting

Report a security problem or unwanted content through a private
vulnerability report on the repository, not a public issue.

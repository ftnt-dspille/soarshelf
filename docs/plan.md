# soarshelf plan

A community site for sharing SOAR playbooks, solution packs and connectors:
browse by use case and connector, see each playbook as a graph, know exactly
what it needs before downloading, and download a file that has been checked
and cleaned.

Independent project, not affiliated with the platform vendor.

## Principles

1. **Never serve an upload.** Every download is rebuilt by the pipeline from
   parsed content. Raw uploads live only in quarantine.
2. **No server to run.** A static site plus serverless functions keeps cost
   near zero and the attack surface small.
3. **Checks are code, policy is one file.** `pipeline/src/soarshelf/policy.py`
   is the whole publish rule set.
4. **Facts, not copies.** From the vendor's Content Hub we keep only names,
   versions and operation names. No descriptions, icons, docs or code.

## Architecture

```
          browser ──── static site (SvelteKit, Cloudflare Pages)
             │              ▲ data/*.json, downloads/*  (built by pipeline)
             │ upload       │
             ▼              │ merge to main → build → deploy
   Worker /api/submit ──► R2 quarantine ──► GitHub Action: soarshelf check
   (GitHub OAuth, Turnstile,                  │
    rate limit, size cap)          publish ◄──┴──► review queue (PR + label)
                                   (auto-merge)      (maintainer approves)
```

| Piece | Service | Cost |
|---|---|---|
| Site hosting + CDN | Cloudflare Pages | free |
| Upload API | Cloudflare Workers | free (100k req/day), $5/mo beyond |
| Quarantine storage | Cloudflare R2 | free to 10 GB, no egress fees |
| Contributors, strikes, rate limits | Cloudflare D1 | free tier |
| Bot protection | Turnstile | free |
| Checks + build | GitHub Actions | free on public repos |
| Domain | registrar | ~$12-60/yr |

## Upload pipeline (implemented: `pipeline/`)

| Stage | Module | Blocks on |
|---|---|---|
| Intake | `intake.py` | wrong type, >2 MB JSON / >20 MB zip, bad JSON, >64 nesting, zip traversal / symlink / encryption / bomb ratio / >2000 entries, config exports (not packs) |
| Sanitize | `sanitize.py` | - (strips owners, version history, timestamps, people/team IRIs, connector config links, global variable values, sample data; forces `isActive: false`) |
| Secrets | `checks/secrets.py` | private keys, cloud/API tokens, JWTs, bearer tokens, URL credentials, literal values in password/key/token fields. Warns on internal/public IPs, real emails, internal hostnames, random-looking strings |
| Structure | `checks/structure.py` | empty, >200 playbooks, >500 steps. Warns on broken routes, unknown step types, **code steps** |
| Brand | `checks/brand.py` | "official/certified by" claims, vendor copyright notices, re-uploads of official content (UUID hash or step-structure hash). Warns on titles that lead with a product name |
| Dependencies | `deps.py` | - (connector hub status, non-core modules, missing referenced playbooks) |
| Setup guide | `setup_guide.py` | - (generated per item from the above) |
| Policy | `policy.py` | trust tiers, below |

### Trust tiers

| Tier | Earned by | Auto-publishes when |
|---|---|---|
| new | default; GitHub account ≥ 30 days old to upload at all | never - always reviewed |
| contributor | 3 approved items, no strikes | no warnings |
| trusted | promoted by a maintainer | no secret/environment/provenance warnings |
| maintainer | runs the site | no blocking findings |

Always reviewed regardless of tier (except maintainers): **connectors** and
anything with **code steps**. Connectors are listed with their manifest and a
link to their source repository; their code is never hosted here.

Abuse controls (phase 2): 3 uploads/day for `new`, 20 for others; duplicate
content hash rejected; 3 reports auto-unpublish pending review; a strike for
any rejected secret or copyright upload, 2 strikes suspends uploads.

## Content Hub sync (implemented)

`soarshelf hub-index` reduces the public `content-hub.json` catalog to
`pipeline/data/hub-index.json` (716 connectors, 132 packs at first snapshot).
A weekly Action refreshes it and opens a PR. Each item gets a status:

- **complete** - every connector and operation is on the hub
- **version-mismatch** - uses an operation or version the hub doesn't list
- **needs-custom** - uses a connector that isn't on the hub

`official-fingerprints.json` hashes collection/playbook UUIDs and step
structures from official solution packs. Built locally from unpacked packs
(76 of 132 so far). **TODO:** fetch every pack zip in CI so all 132 are covered.

## Phases

### Phase 1 - browse site + checks (this commit)
- [x] Pipeline: intake, sanitize, checks, deps, setup guide, policy, build, CLI
- [x] Hub snapshot from the public catalog; official-content fingerprints
- [x] Seed content (9 playbooks, maintainer-authored)
- [x] Site: home, browse (facets + search), item page (graph viewer, setup, deps, checks), guide, about
- [x] CI: tests, content build, site build
- [ ] Pick the name and domain; set `SITE` in `site/src/lib/config.ts` and `SITE_NAME` in the pipeline
- [ ] Create the GitHub repo and Cloudflare Pages project; deploy

### Phase 2 - in-browser uploads
- [x] Worker: GitHub sign-in, Turnstile, size caps, daily limits, account-age gate, strikes (`worker/`)
- [x] Private R2 quarantine; the Action reads it through the internal API
- [x] Submission Action: check job (no write access) and publish job (App token, auto-merge when policy allows)
- [x] Re-uploads of items already on the site are rejected
- [x] Status sync when a submission PR is merged or closed
- [x] Upload page, my-submissions pages, report button (`site/`)
- [ ] Deploy: GitHub App, OAuth app, D1, R2, Worker route, Pages ([deploy.md](deploy.md))
- [ ] Updating your own item from the upload page (today: a PR)

### Phase 3 - community features
- [ ] Versions per item and changelog
- [ ] "Works on my box" confirmations (signed-in, per platform version)
- [ ] Collections / curated lists
- [ ] Optional: pull an item straight into a platform instance via its API (client-side, user's own credentials, never sent to us)

## Open decisions

- **Name / domain.** Candidates: soarshelf.io, openplaybooks.io, runbook.exchange, playbookdepot.dev. Check availability and trademark search before buying.
- **Content licence.** MIT assumed for submissions. Alternative: CC0 for maximum reuse.
- **Employer policy.** Check outside-activity / IP rules before launch.

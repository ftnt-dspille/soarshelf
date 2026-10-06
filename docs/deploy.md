# Deploying

One-time setup, roughly an hour. Everything below fits the free tiers.
Replace `soarshelf.example` with your domain and `OWNER` with your GitHub
account or organisation.

## 1. GitHub repository

1. Create `OWNER/soarshelf` (public) and push `main`.
2. **Settings › General:** allow auto-merge; allow squash merging only.
3. **Settings › Rules › Rulesets**, a rule for `main`:
   - require a pull request with 1 approval and **Code Owner review**
   - required status checks: `build`, `worker`, `author-gate / verify`
   - block force pushes and deletions
4. **Settings › Actions › General:** "Require approval for all outside collaborators".
5. **Settings › Code security:** Dependabot alerts + security updates, secret scanning with push protection, private vulnerability reporting.
6. Labels: `auto-publish`, `needs-review`, `reported`, `hub-refresh`.
7. Update `.github/CODEOWNERS` with your handle, and `content/contributors.yaml`
   (`login: {trust: maintainer, id: <gh api users/<login> --jq .id>}`; an entry without the id grants nothing).

## 2. GitHub App: the submission bot

**Settings › Developer settings › GitHub Apps › New.**

- Name: e.g. `soarshelf-bot`. Webhook: off.
- Repository permissions: **Contents: read & write**, **Pull requests: read & write**, **Issues: read & write**, Metadata: read.
- Install it on `OWNER/soarshelf` only.
- Note the App ID and the installation ID (from the installation URL).
- Generate a private key and convert it to PKCS#8 for the Worker:
  `openssl pkcs8 -topk8 -nocrypt -in app.pem -out app.pkcs8.pem`

Repository **variables**: `SITE_ORIGIN=https://soarshelf.example`,
`SUBMISSION_APP_ID=<app id>`, `SUBMISSION_BOT=soarshelf-bot[bot]`.
Repository **secrets**: `SUBMISSION_APP_KEY` (the original PEM is fine
for Actions), `INTERNAL_TOKEN` (`openssl rand -hex 32`).

Allow the App to bypass nothing. Its PRs go through the same rules; auto-merge
lands them once checks pass and the rules allow it. For auto-publish to merge
without a human, add the App as a bypass actor for the "required approval"
rule only, never for status checks.

## 3. GitHub OAuth App: sign-in

**Developer settings › OAuth Apps › New.** Callback URL:
`https://soarshelf.example/api/auth/callback`. Note the client ID and secret.

## 4. Cloudflare

```bash
cd worker
pnpm exec wrangler d1 create soarshelf          # paste database_id into wrangler.toml
pnpm exec wrangler r2 bucket create soarshelf-quarantine
pnpm exec wrangler r2 bucket lifecycle add soarshelf-quarantine expire-30d --expire-days 30
pnpm run migrate:remote
```

`wrangler.toml` `[vars]`: `SITE_ORIGIN`, `REPO`, `GITHUB_CLIENT_ID`,
`GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`. The Worker has no public URL
(`workers_dev = false`); the site reaches it through a service binding (below).

```bash
for s in GITHUB_CLIENT_SECRET GITHUB_APP_PRIVATE_KEY SESSION_SECRET TURNSTILE_SECRET INTERNAL_TOKEN; do
  pnpm exec wrangler secret put "$s"
done
pnpm run deploy
```

`SESSION_SECRET`: `openssl rand -hex 32`. `INTERNAL_TOKEN`: the same value
as the GitHub secret. **Never set `DEV_LOGIN` in production.**

**Turnstile:** create a widget for `soarshelf.example` (managed mode). The
secret goes to the Worker; the site key goes to the site build as
`PUBLIC_TURNSTILE_SITE_KEY`.

**Pages:** create a Pages project named `soarshelf` with **direct upload**
(no Git connection): CI builds and checks the site, then deploys that exact
build. `site/wrangler.toml` binds the Worker as `API`, and
`site/functions/api/[[path]].ts` forwards `/api/*` to it, so the API lives on
the site's own origin. Static pages never invoke the function.

**Domain:** the domain's DNS can stay where it is. Add the custom domain
(e.g. `soarshelf.example.com`) to the Pages project, then create
`CNAME soarshelf -> soarshelf.pages.dev` at your DNS provider.

For CI, create an API token with *Cloudflare Pages: Edit* and add:
secret `CLOUDFLARE_API_TOKEN`, variables `CLOUDFLARE_ACCOUNT_ID` and
`TURNSTILE_SITE_KEY`. The deploy step stays skipped until
`CLOUDFLARE_ACCOUNT_ID` is set.

## 5. Smoke test

1. Visit `/submit`, sign in with GitHub, upload a playbook.
2. The **submission** Action runs; `/me/<id>` moves to "In review".
3. Merge the PR; the status becomes "Published" and the Pages build puts the item live.
4. Upload a file containing a fake key (`AKIA` + 16 capitals): it's rejected and the account gets a strike.

## Local development

```bash
cp worker/.dev.vars.example worker/.dev.vars
(cd worker && pnpm install && pnpm run migrate:local && pnpm dev)      # API on :8787
(cd site && pnpm dev)                                                   # site on :5173, /api proxied
scripts/simulate-submission.sh <id>      # stands in for the submission Action
```

Or `MOCK_API=1 pnpm dev` in `site/` for the UI alone, with no Worker.

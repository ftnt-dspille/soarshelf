# Upload API (phase 2)

A Cloudflare Worker served on the site's own origin under `/api/*`, so the
site's CSP (`connect-src 'self'`) and same-site session cookies just work.
Types are mirrored in `site/src/lib/api.ts`.

## Flow

```
browser ──POST /api/submissions──► Worker ──► R2 quarantine (private)
                                     │
                                     └─ repository_dispatch {id} ──► GitHub Action
                                                                     │ GET  /api/internal/submissions/:id/file
                                                                     │ soarshelf intake-submission
                                                                     │ open PR (auto-merge if policy allows)
                                                                     └ POST /api/internal/submissions/:id/result
browser ──GET /api/submissions/:id──► status + check report
```

Only the submission **id** crosses into GitHub in the dispatch payload. The
Action fetches everything else from the Worker with a shared secret, so no
user-controlled text is ever interpolated into a workflow.

## Auth

| Route | |
|---|---|
| `GET /api/auth/login?next=/submit` | Redirect to GitHub OAuth (scope: none; public profile only). Sets a short-lived `state` cookie. |
| `GET /api/auth/callback` | Exchanges the code, reads the profile, sets the `session` cookie (HMAC-signed, HttpOnly, Secure, SameSite=Lax, 7 days), redirects to `next`. |
| `POST /api/auth/logout` | Clears the session. |
| `GET /api/me` | `Me` or `401`. |

```ts
interface Me {
  login: string;
  avatarUrl: string;
  trust: 'new' | 'contributor' | 'trusted' | 'maintainer';
  canUpload: boolean;
  reason: string | null;           // why not, e.g. "GitHub account must be 30 days old"
  uploadsToday: number;
  dailyLimit: number;
}
```

## Submissions

`POST /api/submissions`: `multipart/form-data`, same-origin only (checked via `Origin`).

| Field | |
|---|---|
| `file` | `.json` ≤ 2 MB or `.zip` ≤ 20 MB |
| `meta` | JSON string, `SubmissionMeta` |
| `turnstile` | Turnstile token |

```ts
interface SubmissionMeta {
  title: string;                   // 4-80 chars
  summary: string;                 // 10-160 chars
  description: string;             // markdown, ≤ 5000 chars
  useCases: string[];              // 1-3 ids from index.useCases
  tags: string[];                  // ≤ 8, each [a-z0-9-]{2,24}
  version: string;                 // semver-ish
  minVersion: string | null;
  source: string | null;           // https URL, required for connectors
  rightsConfirmed: true;           // "I wrote this or have the right to share it under MIT"
}
```

Responses: `201 { id }`, `400 { error }` (validation), `401`, `403 { error }`
(account too new / suspended), `409 { error, id }` (identical file already
submitted), `413`, `429 { error }` (daily limit).

`GET /api/submissions`: my submissions, newest first: `SubmissionSummary[]`.
`GET /api/submissions/:id`: `Submission` (only the owner, or a maintainer).

```ts
type SubmissionStatus =
  | 'checking'      // queued / Action running
  | 'rejected'      // blocking findings; nothing was published
  | 'in-review'     // PR open, waiting for a maintainer
  | 'publishing'    // PR set to auto-merge
  | 'published'     // merged
  | 'error';        // pipeline failure; maintainers notified

interface SubmissionSummary {
  id: string; title: string; filename: string; status: SubmissionStatus;
  createdAt: string; updatedAt: string; prUrl: string | null; slug: string | null;
}

interface Submission extends SubmissionSummary {
  meta: SubmissionMeta;
  decision: 'publish' | 'review' | 'reject' | null;
  reasons: string[];
  checks: CheckResult[];           // same shape as the item page
}
```

## Reports

`POST /api/reports` `{ slug, reason }` (signed in). One report per user per
item. Three distinct reports flag the item for a maintainer (GitHub issue).

## Internal (Action → Worker)

Authenticated with `Authorization: Bearer $INTERNAL_TOKEN`. Not callable
from browsers (no CORS, token never leaves Worker secrets / Actions secrets).

| Route | |
|---|---|
| `GET /api/internal/submissions/:id` | `{ id, login, githubId, filename, meta }` |
| `GET /api/internal/submissions/:id/file` | the quarantined bytes |
| `POST /api/internal/submissions/:id/result` | `{ status, decision, reasons, checks, prUrl, slug, strike }` |

## Abuse controls

| Control | Value |
|---|---|
| GitHub account age | ≥ 30 days |
| Turnstile | every upload |
| Daily uploads | `new` 3, others 20 |
| Duplicate file (sha256) | rejected with the existing id |
| Strikes | +1 for a reject on secrets or copyright; 2 strikes = uploads suspended |
| Quarantine | R2 objects deleted after 30 days (bucket lifecycle rule) |

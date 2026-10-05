import type { Env } from './env';
import { HttpError, json, nowIso, safeEqual } from './http';
import { ID, STATUSES } from './submissions';

/** Action → Worker. Bearer INTERNAL_TOKEN; never reachable with a browser session. */
function requireInternal(req: Request, env: Env): void {
  const auth = req.headers.get('authorization') ?? '';
  if (!env.INTERNAL_TOKEN || env.INTERNAL_TOKEN.length < 32 || !safeEqual(auth, `Bearer ${env.INTERNAL_TOKEN}`))
    throw new HttpError(401, 'Unauthorized');
}

async function row(env: Env, id: string) {
  if (!ID.test(id)) throw new HttpError(404, 'Not found');
  const r = await env.DB.prepare('SELECT id, github_id, login, filename, meta_json, status FROM submissions WHERE id = ?')
    .bind(id)
    .first<{ id: string; github_id: number; login: string; filename: string; meta_json: string; status: string }>();
  if (!r) throw new HttpError(404, 'Not found');
  return r;
}

export async function meta(req: Request, env: Env, id: string): Promise<Response> {
  requireInternal(req, env);
  const r = await row(env, id);
  return json({ id: r.id, login: r.login, githubId: r.github_id, filename: r.filename, meta: JSON.parse(r.meta_json) });
}

export async function file(req: Request, env: Env, id: string): Promise<Response> {
  requireInternal(req, env);
  await row(env, id);
  const obj = await env.QUARANTINE.get(`q/${id}`);
  if (!obj) throw new HttpError(410, 'Quarantined file has expired');
  return new Response(obj.body, {
    headers: { 'content-type': 'application/octet-stream', 'cache-control': 'no-store' }
  });
}

const SLUG = /^[a-z0-9][a-z0-9-]{0,80}$/;
const SEVERITIES = new Set(['pass', 'info', 'warn', 'block']);

/** Keep only well-formed, bounded check results: this is rendered to users. */
function cleanChecks(v: unknown): unknown[] {
  if (!Array.isArray(v)) return [];
  return v.slice(0, 300).flatMap((c) => {
    if (!c || typeof c !== 'object') return [];
    const o = c as Record<string, unknown>;
    if (typeof o.id !== 'string' || typeof o.title !== 'string' || !SEVERITIES.has(o.severity as string)) return [];
    const out: Record<string, string> = {
      id: o.id.slice(0, 80),
      severity: o.severity as string,
      title: o.title.slice(0, 200),
      detail: typeof o.detail === 'string' ? o.detail.slice(0, 1000) : ''
    };
    if (typeof o.location === 'string') out.location = o.location.slice(0, 300);
    return [out];
  });
}

export async function result(req: Request, env: Env, id: string): Promise<Response> {
  requireInternal(req, env);
  const r = await row(env, id);
  const b = (await req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!b || !STATUSES.includes(b.status as (typeof STATUSES)[number])) throw new HttpError(400, 'Bad status');

  const prUrl = typeof b.prUrl === 'string' && b.prUrl.startsWith(`https://github.com/${env.REPO}/pull/`) ? b.prUrl : null;
  const slug = typeof b.slug === 'string' && SLUG.test(b.slug) ? b.slug : null;
  const decision = ['publish', 'review', 'reject'].includes(b.decision as string) ? (b.decision as string) : null;
  const reasons = Array.isArray(b.reasons) ? b.reasons.filter((x) => typeof x === 'string').slice(0, 50).map((x) => (x as string).slice(0, 300)) : [];

  // A follow-up event (PR merged/closed) only sends status: keep earlier details.
  await env.DB.prepare(
    `UPDATE submissions SET status = ?1,
       decision = COALESCE(?2, decision), reasons_json = CASE WHEN ?3 = '[]' THEN reasons_json ELSE ?3 END,
       checks_json = CASE WHEN ?4 = '[]' THEN checks_json ELSE ?4 END,
       pr_url = COALESCE(?5, pr_url), slug = COALESCE(?6, slug), updated_at = ?7
     WHERE id = ?8`
  )
    .bind(b.status, decision, JSON.stringify(reasons), JSON.stringify(cleanChecks(b.checks)), prUrl, slug, nowIso(), id)
    .run();

  if (b.strike === true && r.status === 'checking') {
    await env.DB.prepare('UPDATE users SET strikes = strikes + 1 WHERE github_id = ?').bind(r.github_id).run();
  }
  return json({ ok: true });
}

import type { Env } from './env';
import { HttpError, json, nowIso, requireSameOrigin } from './http';
import { requireSession } from './session';
import { openIssue } from './github';

export const FLAG_AT = 3;
const SLUG = /^[a-z0-9][a-z0-9-]{0,80}$/;

export async function report(req: Request, env: Env): Promise<Response> {
  requireSameOrigin(req, env);
  const s = await requireSession(req, env);
  const b = (await req.json().catch(() => null)) as { slug?: unknown; reason?: unknown } | null;
  const slug = typeof b?.slug === 'string' ? b.slug : '';
  const reason = typeof b?.reason === 'string' ? b.reason.trim() : '';
  if (!SLUG.test(slug)) throw new HttpError(400, 'Unknown item');
  if (reason.length < 10 || reason.length > 1000) throw new HttpError(400, 'Describe the problem in 10-1000 characters');

  const ins = await env.DB.prepare(
    'INSERT OR IGNORE INTO reports (slug, github_id, reason, created_at) VALUES (?, ?, ?, ?)'
  )
    .bind(slug, s.id, reason, nowIso())
    .run();
  if (!ins.meta.changes) return json({ ok: true, duplicate: true });

  const count = await env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE slug = ?').bind(slug).first<{ n: number }>();
  if (count?.n === FLAG_AT && env.GITHUB_APP_ID) {
    const { results } = await env.DB.prepare('SELECT reason FROM reports WHERE slug = ? ORDER BY created_at').bind(slug).all<{ reason: string }>();
    // Reasons are user text: quoted as plain blocks, and the issue is only a flag for a maintainer.
    const body = [`\`${slug}\` was reported by ${FLAG_AT} people.`, '', ...results.map((r) => '> ' + r.reason.replace(/\n/g, '\n> '))].join('\n');
    await openIssue(env, `Reported: ${slug}`, body, ['reported']).catch((e) => console.error('issue failed', e));
  }
  return json({ ok: true });
}

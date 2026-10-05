import type { Env } from './env';
import { HttpError, json, nowIso, requireSameOrigin } from './http';
import { requireSession } from './session';
import { openIssue } from './github';
import { accountBlock, trustOf } from './trust';

export const FLAG_AT = 3;
const SLUG = /^[a-z0-9][a-z0-9-]{0,80}$/;

export async function report(req: Request, env: Env): Promise<Response> {
  requireSameOrigin(req, env);
  const s = await requireSession(req, env);
  // Same bar as uploading, so throwaway accounts can't mass-flag an item.
  const blocked = await accountBlock(env, s, await trustOf(env, s));
  if (blocked) throw new HttpError(403, blocked);
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
    const body = [`\`${slug}\` was reported by ${FLAG_AT} people.`, '', ...results.map((r) => fenced(r.reason))].join('\n');
    await openIssue(env, `Reported: ${slug}`, body, ['reported']).catch((e) => console.error('issue failed', e));
  }
  return json({ ok: true });
}

/**
 * User text in an issue body, rendered as a literal code block: no mentions,
 * links, images or HTML. The fence is longer than any backtick run inside.
 */
export function fenced(text: string): string {
  const clean = text.replace(/[\u0000-\u0008\u000b-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g, '');
  const longest = Math.max(0, ...(clean.match(/`+/g) ?? []).map((r) => r.length));
  const fence = '`'.repeat(Math.max(3, longest + 1));
  return `${fence}text\n${clean}\n${fence}\n`;
}

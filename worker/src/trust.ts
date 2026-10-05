import type { Env, Session, Trust } from './env';

/**
 * Trust tiers come from content/contributors.yaml on the main branch: the
 * same file the pipeline reads, and one only maintainers can change.
 */
const LINE = /^\s*([A-Za-z0-9-]+(?:\[bot\])?)\s*:\s*(new|contributor|trusted|maintainer)\s*(?:#.*)?$/;

export function parseContributors(text: string): Map<string, Trust> {
  const out = new Map<string, Trust>();
  for (const line of text.split('\n')) {
    const m = LINE.exec(line);
    if (m) out.set(m[1].toLowerCase(), m[2] as Trust);
  }
  return out;
}

export async function trustOf(env: Env, login: string): Promise<Trust> {
  try {
    const res = await fetch(`https://raw.githubusercontent.com/${env.REPO}/main/content/contributors.yaml`, {
      cf: { cacheTtl: 300, cacheEverything: true }
    });
    if (!res.ok) return 'new';
    return parseContributors(await res.text()).get(login.toLowerCase()) ?? 'new';
  } catch {
    return 'new'; // fail closed: unknown means the strictest limits
  }
}

export const MIN_ACCOUNT_AGE_DAYS = 30;
export const MAX_STRIKES = 2;
export const dailyLimit = (t: Trust) => (t === 'new' ? 3 : 20);

export interface Gate {
  trust: Trust;
  canUpload: boolean;
  reason: string | null;
  uploadsToday: number;
  dailyLimit: number;
}

/** Everything that decides whether this person may upload right now. */
export async function gate(env: Env, s: Session): Promise<Gate> {
  const trust = await trustOf(env, s.login);
  const limit = dailyLimit(trust);
  const today = new Date().toISOString().slice(0, 10);
  const row = await env.DB.prepare(
    `SELECT (SELECT strikes FROM users WHERE github_id = ?1) AS strikes,
            (SELECT COUNT(*) FROM submissions WHERE github_id = ?1 AND created_at >= ?2) AS today`
  )
    .bind(s.id, today)
    .first<{ strikes: number | null; today: number }>();
  const uploadsToday = row?.today ?? 0;
  const ageDays = (Date.now() - Date.parse(s.created)) / 86_400_000;

  let reason: string | null = null;
  if ((row?.strikes ?? 0) >= MAX_STRIKES) reason = 'Uploads are suspended on this account. Open an issue to appeal.';
  else if (!(ageDays >= MIN_ACCOUNT_AGE_DAYS) && trust === 'new')
    reason = `Your GitHub account must be at least ${MIN_ACCOUNT_AGE_DAYS} days old to upload.`;
  else if (uploadsToday >= limit) reason = `Daily limit reached (${limit} uploads). Try again tomorrow.`;

  return { trust, canUpload: reason === null, reason, uploadsToday, dailyLimit: limit };
}

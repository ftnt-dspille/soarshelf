import type { Env, Session, Trust } from './env';

/**
 * Trust tiers come from content/contributors.yaml on the main branch: the
 * same file the pipeline reads, and one only maintainers can change.
 *
 * Each entry is `login: {trust: <tier>, id: <numeric GitHub id>}`. Logins can
 * be renamed and re-registered, so a tier only applies to the account whose
 * id matches; any other line (including a bare `login: tier`) grants nothing.
 */
const LINE =
  /^\s*([A-Za-z0-9-]+(?:\[bot\])?)\s*:\s*\{\s*trust\s*:\s*(new|contributor|trusted|maintainer)\s*,\s*id\s*:\s*(\d{1,12})\s*\}\s*(?:#.*)?$/;

export function parseContributors(text: string): Map<string, { trust: Trust; id: number }> {
  const out = new Map<string, { trust: Trust; id: number }>();
  for (const line of text.split('\n')) {
    const m = LINE.exec(line);
    if (m) out.set(m[1].toLowerCase(), { trust: m[2] as Trust, id: Number(m[3]) });
  }
  return out;
}

export async function trustOf(env: Env, s: Pick<Session, 'id' | 'login'>): Promise<Trust> {
  try {
    const res = await fetch(`https://raw.githubusercontent.com/${env.REPO}/main/content/contributors.yaml`, {
      cf: { cacheTtl: 300, cacheEverything: true }
    });
    if (!res.ok) return 'new';
    const entry = parseContributors(await res.text()).get(s.login.toLowerCase());
    return entry && entry.id === s.id ? entry.trust : 'new';
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

/** Why this account may not act at all (suspended, too new), or null. */
export async function accountBlock(env: Env, s: Session, trust: Trust): Promise<string | null> {
  const row = await env.DB.prepare('SELECT strikes FROM users WHERE github_id = ?').bind(s.id).first<{ strikes: number }>();
  const ageDays = (Date.now() - Date.parse(s.created)) / 86_400_000;
  if ((row?.strikes ?? 0) >= MAX_STRIKES) return 'This account is suspended. Open an issue to appeal.';
  if (!(ageDays >= MIN_ACCOUNT_AGE_DAYS) && trust === 'new')
    return `Your GitHub account must be at least ${MIN_ACCOUNT_AGE_DAYS} days old.`;
  return null;
}

/** Everything that decides whether this person may upload right now. The
 * daily count here is advisory; create() enforces it atomically. */
export async function gate(env: Env, s: Session): Promise<Gate> {
  const trust = await trustOf(env, s);
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

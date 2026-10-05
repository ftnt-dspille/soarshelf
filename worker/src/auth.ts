import type { Env } from './env';
import { HttpError, cookie, json, nowIso, randomHex, requireSameOrigin, setCookie } from './http';
import { clearSessionCookie, readSession, sessionCookie, sign, unsign } from './session';
import { gate } from './trust';

const STATE_COOKIE = 'oauth';
const STATE_TTL = 600;

/** Only same-site relative paths, so `next` can't become an open redirect. */
export function safeNext(next: string | null): string {
  return next && /^\/(?![/\\])[\w\-./?=&%#]*$/.test(next) ? next : '/submit';
}

function redirect(location: string, cookies: string[] = []): Response {
  const headers = new Headers({ location, 'cache-control': 'no-store' });
  for (const c of cookies) headers.append('set-cookie', c);
  return new Response(null, { status: 302, headers });
}

function isLocal(req: Request): boolean {
  const host = new URL(req.url).hostname;
  return host === 'localhost' || host === '127.0.0.1';
}

async function upsertUser(env: Env, u: { id: number; login: string; avatar: string; created: string }) {
  await env.DB.prepare(
    `INSERT INTO users (github_id, login, avatar_url, account_created_at, first_seen)
     VALUES (?1, ?2, ?3, ?4, ?5)
     ON CONFLICT (github_id) DO UPDATE SET login = ?2, avatar_url = ?3, account_created_at = ?4`
  )
    .bind(u.id, u.login, u.avatar, u.created, nowIso())
    .run();
}

export async function login(req: Request, env: Env): Promise<Response> {
  const next = safeNext(new URL(req.url).searchParams.get('next'));

  // Local development only: both the env flag AND a localhost request.
  if (env.DEV_LOGIN === '1' && isLocal(req)) {
    const u = { id: 1, login: 'dev-user', avatar: '', created: '2015-01-01T00:00:00Z' };
    await upsertUser(env, u);
    return redirect(next, [await sessionCookie(env, u)]);
  }

  const state = randomHex();
  const url = new URL('https://github.com/login/oauth/authorize');
  url.searchParams.set('client_id', env.GITHUB_CLIENT_ID);
  url.searchParams.set('redirect_uri', `${env.SITE_ORIGIN}/api/auth/callback`);
  url.searchParams.set('state', state);
  url.searchParams.set('scope', ''); // public profile only; we never act on the user's behalf
  return redirect(url.toString(), [setCookie(STATE_COOKIE, await sign(env, { state, next }), STATE_TTL)]);
}

export async function callback(req: Request, env: Env): Promise<Response> {
  const params = new URL(req.url).searchParams;
  const saved = await unsign<{ state: string; next: string }>(env, cookie(req, STATE_COOKIE));
  const code = params.get('code');
  if (!saved || !code || params.get('state') !== saved.state) throw new HttpError(400, 'Sign-in expired. Try again.');

  const tokenRes = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { accept: 'application/json', 'content-type': 'application/json' },
    body: JSON.stringify({
      client_id: env.GITHUB_CLIENT_ID,
      client_secret: env.GITHUB_CLIENT_SECRET,
      code,
      redirect_uri: `${env.SITE_ORIGIN}/api/auth/callback`
    })
  });
  const token = ((await tokenRes.json()) as { access_token?: string }).access_token;
  if (!token) throw new HttpError(400, 'GitHub sign-in failed');

  const userRes = await fetch('https://api.github.com/user', {
    headers: { authorization: `Bearer ${token}`, accept: 'application/vnd.github+json', 'user-agent': 'soarshelf' }
  });
  if (!userRes.ok) throw new HttpError(502, 'Could not read your GitHub profile');
  const gh = (await userRes.json()) as { id: number; login: string; avatar_url: string; created_at: string };
  // The access token is used once, here, and never stored.

  const u = { id: gh.id, login: gh.login, avatar: gh.avatar_url, created: gh.created_at };
  await upsertUser(env, u);
  return redirect(safeNext(saved.next), [await sessionCookie(env, u), setCookie(STATE_COOKIE, '', 0)]);
}

export async function logout(req: Request, env: Env): Promise<Response> {
  requireSameOrigin(req, env);
  return json({ ok: true }, 200, { 'set-cookie': clearSessionCookie() });
}

export async function me(req: Request, env: Env): Promise<Response> {
  const s = await readSession(req, env);
  if (!s) return json({ error: 'Not signed in' }, 401);
  const g = await gate(env, s);
  return json({
    login: s.login,
    avatarUrl: s.avatar,
    trust: g.trust,
    canUpload: g.canUpload,
    reason: g.reason,
    uploadsToday: g.uploadsToday,
    dailyLimit: g.dailyLimit
  });
}

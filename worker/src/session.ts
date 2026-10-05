import type { Env, Session } from './env';
import { HttpError, b64url, cookie, fromB64url, hmac, safeEqual, setCookie } from './http';

const NAME = 'session';
export const SESSION_TTL = 7 * 24 * 3600;

/** `<base64url(json)>.<hmac>`: stateless, so there is no session table to leak or clean up. */
export async function sign(env: Env, data: object): Promise<string> {
  const body = b64url(JSON.stringify(data));
  return `${body}.${await hmac(env.SESSION_SECRET, body)}`;
}

export async function unsign<T>(env: Env, value: string | null): Promise<T | null> {
  if (!value) return null;
  const [body, sig] = value.split('.');
  if (!body || !sig || !safeEqual(sig, await hmac(env.SESSION_SECRET, body))) return null;
  try {
    return JSON.parse(new TextDecoder().decode(fromB64url(body))) as T;
  } catch {
    return null;
  }
}

export async function readSession(req: Request, env: Env): Promise<Session | null> {
  const s = await unsign<Session>(env, cookie(req, NAME));
  return s && s.exp > Date.now() / 1000 ? s : null;
}

export async function requireSession(req: Request, env: Env): Promise<Session> {
  const s = await readSession(req, env);
  if (!s) throw new HttpError(401, 'Sign in first');
  return s;
}

export async function sessionCookie(env: Env, s: Omit<Session, 'exp'>): Promise<string> {
  const value = await sign(env, { ...s, exp: Math.floor(Date.now() / 1000) + SESSION_TTL });
  return setCookie(NAME, value, SESSION_TTL);
}

export const clearSessionCookie = () => setCookie(NAME, '', 0);

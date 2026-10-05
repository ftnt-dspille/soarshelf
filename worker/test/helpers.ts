import { SELF, env } from 'cloudflare:test';
import type { Env } from '../src/env';
import { sessionCookie } from '../src/session';

export const E = env as unknown as Env;
export const ORIGIN = 'https://shelf.test';
export const INTERNAL = { authorization: `Bearer ${'i'.repeat(40)}` };

let nextId = 1000;

/** A signed-in user. `ageDays` is how old their GitHub account is; `id`
 * defaults to a fresh one (boss is 1 and pat is 2 in the stub contributors.yaml). */
export async function user(login: string, ageDays = 400, id = nextId++) {
  const created = new Date(Date.now() - ageDays * 86_400_000).toISOString();
  await E.DB.prepare(
    `INSERT OR IGNORE INTO users (github_id, login, avatar_url, account_created_at, first_seen) VALUES (?, ?, '', ?, ?)`
  )
    .bind(id, login, created, new Date().toISOString())
    .run();
  const set = await sessionCookie(E, { id, login, avatar: '', created });
  return { id, login, cookie: set.split(';')[0] };
}

export function api(path: string, init: RequestInit & { cookie?: string; origin?: string | null } = {}) {
  const headers = new Headers(init.headers);
  if (init.cookie) headers.set('cookie', init.cookie);
  if (init.origin !== null) headers.set('origin', init.origin ?? ORIGIN);
  return SELF.fetch(`${ORIGIN}${path}`, { ...init, headers, redirect: 'manual' });
}

let fileSeq = 0;
export const playbook = () =>
  new File([JSON.stringify({ type: 'workflow_collections', data: [], n: fileSeq++ })], 'playbook.json');

export const META = {
  title: 'Enrich alert IPs',
  summary: 'Looks up the source IP of an alert.',
  description: 'Longer text.',
  useCases: ['enrichment'],
  tags: ['ip'],
  version: '1.0.0',
  minVersion: null,
  source: null,
  rightsConfirmed: true
};

export function upload(cookie: string, file: File = playbook(), meta: object = META, origin?: string | null) {
  const form = new FormData();
  form.set('file', file);
  form.set('meta', JSON.stringify(meta));
  form.set('turnstile', 'token');
  return api('/api/submissions', { method: 'POST', body: form, cookie, origin });
}

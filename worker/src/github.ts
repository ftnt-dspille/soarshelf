import type { Env } from './env';
import { b64url } from './http';

/**
 * GitHub App installation tokens: short-lived (1 h) and scoped to the one
 * repository, instead of a long-lived personal token in Worker secrets.
 */
let cached: { token: string; exp: number } | null = null;

function pemToPkcs8(pem: string): ArrayBuffer {
  if (pem.includes('BEGIN RSA PRIVATE KEY'))
    throw new Error('Convert the GitHub App key to PKCS#8: openssl pkcs8 -topk8 -nocrypt -in key.pem');
  const b64 = pem.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
}

async function appJwt(env: Env): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const head = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const body = b64url(JSON.stringify({ iat: now - 60, exp: now + 540, iss: env.GITHUB_APP_ID }));
  const key = await crypto.subtle.importKey(
    'pkcs8',
    pemToPkcs8(env.GITHUB_APP_PRIVATE_KEY),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(`${head}.${body}`));
  return `${head}.${body}.${b64url(sig)}`;
}

async function installationToken(env: Env): Promise<string> {
  if (cached && cached.exp > Date.now() + 60_000) return cached.token;
  const res = await fetch(`https://api.github.com/app/installations/${env.GITHUB_APP_INSTALLATION_ID}/access_tokens`, {
    method: 'POST',
    headers: { authorization: `Bearer ${await appJwt(env)}`, ...GH_HEADERS }
  });
  if (!res.ok) throw new Error(`GitHub App token: ${res.status}`);
  const t = (await res.json()) as { token: string; expires_at: string };
  cached = { token: t.token, exp: Date.parse(t.expires_at) };
  return t.token;
}

const GH_HEADERS = { accept: 'application/vnd.github+json', 'user-agent': 'soarshelf', 'x-github-api-version': '2022-11-28' };

async function gh(env: Env, path: string, body: unknown): Promise<Response> {
  return fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
    method: 'POST',
    headers: { authorization: `Bearer ${await installationToken(env)}`, 'content-type': 'application/json', ...GH_HEADERS },
    body: JSON.stringify(body)
  });
}

/** Start the submission Action. Only the id is sent: the Action fetches the rest from us. */
export async function dispatchSubmission(env: Env, id: string): Promise<void> {
  const res = await gh(env, '/dispatches', { event_type: 'submission', client_payload: { id } });
  if (res.status !== 204) throw new Error(`repository_dispatch: ${res.status}`);
}

export async function openIssue(env: Env, title: string, body: string, labels: string[]): Promise<void> {
  const res = await gh(env, '/issues', { title, body, labels });
  if (!res.ok) throw new Error(`issue: ${res.status}`);
}

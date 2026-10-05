import type { Env, Session } from './env';
import { HttpError, json, nowIso, randomHex, requireSameOrigin, sha256Hex } from './http';
import { requireSession } from './session';
import { gate, trustOf } from './trust';
import { MAX_ZIP, checkFile, cleanFilename, validateMeta } from './validate';
import { dispatchSubmission } from './github';

export const ID = /^[0-9a-f]{32}$/;
export const STATUSES = ['checking', 'rejected', 'in-review', 'publishing', 'published', 'error'] as const;

interface Row {
  id: string;
  github_id: number;
  login: string;
  filename: string;
  meta_json: string;
  status: string;
  decision: string | null;
  reasons_json: string;
  checks_json: string;
  pr_url: string | null;
  slug: string | null;
  created_at: string;
  updated_at: string;
}

function summary(r: Row) {
  const meta = JSON.parse(r.meta_json) as { title: string };
  return {
    id: r.id,
    title: meta.title,
    filename: r.filename,
    status: r.status,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
    prUrl: r.pr_url,
    slug: r.slug
  };
}

async function verifyTurnstile(env: Env, token: string, ip: string | null): Promise<boolean> {
  const body = new FormData();
  body.set('secret', env.TURNSTILE_SECRET);
  body.set('response', token);
  if (ip) body.set('remoteip', ip);
  const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body });
  return res.ok && ((await res.json()) as { success?: boolean }).success === true;
}

export async function create(req: Request, env: Env): Promise<Response> {
  requireSameOrigin(req, env);
  const s = await requireSession(req, env);

  // Cheapest refusals first: who you are, then how big, then the bot check.
  const g = await gate(env, s);
  if (!g.canUpload) throw new HttpError(g.reason?.startsWith('Daily') ? 429 : 403, g.reason ?? 'Uploads not allowed');
  const declared = Number(req.headers.get('content-length') ?? 0);
  if (declared > MAX_ZIP + 256 * 1024) throw new HttpError(413, 'File is too large');

  const form = await req.formData().catch(() => null);
  if (!form) throw new HttpError(400, 'Expected a multipart form');
  const file = form.get('file');
  const metaRaw = form.get('meta');
  const token = form.get('turnstile');
  if (!(file instanceof File) || typeof metaRaw !== 'string' || typeof token !== 'string')
    throw new HttpError(400, 'Missing file, details or bot check');

  if (!(await verifyTurnstile(env, token, req.headers.get('cf-connecting-ip'))))
    throw new HttpError(403, 'Bot check failed. Reload the page and try again.');

  let parsed: unknown;
  try {
    parsed = JSON.parse(metaRaw);
  } catch {
    throw new HttpError(400, 'Listing details are not valid JSON');
  }
  const meta = validateMeta(parsed);
  if (!meta.ok) throw new HttpError(400, meta.error);

  const bytes = await file.arrayBuffer();
  const kind = checkFile(file.name, bytes);
  if (!kind.ok) throw new HttpError(bytes.byteLength > MAX_ZIP ? 413 : 400, kind.error);

  const sha = await sha256Hex(bytes);
  const dupe = await env.DB.prepare('SELECT id FROM submissions WHERE sha256 = ?').bind(sha).first<{ id: string }>();
  if (dupe) throw new HttpError(409, 'This exact file has already been submitted', { id: dupe.id });

  const id = randomHex();
  const filename = cleanFilename(file.name);
  // Private bucket, never served. A lifecycle rule deletes objects after 30 days.
  await env.QUARANTINE.put(`q/${id}`, bytes, {
    httpMetadata: { contentType: 'application/octet-stream' },
    customMetadata: { filename, login: s.login, sha256: sha }
  });
  const now = nowIso();
  await env.DB.prepare(
    `INSERT INTO submissions (id, github_id, login, filename, size, sha256, meta_json, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'checking', ?, ?)`
  )
    .bind(id, s.id, s.login, filename, bytes.byteLength, sha, JSON.stringify(meta.value), now, now)
    .run();

  try {
    if (env.GITHUB_APP_ID) await dispatchSubmission(env, id);
    else if (env.DEV_LOGIN !== '1') throw new Error('GitHub App is not configured');
  } catch (e) {
    console.error('dispatch failed', id, e);
    await env.DB.prepare(`UPDATE submissions SET status = 'error', updated_at = ? WHERE id = ?`).bind(nowIso(), id).run();
  }
  return json({ id }, 201);
}

export async function list(req: Request, env: Env): Promise<Response> {
  const s = await requireSession(req, env);
  const { results } = await env.DB.prepare(
    'SELECT * FROM submissions WHERE github_id = ? ORDER BY created_at DESC LIMIT 100'
  )
    .bind(s.id)
    .all<Row>();
  return json(results.map(summary));
}

async function canSee(env: Env, s: Session, r: Row): Promise<boolean> {
  return r.github_id === s.id || (await trustOf(env, s.login)) === 'maintainer';
}

export async function get(req: Request, env: Env, id: string): Promise<Response> {
  const s = await requireSession(req, env);
  if (!ID.test(id)) throw new HttpError(404, 'Not found');
  const r = await env.DB.prepare('SELECT * FROM submissions WHERE id = ?').bind(id).first<Row>();
  // Same 404 for "missing" and "not yours": ids aren't an oracle.
  if (!r || !(await canSee(env, s, r))) throw new HttpError(404, 'Not found');
  return json({
    ...summary(r),
    meta: JSON.parse(r.meta_json),
    decision: r.decision,
    reasons: JSON.parse(r.reasons_json),
    checks: JSON.parse(r.checks_json)
  });
}

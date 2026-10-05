// Dev-only stand-in for the upload Worker (docs/api.md), so the submit flow
// can be clicked through without Cloudflare. Enabled by MOCK_API=1 in
// `vite dev` only; it is never part of a build.
import { createHash, randomBytes } from 'node:crypto';
import type { IncomingMessage, ServerResponse } from 'node:http';
import type { Plugin } from 'vite';

type Status = 'checking' | 'rejected' | 'in-review' | 'publishing' | 'published' | 'error';

interface Stored {
  id: string;
  title: string;
  filename: string;
  created: number;
  meta: Record<string, unknown>;
  sha: string;
}

const COOKIE = 'mock_session=demo';
const AVATAR =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" fill="#0f766e"/><text x="20" y="26" font-family="sans-serif" font-size="16" font-weight="700" fill="#fff" text-anchor="middle">DU</text></svg>'
  );

const CHECK_DELAY_MS = 8000;
const submissions: Stored[] = [];
const reports = new Set<string>();

const CHECKS = [
  { id: 'structure.code', severity: 'warn', title: 'Runs code on the platform', detail: 'Code steps are always reviewed by a maintainer: Normalize Records › Python function' },
  { id: 'secrets.public-ip', severity: 'warn', title: 'Public IP address', detail: '52.10.20.30 - use 192.0.2.x / 198.51.100.x / 203.0.113.x for examples.', location: 'Enrichment › Lookup › arguments.params.ip' },
  { id: 'sanitize.config', severity: 'info', title: 'Connector configuration links removed (2)', detail: 'Steps will use the default configuration of each connector on your system.' },
  { id: 'sanitize.deactivated', severity: 'info', title: 'Playbooks set to inactive (1)', detail: 'Downloads are always inactive so nothing fires before you review it.' },
  { id: 'brand.mentions', severity: 'info', title: 'Product names mentioned', detail: 'VirusTotal - used to describe compatibility only.' },
  { id: 'deps.complete', severity: 'pass', title: 'All dependencies are on the Content Hub', detail: '' },
  { id: 'secrets.clean', severity: 'pass', title: 'No credentials found', detail: '' }
];

function status(s: Stored): Status {
  return Date.now() - s.created < CHECK_DELAY_MS ? 'checking' : 'in-review';
}

function summary(s: Stored) {
  const st = status(s);
  const iso = (t: number) => new Date(t).toISOString();
  return {
    id: s.id,
    title: s.title,
    filename: s.filename,
    status: st,
    createdAt: iso(s.created),
    updatedAt: iso(st === 'checking' ? s.created : s.created + CHECK_DELAY_MS),
    prUrl: st === 'checking' ? null : `https://github.com/OWNER/soarshelf/pull/${100 + submissions.indexOf(s)}`,
    slug: null
  };
}

function detail(s: Stored) {
  const base = summary(s);
  const done = base.status !== 'checking';
  return {
    ...base,
    meta: s.meta,
    decision: done ? 'review' : null,
    reasons: done ? ['First submissions from new contributors are reviewed', 'Contains steps that run code'] : [],
    checks: done ? CHECKS : []
  };
}

function json(res: ServerResponse, code: number, body: unknown) {
  res.statusCode = code;
  res.setHeader('content-type', 'application/json');
  res.end(JSON.stringify(body));
}

function toRequest(req: IncomingMessage): Request {
  return new Request(`http://localhost${req.url}`, {
    method: req.method,
    headers: req.headers as Record<string, string>,
    body: req as unknown as BodyInit,
    duplex: 'half'
  } as RequestInit);
}

export function mockApi(): Plugin {
  return {
    name: 'soarshelf-mock-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url ?? '/', 'http://localhost');
        if (!url.pathname.startsWith('/api/')) return next();
        const signedIn = (req.headers.cookie ?? '').includes(COOKIE);
        const p = url.pathname;

        if (p === '/api/auth/login') {
          const nxt = url.searchParams.get('next') ?? '/';
          res.statusCode = 302;
          res.setHeader('set-cookie', `${COOKIE}; Path=/; HttpOnly; SameSite=Lax`);
          res.setHeader('location', nxt.startsWith('/') && !nxt.startsWith('//') ? nxt : '/');
          return res.end();
        }
        if (p === '/api/auth/logout' && req.method === 'POST') {
          res.setHeader('set-cookie', 'mock_session=; Path=/; Max-Age=0');
          return json(res, 200, { ok: true });
        }
        if (!signedIn) return json(res, 401, { error: 'Not signed in' });

        if (p === '/api/me') {
          const today = submissions.filter((s) => Date.now() - s.created < 86_400_000).length;
          return json(res, 200, {
            login: 'demo-user',
            avatarUrl: AVATAR,
            trust: 'new',
            canUpload: today < 3,
            reason: today < 3 ? null : 'You’ve used all 3 uploads for today.',
            uploadsToday: today,
            dailyLimit: 3
          });
        }

        if (p === '/api/submissions' && req.method === 'POST') {
          const form = await toRequest(req).formData();
          const file = form.get('file');
          if (!(file instanceof File)) return json(res, 400, { error: 'Missing file' });
          const bytes = Buffer.from(await file.arrayBuffer());
          const sha = createHash('sha256').update(bytes).digest('hex');
          const dup = submissions.find((s) => s.sha === sha);
          if (dup) return json(res, 409, { error: 'Duplicate', id: dup.id });
          let meta: Record<string, unknown>;
          try {
            meta = JSON.parse(String(form.get('meta') ?? ''));
          } catch {
            return json(res, 400, { error: 'meta is not valid JSON' });
          }
          if (!form.get('turnstile')) return json(res, 400, { error: 'Bot check missing' });
          const s: Stored = { id: randomBytes(16).toString('hex'), title: String(meta.title ?? file.name), filename: file.name, created: Date.now(), meta, sha };
          submissions.unshift(s);
          return json(res, 201, { id: s.id });
        }
        if (p === '/api/submissions' && req.method === 'GET') return json(res, 200, submissions.map(summary));

        const m = p.match(/^\/api\/submissions\/([a-z0-9]+)$/);
        if (m && req.method === 'GET') {
          const s = submissions.find((x) => x.id === m[1]);
          return s ? json(res, 200, detail(s)) : json(res, 404, { error: 'Not found' });
        }

        if (p === '/api/reports' && req.method === 'POST') {
          const body = (await toRequest(req).json().catch(() => ({}))) as { slug?: string };
          if (!body.slug) return json(res, 400, { error: 'Missing slug' });
          if (reports.has(body.slug)) return json(res, 409, { error: 'Already reported' });
          reports.add(body.slug);
          return json(res, 201, { ok: true });
        }

        return json(res, 404, { error: 'Not found' });
      });
    }
  };
}

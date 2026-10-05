import { describe, expect, it } from 'vitest';
import { E, INTERNAL, META, api, playbook, upload, user } from './helpers';
import { safeNext } from '../src/auth';
import { sign } from '../src/session';
import { checkFile, validateMeta } from '../src/validate';
import { parseContributors } from '../src/trust';
import { fenced } from '../src/reports';

describe('auth', () => {
  it('rejects missing and forged sessions', async () => {
    expect((await api('/api/me')).status).toBe(401);
    const forged = await sign({ ...E, SESSION_SECRET: 'attacker-secret-attacker-secret!!' }, {
      id: 1, login: 'boss', avatar: '', created: '2010-01-01', exp: 9e9
    });
    expect((await api('/api/me', { cookie: `session=${forged}` })).status).toBe(401);
  });

  it('reports trust and upload eligibility', async () => {
    const boss = await user('boss', 400, 1);
    const me = await (await api('/api/me', { cookie: boss.cookie })).json<Record<string, unknown>>();
    expect(me).toMatchObject({ login: 'boss', trust: 'maintainer', canUpload: true, dailyLimit: 20 });

    const fresh = await user('fresh-account', 5);
    const m2 = await (await api('/api/me', { cookie: fresh.cookie })).json<Record<string, unknown>>();
    expect(m2.canUpload).toBe(false);
    expect(m2.reason).toMatch(/30 days/);
  });

  it('never redirects off-site after sign-in', () => {
    expect(safeNext('/me/abc')).toBe('/me/abc');
    for (const bad of ['//evil.example', 'https://evil.example', '/\\evil.example', null, 'javascript:alert(1)'])
      expect(safeNext(bad)).toBe('/submit');
  });

  it('refuses a callback without the matching state cookie', async () => {
    const res = await api('/api/auth/callback?code=x&state=y');
    expect(res.status).toBe(400);
  });

  it('dev login only works on localhost', async () => {
    const res = await api('/api/auth/login?next=/me');
    expect(res.headers.get('location')).toMatch(/^https:\/\/github\.com\/login\/oauth\/authorize/);
  });
});

describe('submissions', () => {
  it('quarantines a valid upload and records it', async () => {
    const u = await user('alice');
    const res = await upload(u.cookie);
    expect(res.status).toBe(201);
    const { id } = await res.json<{ id: string }>();
    expect(id).toMatch(/^[0-9a-f]{32}$/);
    expect(await E.QUARANTINE.head(`q/${id}`)).not.toBeNull();
    const detail = await (await api(`/api/submissions/${id}`, { cookie: u.cookie })).json<Record<string, unknown>>();
    expect(detail).toMatchObject({ id, status: 'checking', title: META.title, filename: 'playbook.json' });
  });

  it('refuses cross-site posts, bad details and bad files', async () => {
    const u = await user('bob');
    expect((await upload(u.cookie, playbook(), META, 'https://evil.example')).status).toBe(403);
    expect((await upload(u.cookie, playbook(), META, null)).status).toBe(403);
    expect((await upload(u.cookie, playbook(), { ...META, title: 'x' })).status).toBe(400);
    expect((await upload(u.cookie, playbook(), { ...META, rightsConfirmed: false })).status).toBe(400);
    expect((await upload(u.cookie, new File(['{nope'], 'p.json'))).status).toBe(400);
    expect((await upload(u.cookie, new File(['MZ...'], 'evil.exe'))).status).toBe(400);
    expect((await upload(u.cookie, new File(['not a zip'], 'pack.zip'))).status).toBe(400);
  });

  it('rejects an identical file with the existing id', async () => {
    const u = await user('carol');
    const file = playbook();
    const first = await (await upload(u.cookie, file)).json<{ id: string }>();
    const again = await upload(u.cookie, file);
    expect(again.status).toBe(409);
    expect((await again.json<{ id: string }>()).id).toBe(first.id);
  });

  it('does not let parallel uploads slip past the daily limit', async () => {
    const u = await user('dora');
    const codes = (await Promise.all(Array.from({ length: 6 }, () => upload(u.cookie)))).map((r) => r.status);
    expect(codes.filter((c) => c === 201).length).toBe(3);
    expect(codes.filter((c) => c === 429).length).toBe(3);
  });

  it('gives a renamed-and-reclaimed login no trust', async () => {
    const impostor = await user('boss', 400, 4242);
    const me = await (await api('/api/me', { cookie: impostor.cookie })).json();
    expect(me).toMatchObject({ login: 'boss', trust: 'new', dailyLimit: 3 });
  });

  it('enforces the daily limit for new contributors', async () => {
    const u = await user('dave');
    for (let i = 0; i < 3; i++) expect((await upload(u.cookie)).status).toBe(201);
    expect((await upload(u.cookie)).status).toBe(429);
  });

  it('shows a submission only to its owner and maintainers', async () => {
    const owner = await user('erin');
    const { id } = await (await upload(owner.cookie)).json<{ id: string }>();
    const other = await user('frank');
    expect((await api(`/api/submissions/${id}`, { cookie: other.cookie })).status).toBe(404);
    const boss = await user('boss', 400, 1);
    expect((await api(`/api/submissions/${id}`, { cookie: boss.cookie })).status).toBe(200);
    const list = await (await api('/api/submissions', { cookie: other.cookie })).json<unknown[]>();
    expect(list).toHaveLength(0);
  });
});

describe('internal API', () => {
  it('requires the internal token', async () => {
    const u = await user('gina');
    const { id } = await (await upload(u.cookie)).json<{ id: string }>();
    expect((await api(`/api/internal/submissions/${id}`, { cookie: u.cookie })).status).toBe(401);
    expect((await api(`/api/internal/submissions/${id}`, { headers: { authorization: 'Bearer wrong' } })).status).toBe(401);
    const meta = await (await api(`/api/internal/submissions/${id}`, { headers: INTERNAL })).json<Record<string, unknown>>();
    expect(meta).toMatchObject({ id, login: 'gina', filename: 'playbook.json' });
    const file = await api(`/api/internal/submissions/${id}/file`, { headers: INTERNAL });
    expect(JSON.parse(await file.text()).type).toBe('workflow_collections');
  });

  it('stores results, drops bad fields, and counts strikes', async () => {
    const u = await user('hank');
    const { id } = await (await upload(u.cookie)).json<{ id: string }>();
    const post = (body: object) =>
      api(`/api/internal/submissions/${id}/result`, {
        method: 'POST',
        headers: { ...INTERNAL, 'content-type': 'application/json' },
        body: JSON.stringify(body)
      });
    expect((await post({ status: 'hacked' })).status).toBe(400);
    expect(
      (
        await post({
          status: 'rejected',
          decision: 'reject',
          reasons: ['AWS access key ID found'],
          checks: [{ id: 'secrets.aws-key', severity: 'block', title: 'AWS access key ID found', detail: 'AKIA…LE' }, { bogus: 1 }],
          prUrl: 'https://evil.example/pull/1',
          slug: '../etc',
          strike: true
        })
      ).status
    ).toBe(200);
    const d = await (await api(`/api/submissions/${id}`, { cookie: u.cookie })).json<Record<string, unknown>>();
    expect(d).toMatchObject({ status: 'rejected', decision: 'reject', prUrl: null, slug: null });
    expect(d.checks).toHaveLength(1);
    const strikes = await E.DB.prepare('SELECT strikes FROM users WHERE login = ?').bind('hank').first<{ strikes: number }>();
    expect(strikes?.strikes).toBe(1);
  });

  it('suspends uploads after two strikes', async () => {
    const u = await user('ivan');
    await E.DB.prepare('UPDATE users SET strikes = 2 WHERE login = ?').bind('ivan').run();
    const res = await upload(u.cookie);
    expect(res.status).toBe(403);
    expect((await res.json<{ error: string }>()).error).toMatch(/suspended/);
  });
});

describe('reports', () => {
  it('records one report per user per item', async () => {
    const u = await user('judy');
    const body = JSON.stringify({ slug: 'some-item', reason: 'Contains an internal hostname' });
    const send = () => api('/api/reports', { method: 'POST', body, cookie: u.cookie, headers: { 'content-type': 'application/json' } });
    expect(await (await send()).json()).toEqual({ ok: true });
    expect(await (await send()).json()).toEqual({ ok: true, duplicate: true });
    const bad = await api('/api/reports', { method: 'POST', cookie: u.cookie, body: JSON.stringify({ slug: '../x', reason: 'long enough reason' }) });
    expect(bad.status).toBe(400);
  });

  it('needs the same account age as uploading', async () => {
    const fresh = await user('throwaway', 2);
    const body = JSON.stringify({ slug: 'some-item', reason: 'Contains an internal hostname' });
    const res = await api('/api/reports', { method: 'POST', body, cookie: fresh.cookie, headers: { 'content-type': 'application/json' } });
    expect(res.status).toBe(403);
  });
});

describe('pure helpers', () => {
  it('validates listing details', () => {
    expect(validateMeta(META).ok).toBe(true);
    expect(validateMeta({ ...META, tags: ['Has Space'] }).ok).toBe(false);
    expect(validateMeta({ ...META, source: 'http://insecure.example' }).ok).toBe(false);
    expect(validateMeta({ ...META, useCases: [] }).ok).toBe(false);
  });

  it('checks file type by extension and content', () => {
    expect(checkFile('a.json', new TextEncoder().encode('{}').buffer as ArrayBuffer)).toEqual({ ok: true, value: 'json' });
    expect(checkFile('a.zip', new Uint8Array([0x50, 0x4b, 3, 4, 0]).buffer).ok).toBe(true);
    expect(checkFile('a.svg', new ArrayBuffer(4)).ok).toBe(false);
  });

  it('parses contributors.yaml entries and ignores junk and id-less tiers', () => {
    const m = parseContributors(
      '# c\nboss: {trust: maintainer, id: 1}\nold: maintainer\nx: {trust: admin, id: 3}\nbot[bot]: {trust: trusted, id: 9}  # ok\n'
    );
    expect([...m]).toEqual([['boss', { trust: 'maintainer', id: 1 }], ['bot[bot]', { trust: 'trusted', id: 9 }]]);
  });

  it('fences user text so GitHub renders it literally', () => {
    const out = fenced('@everyone see [x](https://evil.example) ```` break out\u202e');
    expect(out.startsWith('`````text\n')).toBe(true);
    expect(out.trimEnd().endsWith('\n`````')).toBe(true);
    expect(out).not.toContain('\u202e');
  });
});

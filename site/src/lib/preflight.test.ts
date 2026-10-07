import { deflateRawSync, gzipSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { preflight, withoutEnvironmentOnly } from './preflight';

const enc = new TextEncoder();
const file = (name: string, data: Uint8Array | string) => new File([typeof data === 'string' ? data : (data as BlobPart)], name);

const AWS = 'AKIAABCDEFGHIJKLMNOP';
const playbook = (extra: object = {}) => ({
  '@type': 'WorkflowCollection',
  name: 'c',
  workflows: [{ name: 'w', owners: ['admin@corp-example.com'], steps: [{ name: 's', arguments: { to: 'ops@corp-example.com', mock_result: { ip: '10.1.1.1' }, config: 'abc', ...extra } }] }]
});

function zip(files: Record<string, string>): Uint8Array {
  const parts: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let off = 0;
  for (const [name, text] of Object.entries(files)) {
    const raw = enc.encode(text);
    const comp = deflateRawSync(raw);
    const n = enc.encode(name);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(8, 8, true);
    local.setUint32(18, comp.length, true);
    local.setUint32(22, raw.length, true);
    local.setUint16(26, n.length, true);
    parts.push(new Uint8Array(local.buffer), n, comp);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true);
    c.setUint16(10, 8, true);
    c.setUint32(20, comp.length, true);
    c.setUint32(24, raw.length, true);
    c.setUint16(28, n.length, true);
    c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), n);
    off += 30 + n.length + comp.length;
  }
  const cdSize = central.reduce((a, b) => a + b.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(10, Object.keys(files).length, true);
  end.setUint32(12, cdSize, true);
  end.setUint32(16, off, true);
  return Buffer.concat([...parts, ...central, new Uint8Array(end.buffer)]);
}

function tgz(files: Record<string, string>): Uint8Array {
  const blocks: Buffer[] = [];
  for (const [name, text] of Object.entries(files)) {
    const body = Buffer.from(text);
    const h = Buffer.alloc(512);
    h.write(name, 0);
    h.write(body.length.toString(8).padStart(11, '0'), 124);
    h.write('0', 156);
    blocks.push(h, body, Buffer.alloc((512 - (body.length % 512)) % 512));
  }
  blocks.push(Buffer.alloc(1024));
  return gzipSync(Buffer.concat(blocks));
}

describe('preflight', () => {
  it('does not report what the pipeline strips anyway (owners, mock results, config links)', async () => {
    const r = await preflight(file('p.json', JSON.stringify(playbook())));
    expect(r.findings.map((f) => f.detail)).toEqual(['ops@corp-example.com']);
  });

  it('blocks a credential in a playbook and says where', async () => {
    const r = await preflight(file('p.json', JSON.stringify(playbook({ api_key: AWS }))));
    const f = r.findings.find((x) => x.id === 'secrets.aws-key' || x.id === 'secrets.literal-secret');
    expect(f?.severity).toBe('block');
    expect(f?.location).toContain('arguments');
  });

  it('is not fooled by a template reference', async () => {
    const r = await preflight(file('p.json', JSON.stringify(playbook({ password: '{{ vars.pw }}' }))));
    expect(r.findings.every((f) => f.severity !== 'block')).toBe(true);
  });

  it('reads every JSON file in a solution pack zip', async () => {
    const z = zip({ 'a/playbooks/one.json': JSON.stringify({ steps: [], v: AWS }), 'b/two.json': '{"ok": true}', 'readme.md': AWS });
    const r = await preflight(file('pack.zip', z));
    expect(r.files).toBe(2);
    expect(r.findings).toHaveLength(1);
    expect(r.findings[0].location).toContain('a/playbooks/one.json');
  });

  it('scans a connector tgz: manifest and source files', async () => {
    const t = tgz({ 'conn/info.json': '{"name":"x"}', 'conn/connector.py': `KEY = "${AWS}"\n`, 'conn/.env': AWS });
    const r = await preflight(file('conn.tgz', t));
    expect(r.findings.map((f) => f.id)).toEqual(['secrets.aws-key']);
  });

  it('says so when a file can not be checked, instead of passing it', async () => {
    expect((await preflight(file('x.json', '{nope'))).skipped).toBeTruthy();
    expect((await preflight(file('x.bin', 'abc'))).skipped).toBeTruthy();
  });

  it('withoutEnvironmentOnly leaves author content alone', () => {
    const out = withoutEnvironmentOnly({ steps: [{ arguments: { x: 1, mock_result: 2 } }], id: 5, owners: [1] }) as Record<string, unknown>;
    expect(out).toEqual({ steps: [{ arguments: { x: 1 } }] });
  });
});

import { describe, expect, it } from 'vitest';
import { firstSentence, fromJson, guessUseCases, infoFromTar } from './prefill';

function tar(entries: [string, string][]): Uint8Array {
  const enc = new TextEncoder();
  const blocks: Uint8Array[] = [];
  for (const [name, body] of entries) {
    const h = new Uint8Array(512);
    h.set(enc.encode(name), 0);
    const data = enc.encode(body);
    h.set(enc.encode(data.length.toString(8).padStart(11, '0') + '\0'), 124);
    h[156] = '0'.charCodeAt(0);
    blocks.push(h, new Uint8Array(Math.ceil(data.length / 512) * 512).map((_, i) => data[i] ?? 0));
  }
  blocks.push(new Uint8Array(1024));
  const out = new Uint8Array(blocks.reduce((n, b) => n + b.length, 0));
  let o = 0;
  for (const b of blocks) (out.set(b, o), (o += b.length));
  return out;
}

describe('prefill', () => {
  it('reads a connector manifest out of a tar', () => {
    const info = { name: 'c', label: 'My Connector', version: '1.2.0', category: 'Threat Intelligence',
      description: 'Looks up IPs. More text.', operations: [] };
    const t = tar([['c/connector.py', 'x'], ['c/info.json', JSON.stringify(info)]]);
    const p = fromJson(infoFromTar(t));
    expect(p).toMatchObject({ kind: 'connector', name: 'My Connector', summary: 'Looks up IPs.', version: '1.2.0',
      useCases: ['enrichment'] });
  });

  it('ignores an info.json that is not at the package root', () => {
    expect(infoFromTar(tar([['c/tests/info.json', '{}']]))).toBeNull();
  });

  it('reads a playbook export and a widget manifest', () => {
    expect(fromJson({ type: 'workflow_collections', data: [{ name: 'Coll', workflows: [{ name: 'Block IP', description: 'Blocks it.' }] }] }))
      .toMatchObject({ kind: 'playbook', title: 'Block IP', summary: 'Blocks it.' });
    expect(fromJson({ name: 'w', title: 'Run Report', subTitle: 'Charts of runs', version: '1.0.1', metadata: {} }))
      .toMatchObject({ kind: 'widget', title: 'Run Report', useCases: ['reporting'] });
    expect(fromJson({ hello: 1 })).toBeNull();
  });

  it('keeps summaries within 160 characters on a word boundary', () => {
    const s = firstSentence('word '.repeat(60));
    expect(s.length).toBeLessThanOrEqual(160);
    expect(s.endsWith('word…')).toBe(true);
    expect(guessUseCases('nothing relevant')).toEqual([]);
  });
});

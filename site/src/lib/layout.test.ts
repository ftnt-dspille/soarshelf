import { describe, expect, it } from 'vitest';
import { NODE_H, NODE_W, autoLayout, fitZoom } from './layout';
import type { PlaybookEdge, PlaybookNode } from './types';

const n = (id: string): PlaybookNode => ({ id, name: id, label: 'Step', family: 'utility', x: 0, y: 0, args: {} });
const chain = (k: number) => {
  const nodes = Array.from({ length: k }, (_, i) => n(`s${i}`));
  const edges: PlaybookEdge[] = nodes.slice(1).map((x, i) => ({ id: `e${i}`, source: `s${i}`, target: x.id, label: null }));
  return { nodes, edges };
};

const overlaps = (pos: Map<string, { x: number; y: number }>) => {
  const p = [...pos.values()];
  return p.some((a, i) => p.slice(i + 1).some((b) => Math.abs(a.x - b.x) < NODE_W && Math.abs(a.y - b.y) < NODE_H));
};

describe('autoLayout', () => {
  it('keeps a short chain top to bottom', () => {
    const { nodes, edges } = chain(3);
    const l = autoLayout(nodes, edges, 960, 600);
    expect(l.dir).toBe('TB');
    expect(l.positions.get('s0')!.y).toBeLessThan(l.positions.get('s1')!.y);
  });

  it('turns a 4-step chain sideways in a very wide, short frame', () => {
    const { nodes, edges } = chain(4);
    expect(autoLayout(nodes, edges, 1400, 220).dir).toBe('LR');
  });

  it('wraps a long chain into columns so every step is shown readably', () => {
    const { nodes, edges } = chain(14);
    const l = autoLayout(nodes, edges, 960, 600);
    expect(l.wrapped.size).toBeGreaterThan(0);
    expect(fitZoom(l, 960, 600)).toBeGreaterThan(0.5);
    expect(overlaps(l.positions)).toBe(false);
    // Reading order is kept: each column runs top to bottom.
    expect(l.positions.get('s0')!.y).toBeLessThan(l.positions.get('s1')!.y);
  });

  it('uses the frame: a 12-step chain in the front-page frame gets 3 columns, not 2', () => {
    const { nodes, edges } = chain(12);
    const l = autoLayout(nodes, edges, 1600, 1000);
    expect(new Set([...l.positions.values()].map((p) => p.x)).size).toBe(3);
  });

  it('never overlaps steps, branches included', () => {
    const nodes = ['t', 'd', 'a', 'b', 'c', 'end'].map(n);
    const e = (s: string, t: string): PlaybookEdge => ({ id: s + t, source: s, target: t, label: null });
    const l = autoLayout(nodes, [e('t', 'd'), e('d', 'a'), e('d', 'b'), e('d', 'c'), e('a', 'end'), e('b', 'end')]);
    expect(overlaps(l.positions)).toBe(false);
  });
});

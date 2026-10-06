import { describe, expect, it } from 'vitest';
import { NODE_H, NODE_W, autoLayout, fitZoom, jumpPoints } from './layout';
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

  it('routes a column jump through the gap between the columns', () => {
    const { nodes, edges } = chain(12);
    const l = autoLayout(nodes, edges, 1600, 1000);
    const jump = edges.find((e) => l.wrapped.has(e.id))!;
    const s = l.positions.get(jump.source)!;
    const t = l.positions.get(jump.target)!;
    const pts = jumpPoints(l, jump.source, jump.target, { x: s.x + NODE_W / 2, y: s.y + NODE_H }, { x: t.x + NODE_W / 2, y: t.y });
    // the vertical run is right of the source column and left of the target column
    expect(pts[2].x).toBeGreaterThan(s.x + NODE_W);
    expect(pts[2].x).toBeLessThan(t.x);
    // and it ends pointing down into the target's top
    expect(pts.at(-1)).toEqual({ x: t.x + NODE_W / 2, y: t.y });
  });

  it('never overlaps steps, branches included', () => {
    const nodes = ['t', 'd', 'a', 'b', 'c', 'end'].map(n);
    const e = (s: string, t: string): PlaybookEdge => ({ id: s + t, source: s, target: t, label: null });
    const l = autoLayout(nodes, [e('t', 'd'), e('d', 'a'), e('d', 'b'), e('d', 'c'), e('a', 'end'), e('b', 'end')]);
    expect(overlaps(l.positions)).toBe(false);
  });

  // Daily-recon shape: three optional actions in a row, then a long tail with a skip to the end.
  const recon = () => {
    const ids = ['start', 'cfg', 'find', 'd1', 'a1', 'd2', 'a2', 'd3', 'x1', 'x2', 'x3', 'x4', 'end'];
    const nodes = ids.map(n);
    const pairs: [string, string, string | null][] = [
      ['start', 'cfg', null], ['cfg', 'find', null], ['find', 'd1', null],
      ['d1', 'a1', 'Act'], ['d1', 'd2', 'Continue'], ['a1', 'd2', null],
      ['d2', 'a2', 'Act'], ['d2', 'd3', 'Continue'], ['a2', 'd3', null],
      ['d3', 'x1', 'Excel'], ['d3', 'end', 'End'], ['x1', 'x2', null], ['x2', 'x3', null], ['x3', 'x4', null], ['x4', 'end', null]
    ];
    const edges: PlaybookEdge[] = pairs.map(([s, t2, label], i) => ({ id: `e${i}`, source: s, target: t2, label }));
    return { nodes, edges };
  };

  it('only breaks columns where the flow passes through one point', () => {
    const { nodes, edges } = recon();
    const l = autoLayout(nodes, edges, 960, 600);
    if (l.colOf) {
      // a decision's two branches never land in different columns from where they rejoin
      for (const [d, a, j] of [['d1', 'a1', 'd2'], ['d2', 'a2', 'd3']]) {
        expect(l.colOf.get(d)).toBe(l.colOf.get(a));
        const jumps = edges.filter((e) => l.wrapped.has(e.id) && e.target === j);
        expect(new Set(jumps.map((e) => e.target)).size).toBeLessThanOrEqual(1);
      }
    }
  });

  it('sends a skip past several steps down the side of its column, not through them', () => {
    const { nodes, edges } = recon();
    const l = autoLayout(nodes, edges, 960, 600);
    const skip = edges.find((e) => e.label === 'End')!;
    expect(l.sideX?.has(skip.id)).toBe(true);
    const x = l.sideX!.get(skip.id)!;
    for (const id of ['x1', 'x2', 'x3', 'x4']) expect(x).toBeGreaterThan(l.positions.get(id)!.x + NODE_W);
    expect(l.width).toBeGreaterThan(x);
  });

  it('gives jumps sharing a gap their own lanes', () => {
    const { nodes, edges } = recon();
    const l = autoLayout(nodes, edges, 1600, 1000);
    const gapOf = (e: PlaybookEdge) => Math.min(l.colOf!.get(e.source)!, l.colOf!.get(e.target)!);
    const jumps = edges.filter((e) => l.wrapped.has(e.id));
    expect(jumps.length).toBeGreaterThan(1);
    for (const a of jumps)
      for (const b of jumps)
        if (a !== b && gapOf(a) === gapOf(b)) expect(l.laneOffset!.get(a.id)).not.toBe(l.laneOffset!.get(b.id));
  });
});


import { describe, expect, it } from 'vitest';
import { NODE_H, NODE_W, NOTE_W, autoLayout, branchSources, clutter, fitZoom, isRouted, jumpPoints, placeGroups } from './layout';
import heal from './fixtures-heal-playbook.json';
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


describe('placeGroups', () => {
  const rect = (p: { x: number; y: number }) => ({ x: p.x, y: p.y, w: NODE_W, h: NODE_H });
  const hit = (a: { x: number; y: number; w: number; h: number }, b: typeof a) =>
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

  it('puts each note beside its step without covering any step or other note', () => {
    const { nodes, edges } = chain(4);
    const l = autoLayout(nodes, edges, 960, 600);
    const a = placeGroups(l, [
      { id: 'n1', kind: 'note', name: 'One', text: 'x'.repeat(200), anchor: 's1' },
      { id: 'n2', kind: 'note', name: 'Two', text: 'short', anchor: 's1' }
    ]);
    const notes = [...a.notes.values()];
    expect(notes).toHaveLength(2);
    for (const r of notes) for (const p of l.positions.values()) expect(hit(r, rect(p))).toBe(false);
    expect(hit(notes[0], notes[1])).toBe(false);
    expect(notes[0].w).toBe(NOTE_W);
    expect(a.width).toBeGreaterThanOrEqual(Math.max(...notes.map((r) => r.x + r.w)) - a.left);
  });

  it('boxes a block around its steps, but not when another step would land inside', () => {
    const { nodes, edges } = chain(3); // one top-down column (see the first autoLayout test)
    const l = autoLayout(nodes, edges, 960, 600);
    const a = placeGroups(l, [{ id: 'b', kind: 'block', name: 'B', text: '', steps: ['s1', 's2'] }]);
    const box = a.blocks.get('b')!;
    for (const id of ['s1', 's2']) {
      const p = l.positions.get(id)!;
      expect(p.x >= box.x && p.y >= box.y && p.x + NODE_W <= box.x + box.w && p.y + NODE_H <= box.y + box.h).toBe(true);
    }
    expect(placeGroups(l, [{ id: 'b', kind: 'block', name: 'B', text: '', steps: ['s0', 's2'] }]).blocks.size).toBe(0);
  });
});

describe('placeGroups on a wrapped playbook with six notes', () => {
  const pb = heal as unknown as { nodes: PlaybookNode[]; edges: PlaybookEdge[]; groups: import('./types').PlaybookGroup[] };
  const l = autoLayout(pb.nodes, pb.edges, 1440, 700);
  const a = placeGroups(l, pb.groups, pb.edges);
  const rect = (id: string) => ({ ...l.positions.get(id)!, w: NODE_W, h: NODE_H });
  const inside = (p: { x: number; y: number }, r: { x: number; y: number; w: number; h: number }) =>
    p.x > r.x && p.x < r.x + r.w && p.y > r.y && p.y < r.y + r.h;
  const notes = pb.groups.filter((g) => g.kind === 'note');

  it('places every note', () => {
    expect(notes.length).toBeGreaterThan(3);
    for (const g of notes) expect(a.notes.has(g.id)).toBe(true);
  });

  it('keeps each note off every step, other note and edge line', () => {
    for (const g of notes) {
      const r = a.notes.get(g.id)!;
      for (const id of l.positions.keys()) {
        const s = rect(id);
        expect(r.x < s.x + s.w && s.x < r.x + r.w && r.y < s.y + s.h && s.y < r.y + r.h).toBe(false);
      }
      for (const e of pb.edges) {
        const sp = l.positions.get(e.source)!, tp = l.positions.get(e.target)!;
        const A = { x: sp.x + NODE_W / 2, y: sp.y + NODE_H }, B = { x: tp.x + NODE_W / 2, y: tp.y };
        const pts = isRouted(l, e.id) ? jumpPoints(l, e.source, e.target, A, B, e.id) : [A, { x: A.x, y: (A.y + B.y) / 2 }, { x: B.x, y: (A.y + B.y) / 2 }, B];
        for (let i = 1; i < pts.length; i++) {
          // sample along the segment: none of it may be inside the note
          for (let t = 0; t <= 1; t += 0.05) {
            expect(inside({ x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t }, r)).toBe(false);
          }
        }
      }
    }
  });

  it('keeps every note link clear of the other steps', () => {
    for (const g of notes) {
      if (g.kind !== 'note') continue;
      const r = a.notes.get(g.id)!, an = rect(g.anchor);
      const before = r.x + r.w <= an.x;
      const from = { x: before ? an.x : an.x + NODE_W, y: an.y + NODE_H / 2 };
      const to = { x: before ? r.x + r.w : r.x, y: r.y + r.h / 2 };
      for (const id of l.positions.keys()) {
        if (id === g.anchor) continue;
        const s = rect(id);
        for (let t = 0; t <= 1; t += 0.02) {
          expect(inside({ x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t }, s)).toBe(false);
        }
      }
    }
  });
});

describe('placeGroups when a note has no free room', () => {
  // A step boxed in by its neighbours must still get a note within the canvas,
  // not one flung past the far edge of the layout.
  it('keeps a boxed-in note near the layout', () => {
    const nodes = Array.from({ length: 9 }, (_, i) => n(`s${i}`));
    const edges: PlaybookEdge[] = nodes.slice(1).map((x, i) => ({ id: `e${i}`, source: `s${i}`, target: x.id, label: null }));
    const l = autoLayout(nodes, edges, 1440, 700);
    const a = placeGroups(l, [{ id: 'g', kind: 'note', name: 'Note', text: 'x', anchor: 's4' }], edges);
    const r = a.notes.get('g')!;
    expect(r.x + r.w).toBeLessThan(l.width + 3 * NOTE_W);
    expect(r.x).toBeGreaterThan(-3 * NOTE_W);
  });
});

describe('a decision with a short side branch', () => {
  // decision -> A (does nothing but lead to the end) and -> B..E (the long way round), both ending at done.
  const ids = ['start', 'dec', 'a', 'b', 'c', 'd', 'e', 'done'];
  const nodes = ids.map(n);
  const edge = (s: string, t: string): PlaybookEdge => ({ id: `${s}-${t}`, source: s, target: t, label: null });
  const edges = [
    edge('start', 'dec'), edge('dec', 'a'), edge('dec', 'b'), edge('b', 'c'), edge('c', 'd'), edge('d', 'e'), edge('e', 'done'), edge('a', 'done')
  ];

  it('puts the side branch beside its decision, not down at the join', () => {
    const l = autoLayout(nodes, edges, 3000, 3000);
    const dy = l.positions.get('a')!.y - l.positions.get('dec')!.y;
    expect(dy).toBeLessThanOrEqual(NODE_H + 60);
  });

  it('draws it with no arrow through a step or across another arrow', () => {
    expect(clutter(autoLayout(nodes, edges, 3000, 3000), edges)).toBe(0);
  });
});

describe('the Heal playbook example', () => {
  const pb = heal as unknown as { nodes: PlaybookNode[]; edges: PlaybookEdge[] };
  it('lays out with no arrow through a step or across another in the front-page frame', () => {
    expect(clutter(autoLayout(pb.nodes, pb.edges, 1440, 700), pb.edges)).toBe(0);
  });
  const id = (name: string) => pb.nodes.find((n) => n.name === name)!.id;
  it('fans the last decision out to both sides instead of parking a branch under it', () => {
    const l = autoLayout(pb.nodes, pb.edges, 1440, 700);
    const dec = l.positions.get(id('NewKeyValid'))!.x;
    expect(l.positions.get(id('Done'))!.x).toBeLessThan(dec);
    expect(l.positions.get(id('FailRotation'))!.x).toBeGreaterThan(dec);
  });
  it('lines a step up with the one above it when they are only a few px apart', () => {
    const l = autoLayout(pb.nodes, pb.edges, 1440, 700);
    expect(l.positions.get(id('Done'))!.x).toBe(l.positions.get(id('AlreadyHealthy'))!.x);
  });
  it('leaves the layout alone with spread off', () => {
    const l = autoLayout(pb.nodes, pb.edges, 1440, 700, { spread: false });
    expect(Math.abs(l.positions.get(id('FailRotation'))!.x - l.positions.get(id('NewKeyValid'))!.x)).toBeLessThan(NODE_W / 4);
  });
});

describe('branch lines', () => {
  const e = (source: string, target: string, label: string | null): PlaybookEdge => ({ id: `${source}-${target}`, source, target, label });
  it('are for steps whose exits are labelled options, not for a parallel fan-out', () => {
    const edges = [e('dec', 'a', 'Yes'), e('dec', 'b', 'No'), e('fan', 'c', null), e('fan', 'd', null)];
    expect([...branchSources(edges)]).toEqual(['dec']);
  });
});

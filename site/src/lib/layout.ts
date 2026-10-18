import dagre from 'dagre';
import type { PlaybookEdge, PlaybookGroup, PlaybookNode } from './types';

export const NODE_W = 236;
export const NODE_H = 66;

export interface Point {
  x: number;
  y: number;
}

export type Direction = 'TB' | 'LR';

export interface Layout {
  /** Flow direction inside a column; wrapped layouts are TB columns side by side. */
  dir: Direction;
  /** Top-left position of each node, keyed by id. */
  positions: Map<string, Point>;
  width: number;
  height: number;
  /** Edges that jump from the bottom of one column to the top of the next. */
  wrapped: Set<string>;
  /** Wrapped layouts: each column's horizontal extent, and which column a node is in. */
  columns?: { left: number; right: number }[];
  colOf?: Map<string, number>;
  /** Wrapped edges sharing a gap get their own lane: a horizontal offset in px. */
  laneOffset?: Map<string, number>;
  /** Top-down edges that would cross steps: x of the lane they run down beside their column. */
  sideX?: Map<string, number>;
}

/** Edges drawn as routed lines (column jumps and side lanes) rather than smoothstep. */
export function isRouted(l: Layout, edge: string): boolean {
  return l.wrapped.has(edge) || !!l.sideX?.has(edge);
}

const RANKSEP_TB = 56;
const COL_GAP = 96;
const MARGIN = 16;

function run(nodes: PlaybookNode[], edges: PlaybookEdge[], dir: Direction): Layout {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: dir,
    nodesep: dir === 'TB' ? 40 : 28,
    ranksep: dir === 'TB' ? RANKSEP_TB : 72,
    marginx: 16,
    marginy: 16,
    // Network simplex + tight-tree ranking keeps branches compact and edges short.
    ranker: 'network-simplex'
  });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  // A step many others lead to (a shared failure or end step) shouldn't pull the
  // main flow sideways: its incoming edges count for little when aligning steps,
  // so the main chain stays straight instead of drifting into a staircase.
  const into = new Map<string, Set<string>>();
  for (const e of edges) into.set(e.target, (into.get(e.target) ?? new Set()).add(e.source));
  // A short side branch (a decision's step that does nothing but lead to the point where the
  // branches meet) belongs beside its decision; left to the ranker it is dragged down to the
  // join, and its line from the decision then runs the whole length of the playbook. So the
  // line that rejoins is the cheap one to stretch.
  const outOf = new Map<string, number>();
  for (const e of edges) outOf.set(e.source, (outOf.get(e.source) ?? 0) + 1);
  const isBranch = (id: string) => (outOf.get(id) ?? 0) >= 2;
  const sideStep = (id: string) =>
    (into.get(id)?.size ?? 0) === 1 && (outOf.get(id) ?? 0) === 1 && [...(into.get(id) ?? [])].every(isBranch);
  for (const e of edges) {
    if (!g.hasNode(e.source) || !g.hasNode(e.target) || e.source === e.target) continue;
    const joins = (into.get(e.target)?.size ?? 0) >= 2;
    g.setEdge(e.source, e.target, { weight: (into.get(e.target)?.size ?? 0) >= 3 || (sideStep(e.source) && joins) ? 1 : 8 });
  }
  dagre.layout(g);
  const positions = new Map<string, Point>();
  for (const n of nodes) {
    const m = g.node(n.id);
    positions.set(n.id, { x: Math.round(m.x - NODE_W / 2), y: Math.round(m.y - NODE_H / 2) });
  }
  const { width = 0, height = 0 } = g.graph();
  return { dir, positions, width, height, wrapped: new Set() };
}

const LANE = 12;

/**
 * Rank indices where a new column may start. Only where the flow passes
 * through one point: a single edge crosses the cut, or every crossing edge
 * lands on the same step at the top of the next column (branches rejoining).
 * Cutting through a decision's open branches would send each of them to the
 * next column as a separate jump line, which hides which path is which.
 */
function cleanCuts(tb: Layout, edges: PlaybookEdge[], rankOf: Map<string, number>, ranks: number, loose = false): Set<number> {
  const ok = new Set<number>();
  for (let k = 1; k < ranks; k++) {
    const crossing = edges.filter((e) => {
      const a = rankOf.get(e.source), b = rankOf.get(e.target);
      return a !== undefined && b !== undefined && Math.min(a, b) < k && Math.max(a, b) >= k;
    });
    const targets = new Set(crossing.map((e) => e.target));
    const forward = crossing.every((e) => rankOf.get(e.source)! < rankOf.get(e.target)!);
    if (crossing.length === 1 || (forward && targets.size === 1 && rankOf.get([...targets][0]) === k)) ok.add(k);
    // Loose: two forward lines may cross too (a decision's branch and the branch that
    // skips its section). Only used when it shows the playbook clearly larger.
    else if (loose && forward && crossing.length === 2) ok.add(k);
  }
  return ok;
}

/**
 * Split a top-down layout into `cols` columns of consecutive ranks, read left
 * to right like newspaper text, breaking only at clean cuts (see cleanCuts).
 * Long playbooks are mostly chains, so this shows them far larger than one
 * tall column or one wide row. Null when there aren't enough clean cuts.
 */
function wrap(tb: Layout, edges: PlaybookEdge[], cols: number, loose = false): Layout | null {
  const ys = [...new Set([...tb.positions.values()].map((p) => p.y))].sort((a, b) => a - b);
  const rankIndex = new Map(ys.map((y, i) => [y, i]));
  const rankOf = new Map([...tb.positions].map(([id, p]) => [id, rankIndex.get(p.y)!]));
  const cuts = cleanCuts(tb, edges, rankOf, ys.length, loose);
  // Breaks nearest an even split, each column at least two ranks.
  const starts = [0];
  for (let c = 1; c < cols; c++) {
    const ideal = (c * ys.length) / cols;
    const prev = starts[starts.length - 1];
    const pick = [...cuts]
      .filter((k) => k >= prev + 2 && k <= ys.length - 2 * (cols - c))
      .sort((a, b) => Math.abs(a - ideal) - Math.abs(b - ideal))[0];
    if (pick === undefined) return null;
    starts.push(pick);
  }
  const colOfRank = (r: number) => starts.filter((s) => s <= r).length - 1;

  const colOf = new Map<string, number>();
  const positions = new Map<string, Point>();
  let offset = MARGIN;
  let height = 0;
  const columns: { left: number; right: number }[] = [];
  for (let c = 0; c < starts.length; c++) {
    const ids = [...tb.positions].filter(([id]) => colOfRank(rankOf.get(id)!) === c);
    const minX = Math.min(...ids.map(([, p]) => p.x));
    const maxX = Math.max(...ids.map(([, p]) => p.x)) + NODE_W;
    for (const [id, p] of ids) {
      const row = rankOf.get(id)! - starts[c];
      positions.set(id, { x: offset + p.x - minX, y: MARGIN + row * (NODE_H + RANKSEP_TB) });
      colOf.set(id, c);
    }
    const rows = (starts[c + 1] ?? ys.length) - starts[c];
    height = Math.max(height, MARGIN * 2 + rows * NODE_H + (rows - 1) * RANKSEP_TB);
    columns.push({ left: offset, right: offset + maxX - minX });
    offset += maxX - minX + COL_GAP;
  }
  const jumps = edges.filter((e) => colOf.has(e.source) && colOf.has(e.target) && colOf.get(e.source) !== colOf.get(e.target));
  // Jumps that run along the same gap get side-by-side lanes, ordered by where they start.
  const laneOffset = new Map<string, number>();
  const byGap = new Map<number, PlaybookEdge[]>();
  for (const e of jumps) {
    const gap = Math.min(colOf.get(e.source)!, colOf.get(e.target)!);
    byGap.set(gap, [...(byGap.get(gap) ?? []), e]);
  }
  for (const list of byGap.values()) {
    list.sort((a, b) => positions.get(a.source)!.y - positions.get(b.source)!.y || positions.get(a.source)!.x - positions.get(b.source)!.x);
    list.forEach((e, i) => laneOffset.set(e.id, (i - (list.length - 1) / 2) * LANE));
  }
  return {
    dir: 'TB', positions, width: offset - COL_GAP + MARGIN, height,
    wrapped: new Set(jumps.map((e) => e.id)), columns, colOf, laneOffset
  };
}

/** How far a column-jump line runs below its source and above its target. */
export const JUMP_GAP = 22;

/**
 * Route for an edge between wrapped columns, from the source's bottom (`a`)
 * to the target's top (`b`): down, across to the middle of the gap between
 * the columns, along that gap, across, and down into the target. Every turn
 * sits in empty space between rows or columns, never along the frame edge.
 */
export function jumpPoints(l: Layout, source: string, target: string, a: Point, b: Point, edge?: string): Point[] {
  const side = edge ? l.sideX?.get(edge) : undefined;
  if (side !== undefined) {
    return [a, { x: a.x, y: a.y + JUMP_GAP }, { x: side, y: a.y + JUMP_GAP }, { x: side, y: b.y - JUMP_GAP }, { x: b.x, y: b.y - JUMP_GAP }, b];
  }
  const cols = l.columns ?? [];
  const cs = l.colOf?.get(source) ?? 0;
  const ct = l.colOf?.get(target) ?? 0;
  const between = (i: number) => (cols[i].right + cols[i + 1].left) / 2;
  const gx =
    (ct > cs && cols[cs + 1] ? between(cs) : cs > 0 && cols[cs - 1] ? between(cs - 1) : (cols[cs]?.left ?? a.x) - COL_GAP / 2) +
    (edge ? (l.laneOffset?.get(edge) ?? 0) : 0);
  return [a, { x: a.x, y: a.y + JUMP_GAP }, { x: gx, y: a.y + JUMP_GAP }, { x: gx, y: b.y - JUMP_GAP }, { x: b.x, y: b.y - JUMP_GAP }, b];
}

/**
 * In a top-down layout, a straight line from a step to one several rows below
 * runs through the steps in between (a decision's "skip to the end" branch).
 * Those edges get a lane down the right side of their column instead.
 */
function routeSkips(l: Layout, edges: PlaybookEdge[]): Layout {
  if (l.dir !== 'TB') return l;
  const col = (id: string) => l.colOf?.get(id) ?? 0;
  const sideX = new Map<string, number>();
  const lanes = new Map<number, number>();
  let width = l.width;
  const skips = edges
    .filter((e) => l.positions.has(e.source) && l.positions.has(e.target) && col(e.source) === col(e.target))
    .sort((a, b) => l.positions.get(a.source)!.y - l.positions.get(b.source)!.y);
  for (const e of skips) {
    const s = l.positions.get(e.source)!, t = l.positions.get(e.target)!;
    if (t.y <= s.y) continue;
    const sx = s.x + NODE_W / 2, tx = t.x + NODE_W / 2;
    const lo = Math.min(sx, tx) - 8, hi = Math.max(sx, tx) + 8;
    const between = [...l.positions].filter(
      ([id, p]) => col(id) === col(e.source) && p.y > s.y && p.y < t.y
    );
    if (!between.some(([, p]) => p.x < hi && p.x + NODE_W > lo)) continue;
    const c = col(e.source);
    const right = Math.max(...[...l.positions].filter(([id]) => col(id) === c).map(([, p]) => p.x + NODE_W));
    const lane = lanes.get(c) ?? 0;
    lanes.set(c, lane + 1);
    const x = right + 20 + lane * LANE;
    sideX.set(e.id, x);
    width = Math.max(width, x + MARGIN);
  }
  return sideX.size ? { ...l, sideX, width } : l;
}

/** SVG path through orthogonal points, with rounded corners. */
export function roundedPath(pts: Point[], r = 10): string {
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [p, c, n] = [pts[i - 1], pts[i], pts[i + 1]];
    const into = Math.min(r, Math.hypot(c.x - p.x, c.y - p.y) / 2);
    const out = Math.min(r, Math.hypot(n.x - c.x, n.y - c.y) / 2);
    const ux = Math.sign(c.x - p.x), uy = Math.sign(c.y - p.y);
    const vx = Math.sign(n.x - c.x), vy = Math.sign(n.y - c.y);
    d += ` L${c.x - ux * into},${c.y - uy * into} Q${c.x},${c.y} ${c.x + vx * out},${c.y + vy * out}`;
  }
  const last = pts[pts.length - 1];
  return `${d} L${last.x},${last.y}`;
}

/** Zoom at which a layout fits a frame of the given size. */
export function fitZoom(l: Pick<Layout, 'width' | 'height'>, frameW: number, frameH: number, pad = 32): number {
  return Math.min((frameW - pad * 2) / Math.max(l.width, 1), (frameH - pad * 2) / Math.max(l.height, 1));
}

/**
 * How tangled a layout reads, as a score (lower is better): an arrow drawn through a step
 * costs the most, then arrows crossing each other. Uses the lines the viewer draws.
 */
export function clutter(l: Layout, edges: PlaybookEdge[]): number {
  const branching = branchSources(edges);
  const drawn: { id: string; pts: Point[] }[] = [];
  for (const e of edges) {
    const pts = drawnPoints(l, e, branching);
    if (pts) drawn.push({ id: e.id, pts });
  }
  const byId = new Map(edges.map((e) => [e.id, e]));
  let score = 0;
  for (const d of drawn) {
    const e = byId.get(d.id)!;
    for (const [id, p] of l.positions) {
      if (id === e.source || id === e.target) continue;
      const r = { x: p.x, y: p.y, w: NODE_W, h: NODE_H };
      if (d.pts.some((q, i) => i > 0 && segHitsRect(d.pts[i - 1], q, r, 2))) score += 100;
    }
  }
  for (let i = 0; i < drawn.length; i++) {
    for (let j = i + 1; j < drawn.length; j++) {
      const ei = byId.get(drawn[i].id)!, ej = byId.get(drawn[j].id)!;
      // Arrows leaving or entering the same step meet there by design.
      if (ei.source === ej.source || ei.target === ej.target || ei.source === ej.target || ei.target === ej.source) continue;
      for (let a = 1; a < drawn[i].pts.length; a++) {
        for (let b = 1; b < drawn[j].pts.length; b++) {
          if (segCross(drawn[i].pts[a - 1], drawn[i].pts[a], drawn[j].pts[b - 1], drawn[j].pts[b])) score += 10;
        }
      }
    }
  }
  return score;
}

/**
 * Pick the layout that shows the whole playbook largest in the given frame:
 * top-down, left-to-right, or top-down wrapped into columns. Top-down wins
 * ties because it reads most naturally.
 */
export function autoLayout(nodes: PlaybookNode[], edges: PlaybookEdge[], frameW = 960, frameH = 600, { spread = true } = {}): Layout {
  const tb = run(nodes, edges, 'TB');
  if (nodes.length < 3) return routeSkips(tb, edges);
  const zoom = (l: Layout) => fitZoom(l, frameW, frameH);
  let best = tb;
  const lr = run(nodes, edges, 'LR');
  if (zoom(lr) > zoom(best) * 1.1) best = lr;
  // Wrapping costs some readability (edges jump between columns), so it has
  // to show the steps clearly larger than an unwrapped layout. Once wrapped,
  // another column costs little more, so it only has to be a bit larger.
  const ranks = new Set([...tb.positions.values()].map((p) => p.y)).size;
  for (const loose of [false, true]) {
    for (let cols = 2; cols <= Math.min(6, Math.floor(ranks / 2)); cols++) {
      const w = wrap(tb, edges, cols, loose);
      if (!w) continue;
      // Loose cuts send two lines across a gap, so they have to win clearly.
      const bar = (best.wrapped.size ? 1.05 : 1.25) * (loose ? 1.15 : 1);
      if (zoom(w) > zoom(best) * bar) best = w;
    }
  }
  return routeSkips(best.dir === 'TB' && spread ? straighten(clearOptionalSteps(spreadBranches(best, edges), edges), edges) : best, edges);
}

/**
 * Steps a few px out of line with the step above them get a line with a tiny jog in it. Snap
 * them into line so it drops straight, where that overlaps no step and tangles nothing.
 */
function straighten(l: Layout, edges: PlaybookEdge[]): Layout {
  const branching = branchSources(edges);
  for (const e of edges) {
    if (branching.has(e.source) || e.source === e.target) continue;
    const s = l.positions.get(e.source), t = l.positions.get(e.target);
    if (!s || !t || t.y <= s.y) continue;
    const dx = Math.abs(t.x - s.x);
    if (dx === 0 || dx > 24) continue;
    const moved = { x: s.x, y: t.y };
    const hits = [...l.positions].some(
      ([id, p]) => id !== e.target && Math.abs(p.x - moved.x) < NODE_W + 20 && Math.abs(p.y - moved.y) < NODE_H + 20
    );
    if (hits || moved.x < 0) continue;
    const next: Layout = { ...l, positions: new Map(l.positions).set(e.target, moved) };
    if (clutter(next, edges) <= clutter(l, edges)) l = next;
  }
  return l;
}

/**
 * A decision whose branches all go one way, except one step parked straight beneath it, reads
 * as a main line with a side exit rather than a choice. Nudge that step half a column the other
 * way, so the branches fan out to both sides of the fork. Kept only where it overlaps no step
 * and leaves the drawing no more tangled.
 */
function spreadBranches(l: Layout, edges: PlaybookEdge[]): Layout {
  const branching = branchSources(edges);
  const into = new Map<string, number>();
  for (const e of edges) if (e.source !== e.target) into.set(e.target, (into.get(e.target) ?? 0) + 1);
  const shift = NODE_W / 2 + 20;
  for (const src of branching) {
    const s = l.positions.get(src);
    if (!s) continue;
    const targets = [...new Set(edges.filter((e) => e.source === src && e.target !== src).map((e) => e.target))]
      .map((id) => ({ id, p: l.positions.get(id) }))
      .filter((t): t is { id: string; p: Point } => !!t.p && t.p.y > s.y);
    const under = targets.filter((t) => Math.abs(t.p.x - s.x) < NODE_W / 4);
    const others = targets.filter((t) => !under.includes(t));
    if (under.length !== 1 || !others.length || into.get(under[0].id) !== 1) continue;
    const left = others.every((t) => t.p.x < s.x), right = others.every((t) => t.p.x > s.x);
    if (left === right) continue;
    const moved = { x: under[0].p.x + (left ? shift : -shift), y: under[0].p.y };
    if (moved.x < MARGIN) continue;
    const hits = [...l.positions].some(
      ([id, p]) => id !== under[0].id && Math.abs(p.x - moved.x) < NODE_W + 20 && Math.abs(p.y - moved.y) < NODE_H + 20
    );
    if (hits) continue;
    const next: Layout = { ...l, positions: new Map(l.positions).set(under[0].id, moved) };
    next.width = Math.max(l.width, moved.x + NODE_W + MARGIN);
    if (clutter(next, edges) <= clutter(l, edges)) l = next;
  }
  return l;
}

/**
 * A decision that either runs one step or skips straight to the step after it ("Keys to renew"
 * vs "Nothing to renew"). The ranker parks the optional step half a column off the decision's
 * line, which is too little to clear it: the skip then can't drop straight to where the branches
 * meet and is sent down a side lane instead. Move the optional step clear of that line, on the
 * side it already leans to, so the skip drops straight and the step sits beside it.
 */
function clearOptionalSteps(l: Layout, edges: PlaybookEdge[]): Layout {
  const branching = branchSources(edges);
  const outs = (id: string) => [...new Set(edges.filter((e) => e.source === id && e.target !== id).map((e) => e.target))];
  const into = new Map<string, number>();
  for (const e of edges) if (e.source !== e.target) into.set(e.target, (into.get(e.target) ?? 0) + 1);
  const clear = NODE_W / 2 + 24;
  for (const src of branching) {
    const s = l.positions.get(src);
    const targets = outs(src);
    if (!s || targets.length !== 2) continue;
    for (const [a, b] of [targets, [...targets].reverse()]) {
      const pa = l.positions.get(a), pb = l.positions.get(b);
      if (!pa || !pb || into.get(a) !== 1 || outs(a).join() !== b) continue;
      if (!(s.y < pa.y && pa.y < pb.y) || Math.abs(pb.x - s.x) > 2 || Math.abs(pa.x - s.x) >= clear) continue;
      const side = pa.x >= s.x ? 1 : -1;
      const moved = { x: s.x + side * clear, y: pa.y };
      if (moved.x < MARGIN) continue;
      const hits = [...l.positions].some(
        ([id, p]) => id !== a && Math.abs(p.x - moved.x) < NODE_W + 20 && Math.abs(p.y - moved.y) < NODE_H + 20
      );
      // In a wrapped layout, stay out of the gap the column jumps run along.
      const c = l.colOf?.get(src);
      const cols = l.columns;
      const next = c !== undefined && cols ? cols[c + 1] : undefined;
      const prev = c !== undefined && cols ? cols[c - 1] : undefined;
      if (hits || (next && moved.x + NODE_W > next.left - COL_GAP / 2) || (prev && moved.x < prev.right + COL_GAP / 2)) continue;
      const out: Layout = { ...l, positions: new Map(l.positions).set(a, moved) };
      out.width = Math.max(l.width, moved.x + NODE_W + MARGIN);
      if (c !== undefined && cols) {
        out.columns = cols.map((col, i) => (i === c ? { left: Math.min(col.left, moved.x), right: Math.max(col.right, moved.x + NODE_W) } : col));
      }
      if (clutter(out, edges) <= clutter(l, edges)) l = out;
      break;
    }
  }
  return l;
}

// ---- Designer notes and blocks ----------------------------------------------
// The layout above ignores the designer's canvas, so notes can't keep their
// position: each sits beside the step it was closest to, slid along until it
// overlaps nothing. A block is drawn as a box around its steps, but only when no
// other step would land inside the box.

export const NOTE_W = 240;
const NOTE_GAP = 40;
const NOTE_MAX_LINES = 6;
const BLOCK_PAD = 14;
const BLOCK_HEAD = 26;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A note card's height: a title row plus up to NOTE_MAX_LINES of text (the card clamps to that). */
export function noteHeight(text: string): number {
  if (!text.trim()) return 40;
  const lines = text.split('\n').reduce((n, p) => n + Math.max(1, Math.ceil(p.length / 34)), 0);
  return 48 + Math.min(lines, NOTE_MAX_LINES) * 18;
}

const hits = (a: Rect, b: Rect, gap = 12) =>
  a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;

export interface Annotations {
  notes: Map<string, Rect>;
  blocks: Map<string, Rect>;
  /** The extent with the annotations included; a block box can start above or left of 0. */
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Does the segment a-b pass through (a padded) rect? Liang-Barsky clip. */
function segHitsRect(a: Point, b: Point, r: Rect, pad = 0): boolean {
  const x0 = r.x - pad, x1 = r.x + r.w + pad, y0 = r.y - pad, y1 = r.y + r.h + pad;
  let t0 = 0, t1 = 1;
  const dx = b.x - a.x, dy = b.y - a.y;
  for (const [p, q] of [[-dx, a.x - x0], [dx, x1 - a.x], [-dy, a.y - y0], [dy, y1 - a.y]]) {
    if (p === 0) {
      if (q < 0) return false;
    } else {
      const t = q / p;
      if (p < 0) {
        if (t > t1) return false;
        if (t > t0) t0 = t;
      } else {
        if (t < t0) return false;
        if (t < t1) t1 = t;
      }
    }
  }
  return t0 <= t1;
}

/** Do two segments cross? */
function segCross(a: Point, b: Point, c: Point, d: Point): boolean {
  const o = (p: Point, q: Point, r: Point) => Math.sign((q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b);
}

/** How far below a decision its branch lines bend sideways. */
export const BRANCH_BEND = 26;

/**
 * Steps where only one way out is taken: two or more exits, labelled with the option each is
 * for (a decision's branches, a manual input's responses). A step that fans out unlabelled
 * runs all of its exits, so it is not one of these.
 */
export function branchSources(edges: PlaybookEdge[]): Set<string> {
  const total = new Map<string, number>();
  const labelled = new Map<string, number>();
  for (const e of edges) {
    if (e.source === e.target) continue;
    total.set(e.source, (total.get(e.source) ?? 0) + 1);
    if (e.label) labelled.set(e.source, (labelled.get(e.source) ?? 0) + 1);
  }
  return new Set([...total].filter(([id, c]) => c >= 2 && (labelled.get(id) ?? 0) >= 2).map(([id]) => id));
}

/** The corner points of the line the viewer draws for an edge, or null when an end is missing. */
function drawnPoints(l: Layout, e: PlaybookEdge, branching: Set<string>): Point[] | null {
  const s = l.positions.get(e.source), t = l.positions.get(e.target);
  if (!s || !t || e.source === e.target) return null;
  const lr = l.dir === 'LR' && !isRouted(l, e.id);
  const a = lr ? { x: s.x + NODE_W, y: s.y + NODE_H / 2 } : { x: s.x + NODE_W / 2, y: s.y + NODE_H };
  const b = lr ? { x: t.x, y: t.y + NODE_H / 2 } : { x: t.x + NODE_W / 2, y: t.y };
  if (isRouted(l, e.id)) return jumpPoints(l, e.source, e.target, a, b, e.id);
  if (lr) return [a, { x: (a.x + b.x) / 2, y: a.y }, { x: (a.x + b.x) / 2, y: b.y }, b];
  const my = branching.has(e.source) ? Math.min(a.y + BRANCH_BEND, (a.y + b.y) / 2) : (a.y + b.y) / 2;
  return [a, { x: a.x, y: my }, { x: b.x, y: my }, b];
}

/** A segment's bounding box, padded: edges and note links are obstacles a note must not sit on. */
function segRect(a: Point, b: Point, pad: number): Rect {
  return { x: Math.min(a.x, b.x) - pad, y: Math.min(a.y, b.y) - pad, w: Math.abs(a.x - b.x) + 2 * pad, h: Math.abs(a.y - b.y) + 2 * pad };
}

/** The line each edge is drawn along, as axis-aligned segments (smoothstep approximated by its mid-bend). */
function edgeSegments(l: Layout, edges: PlaybookEdge[]): [Point, Point][] {
  const branching = branchSources(edges);
  const out: [Point, Point][] = [];
  for (const e of edges) {
    const pts = drawnPoints(l, e, branching);
    if (!pts) continue;
    for (let i = 1; i < pts.length; i++) out.push([pts[i - 1], pts[i]]);
  }
  return out;
}

export function placeGroups(l: Layout, groups: PlaybookGroup[], edges: PlaybookEdge[] = []): Annotations {
  const nodeRect = (id: string): Rect | null => {
    const p = l.positions.get(id);
    return p ? { x: p.x, y: p.y, w: NODE_W, h: NODE_H } : null;
  };
  const steps = [...l.positions.keys()].map((id) => ({ id, r: nodeRect(id)! }));
  const taken: Rect[] = steps.map((s) => s.r);
  const nodeRectOf = new Map(steps.map((s) => [s.id, s.r]));
  const lines = edgeSegments(l, edges);
  const blocks = new Map<string, Rect>();
  const notes = new Map<string, Rect>();

  for (const g of groups) {
    if (g.kind !== 'block') continue;
    const inside = g.steps.map(nodeRect).filter((r): r is Rect => !!r);
    if (!inside.length) continue;
    const x = Math.min(...inside.map((r) => r.x)) - BLOCK_PAD;
    const y = Math.min(...inside.map((r) => r.y)) - BLOCK_PAD - BLOCK_HEAD;
    const box = {
      x,
      y,
      w: Math.max(...inside.map((r) => r.x + r.w)) + BLOCK_PAD - x,
      h: Math.max(...inside.map((r) => r.y + r.h)) + BLOCK_PAD - y
    };
    const members = new Set(g.steps);
    if (steps.some((s) => !members.has(s.id) && hits(box, s.r, 0))) continue;
    if ([...blocks.values()].some((b) => hits(box, b, 0))) continue;
    blocks.set(g.id, box);
  }

  // Top-down layouts put a note to the right of its step and slide it down;
  // left-to-right layouts put it below and slide it right.
  const across = l.dir === 'LR';
  const ordered = groups
    .filter((g): g is Extract<PlaybookGroup, { kind: 'note' }> => g.kind === 'note' && l.positions.has(g.anchor))
    .sort((a, b) => {
      const pa = l.positions.get(a.anchor)!;
      const pb = l.positions.get(b.anchor)!;
      return across ? pa.x - pb.x || pa.y - pb.y : pa.y - pb.y || pa.x - pb.x;
    });
  for (const g of ordered) {
    const a = l.positions.get(g.anchor)!;
    const h = noteHeight(g.text);
    // Candidates around the step (both sides, several distances and offsets); keep the
    // nearest one that sits on no step, note, block or edge line and whose link to the
    // step runs clear of every other step and note.
    const anchorMid = { x: a.x + NODE_W / 2, y: a.y + NODE_H / 2 };
    const others = [...taken, ...blocks.values()];
    const cands: Rect[] = [];
    for (let k = 0; k < 14; k++) {
      for (let j = -14; j <= 14; j++) {
        const off = j * 24;
        const away = NOTE_GAP + k * 28;
        if (across) {
          const x = a.x + (NODE_W - NOTE_W) / 2 + off;
          cands.push({ x, y: a.y + NODE_H + away, w: NOTE_W, h }, { x, y: a.y - away - h, w: NOTE_W, h });
        } else {
          const y = a.y + (NODE_H - h) / 2 + off;
          cands.push({ x: a.x + NODE_W + away, y, w: NOTE_W, h }, { x: a.x - away - NOTE_W, y, w: NOTE_W, h });
        }
      }
    }
    // Score a spot: null when it sits on something; the link crossing a step is a
    // blocker in the strict pass and a heavy penalty in the relaxed one.
    const score = (r: Rect, strict: boolean): number | null => {
      if (others.some((t) => hits(r, t)) || lines.some((s) => hits(r, segRect(s[0], s[1], 4), 0))) return null;
      const before = across ? r.y + r.h <= a.y : r.x + r.w <= a.x;
      const from = across ? { x: anchorMid.x, y: before ? a.y : a.y + NODE_H } : { x: before ? a.x : a.x + NODE_W, y: anchorMid.y };
      const to = across ? { x: r.x + r.w / 2, y: before ? r.y + r.h : r.y } : { x: before ? r.x + r.w : r.x, y: r.y + r.h / 2 };
      const blockers = others.filter((t) => t !== nodeRectOf.get(g.anchor) && segHitsRect(from, to, t, 4)).length;
      if (blockers && strict) return null;
      const crossed = lines.filter((s) => segCross(from, to, s[0], s[1])).length;
      // Reaching past the canvas shrinks the zoom the whole playbook is shown at, and the
      // frame is wider than tall, so a pixel of height costs about twice a pixel of width.
      const out = 0.5 * Math.max(0, r.x + r.w - l.width, -r.x) + Math.max(0, r.y + r.h - l.height, -r.y);
      return Math.hypot(to.x - from.x, to.y - from.y) + crossed * 40 + blockers * 250 + out;
    };
    let placed: Rect | null = null;
    let bestScore = Infinity;
    const best = (rs: Iterable<Rect>, strict: boolean) => {
      for (const r of rs) {
        const sc = score(r, strict);
        if (sc !== null && sc < bestScore) {
          bestScore = sc;
          placed = r;
        }
      }
    };
    best(cands, true);
    if (!placed) {
      // Boxed in by its neighbours: take the best spot anywhere around the playbook.
      const wide: Rect[] = [];
      for (let x = -NOTE_W - NOTE_GAP; x <= l.width + NOTE_GAP; x += 40) {
        for (let y = -h - NOTE_GAP; y <= l.height + NOTE_GAP; y += 24) wide.push({ x, y, w: NOTE_W, h });
      }
      best(wide, false);
    }
    placed ??= across
      ? { x: a.x + (NODE_W - NOTE_W) / 2, y: Math.max(...taken.map((t) => t.y + t.h)) + NOTE_GAP, w: NOTE_W, h }
      : { x: Math.max(...taken.map((t) => t.x + t.w)) + NOTE_GAP, y: a.y + (NODE_H - h) / 2, w: NOTE_W, h };
    notes.set(g.id, placed);
    taken.push(placed);
  }

  const all = [...notes.values(), ...blocks.values()];
  const left = Math.min(0, ...all.map((r) => r.x));
  const top = Math.min(0, ...all.map((r) => r.y));
  return {
    notes,
    blocks,
    left,
    top,
    width: Math.max(l.width, ...all.map((r) => r.x + r.w)) - left,
    height: Math.max(l.height, ...all.map((r) => r.y + r.h)) - top
  };
}

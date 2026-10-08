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
  for (const e of edges) {
    if (!g.hasNode(e.source) || !g.hasNode(e.target) || e.source === e.target) continue;
    g.setEdge(e.source, e.target, { weight: (into.get(e.target)?.size ?? 0) >= 3 ? 1 : 8 });
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
 * Pick the layout that shows the whole playbook largest in the given frame:
 * top-down, left-to-right, or top-down wrapped into columns. Top-down wins
 * ties because it reads most naturally.
 */
export function autoLayout(nodes: PlaybookNode[], edges: PlaybookEdge[], frameW = 960, frameH = 600): Layout {
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
  return routeSkips(best, edges);
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

export function placeGroups(l: Layout, groups: PlaybookGroup[]): Annotations {
  const nodeRect = (id: string): Rect | null => {
    const p = l.positions.get(id);
    return p ? { x: p.x, y: p.y, w: NODE_W, h: NODE_H } : null;
  };
  const steps = [...l.positions.keys()].map((id) => ({ id, r: nodeRect(id)! }));
  const taken: Rect[] = steps.map((s) => s.r);
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
    // Start beside the step (then the other side of it, then further out) and slide along.
    // Centred on the step, so the note sits evenly beside it and the link runs straight.
    const mid = across ? a.x + (NODE_W - NOTE_W) / 2 : a.y + (NODE_H - h) / 2;
    const starts: Rect[] = across
      ? [a.y + NODE_H + NOTE_GAP, a.y - NOTE_GAP - h, a.y + NODE_H + 2 * NOTE_GAP + h].map((y) => ({ x: mid, y, w: NOTE_W, h }))
      : [a.x + NODE_W + NOTE_GAP, a.x - NOTE_GAP - NOTE_W, a.x + NODE_W + 2 * NOTE_GAP + NOTE_W].map((x) => ({ x, y: mid, w: NOTE_W, h }));
    let placed: Rect | null = null;
    for (const start of starts) {
      let r = start;
      for (let i = 0; i < 40; i++) {
        const hit = [...taken, ...blocks.values()].find((t) => hits(r, t));
        if (!hit) {
          placed = r;
          break;
        }
        r = across ? { ...r, x: hit.x + hit.w + 12 } : { ...r, y: hit.y + hit.h + 12 };
        // Too far from its step to read as its note: try the next start.
        if (across ? r.x - a.x > NODE_W * 2 : r.y - a.y > NODE_H * 3) break;
      }
      if (placed) break;
    }
    placed ??= across
      ? { x: mid, y: Math.max(...taken.map((t) => t.y + t.h)) + NOTE_GAP, w: NOTE_W, h }
      : { x: Math.max(...taken.map((t) => t.x + t.w)) + NOTE_GAP, y: mid, w: NOTE_W, h };
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

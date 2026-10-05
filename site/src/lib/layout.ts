import dagre from 'dagre';
import type { PlaybookEdge, PlaybookNode } from './types';

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
  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target) && e.source !== e.target) g.setEdge(e.source, e.target);
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

/**
 * Split a top-down layout into `cols` columns of consecutive ranks, read
 * left to right like newspaper text. Long playbooks are mostly chains, so
 * this shows them far larger than one tall column or one wide row.
 */
function wrap(tb: Layout, edges: PlaybookEdge[], cols: number): Layout {
  const ys = [...new Set([...tb.positions.values()].map((p) => p.y))].sort((a, b) => a - b);
  const perCol = Math.ceil(ys.length / cols);
  const rankIndex = new Map(ys.map((y, i) => [y, i]));
  const colOf = new Map<string, number>();
  const positions = new Map<string, Point>();

  let offset = MARGIN;
  let height = 0;
  for (let c = 0; c * perCol < ys.length; c++) {
    const ids = [...tb.positions].filter(([, p]) => Math.floor(rankIndex.get(p.y)! / perCol) === c);
    const minX = Math.min(...ids.map(([, p]) => p.x));
    const maxX = Math.max(...ids.map(([, p]) => p.x)) + NODE_W;
    for (const [id, p] of ids) {
      const row = rankIndex.get(p.y)! - c * perCol;
      positions.set(id, { x: offset + p.x - minX, y: MARGIN + row * (NODE_H + RANKSEP_TB) });
      colOf.set(id, c);
    }
    const rows = Math.min(perCol, ys.length - c * perCol);
    height = Math.max(height, MARGIN * 2 + rows * NODE_H + (rows - 1) * RANKSEP_TB);
    offset += maxX - minX + COL_GAP;
  }
  const wrapped = new Set(edges.filter((e) => colOf.get(e.source) !== colOf.get(e.target)).map((e) => e.id));
  return { dir: 'TB', positions, width: offset - COL_GAP + MARGIN, height, wrapped };
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
  if (nodes.length < 3) return tb;
  const zoom = (l: Layout) => fitZoom(l, frameW, frameH);
  let best = tb;
  const lr = run(nodes, edges, 'LR');
  if (zoom(lr) > zoom(best) * 1.1) best = lr;
  // Wrapping costs some readability (edges jump between columns), so it has
  // to show the steps clearly larger to be worth it.
  const ranks = new Set([...tb.positions.values()].map((p) => p.y)).size;
  for (let cols = 2; cols <= Math.min(6, Math.floor(ranks / 2)); cols++) {
    const w = wrap(tb, edges, cols);
    if (zoom(w) > zoom(best) * 1.25) best = w;
  }
  return best;
}

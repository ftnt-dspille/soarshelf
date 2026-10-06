import { JUMP_GAP, NODE_H, NODE_W, autoLayout, jumpPoints, roundedPath } from './layout';
import type { NodeFamily, PlaybookNode } from './types';

/** Same geometry as the full viewer, so previews and the canvas match. */
export const PV_W = NODE_W;
export const PV_H = NODE_H;

export interface PreviewNode {
  id: string;
  name: string;
  label: string;
  family: NodeFamily;
  connector?: string;
}

export interface PreviewEdge {
  id: string;
  source: string;
  target: string;
  label: string | null;
}

export interface LaidOutPreview {
  width: number;
  height: number;
  nodes: (PreviewNode & { x: number; y: number; rank: number })[];
  edges: (PreviewEdge & { d: string; mid: { x: number; y: number }; rank: number })[];
}

/** Room above and below wrapped columns for the lines that jump between them. */
const JUMP_PAD = JUMP_GAP + 8;

/**
 * Lay a playbook out with the viewer's engine (top-down, sideways, or
 * wrapped into columns) for a frame of the given aspect, and turn its edges
 * into SVG paths. A jump between columns runs along the gap between them.
 */
export function previewLayout(nodes: PreviewNode[], edges: PreviewEdge[], aspect = 16 / 10): LaidOutPreview {
  const asNodes = nodes.map((n) => ({ ...n, x: 0, y: 0, args: {} }) as PlaybookNode);
  const l = autoLayout(asNodes, edges, 1000 * aspect, 1000);
  const across = l.dir === 'LR';

  // Rank = order along the flow, used to stagger the draw-in animation.
  const keyOf = (p: { x: number; y: number }) => (across ? p.x : p.x * 1e4 + p.y);
  const order = [...l.positions.values()].map(keyOf).sort((a, b) => a - b);
  const rankOf = (id: string) => order.indexOf(keyOf(l.positions.get(id)!));

  const pad = l.wrapped.size ? JUMP_PAD : 0;
  const placed = nodes.map((n) => {
    const p = l.positions.get(n.id)!;
    return { ...n, x: p.x, y: p.y + pad, rank: rankOf(n.id) };
  });
  const at = new Map(placed.map((n) => [n.id, n]));
  const valid = edges.filter((e) => at.has(e.source) && at.has(e.target) && e.source !== e.target);

  const laid = valid.map((e) => {
      const s = at.get(e.source)!;
      const t = at.get(e.target)!;
      // Exit/enter on the sides that face the flow direction.
      const a = across ? { x: s.x + PV_W, y: s.y + PV_H / 2 } : { x: s.x + PV_W / 2, y: s.y + PV_H };
      const b = across ? { x: t.x, y: t.y + PV_H / 2 } : { x: t.x + PV_W / 2, y: t.y };
      if (l.wrapped.has(e.id)) {
        // Layout coordinates, shifted down by the padding added above the columns.
        const pts = jumpPoints(l, e.source, e.target, { x: a.x, y: a.y - pad }, { x: b.x, y: b.y - pad }).map((q) => ({ x: q.x, y: q.y + pad }));
        return { ...e, d: roundedPath(pts), mid: { x: pts[2].x, y: (pts[2].y + pts[3].y) / 2 }, rank: s.rank };
      }
      const bend = across ? Math.max(40, (b.x - a.x) / 2) : Math.max(40, Math.abs(b.y - a.y) / 2);
      const d = across
        ? `M${a.x},${a.y} C${a.x + bend},${a.y} ${b.x - bend},${b.y} ${b.x},${b.y}`
        : `M${a.x},${a.y} C${a.x},${a.y + bend} ${b.x},${b.y - bend} ${b.x},${b.y}`;
      return { ...e, d, mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, rank: s.rank };
    });

  return { width: l.width, height: l.height + pad * 2, nodes: placed, edges: laid };
}

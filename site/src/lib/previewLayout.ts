import { NODE_H, NODE_W, autoLayout } from './layout';
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

/**
 * Lay a playbook out with the viewer's engine (top-down, sideways, or
 * wrapped into columns) for a frame of the given aspect, and turn its edges
 * into SVG paths.
 */
export function previewLayout(nodes: PreviewNode[], edges: PreviewEdge[], aspect = 16 / 10): LaidOutPreview {
  const asNodes = nodes.map((n) => ({ ...n, x: 0, y: 0, args: {} }) as PlaybookNode);
  const l = autoLayout(asNodes, edges, 1000 * aspect, 1000);
  const across = l.dir === 'LR';

  // Rank = order along the flow, used to stagger the draw-in animation.
  const keyOf = (p: { x: number; y: number }) => (across ? p.x : p.x * 1e4 + p.y);
  const order = [...l.positions.values()].map(keyOf).sort((a, b) => a - b);
  const rankOf = (id: string) => order.indexOf(keyOf(l.positions.get(id)!));

  const placed = nodes.map((n) => ({ ...n, ...l.positions.get(n.id)!, rank: rankOf(n.id) }));
  const at = new Map(placed.map((n) => [n.id, n]));

  const laid = edges
    .filter((e) => at.has(e.source) && at.has(e.target) && e.source !== e.target)
    .map((e) => {
      const s = at.get(e.source)!;
      const t = at.get(e.target)!;
      // Exit/enter on the sides that face the flow direction.
      const a = across ? { x: s.x + PV_W, y: s.y + PV_H / 2 } : { x: s.x + PV_W / 2, y: s.y + PV_H };
      const b = across ? { x: t.x, y: t.y + PV_H / 2 } : { x: t.x + PV_W / 2, y: t.y };
      if (l.wrapped.has(e.id)) {
        // Column jump: drop below the source, run up the gutter between the
        // columns, and come down into the target - all inside the frame.
        const gx = (s.x + PV_W + t.x) / 2;
        const pts = [a, { x: a.x, y: a.y + 12 }, { x: gx, y: a.y + 12 }, { x: gx, y: b.y - 12 }, { x: b.x, y: b.y - 12 }, b];
        return { ...e, d: rounded(pts), mid: { x: gx, y: (a.y + b.y) / 2 }, rank: s.rank };
      }
      const bend = across ? Math.max(40, (b.x - a.x) / 2) : Math.max(40, Math.abs(b.y - a.y) / 2);
      const d = across
        ? `M${a.x},${a.y} C${a.x + bend},${a.y} ${b.x - bend},${b.y} ${b.x},${b.y}`
        : `M${a.x},${a.y} C${a.x},${a.y + bend} ${b.x},${b.y - bend} ${b.x},${b.y}`;
      return { ...e, d, mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, rank: s.rank };
    });

  return { width: l.width, height: l.height, nodes: placed, edges: laid };
}

/** Orthogonal polyline with rounded corners. */
function rounded(pts: { x: number; y: number }[], r = 10): string {
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

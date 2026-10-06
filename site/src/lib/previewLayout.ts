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
  /** Column jumps, drawn as a lettered badge under the source and above the target. */
  jumps: Jump[];
}

export interface Jump {
  id: string;
  tag: string;
  rank: number;
  /** Stub from the source down to its badge, and from the target's badge into the target. */
  out: { d: string; at: { x: number; y: number } };
  in: { d: string; at: { x: number; y: number } };
}

/** Badge radius and the stub between a step and its badge. */
export const JUMP_R = 11;
const STUB = 14;
/** Room above and below the columns for the badges. */
const JUMP_PAD = STUB + JUMP_R * 2 + 4;

/**
 * Lay a playbook out with the viewer's engine (top-down, sideways, or
 * wrapped into columns) for a frame of the given aspect, and turn its edges
 * into SVG paths. Column jumps become lettered connector badges rather than
 * long lines around the outside.
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

  // One letter per jump target, so several jumps into one step share it.
  const tags = new Map<string, string>();
  const jumps: Jump[] = [];
  const sideOut = (id: string) => valid.some((e) => e.source === id && !l.wrapped.has(e.id));
  const sideIn = (id: string) => valid.some((e) => e.target === id && !l.wrapped.has(e.id));
  for (const e of valid.filter((e) => l.wrapped.has(e.id))) {
    const s = at.get(e.source)!;
    const t = at.get(e.target)!;
    if (!tags.has(e.target)) tags.set(e.target, String.fromCharCode(65 + (tags.size % 26)));
    // Step aside from an ordinary edge that leaves or enters the same side.
    const sx = s.x + PV_W / 2 + (sideOut(e.source) ? PV_W * 0.3 : 0);
    const tx = t.x + PV_W / 2 - (sideIn(e.target) ? PV_W * 0.3 : 0);
    const sy = s.y + PV_H;
    const ty = t.y;
    jumps.push({
      id: e.id,
      tag: tags.get(e.target)!,
      rank: s.rank,
      out: { d: `M${sx},${sy} L${sx},${sy + STUB}`, at: { x: sx, y: sy + STUB + JUMP_R } },
      in: { d: `M${tx},${ty - STUB} L${tx},${ty}`, at: { x: tx, y: ty - STUB - JUMP_R } }
    });
  }

  const laid = valid
    .filter((e) => !l.wrapped.has(e.id))
    .map((e) => {
      const s = at.get(e.source)!;
      const t = at.get(e.target)!;
      // Exit/enter on the sides that face the flow direction.
      const a = across ? { x: s.x + PV_W, y: s.y + PV_H / 2 } : { x: s.x + PV_W / 2, y: s.y + PV_H };
      const b = across ? { x: t.x, y: t.y + PV_H / 2 } : { x: t.x + PV_W / 2, y: t.y };
      const bend = across ? Math.max(40, (b.x - a.x) / 2) : Math.max(40, Math.abs(b.y - a.y) / 2);
      const d = across
        ? `M${a.x},${a.y} C${a.x + bend},${a.y} ${b.x - bend},${b.y} ${b.x},${b.y}`
        : `M${a.x},${a.y} C${a.x},${a.y + bend} ${b.x},${b.y - bend} ${b.x},${b.y}`;
      return { ...e, d, mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, rank: s.rank };
    });

  return { width: l.width, height: l.height + pad * 2, nodes: placed, edges: laid, jumps };
}

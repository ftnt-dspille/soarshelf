// A glow that travels the arrows from the start of a playbook to its end: each edge
// lights up a beat after the edge that feeds it, then the whole thing rests and repeats.

export interface GlowEdge {
  id: string;
  source: string;
  target: string;
}

/** Hops from the nearest start step (one nothing leads to) to each edge's source. A step on a loop keeps its first depth. */
export function edgeDepths(nodeIds: string[], edges: GlowEdge[]): Map<string, number> {
  const out = new Map<string, GlowEdge[]>();
  const hasIn = new Set<string>();
  for (const e of edges) {
    if (e.source === e.target) continue;
    (out.get(e.source) ?? out.set(e.source, []).get(e.source)!).push(e);
    hasIn.add(e.target);
  }
  const starts = nodeIds.filter((id) => !hasIn.has(id));
  const depth = new Map<string, number>();
  const queue = (starts.length ? starts : nodeIds.slice(0, 1)).map((id) => (depth.set(id, 0), id));
  for (let i = 0; i < queue.length; i++) {
    const id = queue[i];
    for (const e of out.get(id) ?? []) {
      if (!depth.has(e.target)) {
        depth.set(e.target, depth.get(id)! + 1);
        queue.push(e.target);
      }
    }
  }
  const byEdge = new Map<string, number>();
  for (const e of edges) byEdge.set(e.id, depth.get(e.source) ?? 0);
  return byEdge;
}

const STEP_MS = 420; // between one edge lighting and the next down the flow
const GLOW_MS = 900; // one edge's glow, up and back down
const REST_MS = 2200; // quiet before the cascade starts over
const TRACE_MS = 650; // a comet's run along one edge
const COMET = 26; // a comet's length in px

/**
 * How the glow moves: `cascade` lights each whole arrow a beat after the one feeding it,
 * `trace` runs a short comet along each arrow in turn, `pulse` breathes every arrow at once.
 */
export type GlowMode = 'cascade' | 'trace' | 'pulse';
export const GLOW_MODES: GlowMode[] = ['cascade', 'trace', 'pulse'];
/** Multiplier on every duration: higher is slower. */
export const GLOW_SPEEDS = { fast: 0.6, normal: 1, slow: 1.7 } as const;
export type GlowSpeed = keyof typeof GLOW_SPEEDS;

export interface GlowOptions {
  mode?: GlowMode;
  speed?: GlowSpeed;
  /** Run even when the visitor asks for reduced motion (dev comparison only). */
  force?: boolean;
}

/**
 * Animate the drawn arrows under `root`. Returns a function that stops it. Does nothing for
 * visitors who ask for reduced motion.
 */
export function startEdgeGlow(root: HTMLElement, nodeIds: string[], edges: GlowEdge[], opts: GlowOptions = {}): () => void {
  const { mode = 'cascade', speed = 'normal', force = false } = opts;
  if (!force && typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches) return () => {};
  const k = GLOW_SPEEDS[speed];
  const step = (mode === 'trace' ? TRACE_MS : STEP_MS) * k;
  const glow = GLOW_MS * k;
  const restMs = REST_MS * k;
  const depths = edgeDepths(nodeIds, edges);
  const last = Math.max(0, ...depths.values());
  const cycle = mode === 'pulse' ? glow * 2 + restMs / 2 : last * step + (mode === 'trace' ? step : glow) + restMs;
  const color = getComputedStyle(root).getPropertyValue('--accent').trim() || '#d81b60';
  const running: Animation[] = [];
  const added: Element[] = [];
  for (const e of edges) {
    const path = root.querySelector<SVGPathElement>(`.svelte-flow__edge[data-id="${CSS.escape(e.id)}"] .svelte-flow__edge-path`);
    if (!path) continue;
    const delay = mode === 'pulse' ? 0 : (depths.get(e.id) ?? 0) * step;
    if (mode === 'trace') {
      // A copy of the line, drawn as one short dash that slides from its start to its end.
      const len = path.getTotalLength();
      const comet = path.cloneNode() as SVGPathElement;
      comet.removeAttribute('marker-end');
      comet.removeAttribute('marker-start');
      comet.removeAttribute('id');
      comet.setAttribute('class', 'edge-comet');
      comet.setAttribute(
        'style',
        `fill: none; stroke: ${color}; stroke-width: 2.6px; stroke-linecap: round; pointer-events: none;` +
          ` stroke-dasharray: ${COMET} ${len + COMET}; stroke-dashoffset: ${COMET};` +
          ` filter: drop-shadow(0 0 3px ${color}) drop-shadow(0 0 7px ${color});`
      );
      path.after(comet);
      added.push(comet);
      const run = step / cycle;
      running.push(
        comet.animate(
          [
            { strokeDashoffset: `${COMET}`, offset: 0 },
            { strokeDashoffset: `${-len}`, offset: run },
            { strokeDashoffset: `${-len}`, offset: 1 }
          ],
          { duration: cycle, delay, iterations: Infinity }
        )
      );
      continue;
    }
    const hot = (mode === 'pulse' ? glow * 2 : glow) / cycle;
    // Every keyframe sets every animated property: one left out is faded across the whole
    // cycle instead of snapping back to rest.
    const cs = getComputedStyle(path);
    const base = { stroke: cs.stroke, strokeWidth: cs.strokeWidth };
    const rest = { ...base, filter: 'drop-shadow(0 0 0 transparent)' };
    const lit = { stroke: color, strokeWidth: '2.5px', filter: `drop-shadow(0 0 4px ${color}) drop-shadow(0 0 9px ${color})` };
    // Delay is applied once; every edge shares the same period, so the order never drifts.
    running.push(
      path.animate(
        [
          { ...rest, offset: 0 },
          { ...lit, offset: hot * (mode === 'pulse' ? 0.5 : 0.35) },
          { ...rest, offset: hot },
          { ...rest, offset: 1 }
        ],
        { duration: cycle, delay, iterations: Infinity }
      )
    );
  }
  return () => {
    running.forEach((a) => a.cancel());
    added.forEach((el) => el.remove());
  };
}

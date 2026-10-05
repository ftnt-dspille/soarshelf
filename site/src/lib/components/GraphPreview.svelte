<script lang="ts">
  import { FAMILY_ICON } from '$lib/icons';
  import { PV_H, PV_W, previewLayout, type PreviewEdge, type PreviewNode } from '$lib/previewLayout';

  // Read-only SVG drawing of a playbook. No canvas library, so it is cheap
  // enough to render on the home page and scales with its container.
  let {
    nodes,
    edges,
    labels = {},
    aspect = 16 / 10
  }: { nodes: PreviewNode[]; edges: PreviewEdge[]; labels?: Record<string, string>; aspect?: number } = $props();

  const g = $derived(previewLayout(nodes, edges, aspect));
  const uid = $props.id();

  function fit(s: string, n: number): string {
    return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
  }
  function kind(n: PreviewNode): string {
    return n.connector ? (labels[n.connector] ?? n.connector) : n.label;
  }
</script>

<svg
  viewBox="0 0 {g.width} {g.height}"
  preserveAspectRatio="xMidYMid meet"
  class="h-full w-full"
  role="img"
  aria-label="Playbook graph with {nodes.length} steps"
>
  <defs>
    <marker id="{uid}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--border-strong)" />
    </marker>
  </defs>

  {#each g.edges as e (e.id)}
    <g class="edge" style="--d: {e.rank * 90}ms">
      <path d={e.d} class="wire" marker-end="url(#{uid}-arrow)" />
      <path d={e.d} class="flow" />
      {#if e.label}
        <g transform="translate({e.mid.x} {e.mid.y})">
          <rect x={-(fit(e.label, 18).length * 3.9 + 10)} y="-11" width={fit(e.label, 18).length * 7.8 + 20} height="22" rx="11" class="pill" />
          <text text-anchor="middle" dy="4" class="pill-text">{fit(e.label, 18)}</text>
        </g>
      {/if}
    </g>
  {/each}

  {#each g.nodes as n (n.id)}
    {@const Icon = FAMILY_ICON[n.family]}
    <g transform="translate({n.x} {n.y})">
      <g class="node" style="--fam: var(--fam-{n.family}); --d: {n.rank * 90}ms">
        <rect width={PV_W} height={PV_H} rx="12" class="card" />
        <rect x="0" y="12" width="3.5" height={PV_H - 24} rx="1.75" class="bar" />
        <rect x="14" y={(PV_H - 34) / 2} width="34" height="34" rx="9" class="chip" />
        <Icon x={22} y={(PV_H - 18) / 2} size={18} class="ico" aria-hidden="true" />
        <text x="60" y="28" class="kind">{fit(kind(n).toUpperCase(), 26)}</text>
        <text x="60" y="47" class="name">{fit(n.name, 22)}</text>
      </g>
    </g>
  {/each}
</svg>

<style>
  .card {
    fill: var(--surface);
    stroke: var(--border);
  }
  .bar {
    fill: var(--fam);
  }
  .chip {
    fill: color-mix(in srgb, var(--fam) 14%, transparent);
  }
  .node :global(.ico) {
    color: var(--fam);
  }
  .kind {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    fill: var(--faint);
  }
  .name {
    font-size: 15px;
    font-weight: 600;
    fill: var(--fg);
  }
  .wire {
    fill: none;
    stroke: var(--border-strong);
    stroke-width: 2;
  }
  .flow {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-dasharray: 2 16;
    opacity: 0.75;
  }
  .pill {
    fill: var(--surface-2);
    stroke: var(--border);
  }
  .pill-text {
    font-size: 12px;
    font-weight: 500;
    fill: var(--muted);
  }

  @media (prefers-reduced-motion: no-preference) {
    .node,
    .edge {
      animation: rise 0.45s ease-out both;
      animation-delay: var(--d);
    }
    .flow {
      animation: flow 1.1s linear infinite;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .flow {
      display: none;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }
  @keyframes flow {
    to {
      stroke-dashoffset: -18;
    }
  }
</style>

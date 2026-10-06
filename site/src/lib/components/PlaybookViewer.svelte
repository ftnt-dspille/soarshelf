<script lang="ts">
  import { SvelteFlow, Background, Controls, MarkerType, type Node, type Edge, type useSvelteFlow } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { untrack } from 'svelte';
  import type { Collection, PlaybookNode } from '$lib/types';
  import { theme } from '$lib/theme.svelte';
  import { NODE_H, NODE_W, autoLayout, fitZoom, jumpPoints, type Layout } from '$lib/layout';
  import { FAMILY_ICON } from '$lib/icons';
  import { FAMILY_KEY } from '$lib/format';
  import StepNode from './StepNode.svelte';
  import JumpEdge from './JumpEdge.svelte';
  import StepInspector from './StepInspector.svelte';
import MinimapNav from './MinimapNav.svelte';
  import Zap from '@lucide/svelte/icons/zap';

  let {
    collections,
    labels,
    initialKey = '0:0',
    initialStep = null
  }: { collections: Collection[]; labels: Map<string, string>; initialKey?: string; initialStep?: string | null } = $props();

  // Flatten to one list so a single <select> can pick any playbook in any collection.
  const options = $derived(
    collections.flatMap((c, ci) => c.playbooks.map((p, pi) => ({ key: `${ci}:${pi}`, collection: c, playbook: p })))
  );
  let selectedKey = $state(untrack(() => initialKey));
  // Follow deep links that arrive after mount (hash changes while the viewer is open).
  $effect(() => {
    const k = initialKey;
    untrack(() => {
      if (options.some((o) => o.key === k)) selectedKey = k;
    });
  });
  const current = $derived(options.find((o) => o.key === selectedKey) ?? options[0]);
  const playbook = $derived(current?.playbook);


  let selectedId = $state<string | null>(null);
  const selected = $derived(playbook?.nodes.find((n) => n.id === selectedId) ?? null);

  const nodeTypes = { step: StepNode };
  const edgeTypes = { jump: JumpEdge };
  let boxW = $state(0);
  let boxH = $state(0);

  // Always laid out automatically: export coordinates are often missing or
  // overlapping, and a consistent layout reads better across playbooks.
  let layout: Layout | null = null;

  function buildNodes(): Node[] {
    if (!playbook) return [];
    layout = autoLayout(playbook.nodes, playbook.edges, boxW || 960, boxH || 600);
    const l = layout;
    return playbook.nodes.map((n) => ({
      id: n.id,
      type: 'step',
      position: l.positions.get(n.id) ?? { x: 0, y: 0 },
      data: { step: n, connectorLabel: n.connector ? (labels.get(n.connector) ?? n.connector) : null, dir: l.dir },
      selected: n.id === selectedId,
      draggable: false,
      connectable: false,
      deletable: false
    }));
  }

  function buildEdges(): Edge[] {
    if (!playbook) return [];
    const l = layout;
    const wrapped = l?.wrapped ?? new Set<string>();
    const at = (id: string) => l?.positions.get(id) ?? { x: 0, y: 0 };
    return playbook.edges.map((e) => {
      const jump = !!l && wrapped.has(e.id);
      // The line runs along the gap between the two columns.
      const gx = jump
        ? jumpPoints(l!, e.source, e.target, { x: at(e.source).x + NODE_W / 2, y: at(e.source).y + NODE_H }, { x: at(e.target).x + NODE_W / 2, y: at(e.target).y })[2].x
        : 0;
      return {
      id: e.id,
      source: e.source,
      target: e.target,
      type: jump ? 'jump' : 'smoothstep',
      data: jump ? { gx } : undefined,
      label: e.label ?? undefined,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      deletable: false,
      selectable: false
      };
    });
  }

  // Rebuilt (and the canvas re-keyed) only when the playbook changes or the
  // canvas is first measured, not on selection changes.
  let nodes = $state.raw<Node[]>([]);
  let edges = $state.raw<Edge[]>([]);
  const viewKey = $derived(`${selectedKey}|${boxW > 0}`);
  // The canvas is re-created via renderKey only after nodes are rebuilt, so its
  // initial viewport is computed from the new playbook rather than the previous one.
  let renderKey = $state(0);
  $effect(() => {
    void viewKey;
    untrack(() => {
      // A deep link can open with one step selected (inspector showing).
      selectedId = initialStep && playbook?.nodes.some((n) => n.id === initialStep) ? initialStep : null;
      nodes = buildNodes();
      edges = buildEdges();
      renderKey++;
    });
  });

  // Open on the whole playbook, centred, at the largest zoom that fits it
  // (capped so small playbooks don't look oversized).
  function initialViewport() {
    if (!layout || !boxW || !boxH) return { x: 0, y: 0, zoom: 1 };
    // Wrapped layouts need room above and below the columns for the lines between them.
    const zoom = Math.max(Math.min(fitZoom(layout, boxW, boxH, layout.wrapped.size ? 56 : 32), 1), 0.2);
    return {
      x: (boxW - layout.width * zoom) / 2,
      y: (boxH - layout.height * zoom) / 2,
      zoom
    };
  }

  function selectNode(n: PlaybookNode | null) {
    selectedId = n?.id ?? null;
    nodes = nodes.map((x) => ({ ...x, selected: x.id === selectedId }));
  }

  // A later deep link to another step of the same playbook.
  $effect(() => {
    const id = initialStep;
    untrack(() => {
      const n = id ? playbook?.nodes.find((x) => x.id === id) : undefined;
      if (n && n.id !== selectedId) selectNode(n);
    });
  });

  let flow: ReturnType<typeof useSvelteFlow> | null = null;

  /** Select a step by name and bring it into view (decision branch links). */
  function jumpTo(name: string) {
    const n = playbook?.nodes.find((x) => x.name === name);
    const placed = n && nodes.find((x) => x.id === n.id);
    if (!n || !placed) return;
    selectNode(n);
    flow?.setCenter(placed.position.x + NODE_W / 2, placed.position.y + NODE_H / 2, {
      zoom: Math.max(flow.getViewport().zoom, 0.8),
      duration: 300
    });
  }
</script>

{#if !playbook}
  <p class="rounded-xl border border-dashed border-line p-8 text-center text-sm text-muted">This item has no playbooks to show.</p>
{:else}
  <div class="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
    <div class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
      {#if options.length > 1}
        <label class="flex min-w-0 flex-1 items-center gap-2 text-sm sm:flex-none">
          <span class="sr-only">Playbook</span>
          <select
            bind:value={selectedKey}
            class="h-9 w-full min-w-0 rounded-lg border border-line bg-surface px-2.5 text-sm text-fg sm:w-80"
          >
            {#each collections as c, ci (ci)}
              <optgroup label={c.name}>
                {#each c.playbooks as p, pi (pi)}
                  <option value="{ci}:{pi}">{p.name}</option>
                {/each}
              </optgroup>
            {/each}
          </select>
        </label>
      {:else}
        <h3 class="min-w-0 flex-1 truncate text-sm font-semibold sm:flex-none">{playbook.name}</h3>
      {/if}
      <span class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">
        <Zap size={12} style="color: var(--fam-trigger)" aria-hidden="true" />{playbook.trigger}
      </span>
      <span class="text-xs text-faint">{playbook.nodes.length} steps</span>
    </div>
    {#if playbook.description}
      <p class="border-b border-line px-4 py-2.5 text-sm text-muted">{playbook.description}</p>
    {/if}

    <div class="flex flex-col lg:flex-row">
      <div class="h-[460px] min-w-0 flex-1 sm:h-[600px]" bind:clientWidth={boxW} bind:clientHeight={boxH}>
        {#key renderKey}
          {#if boxW && nodes.length}
          <SvelteFlow
            bind:nodes
            bind:edges
            {nodeTypes}
            {edgeTypes}
            colorMode={theme.current}
            initialViewport={initialViewport()}
            minZoom={0.2}
            maxZoom={1.8}
            nodesConnectable={false}
            nodesDraggable={false}
            elementsSelectable={true}
            deleteKey={null}
            zoomOnScroll={false}
            panOnScroll={false}
            preventScrolling={false}
            onnodeclick={({ node }) => selectNode((node.data as { step: PlaybookNode }).step)}
            onpaneclick={() => selectNode(null)}
          >
            <Background gap={18} size={1.2} />
            <Controls showLock={false} />
            <MinimapNav onflow={(f) => (flow = f)} />
          </SvelteFlow>
          {/if}
        {/key}
      </div>

      <aside
        class="border-t border-line lg:w-[380px] lg:shrink-0 lg:border-t-0 lg:border-l"
        aria-label="Step inspector"
        aria-live="polite"
      >
        {#if selected}
          <StepInspector
            step={selected}
            connectorLabel={selected.connector ? (labels.get(selected.connector) ?? selected.connector) : null}
            onclose={() => selectNode(null)}
            onjump={jumpTo}
          />
        {:else}
          <div class="p-5 text-sm text-muted">
            <p class="font-medium text-fg">Inspect a step</p>
            <p class="mt-1">Select any step to see its type, connector operation and arguments.</p>
            <ul class="mt-4 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
              {#each [...new Set(playbook.nodes.map((n) => n.family))] as fam (fam)}
                {@const Icon = FAMILY_ICON[fam]}
                <li class="flex items-center gap-1.5">
                  <span style="color: var(--fam-{fam})" aria-hidden="true"><Icon size={13} /></span>{FAMILY_KEY[fam]}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </aside>
    </div>
  </div>
{/if}

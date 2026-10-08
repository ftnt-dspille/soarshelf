<script lang="ts">
  import { SvelteFlow, Background, Controls, MarkerType, type Node, type Edge, type useSvelteFlow } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { untrack } from 'svelte';
  import type { Collection, PlaybookNode } from '$lib/types';
  import { theme } from '$lib/theme.svelte';
  import { NODE_H, NODE_W, autoLayout, fitZoom, isRouted, jumpPoints, placeGroups, type Annotations, type Layout } from '$lib/layout';
  import { FAMILY_ICON } from '$lib/icons';
  import { FAMILY_KEY } from '$lib/format';
  import StepNode from './StepNode.svelte';
  import NoteNode from './NoteNode.svelte';
  import BlockNode from './BlockNode.svelte';
  import JumpEdge from './JumpEdge.svelte';
  import StepInspector from './StepInspector.svelte';
import MinimapNav from './MinimapNav.svelte';
  import Zap from '@lucide/svelte/icons/zap';
  import Workflow from '@lucide/svelte/icons/workflow';
  import CornerDownRight from '@lucide/svelte/icons/corner-down-right';
  import ClipboardCopy from '@lucide/svelte/icons/clipboard-copy';
  import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
  import { playbookRelations, roleOf } from '$lib/playbookRelations';
  import { clipboardText } from '$lib/clipboard';

  let {
    collections,
    labels,
    icons = {},
    initialKey = null,
    initialStep = null,
    download = null
  }: { collections: Collection[]; labels: Map<string, string>; icons?: Record<string, string>; initialKey?: string | null; initialStep?: string | null; download?: { path: string; filename: string } | null } = $props();

  // Flatten to one list so a single <select> can pick any playbook in any collection.
  const options = $derived(
    collections.flatMap((c, ci) => c.playbooks.map((p, pi) => ({ key: `${ci}:${pi}`, collection: c, playbook: p })))
  );
  // Parents before the playbooks they call, so the page opens on where the work starts.
  const rel = $derived(playbookRelations(collections));
  const defaultKey = $derived.by(() => {
    const ci = collections.findIndex((c) => c.playbooks.length);
    return ci < 0 ? '0:0' : `${ci}:${rel.order[ci][0]}`;
  });
  let selectedKey = $state<string>(untrack(() => initialKey ?? defaultKey));
  const ROLE_LABEL = { parent: 'Parent playbook', child: 'Child playbook', both: 'Parent and child' } as const;
  const SUFFIX = { parent: ' (parent)', child: ' (child)', both: ' (parent and child)' } as const;
  function openPlaybook(key: string) {
    if (options.some((o) => o.key === key)) selectedKey = key;
  }
  // Follow deep links that arrive after mount (hash changes while the viewer is open).
  $effect(() => {
    const k = initialKey;
    untrack(() => {
      if (k && options.some((o) => o.key === k)) selectedKey = k;
    });
  });
  const current = $derived(options.find((o) => o.key === selectedKey) ?? options[0]);
  const role = $derived(current ? roleOf(rel, current.key) : null);
  const calls = $derived(current ? (rel.calls.get(current.key) ?? []) : []);
  const calledBy = $derived(current ? (rel.calledBy.get(current.key) ?? []) : []);
  const playbook = $derived(current?.playbook);


  let selectedId = $state<string | null>(null);
  const selected = $derived(playbook?.nodes.find((n) => n.id === selectedId) ?? null);

  const nodeTypes = { step: StepNode, note: NoteNode, block: BlockNode };
  const edgeTypes = { jump: JumpEdge };
  let boxW = $state(0);
  let boxH = $state(0);
  let canvasEl: HTMLDivElement | undefined = $state();
  // Read from the element: bind:clientHeight lags behind a height change.
  const frameW = () => canvasEl?.clientWidth || boxW || 960;
  const frameH = () => canvasEl?.clientHeight || boxH || 600;
  // Long playbooks get a taller canvas (decided before layout, so the layout fits it).
  const tall = $derived((playbook?.nodes.length ?? 0) > 12);

  // Always laid out automatically: export coordinates are often missing or
  // overlapping, and a consistent layout reads better across playbooks.
  let layout: Layout | null = null;
  let extras: Annotations | null = null;
  // Note node id -> the step it belongs to (clicking a note selects that step).
  let noteAnchor = new Map<string, string>();

  function groupNodes(): Node[] {
    if (!playbook?.groups?.length || !layout) return [];
    const l = layout;
    const a = (extras = placeGroups(l, playbook.groups));
    noteAnchor = new Map();
    return playbook.groups.flatMap((g): Node[] => {
      const r = g.kind === 'note' ? a.notes.get(g.id) : a.blocks.get(g.id);
      if (!r) return [];
      if (g.kind === 'note') noteAnchor.set(`note-${g.id}`, g.anchor);
      return g.kind === 'note'
        ? [{ id: `note-${g.id}`, type: 'note', position: { x: r.x, y: r.y }, data: { name: g.name, text: g.text, height: r.h, dir: l.dir },
            draggable: false, connectable: false, deletable: false, selectable: false }]
        : [{ id: `block-${g.id}`, type: 'block', position: { x: r.x, y: r.y }, zIndex: -1, data: { name: g.name, text: g.text, width: r.w, height: r.h },
            draggable: false, connectable: false, deletable: false, selectable: false, focusable: false }];
    });
  }

  function buildNodes(): Node[] {
    if (!playbook) return [];
    layout = autoLayout(playbook.nodes, playbook.edges, frameW(), frameH());
    extras = null;
    const l = layout;
    return [...groupNodes(), ...playbook.nodes.map((n) => ({
      id: n.id,
      type: 'step',
      position: l.positions.get(n.id) ?? { x: 0, y: 0 },
      data: {
        step: n,
        childName: n.reference ? (rel.byUuid.get(n.reference.toLowerCase())?.name ?? null) : null,
        connectorLabel: n.connector ? (labels.get(n.connector) ?? n.connector) : null,
        connectorIcon: n.connector ? (icons[n.connector] ?? null) : null,
        dir: l.dir
      },
      selected: n.id === selectedId,
      draggable: false,
      connectable: false,
      deletable: false
    }))];
  }

  function buildEdges(): Edge[] {
    if (!playbook) return [];
    const l = layout;
    const at = (id: string) => l?.positions.get(id) ?? { x: 0, y: 0 };
    const noteLinks: Edge[] = [...noteAnchor].map(([id, anchor]) => {
      // A note placed before its step (left of it, or above in a sideways layout) links from that side.
      const r = extras?.notes.get(id.slice('note-'.length));
      const p = at(anchor);
      const before = !!r && (l?.dir === 'LR' ? r.y + r.h <= p.y : r.x + r.w <= p.x);
      return {
      id: `link-${id}`,
      source: anchor,
      sourceHandle: before ? 'note-alt' : 'note',
      target: id,
      targetHandle: before ? 'in-alt' : 'in',
      type: 'straight',
      style: 'stroke: var(--faint); stroke-dasharray: 4 4;',
      deletable: false,
      selectable: false,
      focusable: false
      };
    });
    return [...noteLinks, ...playbook.edges.map((e) => {
      const jump = !!l && isRouted(l, e.id);
      // The line runs along the gap between the two columns.
      const gx = jump
        ? jumpPoints(l!, e.source, e.target, { x: at(e.source).x + NODE_W / 2, y: at(e.source).y + NODE_H }, { x: at(e.target).x + NODE_W / 2, y: at(e.target).y }, e.id)[2].x
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
    })];
  }

  // Rebuilt (and the canvas re-keyed) only when the playbook changes or the
  // canvas is first measured, not on selection changes.
  let nodes = $state.raw<Node[]>([]);
  let edges = $state.raw<Edge[]>([]);
  const viewKey = $derived(`${selectedKey}|${boxW > 0}|${tall}`);
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
  // (capped so small playbooks don't look oversized). A playbook too big to fit
  // at a readable size opens at its top instead, and the rest is a pan away.
  const READABLE = 0.6;
  function initialViewport() {
    if (!layout || !boxW) return { x: 0, y: 0, zoom: 1 };
    const W = frameW(), H = frameH();
    const box = extras ?? { left: 0, top: 0, width: layout.width, height: layout.height };
    // Wrapped layouts need room above and below the columns for the lines between them.
    const fit = Math.min(fitZoom(box, W, H, layout.wrapped.size || layout.sideX?.size ? 56 : 32), 1);
    const zoom = Math.max(fit, READABLE);
    const x = box.width * zoom <= W ? (W - box.width * zoom) / 2 : 24;
    const y = box.height * zoom <= H ? (H - box.height * zoom) / 2 : 16;
    return { x: x - box.left * zoom, y: y - box.top * zoom, zoom };
  }

  function selectNode(n: PlaybookNode | null) {
    selectedId = n?.id ?? null;
    nodes = nodes.map((x) => (x.type && x.type !== 'step' ? x : { ...x, selected: x.id === selectedId }));
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

  // Opening the inspector narrows the canvas: pan if the selected step would be hidden.
  $effect(() => {
    const id = selectedId;
    void boxW;
    untrack(() => {
      const placed = id ? nodes.find((x) => x.id === id) : undefined;
      if (!flow || !placed) return;
      const { x, y, zoom } = flow.getViewport();
      const left = placed.position.x * zoom + x, top = placed.position.y * zoom + y;
      const out = left < 0 || top < 0 || left + NODE_W * zoom > frameW() || top + NODE_H * zoom > frameH();
      if (out) flow.setCenter(placed.position.x + NODE_W / 2, placed.position.y + NODE_H / 2, { zoom, duration: 250 });
    });
  });

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

  // Designer clipboard format: paste into any playbook with Cmd/Ctrl+V.
  let copyState = $state<'idle' | 'copying' | 'copied' | 'failed'>('idle');
  let copyTimer: ReturnType<typeof setTimeout> | undefined;
  const canCopy = $derived(!!download && !!playbook?.uuid);
  $effect(() => {
    void selectedKey;
    copyState = 'idle';
  });
  async function copySteps() {
    if (!canCopy || !playbook || copyState === 'copying') return;
    copyState = 'copying';
    clearTimeout(copyTimer);
    try {
      const text = clipboardText(download!, playbook.uuid!);
      // Hand the clipboard a promise so the write still counts as part of the click
      // (Safari drops the permission once we await the download first).
      if (typeof ClipboardItem !== 'undefined' && navigator.clipboard.write)
        await navigator.clipboard.write([
          new ClipboardItem({ 'text/plain': text.then((t) => new Blob([t], { type: 'text/plain' })) })
        ]);
      else await navigator.clipboard.writeText(await text);
      copyState = 'copied';
    } catch {
      copyState = 'failed';
    }
    copyTimer = setTimeout(() => (copyState = 'idle'), 12_000);
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
                {#each rel.order[ci] as pi (pi)}
                  {@const r = roleOf(rel, `${ci}:${pi}`)}
                  <option value="{ci}:{pi}">{c.playbooks[pi].name}{r ? SUFFIX[r] : ''}</option>
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
      {#if canCopy}
      <div class="ml-auto flex items-center gap-2">
        {#if copyState === 'copied'}
          <span class="hidden text-xs text-muted sm:inline">Open a playbook in the designer, click the canvas, press <kbd class="rounded border border-line px-1 font-mono">⌘V</kbd> / <kbd class="rounded border border-line px-1 font-mono">Ctrl V</kbd></span>
        {:else if copyState === 'failed'}
          <span class="text-xs text-block">Couldn't copy. Use the download instead.</span>
        {/if}
        <button
          type="button"
          onclick={copySteps}
          disabled={copyState === 'copying'}
          title={calls.length
            ? 'Copies the steps for pasting into the playbook designer. This playbook calls other playbooks in this item: import the download to get those too.'
            : 'Copies the steps for pasting into the playbook designer'}
          class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-fg hover:border-line-strong hover:bg-surface-2 disabled:opacity-60"
        >
          {#if copyState === 'copied'}
            <ClipboardCheck size={15} class="text-ok" aria-hidden="true" />Copied
          {:else}
            <ClipboardCopy size={15} aria-hidden="true" />Copy steps
          {/if}
        </button>
      </div>
      {/if}
    </div>
    {#if playbook.description}
      <p class="border-b border-line px-4 py-2.5 text-sm text-muted">{playbook.description}</p>
    {/if}
    {#if role}
      <!-- How this playbook relates to the others in the item, with a way to jump to them. -->
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1.5 border-b border-line bg-surface-2/40 px-4 py-2 text-xs">
        <span class="inline-flex items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 font-medium text-accent-text">
          <Workflow size={12} aria-hidden="true" />{ROLE_LABEL[role]}
        </span>
        {#if calls.length}
          <span class="text-muted">Calls</span>
          {#each calls as r (r.key)}
            <button type="button" onclick={() => openPlaybook(r.key)} class="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-0.5 text-fg hover:border-line-strong hover:bg-surface-2">
              <CornerDownRight size={11} aria-hidden="true" />{r.name}
            </button>
          {/each}
        {/if}
        {#if calledBy.length}
          <span class="text-muted">Called by</span>
          {#each calledBy as r (r.key)}
            <button type="button" onclick={() => openPlaybook(r.key)} class="rounded-full border border-line px-2.5 py-0.5 text-fg hover:border-line-strong hover:bg-surface-2">{r.name}</button>
          {/each}
        {/if}
      </div>
    {/if}

    <div class="flex flex-col lg:flex-row">
      <div
        bind:this={canvasEl}
        class="min-w-0 flex-1 {tall ? 'h-[560px] sm:h-[min(85vh,860px)]' : 'h-[460px] sm:h-[600px]'}"
        bind:clientWidth={boxW}
        bind:clientHeight={boxH}
      >
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
            onnodeclick={({ node }) => {
              if (node.type === 'block') return;
              const id = node.type === 'note' ? noteAnchor.get(node.id) : node.id;
              selectNode(playbook?.nodes.find((n) => n.id === id) ?? null);
            }}
            onpaneclick={() => selectNode(null)}
          >
            <Background gap={18} size={1.2} />
            <Controls showLock={false} />
            <MinimapNav onflow={(f) => (flow = f)} />
          </SvelteFlow>
          {/if}
        {/key}
      </div>

      {#if selected}
        <aside
          class="border-t border-line lg:w-[380px] lg:shrink-0 lg:border-t-0 lg:border-l"
          aria-label="Step inspector"
          aria-live="polite"
        >
          <StepInspector
            step={selected}
            connectorLabel={selected.connector ? (labels.get(selected.connector) ?? selected.connector) : null}
            onclose={() => selectNode(null)}
            onjump={jumpTo}
            child={selected.reference ? (rel.byUuid.get(selected.reference.toLowerCase()) ?? null) : null}
            onopen={openPlaybook}
          />
        </aside>
      {/if}
    </div>
    {#if !selected}
      <!-- With nothing selected the graph gets the full width; the key sits underneath. -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line px-4 py-2.5 text-xs text-muted">
        <span class="font-medium text-fg">Select a step to inspect it</span>
        {#each [...new Set(playbook.nodes.map((n) => n.family))] as fam (fam)}
          {@const Icon = FAMILY_ICON[fam]}
          <span class="inline-flex items-center gap-1.5">
            <span style="color: var(--fam-{fam})" aria-hidden="true"><Icon size={13} /></span>{FAMILY_KEY[fam]}
          </span>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<script lang="ts">
  import { MiniMap, useSvelteFlow, type Node } from '@xyflow/svelte';
  import type { PlaybookNode } from '$lib/types';

  // The stock minimap only lets you drag its viewport box. This adds
  // click-to-jump: a click (not a drag) centres the canvas on that point.
  // Must be rendered inside <SvelteFlow> so useSvelteFlow() has a context.
  let { onflow }: { onflow?: (flow: ReturnType<typeof useSvelteFlow>) => void } = $props();
  const flow = useSvelteFlow();
  // Hand the canvas API to the parent, which lives outside the flow context.
  $effect(() => onflow?.(flow));
  let down: { x: number; y: number } | null = null;
  let anchor = $state<HTMLElement>();

  // Delegated from the flow root: the minimap mounts later and is rendered
  // into the panel layer, so it can't be wrapped or found up front.
  $effect(() => {
    const el = anchor?.closest<HTMLElement>('.svelte-flow');
    if (!el) return;
    // Capture phase, and pointerup rather than click: the minimap's own
    // pan/zoom handling swallows the mouse events of a real click.
    el.addEventListener('pointerdown', onpointerdown, true);
    el.addEventListener('pointerup', onpointerup, true);
    return () => {
      el.removeEventListener('pointerdown', onpointerdown, true);
      el.removeEventListener('pointerup', onpointerup, true);
    };
  });

  const minimapOf = (e: Event) => (e.target as Element | null)?.closest?.('.svelte-flow__minimap');

  function onpointerdown(e: PointerEvent) {
    down = minimapOf(e) ? { x: e.clientX, y: e.clientY } : null;
  }

  function onpointerup(e: PointerEvent) {
    const start = down;
    down = null;
    const mm = minimapOf(e);
    if (!mm || !start || Math.hypot(e.clientX - start.x, e.clientY - start.y) > 4) return; // not ours, or a drag
    const svg = mm.querySelector('svg');
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return;
    // The minimap's SVG viewBox is in flow coordinates, so inverting its
    // screen transform turns the click into a canvas position directly.
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    // Deferred: the minimap's pan gesture ends after pointerup and would
    // otherwise reset the viewport over the top of this move.
    setTimeout(() => flow.setCenter(p.x, p.y, { zoom: flow.getViewport().zoom, duration: 300 }), 0);
  }
</script>

<!-- Anchor for finding the flow root. Click-to-jump is a pointer-only
     shortcut; keyboard users pan with the canvas controls. -->
<span bind:this={anchor} hidden></span>
<MiniMap
    width={170}
    height={112}
    pannable
    zoomable
    ariaLabel="Overview map: click to jump, drag to pan"
    nodeColor={(n: Node) => `var(--fam-${(n.data as { step: PlaybookNode }).step.family})`}
    nodeBorderRadius={6}
    class="!hidden cursor-pointer sm:!block"
  />

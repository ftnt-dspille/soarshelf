<script lang="ts">
  import { BaseEdge, type EdgeProps } from '@xyflow/svelte';

  // A jump between wrapped columns, drawn as a short stub out of the source
  // and one into the target, each ending at a matching lettered badge (the
  // flowchart "continues at A" convention) instead of a long line around
  // the outside. `data.out` / `data.in` shift a stub sideways when an
  // ordinary edge uses the same side of the step.
  let { id, sourceX, sourceY, targetX, targetY, markerEnd, data }: EdgeProps = $props();

  const R = 11;
  const STUB = 14;
  const tag = $derived(String(data?.tag ?? ''));
  const sx = $derived(sourceX + Number(data?.out ?? 0));
  const tx = $derived(targetX + Number(data?.in ?? 0));
  const path = $derived(`M${sx},${sourceY} L${sx},${sourceY + STUB} M${tx},${targetY - STUB} L${tx},${targetY}`);
</script>

<BaseEdge {id} {path} {markerEnd} />
{#each [{ x: sx, y: sourceY + STUB + R, title: `Continues at ${tag}` }, { x: tx, y: targetY - STUB - R, title: `Continued from ${tag}` }] as b (b.title)}
  <g transform="translate({b.x} {b.y})" class="jump-badge">
    <title>{b.title}</title>
    <circle r={R} />
    <text text-anchor="middle" dy="4">{tag}</text>
  </g>
{/each}

<style>
  .jump-badge circle {
    fill: var(--surface-2);
    stroke: var(--accent);
    stroke-width: 1.5;
  }
  .jump-badge text {
    font-size: 11px;
    font-weight: 700;
    fill: var(--accent-text);
  }
</style>

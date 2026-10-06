<script lang="ts">
  import { BaseEdge, EdgeLabel, type EdgeProps } from '@xyflow/svelte';
  import { JUMP_GAP, roundedPath } from '$lib/layout';

  // An edge between wrapped columns: down out of the source, along the gap
  // between the columns (`data.gx`), and down into the target, so it reads as
  // an ordinary connection instead of a line hugging the canvas edge. A
  // decision's label sits on the short drop below the source, where the
  // branch starts.
  let { id, sourceX, sourceY, targetX, targetY, markerEnd, data, label }: EdgeProps = $props();

  const path = $derived.by(() => {
    const gx = Number(data?.gx ?? (sourceX + targetX) / 2);
    return roundedPath([
      { x: sourceX, y: sourceY },
      { x: sourceX, y: sourceY + JUMP_GAP },
      { x: gx, y: sourceY + JUMP_GAP },
      { x: gx, y: targetY - JUMP_GAP },
      { x: targetX, y: targetY - JUMP_GAP },
      { x: targetX, y: targetY }
    ]);
  });
</script>

<BaseEdge {id} {path} {markerEnd} />
{#if label}
  <EdgeLabel x={sourceX} y={sourceY + JUMP_GAP / 2}>{label}</EdgeLabel>
{/if}

<script lang="ts">
  import { BaseEdge, type EdgeProps } from '@xyflow/svelte';
  import { JUMP_GAP, roundedPath } from '$lib/layout';

  // An edge between wrapped columns: down out of the source, along the gap
  // between the columns (`data.gx`), and down into the target, so it reads as
  // an ordinary connection instead of a line hugging the canvas edge.
  let { id, sourceX, sourceY, targetX, targetY, markerEnd, data }: EdgeProps = $props();

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

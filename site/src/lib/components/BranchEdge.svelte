<script lang="ts">
  import { BaseEdge, EdgeLabel, Position, getSmoothStepPath, type EdgeProps } from '@xyflow/svelte';
  import { BRANCH_BEND, roundedPath } from '$lib/layout';
  import { branchStyle } from '$lib/branchStyle.svelte';

  // A line leaving a decision, where only one way is taken. The site draws an elbow: a stem to a
  // fork marker, a bar, and a square drop into each target, labelled on the drop. The other
  // shapes in BRANCH_VARIANTS are kept for the dev picker.
  let { id, sourceX, sourceY, targetX, targetY, markerEnd, label }: EdgeProps = $props();

  const v = $derived(branchStyle.variant);
  const forkY = $derived(Math.min(sourceY + BRANCH_BEND, (sourceY + targetY) / 2));
  const dir = $derived(Math.abs(targetX - sourceX) < 2 ? 0 : Math.sign(targetX - sourceX));

  // fan: one stem to the fork, then a curve with vertical tangents at both ends.
  const k = $derived(Math.max(8, (targetY - forkY) * 0.7));
  const c1 = $derived({ x: sourceX, y: forkY + k });
  const c2 = $derived({ x: targetX, y: targetY - k });
  const bez = (t: number) => {
    const u = 1 - t;
    return {
      x: u * u * u * sourceX + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * targetX,
      y: u * u * u * forkY + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * targetY
    };
  };

  // exits: each branch leaves the decision's bottom edge at its own point, toward its target.
  const exitX = $derived(sourceX + dir * Math.min(Math.abs(targetX - sourceX), 48));
  const exitY = $derived(sourceY + 14);

  // tree: a straight diagonal from the fork to just above the target, then down.
  const landY = $derived(Math.max(forkY + 4, targetY - 12));

  const plain = $derived(
    getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition: Position.Bottom, targetPosition: Position.Top, borderRadius: 8 })
  );

  const path = $derived.by(() => {
    switch (v) {
      case 'elbow':
        return roundedPath([{ x: sourceX, y: sourceY }, { x: sourceX, y: forkY }, { x: targetX, y: forkY }, { x: targetX, y: targetY }], 8);
      case 'exits':
        return roundedPath([{ x: exitX, y: sourceY }, { x: exitX, y: exitY }, { x: targetX, y: exitY }, { x: targetX, y: targetY }], 8);
      case 'tree':
        return `M${sourceX},${sourceY} L${sourceX},${forkY} L${targetX},${landY} L${targetX},${targetY}`;
      case 'plain':
        return plain[0];
      default:
        return `M${sourceX},${sourceY} L${sourceX},${forkY} C${c1.x},${c1.y} ${c2.x},${c2.y} ${targetX},${targetY}`;
    }
  });

  // Where the label sits: on the line, past the split, so sibling labels stay apart.
  const labelAt = $derived.by(() => {
    switch (v) {
      case 'elbow':
        return { x: targetX, y: (forkY + targetY) / 2 };
      case 'exits':
        return { x: (exitX + targetX) / 2, y: exitY };
      case 'tree':
        return { x: sourceX + (targetX - sourceX) * 0.6, y: forkY + (landY - forkY) * 0.6 };
      case 'plain':
        return { x: plain[1], y: plain[2] };
      default:
        return bez(0.6);
    }
  });

  const fork = $derived(v === 'fan' || v === 'elbow' || v === 'tree');
  const style = $derived(
    v === 'plain' || !branchStyle.color ? undefined : 'stroke: color-mix(in srgb, var(--fam-decision) 75%, var(--faint))'
  );
</script>

<BaseEdge {id} {path} {markerEnd} {style} />
{#if fork}
  <EdgeLabel x={sourceX} y={forkY} transparent>
    <span class="fork" class:tinted={branchStyle.color} title="Only one of these paths is taken" aria-hidden="true"
      ><svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
        ><path d="M16 3h5v5" /><path d="M8 3H3v5" /><path d="M12 22v-8.3a4 4 0 0 0-1.172-2.872L3 3" /><path d="m15 9 6-6" /></svg
      ></span>
  </EdgeLabel>
{/if}
{#if label}
  <EdgeLabel x={labelAt.x} y={labelAt.y}>{label}</EdgeLabel>
{/if}

<style>
  .fork {
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--muted);
    pointer-events: none;
  }
  .fork.tinted {
    border-color: color-mix(in srgb, var(--fam-decision) 75%, var(--border));
    color: var(--fam-decision);
  }
</style>

<script lang="ts">
  import type { NodeProps, Node } from '@xyflow/svelte';

  type BlockData = { name: string; text: string; width: number; height: number };
  let { data }: NodeProps<Node<BlockData>> = $props();
</script>

<!-- A designer block: a labelled box behind the steps inside it. -->
<div class="block" style="width: {data.width}px; height: {data.height}px" title={data.text || undefined}>
  <span class="label">{data.name || 'Block'}</span>
</div>

<style>
  .block {
    border: 1px dashed var(--border-strong);
    border-radius: 12px;
    background: color-mix(in srgb, var(--surface-2) 45%, transparent);
    padding: 6px 12px;
    pointer-events: none;
  }
  .label {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
  }
</style>

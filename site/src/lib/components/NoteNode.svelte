<script lang="ts">
  import { Handle, Position, type NodeProps, type Node } from '@xyflow/svelte';
  import StickyNote from '@lucide/svelte/icons/sticky-note';

  type NoteData = { name: string; text: string; height: number; dir: 'TB' | 'LR' };
  let { data }: NodeProps<Node<NoteData>> = $props();
</script>

<!-- A designer note. Plain text only: notes are uploaded content. -->
<div class="note" style="height: {data.height}px" title={data.text || data.name}>
  <!-- At the note's middle: a note is centred on its step, so the link runs straight. -->
  <Handle type="target" id="in" position={data.dir === 'LR' ? Position.Top : Position.Left} isConnectable={false} />
  <Handle type="target" id="in-alt" position={data.dir === 'LR' ? Position.Bottom : Position.Right} isConnectable={false} />
  <span class="head"><StickyNote size={13} aria-hidden="true" /><span class="truncate">{data.name || 'Note'}</span></span>
  {#if data.text}<span class="text">{data.text}</span>{/if}
</div>

<style>
  .note {
    width: 240px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px;
    overflow: hidden;
    background: var(--warn-soft);
    border: 1px solid color-mix(in srgb, var(--warn) 30%, var(--border));
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--fg);
  }
  .text {
    display: -webkit-box;
    -webkit-line-clamp: 6;
    line-clamp: 6;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: pre-line;
    overflow-wrap: anywhere;
    font-size: 12px;
    line-height: 18px;
    color: var(--muted);
  }
  .note :global(.svelte-flow__handle) {
    opacity: 0;
  }
</style>

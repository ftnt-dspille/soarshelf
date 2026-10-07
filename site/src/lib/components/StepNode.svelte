<script lang="ts">
  import { Handle, Position, type NodeProps, type Node } from '@xyflow/svelte';
  import type { PlaybookNode } from '$lib/types';
  import { FAMILY_ICON } from '$lib/icons';
  import { humanizeKey } from '$lib/args';

  type StepData = { step: PlaybookNode; connectorLabel: string | null; connectorIcon?: string | null; childName?: string | null; dir: 'TB' | 'LR' };
  let { data, selected }: NodeProps<Node<StepData>> = $props();
  const step = $derived(data.step);
  const Icon = $derived(FAMILY_ICON[step.family]);
  const across = $derived(data.dir === 'LR');
  // A code snippet step's connector is also called "Code Snippet"; say it once.
  const showConnector = $derived(
    !!step.connector && !!data.connectorLabel && data.connectorLabel.trim().toLowerCase() !== step.label.trim().toLowerCase()
  );
</script>

<div class="step" class:selected style="--fam: var(--fam-{step.family})">
  <Handle type="target" position={across ? Position.Left : Position.Top} isConnectable={false} />
  <span class="icon" aria-hidden="true">{#if data.connectorIcon}<img src={data.connectorIcon} alt="" width="20" height="20" />{:else}<Icon size={16} />{/if}</span>
  <span class="min-w-0 flex-1">
    <span class="kind">{step.label}{#if showConnector}{' · '}{data.connectorLabel}{/if}</span>
    <span class="name" title={step.name}>{step.name}</span>
    {#if data.childName}<span class="op" title="Runs the child playbook {data.childName}">↳ {data.childName}</span>{/if}
    {#if step.operation}<span class="op" title={step.operation}>{step.operationTitle ?? humanizeKey(step.operation)}</span>{/if}
  </span>
  <Handle type="source" position={across ? Position.Right : Position.Bottom} isConnectable={false} />
</div>

<style>
  .step {
    width: 236px;
    min-height: 66px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--fam);
    border-radius: 10px;
    box-shadow: var(--shadow);
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
    text-align: left;
  }
  .step:hover {
    border-color: color-mix(in srgb, var(--fam) 55%, var(--border));
    border-left-color: var(--fam);
  }
  .step.selected {
    border-color: var(--fam);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--fam) 22%, transparent), var(--shadow);
  }
  .icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    border-radius: 8px;
    color: var(--fam);
    background: color-mix(in srgb, var(--fam) 13%, transparent);
  }
  .kind {
    display: block;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--faint);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .name {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--fg);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .op {
    display: block;
    font-size: 11.5px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .step :global(.svelte-flow__handle) {
    opacity: 0;
    width: 6px;
    height: 6px;
    min-width: 0;
    min-height: 0;
    border: 0;
  }
</style>

<script lang="ts">
  import ArgValue from './ArgValue.svelte';
  import Jinja from './Jinja.svelte';
  import { humanizeKey } from '$lib/args';

  // One step-argument value, rendered by type. Recursive for objects/arrays.
  let { value, depth = 0 }: { value: unknown; depth?: number } = $props();

  const isPrim = (v: unknown) => v === null || ['string', 'number', 'boolean'].includes(typeof v);
  const entries = $derived(
    value && typeof value === 'object' && !Array.isArray(value) ? Object.entries(value as Record<string, unknown>) : []
  );
</script>

{#if value === null || value === undefined || value === ''}
  <span class="text-faint italic">empty</span>
{:else if typeof value === 'boolean'}
  <span class="rounded-md px-1.5 py-0.5 text-xs font-medium {value ? 'bg-ok-soft text-ok' : 'bg-surface-2 text-muted'}">{value ? 'Yes' : 'No'}</span>
{:else if typeof value === 'number'}
  <span class="font-mono text-[12.5px] text-fg tabular-nums">{value}</span>
{:else if typeof value === 'string'}
  {#if value.includes('\n') && value.length > 60}
    <Jinja {value} block />
  {:else if /\{[{%]/.test(value) || value.length > 48}
    <Jinja {value} />
  {:else}
    <span class="text-fg [overflow-wrap:anywhere]">{value}</span>
  {/if}
{:else if Array.isArray(value)}
  {#if !value.length}
    <span class="text-faint italic">none</span>
  {:else if value.every((v) => isPrim(v) && String(v).length < 40)}
    <span class="flex flex-wrap gap-1">
      {#each value as v, i (i)}
        <span class="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11.5px] text-fg">{String(v)}</span>
      {/each}
    </span>
  {:else}
    <ol class="space-y-2">
      {#each value as v, i (i)}
        <li class="rounded-lg border border-line bg-surface-2/60 p-2.5">
          <span class="mb-1 block text-[10.5px] font-semibold tracking-wider text-faint uppercase">Item {i + 1}</span>
          <ArgValue value={v} depth={depth + 1} />
        </li>
      {/each}
    </ol>
  {/if}
{:else if entries.length}
  {#if depth > 4}
    <code class="block overflow-auto font-mono text-[11.5px] whitespace-pre text-muted">{JSON.stringify(value, null, 2)}</code>
  {:else}
    <dl class="space-y-2 {depth ? 'border-l border-line pl-3' : ''}">
      {#each entries as [k, v] (k)}
        <div>
          <dt class="text-[11.5px] font-medium text-muted" title={k}>{humanizeKey(k)}</dt>
          <dd class="mt-0.5 text-[13px]"><ArgValue value={v} depth={depth + 1} /></dd>
        </div>
      {/each}
    </dl>
  {/if}
{:else}
  <span class="text-faint italic">empty</span>
{/if}

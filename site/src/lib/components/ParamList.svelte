<script lang="ts">
  import type { ConnectorParam } from '$lib/types';
  import ParamList from './ParamList.svelte';

  let { params }: { params: ConnectorParam[] } = $props();
</script>

<ul class="divide-y divide-line">
  {#each params as p (p.name)}
    <li class="py-3 first:pt-0 last:pb-0">
      <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span class="font-medium">{p.title}</span>
        <code class="font-mono text-xs text-faint">{p.name}</code>
        <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">{p.type}</span>
        {#if p.required}<span class="rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-medium text-accent-text">required</span>{/if}
      </div>
      {#if p.description}<p class="mt-1 text-[13px] leading-relaxed whitespace-pre-line text-muted">{p.description}</p>{/if}
      {#if p.value !== undefined && p.value !== ''}
        <p class="mt-1 text-xs text-faint">Default <code class="rounded bg-surface-2 px-1 py-0.5 font-mono text-muted">{String(p.value)}</code></p>
      {/if}
      {#if p.options?.length}
        <div class="mt-1.5 flex flex-wrap items-center gap-1 text-xs">
          <span class="text-faint">Options</span>
          {#each p.options as o, i (i)}<span class="rounded border border-line px-1.5 py-0.5 text-muted">{o}</span>{/each}
        </div>
      {/if}
      {#if p.onchange}
        {#each Object.entries(p.onchange) as [option, sub] (option)}
          <div class="mt-2.5 border-l-2 border-line pl-3">
            <p class="mb-2 text-xs text-faint">When <span class="font-medium text-muted">{p.title}</span> is <span class="font-medium text-muted">{option}</span></p>
            <ParamList params={sub} />
          </div>
        {/each}
      {/if}
    </li>
  {/each}
</ul>

<script lang="ts">
  import type { ItemSummary } from '$lib/types';
  import { formatDate, plural } from '$lib/format';
  import TypePill from './TypePill.svelte';
  import HubBadge from './HubBadge.svelte';
  import Code from '@lucide/svelte/icons/code';

  let { item, labels }: { item: ItemSummary; labels: Map<string, string> } = $props();
  const shown = $derived(item.connectors.slice(0, 3));
  const more = $derived(item.connectors.length - shown.length);
</script>

<a
  href="/items/{item.slug}"
  class="group flex h-full flex-col rounded-xl border border-line bg-surface p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-pop"
>
  <div class="flex flex-wrap items-center gap-2">
    <TypePill type={item.type} />
    <HubBadge status={item.hubStatus} />
    {#if item.hasCode}
      <span class="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted" title="Contains code steps">
        <Code size={13} aria-hidden="true" />Code
      </span>
    {/if}
  </div>

  <h3 class="mt-3.5 text-[15px] font-semibold leading-snug tracking-tight text-fg group-hover:text-accent-text">
    {item.title}
  </h3>
  <p class="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">{item.summary}</p>

  {#if item.connectors.length}
    <div class="mt-4 flex flex-wrap gap-1.5">
      {#each shown as c (c)}
        <span class="rounded-full border border-line px-2 py-0.5 text-xs text-muted">{labels.get(c) ?? c}</span>
      {/each}
      {#if more > 0}<span class="rounded-full px-1.5 py-0.5 text-xs text-faint">+{more}</span>{/if}
    </div>
  {/if}

  <div class="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pt-5 text-xs text-faint">
    <span>
      {#if item.type === 'connector' || item.type === 'widget'}v{item.version}{:else}{plural(item.playbookCount, 'playbook')} · {plural(item.stepCount, 'step')}{/if}
    </span>
    <span>@{item.author.github} · {formatDate(item.published)}</span>
  </div>
</a>

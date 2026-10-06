<script lang="ts">
  import type { CuratedCollection, ItemSummary } from '$lib/types';
  import { plural } from '$lib/format';
  import Library from '@lucide/svelte/icons/library';
  import BadgeCheck from '@lucide/svelte/icons/badge-check';

  let { collection, items }: { collection: CuratedCollection; items: Map<string, ItemSummary> } = $props();
  const members = $derived(collection.items.map((i) => items.get(i.slug)).filter((i): i is ItemSummary => !!i));
  const tested = $derived(members.filter((i) => i.tested?.result === 'ran').length);
</script>

<a
  href="/collections/{collection.slug}"
  class="group flex h-full min-w-0 flex-col rounded-xl border border-line bg-surface p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-pop"
>
  <div class="flex items-center gap-2 text-xs text-faint">
    <Library size={14} class="text-accent-text" aria-hidden="true" />
    <span>{plural(members.length, 'item')}</span>
    {#if tested}
      <span class="ml-auto inline-flex items-center gap-1 text-accent-text" title="Items in this collection that ran end to end on a live FortiSOAR">
        <BadgeCheck size={13} aria-hidden="true" />{tested} tested
      </span>
    {/if}
  </div>
  <h3 class="mt-3 text-base font-semibold tracking-tight text-fg group-hover:text-accent-text">{collection.title}</h3>
  <p class="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">{collection.summary}</p>
  <ol class="mt-auto space-y-1 pt-4 text-xs text-muted">
    {#each members.slice(0, 3) as m, i (m.slug)}
      <li class="flex min-w-0 items-baseline gap-2"><span class="w-3 shrink-0 text-right tabular-nums text-faint">{i + 1}</span><span class="min-w-0 truncate">{m.displayName || m.title}</span></li>
    {/each}
    {#if members.length > 3}<li class="pl-5 text-faint">and {members.length - 3} more</li>{/if}
  </ol>
</a>

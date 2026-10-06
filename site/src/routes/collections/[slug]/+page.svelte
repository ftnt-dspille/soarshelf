<script lang="ts">
  import { SITE } from '$lib/config';
  import { connectorLabels } from '$lib/data';
  import { plural } from '$lib/format';
  import type { ItemSummary } from '$lib/types';
  import ItemCard from '$lib/components/ItemCard.svelte';
  import Markdown from '$lib/components/Markdown.svelte';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import BadgeCheck from '@lucide/svelte/icons/badge-check';

  let { data } = $props();
  const c = $derived(data.collection);
  const labels = $derived(connectorLabels(data.index));
  const bySlug = $derived(new Map(data.index.items.map((i) => [i.slug, i])));
  type Entry = { slug: string; note: string; item: ItemSummary };
  const entries = $derived(
    c.items.flatMap((e): Entry[] => {
      const item = bySlug.get(e.slug);
      return item ? [{ ...e, item }] : [];
    })
  );
  const tested = $derived(entries.filter((e) => e.item.tested?.result === 'ran').length);
</script>

<svelte:head>
  <title>{c.title} · {SITE.name}</title>
  <meta name="description" content={c.summary} />
</svelte:head>

<div class="mx-auto max-w-5xl px-4 pt-8 pb-16 sm:px-6">
  <nav aria-label="Breadcrumb" class="flex items-center gap-1 text-sm text-faint">
    <a href="/collections" class="hover:text-fg">Collections</a><ChevronRight size={14} aria-hidden="true" /><span class="truncate text-muted">{c.title}</span>
  </nav>
  <h1 class="mt-4 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{c.title}</h1>
  <p class="mt-3 max-w-2xl text-base text-muted sm:text-lg">{c.summary}</p>
  <p class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
    <span>{plural(entries.length, 'item')}</span>
    {#if tested}<span class="inline-flex items-center gap-1 text-accent-text"><BadgeCheck size={14} aria-hidden="true" />{tested} verified</span>{/if}
  </p>
  {#if c.description}<div class="mt-6 max-w-3xl"><Markdown source={c.description} /></div>{/if}

  <ol class="mt-10 space-y-6">
    {#each entries as e, i (e.slug)}
      <li class="grid gap-3 sm:grid-cols-[2.5rem_1fr]">
        <span class="hidden h-8 w-8 items-center justify-center rounded-full border border-line text-sm font-semibold tabular-nums text-muted sm:flex">{i + 1}</span>
        <div>
          {#if e.note}<p class="mb-2.5 text-sm text-muted"><span class="font-semibold text-fg sm:hidden">{i + 1}. </span>{e.note}</p>{/if}
          <ItemCard item={e.item} {labels} />
        </div>
      </li>
    {/each}
  </ol>
</div>

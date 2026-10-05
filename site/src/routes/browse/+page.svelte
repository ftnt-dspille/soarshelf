<script lang="ts">
  import { afterNavigate, replaceState } from '$app/navigation';
  import { page } from '$app/state';
  import { SITE } from '$lib/config';
  import { connectorLabels } from '$lib/data';
  import { HUB_LABEL, TYPE_LABEL } from '$lib/format';
  import {
    EMPTY_FILTERS,
    activeFilterCount,
    applyFilters,
    createSearch,
    facetCounts,
    parseFilters,
    serializeFilters,
    toggle,
    type FacetKey,
    type FilterState
  } from '$lib/filter';
  import type { HubStatus, ItemType } from '$lib/types';
  import ItemCard from '$lib/components/ItemCard.svelte';
  import FacetGroup from '$lib/components/FacetGroup.svelte';
  import Search from '@lucide/svelte/icons/search';
  import Funnel from '@lucide/svelte/icons/funnel';
  import X from '@lucide/svelte/icons/x';
  import ScanSearch from '@lucide/svelte/icons/scan-search';

  let { data } = $props();
  const index = $derived(data.index);
  const labels = $derived(connectorLabels(index));
  const search = $derived(createSearch(index.items, index.connectors, index.useCases));

  let f = $state<FilterState>({ ...EMPTY_FILTERS });
  let ready = $state(false);
  let drawer = $state(false);
  let searchEl: HTMLInputElement | undefined = $state();

  // URL → state on every real navigation (incl. the first). Never runs during prerender.
  afterNavigate(() => {
    f = parseFilters(page.url.searchParams);
    ready = true;
    if (page.url.searchParams.get('focus') === '1') searchEl?.focus();
  });

  // State → URL, shallowly, so links are shareable without re-running load.
  $effect(() => {
    const qs = serializeFilters(f);
    if (!ready) return;
    if (qs !== page.url.search) replaceState(`/browse${qs}`, {});
  });

  const results = $derived(applyFilters(index.items, f, search));
  const counts = $derived(facetCounts(index.items, f, search));
  const active = $derived(activeFilterCount(f));

  const opts = (key: FacetKey, values: { value: string; label: string }[]) =>
    values.map((v) => ({ ...v, count: counts[key].get(v.value) ?? 0 }));

  const typeOpts = $derived(opts('types', (Object.keys(TYPE_LABEL) as ItemType[]).map((t) => ({ value: t, label: TYPE_LABEL[t] }))));
  const ucOpts = $derived(opts('useCases', index.useCases.map((u) => ({ value: u.id, label: u.label }))));
  const hubOpts = $derived(opts('hub', (Object.keys(HUB_LABEL) as HubStatus[]).map((h) => ({ value: h, label: HUB_LABEL[h] }))));
  const triggerOpts = $derived(
    opts('triggers', [...new Set(index.items.flatMap((i) => i.triggers))].sort().map((t) => ({ value: t, label: t })))
  );
  const connOpts = $derived(
    opts('connectors', index.connectors.map((c) => ({ value: c.name, label: c.label }))).sort(
      (a, b) => b.count - a.count || a.label.localeCompare(b.label)
    )
  );

  function flip(key: FacetKey, value: string) {
    f = { ...f, [key]: toggle(f[key] as string[], value) };
  }

  const chips = $derived([
    ...f.types.map((v) => ({ key: 'types' as FacetKey, v, label: TYPE_LABEL[v] })),
    ...f.useCases.map((v) => ({ key: 'useCases' as FacetKey, v, label: index.useCases.find((u) => u.id === v)?.label ?? v })),
    ...f.hub.map((v) => ({ key: 'hub' as FacetKey, v, label: HUB_LABEL[v] })),
    ...f.triggers.map((v) => ({ key: 'triggers' as FacetKey, v, label: v })),
    ...f.connectors.map((v) => ({ key: 'connectors' as FacetKey, v, label: labels.get(v) ?? v }))
  ]);

  function clearAll() {
    f = { ...EMPTY_FILTERS, sort: f.sort };
  }
</script>

<svelte:head><title>Browse · {SITE.name}</title></svelte:head>

{#snippet rail()}
  <FacetGroup title="Type" options={typeOpts} selected={f.types} onToggle={(v) => flip('types', v)} />
  <FacetGroup title="Use case" options={ucOpts} selected={f.useCases} onToggle={(v) => flip('useCases', v)} limit={10} />
  <FacetGroup title="Content Hub" options={hubOpts} selected={f.hub} onToggle={(v) => flip('hub', v)} />
  <FacetGroup title="Trigger" options={triggerOpts} selected={f.triggers} onToggle={(v) => flip('triggers', v)} />
  <FacetGroup title="Connector" options={connOpts} selected={f.connectors} onToggle={(v) => flip('connectors', v)} searchable />
  <div class="py-4">
    <label class="flex cursor-pointer items-center justify-between gap-3 text-sm">
      <span>
        <span class="block font-medium">No code steps</span>
        <span class="block text-xs text-faint">Hide items that run custom Python</span>
      </span>
      <input type="checkbox" bind:checked={f.noCode} class="peer sr-only" />
      <span
        class="relative h-5 w-9 shrink-0 rounded-full bg-surface-3 transition peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-[var(--ring)] after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-4"
        aria-hidden="true"
      ></span>
    </label>
  </div>
{/snippet}

<div class="mx-auto max-w-7xl px-4 pt-10 sm:px-6">
  <h1 class="text-3xl font-semibold tracking-tight">Browse</h1>
  <p class="mt-1 text-muted">Playbooks, solution packs and connectors shared by the community.</p>

  <div class="mt-6 flex gap-2">
    <label class="flex h-12 min-w-0 flex-1 items-center gap-3 rounded-xl border border-line-strong bg-surface px-4 shadow-card transition focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15">
      <Search size={18} class="shrink-0 text-faint" aria-hidden="true" />
      <span class="sr-only">Search</span>
      <input
        data-search
        bind:this={searchEl}
        bind:value={f.q}
        type="search"
        placeholder="Search titles, connectors, tags…"
        class="h-full min-w-0 flex-1 bg-transparent outline-none placeholder:text-faint"
        autocomplete="off"
      />
      <kbd class="hidden rounded-md border border-line bg-surface-2 px-2 py-0.5 font-mono text-xs text-muted sm:block">/</kbd>
    </label>
    <button
      type="button"
      class="relative inline-flex h-12 items-center gap-2 rounded-xl border border-line bg-surface px-4 text-sm font-medium lg:hidden"
      onclick={() => (drawer = true)}
      aria-haspopup="dialog"
    >
      <Funnel size={16} aria-hidden="true" />Filters
      {#if active}<span class="grid size-5 place-items-center rounded-full bg-accent text-[11px] text-accent-fg">{active}</span>{/if}
    </button>
  </div>

  <div class="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-[250px_minmax(0,1fr)]">
    <aside class="hidden lg:block" aria-label="Filters">
      <div class="scroll-quiet sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto pr-3">{@render rail()}</div>
    </aside>

    <section aria-label="Results" class="min-w-0">
      <div class="flex flex-wrap items-center gap-3">
        <p class="text-sm text-muted" aria-live="polite">
          <span class="font-semibold text-fg tabular-nums">{results.length}</span>
          {results.length === 1 ? 'result' : 'results'}{#if f.q.trim()} for “{f.q.trim()}”{/if}
        </p>
        <label class="ml-auto flex items-center gap-2 text-sm text-muted">
          Sort
          <select bind:value={f.sort} class="h-9 rounded-lg border border-line bg-surface px-2.5 text-sm text-fg">
            <option value="relevance">Relevance</option>
            <option value="newest">Newest</option>
            <option value="name">Name</option>
          </select>
        </label>
      </div>

      {#if chips.length || f.noCode}
        <div class="mt-3 flex flex-wrap items-center gap-2">
          {#each chips as c (c.key + c.v)}
            <button
              type="button"
              onclick={() => flip(c.key, c.v)}
              class="inline-flex items-center gap-1 rounded-full border border-line bg-surface py-1 pr-2 pl-3 text-xs text-fg transition hover:border-line-strong"
              aria-label="Remove filter {c.label}"
            >
              {c.label}<X size={12} class="text-faint" aria-hidden="true" />
            </button>
          {/each}
          {#if f.noCode}
            <button
              type="button"
              onclick={() => (f.noCode = false)}
              class="inline-flex items-center gap-1 rounded-full border border-line bg-surface py-1 pr-2 pl-3 text-xs"
              aria-label="Remove filter no code steps">No code<X size={12} class="text-faint" aria-hidden="true" /></button
            >
          {/if}
          <button type="button" onclick={clearAll} class="px-1 text-xs font-medium text-accent-text hover:underline">Clear all</button>
        </div>
      {/if}

      {#if results.length}
        <div class="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {#each results as item (item.slug)}
            <ItemCard {item} {labels} />
          {/each}
        </div>
      {:else}
        <div class="mt-5 rounded-xl border border-dashed border-line px-6 py-16 text-center">
          <ScanSearch size={28} class="mx-auto text-faint" aria-hidden="true" />
          <h2 class="mt-3 font-semibold">Nothing matches yet</h2>
          <p class="mx-auto mt-1 max-w-sm text-sm text-muted">Try fewer filters or a broader search. If it doesn't exist, maybe you're the one to build it.</p>
          <div class="mt-5 flex justify-center gap-3">
            <button type="button" onclick={() => (f = { ...EMPTY_FILTERS })} class="rounded-lg border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface-2">Reset search</button>
            <a href="/guide#contributing" class="rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-fg hover:bg-accent-hover">Contribute</a>
          </div>
        </div>
      {/if}
    </section>
  </div>
</div>

{#if drawer}
  <div class="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
    <button type="button" class="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-label="Close filters" onclick={() => (drawer = false)}></button>
    <div class="absolute inset-y-0 right-0 flex w-[min(22rem,90vw)] flex-col bg-bg shadow-pop">
      <div class="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 class="font-semibold">Filters</h2>
        <button type="button" class="grid size-8 place-items-center rounded-md hover:bg-surface-2" aria-label="Close filters" onclick={() => (drawer = false)}><X size={18} /></button>
      </div>
      <div class="flex-1 overflow-y-auto px-5">{@render rail()}</div>
      <div class="flex gap-3 border-t border-line p-4">
        <button type="button" onclick={clearAll} class="flex-1 rounded-lg border border-line py-2.5 text-sm font-medium">Clear</button>
        <button type="button" onclick={() => (drawer = false)} class="flex-1 rounded-lg bg-accent py-2.5 text-sm font-medium text-accent-fg">Show {results.length}</button>
      </div>
    </div>
  </div>
{/if}

<svelte:window onkeydown={(e) => drawer && e.key === 'Escape' && (drawer = false)} />

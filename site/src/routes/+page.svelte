<script lang="ts">
  import { goto } from '$app/navigation';
  import { SITE } from '$lib/config';
  import { connectorLabels } from '$lib/data';
  import { byLastChange } from '$lib/format';
  import { useCaseIcon } from '$lib/icons';
  import ItemCard from '$lib/components/ItemCard.svelte';
  import CollectionCard from '$lib/components/CollectionCard.svelte';
  import FeaturedGraphs from '$lib/components/FeaturedGraphs.svelte';
  import Search from '@lucide/svelte/icons/search';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import ScanSearch from '@lucide/svelte/icons/scan-search';
  import Layers from '@lucide/svelte/icons/layers';
  import Download from '@lucide/svelte/icons/download';
  import ShieldCheck from '@lucide/svelte/icons/shield-check';

  let { data } = $props();
  const index = $derived(data.index);
  const labels = $derived(connectorLabels(index));
  const recent = $derived(
    [...index.items]
      .sort((a, b) => byLastChange(a, b) || b.published.localeCompare(a.published))
      .slice(0, 6)
  );
  const ucCounts = $derived(
    new Map(index.useCases.map((u) => [u.id, index.items.filter((i) => i.useCases.includes(u.id)).length]))
  );
  const bySlug = $derived(new Map(index.items.map((i) => [i.slug, i])));
  const featuredCollections = $derived(data.collections.filter((c) => c.featured).slice(0, 3));
  const total = $derived(index.items.length);
  const complete = $derived(index.items.filter((i) => i.hubStatus === 'complete').length);
  const popular = $derived(index.connectors.slice(0, 6));

  let q = $state('');
  function submit(e: SubmitEvent) {
    e.preventDefault();
    goto(q.trim() ? `/browse?q=${encodeURIComponent(q.trim())}` : '/browse');
  }

  const steps = [
    { icon: ScanSearch, title: 'Find', body: 'Search by use case, connector or trigger, and open any playbook as an interactive graph.' },
    { icon: Layers, title: 'Check dependencies', body: 'Every item lists the connectors it needs and whether they are on the Content Hub.' },
    { icon: Download, title: 'Import', body: 'Download a sanitized, inactive export and bring it in with the Import Wizard.' }
  ];
</script>

<svelte:head>
  <title>{SITE.name} · Community SOAR playbooks</title>
</svelte:head>

<section class="relative overflow-hidden border-b border-line">
  <div
    class="pointer-events-none absolute inset-0 [background-image:radial-gradient(var(--grid)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]"
    aria-hidden="true"
  ></div>
  <div
    class="pointer-events-none absolute -top-40 left-1/2 h-80 w-[48rem] max-w-[120vw] -translate-x-1/2 rounded-full bg-accent/15 blur-3xl"
    aria-hidden="true"
  ></div>

  <div class="relative mx-auto max-w-4xl px-4 pt-20 pb-16 text-center sm:px-6 sm:pt-28 sm:pb-20">
    <a
      href="/guide#checks"
      class="inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1 text-xs text-muted backdrop-blur transition hover:border-line-strong hover:text-fg"
    >
      <ShieldCheck size={13} class="text-accent-text" aria-hidden="true" />Every upload is scanned and sanitized
      <ArrowRight size={12} aria-hidden="true" />
    </a>
    <h1 class="mt-6 text-4xl font-semibold tracking-[-0.035em] text-balance sm:text-6xl">
      Playbooks the community <span class="text-accent-text">already built</span>
    </h1>
    <p class="mx-auto mt-5 max-w-2xl text-base text-pretty text-muted sm:text-lg">{SITE.tagline} Explore them visually, check what they need, import in minutes.</p>

    <form onsubmit={submit} class="mx-auto mt-9 max-w-2xl" role="search">
      <label class="group flex h-14 items-center gap-3 rounded-2xl border border-line-strong bg-surface px-4 shadow-pop transition focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15">
        <Search size={20} class="shrink-0 text-faint" aria-hidden="true" />
        <span class="sr-only">Search playbooks, packs and connectors</span>
        <input
          data-search
          bind:value={q}
          type="search"
          placeholder="Search “phishing”, “VirusTotal”, “block IP”…"
          class="h-full min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-faint sm:text-base"
          autocomplete="off"
        />
        <kbd class="hidden rounded-md border border-line bg-surface-2 px-2 py-0.5 font-mono text-xs text-muted sm:block">/</kbd>
      </label>
    </form>

    {#if popular.length}
      <div class="mt-5 flex flex-wrap items-center justify-center gap-2 text-sm">
        <span class="text-faint">Popular:</span>
        {#each popular as c (c.name)}
          <a href="/browse?conn={c.name}" class="rounded-full border border-line bg-surface/60 px-3 py-1 text-muted transition hover:border-line-strong hover:text-fg">{c.label}</a>
        {/each}
      </div>
    {/if}
  </div>

  <div class="relative border-t border-line bg-surface/50">
    <dl class="mx-auto grid max-w-5xl grid-cols-2 divide-line px-4 sm:grid-cols-4 sm:divide-x sm:px-6">
      {#each [{ k: 'Playbooks', v: index.counts.playbook }, { k: 'Solution packs', v: index.counts['solution-pack'] }, { k: 'Connectors & widgets', v: index.counts.connector + (index.counts.widget ?? 0) }, { k: 'Ready from Content Hub', v: total ? `${Math.round((complete / total) * 100)}%` : '-' }] as s (s.k)}
        <div class="px-2 py-5 text-center">
          <dt class="text-xs text-faint">{s.k}</dt>
          <dd class="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{s.v}</dd>
        </div>
      {/each}
    </dl>
  </div>
</section>

<FeaturedGraphs featured={data.featured} useCases={index.useCases} />

<section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
  <div class="flex items-end justify-between gap-4">
    <div>
      <h2 class="text-2xl font-semibold tracking-tight">Browse by use case</h2>
      <p class="mt-1 text-muted">Start from the problem you're solving.</p>
    </div>
    <a href="/browse" class="hidden items-center gap-1 text-sm font-medium text-accent-text hover:underline sm:inline-flex">All items <ArrowRight size={14} /></a>
  </div>
  <div class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
    {#each index.useCases as u (u.id)}
      {@const Icon = useCaseIcon(u.icon)}
      <a
        href="/browse?uc={u.id}"
        class="group rounded-xl border border-line bg-surface p-4 transition hover:-translate-y-0.5 hover:border-line-strong hover:shadow-pop"
      >
        <div class="flex items-center justify-between">
          <span class="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent-text"><Icon size={17} aria-hidden="true" /></span>
          <span class="text-xs text-faint tabular-nums">{ucCounts.get(u.id) ?? 0}</span>
        </div>
        <h3 class="mt-3 text-sm font-semibold group-hover:text-accent-text">{u.label}</h3>
        <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{u.description}</p>
      </a>
    {/each}
  </div>
</section>

{#if featuredCollections.length}
  <section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
    <div class="flex items-end justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Collections</h2>
        <p class="mt-1 text-muted">Hand-picked sets, in the order to try them.</p>
      </div>
      <a href="/collections" class="hidden items-center gap-1 text-sm font-medium text-accent-text hover:underline sm:inline-flex">All collections <ArrowRight size={14} /></a>
    </div>
    <div class="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each featuredCollections as c (c.slug)}<CollectionCard collection={c} items={bySlug} />{/each}
    </div>
  </section>
{/if}

<section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
  <div class="flex items-end justify-between gap-4">
    <div>
      <h2 class="text-2xl font-semibold tracking-tight">New and updated</h2>
      <p class="mt-1 text-muted">The latest from contributors, checked and sanitized.</p>
    </div>
    <a href="/changes" class="hidden items-center gap-1 text-sm font-medium text-accent-text hover:underline sm:inline-flex">All changes <ArrowRight size={14} /></a>
  </div>
  <div class="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each recent as item (item.slug)}
      <ItemCard {item} {labels} />
    {/each}
  </div>
</section>

<section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
  <h2 class="text-2xl font-semibold tracking-tight">How it works</h2>
  <ol class="mt-8 grid gap-4 md:grid-cols-3">
    {#each steps as s, i (s.title)}
      <li class="relative rounded-xl border border-line bg-surface p-6">
        <span class="font-mono text-xs text-faint">0{i + 1}</span>
        <s.icon size={20} class="mt-3 text-accent-text" aria-hidden="true" />
        <h3 class="mt-3 font-semibold">{s.title}</h3>
        <p class="mt-1.5 text-sm leading-relaxed text-muted">{s.body}</p>
      </li>
    {/each}
  </ol>
</section>

<section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
  <div class="relative overflow-hidden rounded-2xl border border-line bg-surface px-6 py-12 text-center sm:px-12">
    <div class="pointer-events-none absolute -bottom-24 left-1/2 h-48 w-[36rem] max-w-[120vw] -translate-x-1/2 rounded-full bg-accent/15 blur-3xl" aria-hidden="true"></div>
    <h2 class="relative text-2xl font-semibold tracking-tight sm:text-3xl">Built something useful? Share it.</h2>
    <p class="relative mx-auto mt-3 max-w-xl text-muted">
      Submit a playbook, solution pack or connector. Automated checks strip owners and secrets, then it goes live once it passes review.
    </p>
    <div class="relative mt-7 flex flex-wrap justify-center gap-3">
      <a href="/guide#contributing" class="rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg transition hover:bg-accent-hover">How to contribute</a>
      <a href="/guide#checks" class="rounded-lg border border-line bg-surface px-4 py-2.5 text-sm font-medium transition hover:bg-surface-2">What we check</a>
    </div>
  </div>
</section>

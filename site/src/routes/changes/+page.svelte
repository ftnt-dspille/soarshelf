<script lang="ts">
  import { SITE } from '$lib/config';
  import { formatDate } from '$lib/format';
  import type { ActivityEvent } from '$lib/types';
  import TypePill from '$lib/components/TypePill.svelte';
  import Rss from '@lucide/svelte/icons/rss';

  let { data } = $props();

  type Show = 'all' | 'added' | 'updated';
  const FILTERS: { id: Show; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'added', label: 'Added' },
    { id: 'updated', label: 'Updated' }
  ];
  let show = $state<Show>('all');

  const events = $derived(data.activity.events.filter((e) => show === 'all' || e.kind === show));
  const counts = $derived({
    all: data.activity.events.length,
    added: data.activity.events.filter((e) => e.kind === 'added').length,
    updated: data.activity.events.filter((e) => e.kind === 'updated').length
  });
  // Events arrive newest first; group consecutive ones by day.
  const days = $derived(
    events.reduce<{ date: string; events: ActivityEvent[] }[]>((acc, e) => {
      const last = acc.at(-1);
      if (last && last.date === e.date) last.events.push(e);
      else acc.push({ date: e.date, events: [e] });
      return acc;
    }, [])
  );
</script>

<svelte:head>
  <title>Changes · {SITE.name}</title>
  <link rel="alternate" type="application/atom+xml" title="{SITE.name}: new and updated" href="/feed.xml" />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 pt-12 pb-8 sm:px-6">
  <p class="font-mono text-sm text-accent-text">Changes</p>
  <div class="mt-1.5 flex flex-wrap items-end justify-between gap-4">
    <h1 class="text-4xl font-semibold tracking-tight">New and updated</h1>
    <a href="/feed.xml" class="inline-flex items-center gap-1.5 text-sm font-medium text-accent-text hover:underline">
      <Rss size={14} aria-hidden="true" />Atom feed
    </a>
  </div>
  <p class="mt-3 text-muted">Everything added to the shelf and every new version, newest first.</p>

  <div role="radiogroup" aria-label="Show" class="mt-8 inline-flex rounded-lg border border-line bg-surface p-0.5">
    {#each FILTERS as f (f.id)}
      <button
        type="button"
        role="radio"
        aria-checked={show === f.id}
        onclick={() => (show = f.id)}
        class="rounded-md px-3 py-1.5 text-sm transition {show === f.id ? 'bg-surface-2 font-medium text-fg' : 'text-muted hover:text-fg'}"
      >
        {f.label} <span class="tabular-nums text-faint">{counts[f.id]}</span>
      </button>
    {/each}
  </div>

  {#if !days.length}
    <p class="mt-10 text-muted">Nothing here yet.</p>
  {/if}

  <ol class="mt-8 space-y-10">
    {#each days as d (d.date)}
      <li>
        <h2 class="sticky top-16 z-10 -mx-1 bg-bg/90 px-1 py-1 text-xs font-semibold uppercase tracking-wider text-faint backdrop-blur">
          <time datetime={d.date}>{formatDate(d.date)}</time>
        </h2>
        <ul class="mt-2 divide-y divide-line border-y border-line">
          {#each d.events as e (e.slug + e.kind + e.version)}
            <li class="py-4">
              <div class="flex flex-wrap items-center gap-2">
                {#if e.kind === 'updated'}
                  <span class="rounded-md bg-info-soft px-2 py-0.5 text-xs font-medium text-info">Updated · v{e.version}</span>
                {:else}
                  <span class="rounded-md bg-ok-soft px-2 py-0.5 text-xs font-medium text-ok">Added</span>
                {/if}
                <TypePill type={e.type} />
              </div>
              <a href="/items/{e.slug}" class="mt-2 block font-semibold tracking-tight text-fg hover:text-accent-text">{e.title}</a>
              {#if e.notes}<p class="mt-1 text-sm leading-relaxed text-muted">{e.notes}</p>{/if}
            </li>
          {/each}
        </ul>
      </li>
    {/each}
  </ol>
</div>

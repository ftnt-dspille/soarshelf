<script lang="ts">
  import { fade } from 'svelte/transition';
  import { goto } from '$app/navigation';
  import type { Featured, NodeFamily, UseCase } from '$lib/types';
  import { BUILTIN_CONNECTORS, FAMILY_KEY, triggerPlain } from '$lib/format';
  import GraphPreview from './GraphPreview.svelte';
  import HubBadge from './HubBadge.svelte';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Zap from '@lucide/svelte/icons/zap';
  import Plug from '@lucide/svelte/icons/plug';
  import Pause from '@lucide/svelte/icons/pause';
  import Play from '@lucide/svelte/icons/play';

  let { featured, useCases = [] }: { featured: Featured; useCases?: UseCase[] } = $props();

  const ROTATE_MS = 7000;
  const items = $derived(featured.items);
  let active = $state(0);
  const current = $derived(items[active]);
  const href = $derived(current ? `/items/${current.slug}#playbooks/${current.key}` : '/browse');
  const stepHref = $derived((id: string) => `${href}/${encodeURIComponent(id)}`);

  const ucLabel = $derived(new Map(useCases.map((u) => [u.id, u.label])));
  const connectorName = (c: string) => featured.connectorLabels[c] ?? c;
  // Families in the order the key lists them, limited to what this graph uses.
  const FAMILY_ORDER: NodeFamily[] = ['trigger', 'connector', 'decision', 'record', 'code', 'human', 'reference', 'utility', 'end', 'other'];
  const families = $derived(
    current ? FAMILY_ORDER.filter((f) => current.playbook.nodes.some((n) => n.family === f)) : []
  );

  /** Connectors worth naming: built-ins dropped, the most-used steps first. */
  function keyConnectors(i: number): string[] {
    const f = items[i];
    const uses = (c: string) => f.playbook.nodes.filter((n) => n.connector === c).length;
    return f.connectors.filter((c) => !BUILTIN_CONNECTORS.has(c)).sort((a, b) => uses(b) - uses(a));
  }
  const shownConnectors = $derived(keyConnectors(active));

  /** "Phishing response · Microsoft Graph Mail · 12 steps": what a visitor picks by. */
  function subtitle(i: number): string {
    const f = items[i];
    const uc = f.useCases.map((u) => ucLabel.get(u)).find(Boolean);
    const first = keyConnectors(i)[0];
    return [uc, first && connectorName(first), `${f.playbook.nodes.length} steps`].filter(Boolean).join(' · ');
  }

  // The stage isn't one big link (steps are links of their own); a click on
  // its empty space still opens the playbook. Keyboard users have the title
  // and footer links.
  function openFromStage(e: MouseEvent) {
    if ((e.target as Element).closest('a, button')) return;
    goto(href);
  }

  // Rotation pauses while the pointer or keyboard focus is inside, while the tab
  // is hidden, and when the visitor pressed pause. Reduced motion keeps the
  // rotation (the Pause button is the control for that) but drops the fade and
  // the progress animation.
  let hovering = $state(false);
  let focused = $state(false);
  let userPaused = $state(false);
  let hidden = $state(false);
  let reduced = $state(false);
  const paused = $derived(hovering || focused || userPaused || hidden);

  $effect(() => {
    const mq = matchMedia('(prefers-reduced-motion: reduce)');
    reduced = mq.matches;
    const onMq = () => (reduced = mq.matches);
    const onVis = () => (hidden = document.hidden);
    mq.addEventListener('change', onMq);
    document.addEventListener('visibilitychange', onVis);
    return () => {
      mq.removeEventListener('change', onMq);
      document.removeEventListener('visibilitychange', onVis);
    };
  });

  // Pausing keeps the time already shown, so hovering doesn't restart the
  // slide; a new slide (rotation or a manual pick) gets a full interval.
  let elapsed = 0;
  let shown = -1;
  $effect(() => {
    const a = active;
    if (a !== shown) {
      shown = a;
      elapsed = 0;
    }
    if (paused || items.length < 2) return;
    const start = performance.now();
    const t = setTimeout(() => (active = (a + 1) % items.length), Math.max(0, ROTATE_MS - elapsed));
    return () => {
      clearTimeout(t);
      if (shown === a) elapsed += performance.now() - start;
    };
  });
</script>

{#if current}
  <section
    class="mx-auto max-w-7xl px-4 pt-20 sm:px-6"
    aria-roledescription="carousel"
    aria-label="Featured playbooks"
    onmouseenter={() => (hovering = true)}
    onmouseleave={() => (hovering = false)}
    onfocusin={(e) => (focused = (e.target as Element).matches(':focus-visible'))}
    onfocusout={() => (focused = false)}
  >
    <div class="flex items-end justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Look inside</h2>
        <p class="mt-1 text-muted">Every playbook opens as a graph. Click one to explore it step by step.</p>
      </div>
      {#if items.length > 1}
        <button
          type="button"
          onclick={() => (userPaused = !userPaused)}
          class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs font-medium text-muted transition hover:border-line-strong hover:text-fg"
          aria-label={userPaused ? 'Resume rotation' : 'Pause rotation'}
        >
          {#if userPaused}<Play size={13} aria-hidden="true" />Play{:else}<Pause size={13} aria-hidden="true" />Pause{/if}
        </button>
      {/if}
    </div>

    <div class="mt-8 grid gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
      <!-- Picker: one row per featured playbook, with a progress bar on the active one. -->
      <div class="order-2 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] lg:order-1 lg:flex-col lg:overflow-visible lg:pb-0" role="tablist" aria-label="Choose a playbook">
        {#each items as f, i (f.slug)}
          <button
            type="button"
            role="tab"
            aria-selected={i === active}
            onclick={() => (active = i)}
            class="relative w-64 shrink-0 overflow-hidden rounded-xl border p-3.5 text-left transition lg:w-auto {i === active
              ? 'border-line-strong bg-surface shadow-card'
              : 'border-transparent hover:border-line hover:bg-surface/60'}"
          >
            <span class="block truncate text-sm font-semibold {i === active ? 'text-fg' : 'text-muted'}">{f.title}</span>
            <span class="mt-0.5 block truncate text-xs text-faint">{subtitle(i)}</span>
            {#if i === active && items.length > 1 && !reduced}
              {#key active}
                <span class="absolute inset-x-0 bottom-0 h-0.5 bg-line" aria-hidden="true">
                  <span class="progress block h-full bg-accent" class:paused style="--ms: {ROTATE_MS}ms"></span>
                </span>
              {/key}
            {/if}
          </button>
        {/each}
      </div>

      <!-- Stage: each step links to itself on the item page; empty space opens the playbook. -->
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div
        onclick={openFromStage}
        class="group relative order-1 cursor-pointer overflow-hidden rounded-2xl border border-line bg-surface shadow-card transition hover:border-line-strong hover:shadow-pop lg:order-2"
        aria-live={paused ? 'polite' : 'off'}
      >
        <div
          class="pointer-events-none absolute inset-0 [background-image:radial-gradient(var(--grid)_1px,transparent_1px)] [background-size:18px_18px]"
          aria-hidden="true"
        ></div>
        <div class="relative grid">
          {#key active}
            <div class="col-start-1 row-start-1" in:fade={{ duration: reduced ? 0 : 300, delay: reduced ? 0 : 120 }} out:fade={{ duration: reduced ? 0 : 150 }}>
              <div class="border-b border-line bg-surface/80 px-5 py-3.5 backdrop-blur">
                <a {href} class="block truncate text-sm font-semibold hover:text-accent-text">{current.title}</a>
                <!-- One line, so every slide's header is the same height and the page doesn't jump. -->
                <div class="mt-2 flex items-center gap-1.5 overflow-hidden whitespace-nowrap text-xs">
                  <span class="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-surface-2 px-2 py-0.5 text-muted">
                    <Zap size={12} style="color: var(--fam-trigger)" aria-hidden="true" />{triggerPlain(current.playbook.trigger)}
                  </span>
                  {#if current.hubStatus}<span class="shrink-0"><HubBadge status={current.hubStatus} /></span>{/if}
                  {#each shownConnectors.slice(0, 2) as c (c)}
                    <span class="inline-flex min-w-0 items-center gap-1.5 rounded-md bg-surface-2 px-2 py-0.5 text-muted">
                      <Plug size={12} class="shrink-0" style="color: var(--fam-connector)" aria-hidden="true" /><span class="truncate">{connectorName(c)}</span>
                    </span>
                  {/each}
                  {#if shownConnectors.length > 2}
                    <span class="shrink-0 text-faint" title={shownConnectors.slice(2).map(connectorName).join(', ')}>+{shownConnectors.length - 2} more</span>
                  {/if}
                </div>
              </div>
              <div class="relative aspect-[16/10] w-full p-4 sm:p-6">
                <GraphPreview
                  nodes={current.playbook.nodes}
                  edges={current.playbook.edges}
                  labels={featured.connectorLabels}
                  {stepHref}
                />
                <ul class="pointer-events-none absolute bottom-2 left-3 hidden flex-wrap gap-x-3 gap-y-1 text-[11px] text-faint sm:flex" aria-label="Step colours">
                  {#each families as f (f)}
                    <li class="inline-flex items-center gap-1.5">
                      <span class="size-2 rounded-full" style="background: var(--fam-{f})" aria-hidden="true"></span>{FAMILY_KEY[f]}
                    </li>
                  {/each}
                </ul>
              </div>
              <div class="flex items-center justify-between gap-4 border-t border-line bg-surface/80 px-5 py-3.5 backdrop-blur">
                <p class="line-clamp-1 min-w-0 text-sm text-muted">{current.summary}</p>
                <a {href} class="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-accent-text">
                  Open playbook <ArrowRight size={14} class="transition group-hover:translate-x-0.5" aria-hidden="true" />
                </a>
              </div>
            </div>
          {/key}
        </div>
      </div>
    </div>
  </section>
{/if}

<style>
  .progress {
    width: 0;
    animation: grow var(--ms) linear forwards;
  }
  .progress.paused {
    animation-play-state: paused;
    opacity: 0.6;
  }
  @keyframes grow {
    to {
      width: 100%;
    }
  }
</style>

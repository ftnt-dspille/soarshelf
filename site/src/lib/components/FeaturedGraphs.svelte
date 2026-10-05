<script lang="ts">
  import { fade } from 'svelte/transition';
  import type { Featured } from '$lib/types';
  import GraphPreview from './GraphPreview.svelte';
  import TypePill from './TypePill.svelte';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Zap from '@lucide/svelte/icons/zap';
  import Pause from '@lucide/svelte/icons/pause';
  import Play from '@lucide/svelte/icons/play';

  let { featured }: { featured: Featured } = $props();

  const ROTATE_MS = 7000;
  const items = $derived(featured.items);
  let active = $state(0);
  const current = $derived(items[active]);
  const href = $derived(current ? `/items/${current.slug}#playbooks/${current.key}` : '/browse');

  // Rotation pauses while the pointer or focus is inside, while the tab is
  // hidden, when the visitor pressed pause, and always under reduced motion.
  let hovering = $state(false);
  let focused = $state(false);
  let userPaused = $state(false);
  let hidden = $state(false);
  let reduced = $state(false);
  const paused = $derived(hovering || focused || userPaused || hidden || reduced);

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

  // Restarted whenever the slide or pause state changes, so a manual pick
  // always gets a full interval before the next rotation.
  $effect(() => {
    void active;
    if (paused || items.length < 2) return;
    const t = setTimeout(() => (active = (active + 1) % items.length), ROTATE_MS);
    return () => clearTimeout(t);
  });

  function stepCount(i: number) {
    return items[i].playbook.nodes.length;
  }
</script>

{#if current}
  <section
    class="mx-auto max-w-7xl px-4 pt-20 sm:px-6"
    aria-roledescription="carousel"
    aria-label="Featured playbooks"
    onmouseenter={() => (hovering = true)}
    onmouseleave={() => (hovering = false)}
    onfocusin={() => (focused = true)}
    onfocusout={() => (focused = false)}
  >
    <div class="flex items-end justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Look inside</h2>
        <p class="mt-1 text-muted">Every playbook opens as a graph. Click one to explore it step by step.</p>
      </div>
      {#if items.length > 1 && !reduced}
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
            <span class="mt-0.5 block truncate text-xs text-faint">{f.playbook.name} · {stepCount(i)} steps</span>
            {#if i === active && items.length > 1}
              {#key `${active}-${paused}`}
                <span class="absolute inset-x-0 bottom-0 h-0.5 bg-line" aria-hidden="true">
                  <span class="progress block h-full bg-accent" class:paused style="--ms: {ROTATE_MS}ms"></span>
                </span>
              {/key}
            {/if}
          </button>
        {/each}
      </div>

      <!-- Stage: the whole card links to the playbook on its item page. -->
      <a
        {href}
        class="group relative order-1 block overflow-hidden rounded-2xl border border-line bg-surface shadow-card transition hover:border-line-strong hover:shadow-pop lg:order-2"
        aria-live={paused ? 'polite' : 'off'}
      >
        <div
          class="pointer-events-none absolute inset-0 [background-image:radial-gradient(var(--grid)_1px,transparent_1px)] [background-size:18px_18px]"
          aria-hidden="true"
        ></div>
        <div class="relative grid">
          {#key active}
            <div class="col-start-1 row-start-1" in:fade={{ duration: 300, delay: 120 }} out:fade={{ duration: 150 }}>
              <div class="flex flex-wrap items-center gap-2 border-b border-line bg-surface/80 px-5 py-3.5 backdrop-blur">
                <TypePill type={current.type} />
                <span class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">
                  <Zap size={12} style="color: var(--fam-trigger)" aria-hidden="true" />{current.playbook.trigger}
                </span>
                <span class="min-w-0 truncate text-sm font-semibold">{current.title}</span>
              </div>
              <div class="aspect-[16/10] w-full p-4 sm:p-6">
                <GraphPreview
                  nodes={current.playbook.nodes}
                  edges={current.playbook.edges}
                  labels={featured.connectorLabels}
                />
              </div>
              <div class="flex items-center justify-between gap-4 border-t border-line bg-surface/80 px-5 py-3.5 backdrop-blur">
                <p class="line-clamp-1 min-w-0 text-sm text-muted">{current.summary}</p>
                <span class="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-accent-text">
                  Open playbook <ArrowRight size={14} class="transition group-hover:translate-x-0.5" aria-hidden="true" />
                </span>
              </div>
            </div>
          {/key}
        </div>
      </a>
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
  }
  @keyframes grow {
    to {
      width: 100%;
    }
  }
</style>

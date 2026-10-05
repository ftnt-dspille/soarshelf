<script lang="ts">
  // Pipeline check results grouped by severity. Shared by the item page and
  // the submission detail page so a contributor sees exactly what visitors will.
  import type { Component } from 'svelte';
  import type { CheckResult, Severity } from '$lib/types';
  import { SEVERITY_LABEL, plural } from '$lib/format';
  import Markdown from './Markdown.svelte';
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
  import CircleCheck from '@lucide/svelte/icons/circle-check';
  import Info from '@lucide/svelte/icons/info';
  import X from '@lucide/svelte/icons/x';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';

  let { checks, intro = true }: { checks: CheckResult[]; intro?: boolean } = $props();

  const ORDER: Severity[] = ['block', 'warn', 'info', 'pass'];
  const SEV_TONE: Record<Severity, string> = {
    block: 'text-block bg-block-soft',
    warn: 'text-warn bg-warn-soft',
    info: 'text-info bg-info-soft',
    pass: 'text-ok bg-ok-soft'
  };
  const SEV_ICON: Record<Severity, Component> = { block: X, warn: TriangleAlert, info: Info, pass: CircleCheck };
  const grouped = $derived(ORDER.map((s) => ({ s, list: checks.filter((c) => c.severity === s) })).filter((g) => g.list.length));
</script>

{#snippet checkRow(c: CheckResult)}
  {@const Icon = SEV_ICON[c.severity]}
  <li class="flex gap-3 px-4 py-3.5">
    <span class="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md {SEV_TONE[c.severity]}"><Icon size={14} aria-hidden="true" /></span>
    <div class="min-w-0">
      <p class="text-sm font-medium">{c.title}</p>
      {#if c.detail}<div class="mt-0.5 text-sm text-muted [&_.prose]:text-sm! [&_.prose]:text-muted!"><Markdown source={c.detail} /></div>{/if}
      {#if c.location}<p class="mt-1 truncate font-mono text-xs text-faint" title={c.location}>{c.location}</p>{/if}
    </div>
  </li>
{/snippet}

{#if !checks.length}
  <p class="text-sm text-muted">No check results yet.</p>
{:else}
  <div class="flex flex-wrap gap-2">
    {#each grouped as g (g.s)}
      <span class="rounded-md px-2.5 py-1 text-xs font-medium {SEV_TONE[g.s]}">{g.list.length} {SEVERITY_LABEL[g.s].toLowerCase()}</span>
    {/each}
  </div>
  {#if intro}
    <p class="mt-3 text-sm text-muted">
      Results from the automated pipeline. <a href="/guide#checks" class="font-medium text-accent-text hover:underline">What each check does</a>.
    </p>
  {/if}
  <div class="mt-6 space-y-6">
    {#each grouped.filter((g) => g.s !== 'pass') as g (g.s)}
      <section>
        <h3 class="text-xs font-semibold tracking-wider text-faint uppercase">{SEVERITY_LABEL[g.s]}</h3>
        <ul class="mt-2 divide-y divide-line rounded-xl border border-line bg-surface">
          {#each g.list as c, i (c.id + (c.location ?? '') + i)}{@render checkRow(c)}{/each}
        </ul>
      </section>
    {/each}
    {#each grouped.filter((g) => g.s === 'pass') as g (g.s)}
      <details class="group rounded-xl border border-line bg-surface">
        <summary class="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
          <span class="inline-flex items-center gap-2"><CircleCheck size={15} class="text-ok" aria-hidden="true" />{plural(g.list.length, 'check')} passed</span>
          <ChevronDown size={15} class="text-faint transition group-open:rotate-180" aria-hidden="true" />
        </summary>
        <ul class="divide-y divide-line border-t border-line">
          {#each g.list as c, i (c.id + (c.location ?? '') + i)}{@render checkRow(c)}{/each}
        </ul>
      </details>
    {/each}
  </div>
{/if}

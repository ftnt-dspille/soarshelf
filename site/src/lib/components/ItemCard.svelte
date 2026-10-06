<script lang="ts">
  import type { ItemSummary } from '$lib/types';
  import { BUILTIN_CONNECTORS, formatDate, lastChange, plural, testedHint } from '$lib/format';
  import TypePill from './TypePill.svelte';
  import HubBadge from './HubBadge.svelte';
  import Code from '@lucide/svelte/icons/code';
  import BadgeCheck from '@lucide/svelte/icons/badge-check';

  let { item, labels }: { item: ItemSummary; labels: Map<string, string> } = $props();
  // Built-in connectors (utilities, code snippet) are in nearly every playbook, so the
  // card leads with the ones that tell you what it integrates with.
  const external = $derived(item.connectors.filter((c) => !BUILTIN_CONNECTORS.has(c)));
  const shown = $derived(external.slice(0, 2));
  const more = $derived(external.length - shown.length);
  const change = $derived(lastChange(item));
</script>

<a
  href="/items/{item.slug}"
  class="group flex h-full flex-col rounded-xl border border-line bg-surface p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-pop"
>
  <!-- One line: type on the left, status as icons on the right (labels on hover and for screen readers). -->
  <div class="flex items-center gap-2">
    <TypePill type={item.type} />
    {#if item.tested?.result === 'ran'}
      <span class="inline-flex shrink-0 items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-text" title={testedHint(item.tested)}>
        <BadgeCheck size={13} aria-hidden="true" />Verified
      </span>
    {/if}
    {#if change.kind === 'updated'}
      <span class="truncate rounded-md bg-info-soft px-2 py-0.5 text-xs font-medium text-info" title="v{change.version}{change.notes ? `: ${change.notes}` : ''}">Updated</span>
    {/if}
    <span class="ml-auto flex shrink-0 items-center gap-1.5">
      <HubBadge status={item.hubStatus} compact />
      {#if item.hasCode}
        <span class="inline-flex items-center rounded-md bg-surface-2 px-1.5 py-0.5 text-muted" title="Contains code steps">
          <Code size={13} aria-hidden="true" /><span class="sr-only">Contains code steps</span>
        </span>
      {/if}
    </span>
  </div>

  {#if item.displayName}
    <!-- Connectors and widgets are looked for by name, so the name leads. -->
    <h3 class="mt-3.5 truncate text-base font-semibold tracking-tight text-fg group-hover:text-accent-text">
      {item.displayName}
    </h3>
    {#if item.title !== item.displayName}<p class="mt-0.5 text-sm leading-snug text-fg">{item.title}</p>{/if}
  {:else}
    <h3 class="mt-3.5 text-[15px] font-semibold leading-snug tracking-tight text-fg group-hover:text-accent-text">
      {item.title}
    </h3>
  {/if}
  <p class="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">{item.summary}</p>

  {#if shown.length && !item.displayName}
    <div class="mt-4 flex min-w-0 items-center gap-1.5" title={external.map((c) => labels.get(c) ?? c).join(', ')}>
      {#each shown as c, i (c)}
        <!-- The first chip keeps its name; a long second one is cut short instead. -->
        <span class="truncate rounded-full border border-line px-2 py-0.5 text-xs text-muted {i === 0 && shown.length > 1 ? 'max-w-[65%] shrink-0' : 'min-w-0'}">{labels.get(c) ?? c}</span>
      {/each}
      {#if more > 0}<span class="shrink-0 rounded-full px-1.5 py-0.5 text-xs text-faint">+{more}</span>{/if}
    </div>
  {/if}

  <div class="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pt-5 text-xs text-faint">
    <span>
      {#if item.type === 'connector' || item.type === 'widget'}v{item.version}{:else}{plural(item.playbookCount, 'playbook')} · {plural(item.stepCount, 'step')}{/if}
    </span>
    <span>@{item.author.github} · {change.kind === 'updated' ? 'updated ' : ''}{formatDate(change.date)}</span>
  </div>
</a>

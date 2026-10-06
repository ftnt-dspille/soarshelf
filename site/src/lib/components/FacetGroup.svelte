<script lang="ts">
  import ChevronDown from '@lucide/svelte/icons/chevron-down';

  type Option = { value: string; label: string; count: number };
  let {
    title,
    options,
    selected,
    onToggle,
    searchable = false,
    limit = 8
  }: {
    title: string;
    options: Option[];
    selected: string[];
    onToggle: (value: string) => void;
    searchable?: boolean;
    limit?: number;
  } = $props();

  let open = $state(true);
  let filter = $state('');
  let showAll = $state(false);
  const id = $props.id();

  // Selected values always stay visible, even when their count drops to zero.
  const visible = $derived.by(() => {
    const f = filter.trim().toLowerCase();
    const matched = options.filter((o) => (o.count > 0 || selected.includes(o.value)) && (!f || o.label.toLowerCase().includes(f)));
    return showAll || f ? matched : matched.slice(0, limit);
  });
  const hidden = $derived(
    options.filter((o) => o.count > 0 || selected.includes(o.value)).length - visible.length
  );
</script>

<fieldset class="min-w-0 border-b border-line py-4 last:border-b-0">
  <legend class="contents">
    <button
      type="button"
      class="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-faint hover:text-muted"
      aria-expanded={open}
      aria-controls={id}
      onclick={() => (open = !open)}
    >
      {title}
      <ChevronDown size={14} class="transition {open ? '' : '-rotate-90'}" aria-hidden="true" />
    </button>
  </legend>
  <div id={id} class:hidden={!open} class="mt-3">
    {#if searchable}
      <input
        bind:value={filter}
        type="search"
        placeholder="Filter {title.toLowerCase()}…"
        aria-label="Filter {title.toLowerCase()}"
        class="mb-2 h-8 w-full rounded-md border border-line bg-surface px-2.5 text-sm outline-none placeholder:text-faint focus:border-accent"
      />
    {/if}
    <ul class="space-y-0.5">
      {#each visible as o (o.value)}
        {@const on = selected.includes(o.value)}
        <li>
          <label
            class="flex cursor-pointer items-start gap-2.5 rounded-md px-1.5 py-1.5 text-sm transition hover:bg-surface-2 {on ? 'text-fg' : 'text-muted'}"
          >
            <input
              type="checkbox"
              checked={on}
              onchange={() => onToggle(o.value)}
              class="mt-0.5 size-4 shrink-0 rounded border-line-strong accent-[var(--accent)]"
            />
            <span class="min-w-0 flex-1 leading-snug break-words">{o.label}</span>
            <span class="w-6 shrink-0 pt-px text-right text-xs leading-5 tabular-nums text-faint">{o.count}</span>
          </label>
        </li>
      {:else}
        <li class="px-1.5 py-1 text-sm text-faint">No matches</li>
      {/each}
    </ul>
    {#if hidden > 0 && !filter}
      <button type="button" class="mt-1 px-1.5 text-xs font-medium text-accent-text hover:underline" onclick={() => (showAll = true)}>
        Show {hidden} more
      </button>
    {:else if showAll && !filter && options.length > limit}
      <button type="button" class="mt-1 px-1.5 text-xs font-medium text-accent-text hover:underline" onclick={() => (showAll = false)}>
        Show fewer
      </button>
    {/if}
  </div>
</fieldset>

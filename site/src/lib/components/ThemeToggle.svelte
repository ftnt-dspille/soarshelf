<script lang="ts">
  import Sun from '@lucide/svelte/icons/sun';
  import Moon from '@lucide/svelte/icons/moon';
  import Check from '@lucide/svelte/icons/check';
  import { theme, type Palette, type Theme } from '$lib/theme.svelte';

  // Swatches show each palette's own colours, whatever palette is active.
  const PALETTES: { id: Palette; label: string; note: string; swatch: [string, string, string] }[] = [
    { id: 'default', label: 'Default', note: 'Teal on neutral', swatch: ['#fbfbfa', '#0f766e', '#18181b'] },
    { id: 'docs', label: 'API docs', note: 'FortiSOAR API docs', swatch: ['#111728', '#f06292', '#a5d6ff'] }
  ];
  const MODES: { id: Theme; label: string }[] = [
    { id: 'light', label: 'Light' },
    { id: 'dark', label: 'Dark' }
  ];

  let open = $state(false);
  let el = $state<HTMLElement>();
  function onDocClick(e: MouseEvent) {
    if (open && el && !el.contains(e.target as Node)) open = false;
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) open = false;
  }
</script>

<svelte:document onclick={onDocClick} onkeydown={onKey} />

<div class="relative" bind:this={el}>
  <button
    type="button"
    onclick={() => (open = !open)}
    class="grid size-9 place-items-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-fg"
    aria-label="Theme"
    aria-haspopup="true"
    aria-expanded={open}
    title="Theme"
  >
    {#if theme.current === 'dark'}<Moon size={17} />{:else}<Sun size={17} />{/if}
  </button>
  {#if open}
    <div class="absolute right-0 z-50 mt-2 w-64 rounded-xl border border-line bg-surface p-3 shadow-pop">
      <p class="px-1 text-xs font-semibold uppercase tracking-wider text-faint" id="theme-palette">Palette</p>
      <div class="mt-2 space-y-1" role="radiogroup" aria-labelledby="theme-palette">
        {#each PALETTES as p (p.id)}
          <button
            type="button"
            role="radio"
            aria-checked={theme.palette === p.id}
            onclick={() => theme.setPalette(p.id)}
            class="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-surface-2 {theme.palette === p.id ? 'bg-surface-2' : ''}"
          >
            <span class="flex shrink-0 overflow-hidden rounded-md border border-line" aria-hidden="true">
              {#each p.swatch as c, i (i)}<span class="h-6 w-3" style="background: {c}"></span>{/each}
            </span>
            <span class="min-w-0 flex-1">
              <span class="block text-sm font-medium">{p.label}</span>
              <span class="block truncate text-xs text-faint">{p.note}</span>
            </span>
            {#if theme.palette === p.id}<Check size={15} class="shrink-0 text-accent-text" aria-hidden="true" />{/if}
          </button>
        {/each}
      </div>
      <p class="mt-3 px-1 text-xs font-semibold uppercase tracking-wider text-faint" id="theme-mode">Mode</p>
      <div class="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-surface-2 p-1" role="radiogroup" aria-labelledby="theme-mode">
        {#each MODES as m (m.id)}
          <button
            type="button"
            role="radio"
            aria-checked={theme.current === m.id}
            onclick={() => theme.set(m.id)}
            class="flex items-center justify-center gap-1.5 rounded-md py-1.5 text-sm transition {theme.current === m.id ? 'bg-surface font-medium text-fg shadow-card' : 'text-muted hover:text-fg'}"
          >
            {#if m.id === 'dark'}<Moon size={14} aria-hidden="true" />{:else}<Sun size={14} aria-hidden="true" />{/if}{m.label}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

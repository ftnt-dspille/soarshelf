<script lang="ts">
  import { page } from '$app/state';
  import Menu from '@lucide/svelte/icons/menu';
  import X from '@lucide/svelte/icons/x';
  import Search from '@lucide/svelte/icons/search';
  import Logo from './Logo.svelte';
  import ThemeToggle from './ThemeToggle.svelte';

  const links = [
    { href: '/browse', label: 'Browse' },
    { href: '/guide', label: 'Guide' },
    { href: '/about', label: 'About' }
  ];
  let open = $state(false);
  const isActive = (href: string) => page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);

  $effect(() => {
    void page.url.pathname;
    open = false;
  });
</script>

<header class="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-xl">
  <div class="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
    <a href="/" class="rounded-lg" aria-label="Home"><Logo /></a>

    <nav class="hidden items-center gap-1 md:flex" aria-label="Main">
      {#each links as l (l.href)}
        <a
          href={l.href}
          class="rounded-md px-3 py-1.5 text-sm transition {isActive(l.href) ? 'bg-surface-2 text-fg' : 'text-muted hover:text-fg'}"
          aria-current={isActive(l.href) ? 'page' : undefined}>{l.label}</a
        >
      {/each}
    </nav>

    <div class="ml-auto flex items-center gap-1.5">
      <a
        href="/browse"
        class="hidden h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm text-faint shadow-card transition hover:border-line-strong hover:text-muted sm:flex"
      >
        <Search size={15} />
        <span class="pr-6">Search</span>
        <kbd class="rounded border border-line bg-surface-2 px-1.5 font-mono text-[11px] text-muted">/</kbd>
      </a>
      <ThemeToggle />
      <a
        href="/guide#contributing"
        class="hidden h-9 items-center rounded-lg bg-fg px-3.5 text-sm font-medium text-bg transition hover:opacity-85 md:flex"
        >Contribute</a
      >
      <button
        type="button"
        class="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg md:hidden"
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
        aria-controls="mobile-nav"
        onclick={() => (open = !open)}
      >
        {#if open}<X size={19} />{:else}<Menu size={19} />{/if}
      </button>
    </div>
  </div>

  {#if open}
    <nav id="mobile-nav" class="border-t border-line bg-bg px-4 py-3 md:hidden" aria-label="Mobile">
      {#each [...links, { href: '/guide#contributing', label: 'Contribute' }] as l (l.href)}
        <a href={l.href} class="block rounded-md px-3 py-2.5 text-[15px] text-fg hover:bg-surface-2">{l.label}</a>
      {/each}
    </nav>
  {/if}
</header>

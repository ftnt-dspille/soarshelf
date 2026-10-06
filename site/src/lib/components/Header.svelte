<script lang="ts">
  import Avatar from '$lib/components/Avatar.svelte';
  import { page } from '$app/state';
  import Menu from '@lucide/svelte/icons/menu';
  import X from '@lucide/svelte/icons/x';
  import Search from '@lucide/svelte/icons/search';
  import LogIn from '@lucide/svelte/icons/log-in';
  import Inbox from '@lucide/svelte/icons/inbox';
  import LogOut from '@lucide/svelte/icons/log-out';
  import { goto } from '$app/navigation';
  import { loginUrl } from '$lib/api';
  import { session } from '$lib/session.svelte';
  import Logo from './Logo.svelte';
  import ThemeToggle from './ThemeToggle.svelte';

  const links = [
    { href: '/browse', label: 'Browse' },
    { href: '/collections', label: 'Collections' },
    { href: '/changes', label: 'Changes' },
    { href: '/guide', label: 'Guide' },
    { href: '/about', label: 'About' }
  ];
  let open = $state(false);
  const isActive = (href: string) => page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);

  $effect(() => {
    void page.url.pathname;
    open = false;
    menuOpen = false;
  });

  // Signed-in state is browser-only: prerendered pages show "Sign in".
  $effect(() => {
    session.load();
  });

  let menuOpen = $state(false);
  let menuEl = $state<HTMLElement>();
  function onDocClick(e: MouseEvent) {
    if (menuOpen && menuEl && !menuEl.contains(e.target as Node)) menuOpen = false;
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && menuOpen) menuOpen = false;
  }
  async function signOut() {
    menuOpen = false;
    await session.signOut();
    if (page.url.pathname.startsWith('/me')) goto('/');
  }
</script>

<svelte:document onclick={onDocClick} onkeydown={onKey} />

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
        href="/submit"
        class="hidden h-9 items-center rounded-lg bg-fg px-3.5 text-sm font-medium text-bg transition hover:opacity-85 md:flex"
        >Contribute</a
      >
      {#if session.me}
        <div class="relative" bind:this={menuEl}>
          <button
            type="button"
            onclick={() => (menuOpen = !menuOpen)}
            class="grid size-9 place-items-center rounded-full ring-offset-2 ring-offset-bg transition hover:ring-2 hover:ring-line-strong"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="Account menu for {session.me.login}"
          >
            <Avatar url={session.me.avatarUrl} login={session.me.login} size={30} />
          </button>
          {#if menuOpen}
            <div role="menu" class="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-line bg-surface shadow-pop">
              <div class="border-b border-line px-3.5 py-3">
                <p class="truncate text-sm font-semibold">{session.me.login}</p>
                <p class="text-xs text-faint">Signed in with GitHub</p>
              </div>
              <a role="menuitem" href="/me" class="flex items-center gap-2.5 px-3.5 py-2.5 text-sm hover:bg-surface-2"><Inbox size={15} class="text-faint" aria-hidden="true" />My submissions</a>
              <button role="menuitem" type="button" onclick={signOut} class="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-sm hover:bg-surface-2"><LogOut size={15} class="text-faint" aria-hidden="true" />Sign out</button>
            </div>
          {/if}
        </div>
      {:else}
        <a
          href={loginUrl(page.url.pathname)}
          data-sveltekit-reload
          class="hidden h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm text-muted transition hover:bg-surface-2 hover:text-fg md:flex"
          ><LogIn size={15} aria-hidden="true" />Sign in</a
        >
      {/if}
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
      {#each [...links, { href: '/submit', label: 'Contribute' }] as l (l.href)}
        <a href={l.href} class="block rounded-md px-3 py-2.5 text-[15px] text-fg hover:bg-surface-2">{l.label}</a>
      {/each}
      <div class="mt-2 border-t border-line pt-2">
        {#if session.me}
          <a href="/me" class="block rounded-md px-3 py-2.5 text-[15px] text-fg hover:bg-surface-2">My submissions</a>
          <button type="button" onclick={signOut} class="block w-full rounded-md px-3 py-2.5 text-left text-[15px] text-fg hover:bg-surface-2">Sign out ({session.me.login})</button>
        {:else}
          <a href={loginUrl(page.url.pathname)} data-sveltekit-reload class="block rounded-md px-3 py-2.5 text-[15px] text-fg hover:bg-surface-2">Sign in with GitHub</a>
        {/if}
      </div>
    </nav>
  {/if}
</header>

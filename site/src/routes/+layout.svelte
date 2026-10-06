<script lang="ts">
  import '@fontsource-variable/inter';
  import '@fontsource/jetbrains-mono/400.css';
  import '@fontsource/jetbrains-mono/500.css';
  import '../app.css';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { SITE } from '$lib/config';
  import { theme } from '$lib/theme.svelte';
  import Header from '$lib/components/Header.svelte';
  import Footer from '$lib/components/Footer.svelte';

  let { children } = $props();

  onMount(() => theme.init());

  // "/" focuses the page's search box, or jumps to /browse when the page has none.
  function onKey(e: KeyboardEvent) {
    if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target as HTMLElement | null;
    if (t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))) return;
    e.preventDefault();
    const box = document.querySelector<HTMLInputElement>('[data-search]');
    if (box) box.focus();
    else goto('/browse?focus=1');
  }
</script>

<svelte:window onkeydown={onKey} />
<svelte:head>
  <meta name="description" content={SITE.description} />
  <meta property="og:site_name" content={SITE.name} />
  <meta name="theme-color" content={theme.palette === 'docs' ? '#f06292' : '#0f766e'} />
</svelte:head>

<a
  href="#main"
  class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-pop"
  >Skip to content</a
>
<Header />
<main id="main" class="min-h-[60vh]" data-path={page.url.pathname}>
  {@render children()}
</main>
<Footer />

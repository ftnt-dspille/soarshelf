<script lang="ts">
  import { page } from '$app/state';
  import { SITE } from '$lib/config';
</script>

<svelte:head><title>{page.status === 404 ? 'Not found' : 'Error'} · {SITE.name}</title></svelte:head>

<section class="mx-auto max-w-xl px-4 py-28 text-center sm:px-6">
  <p class="font-mono text-sm text-accent-text">{page.status}</p>
  <h1 class="mt-2 text-3xl font-semibold tracking-tight">
    {page.status === 404 ? 'Nothing on this shelf' : 'Something went wrong'}
  </h1>
  <p class="mt-3 text-muted">{page.status === 404 ? 'That page or item doesn’t exist, or it was taken down.' : page.error?.message}</p>
  <div class="mt-8 flex justify-center gap-3">
    <a href="/browse" class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:bg-accent-hover">Browse everything</a>
    <a href="/" class="rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface-2">Home</a>
  </div>
</section>

<script lang="ts">
  import { SITE } from '$lib/config';
  import CollectionCard from '$lib/components/CollectionCard.svelte';

  let { data } = $props();
  const items = $derived(new Map(data.index.items.map((i) => [i.slug, i])));
</script>

<svelte:head><title>Collections · {SITE.name}</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 pt-12 pb-16 sm:px-6">
  <p class="font-mono text-sm text-accent-text">Collections</p>
  <h1 class="mt-1.5 text-4xl font-semibold tracking-tight">Hand-picked sets</h1>
  <p class="mt-3 max-w-2xl text-muted">
    Items that belong together, in the order to try them. Look for <span class="font-medium text-accent-text">Tested</span>:
    those ran end to end on a live FortiSOAR.
  </p>

  {#if data.collections.length}
    <div class="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each data.collections as c (c.slug)}<CollectionCard collection={c} {items} />{/each}
    </div>
  {:else}
    <p class="mt-10 text-muted">No collections yet.</p>
  {/if}
</div>

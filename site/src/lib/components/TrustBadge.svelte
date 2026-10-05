<script lang="ts">
  import type { Trust } from '$lib/types';
  import { TRUST_LABEL } from '$lib/format';
  import ShieldCheck from '@lucide/svelte/icons/shield-check';
  let { trust }: { trust: Trust } = $props();
  const strong = $derived(trust === 'trusted' || trust === 'maintainer');
</script>

<span
  class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium {strong
    ? 'bg-accent-soft text-accent-text'
    : 'bg-surface-2 text-muted'}"
>
  {#if strong}<ShieldCheck size={12} aria-hidden="true" />{/if}{TRUST_LABEL[trust]}
</span>

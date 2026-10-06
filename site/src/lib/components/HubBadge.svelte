<script lang="ts">
  import type { HubStatus } from '$lib/types';
  import { HUB_HINT, HUB_LABEL } from '$lib/format';
  import CircleCheck from '@lucide/svelte/icons/circle-check';
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
  import Info from '@lucide/svelte/icons/info';
  let { status, compact = false }: { status: HubStatus; compact?: boolean } = $props();
  const tone = $derived(
    status === 'complete' ? 'bg-ok-soft text-ok' : status === 'needs-custom' ? 'bg-warn-soft text-warn' : 'bg-info-soft text-info'
  );
</script>

{#if status !== 'none'}
<span class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium {tone}" title={HUB_HINT[status]}>
  {#if status === 'complete'}<CircleCheck size={13} aria-hidden="true" />{:else if status === 'needs-custom'}<TriangleAlert
      size={13}
      aria-hidden="true"
    />{:else}<Info size={13} aria-hidden="true" />{/if}
  {#if compact}<span class="sr-only">{HUB_LABEL[status]}</span>{:else}{HUB_LABEL[status]}{/if}
</span>
{/if}

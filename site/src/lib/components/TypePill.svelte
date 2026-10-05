<script lang="ts">
  import type { ItemType } from '$lib/types';
  import { TYPE_LABEL } from '$lib/format';
  import { TYPE_ICON } from '$lib/icons';
  let { type }: { type: ItemType } = $props();
  const Icon = $derived(TYPE_ICON[type]);
</script>

<span class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted">
  <Icon size={13} aria-hidden="true" />{TYPE_LABEL[type]}
</span>

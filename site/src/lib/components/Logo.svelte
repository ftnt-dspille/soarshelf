<script lang="ts">
  import { SITE } from '$lib/config';
  let { size = 28 }: { size?: number } = $props();
</script>

<span class="inline-flex items-center gap-2.5">
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" class="shrink-0">
    <rect width="32" height="32" rx="8" fill="var(--accent)" />
    <path d="M9 11h14M9 16h10M9 21h14" stroke="var(--accent-fg)" stroke-width="2.6" stroke-linecap="round" />
  </svg>
  <span class="text-[15px] font-semibold tracking-tight text-fg">{SITE.name}</span>
</span>

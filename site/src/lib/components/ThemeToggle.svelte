<script lang="ts">
  import Sun from '@lucide/svelte/icons/sun';
  import Moon from '@lucide/svelte/icons/moon';
  import { theme } from '$lib/theme.svelte';
</script>

<button
  type="button"
  onclick={() => theme.toggle()}
  class="grid size-9 place-items-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-fg"
  aria-label={theme.current === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
  title="Toggle theme"
>
  {#if theme.current === 'dark'}<Sun size={17} />{:else}<Moon size={17} />{/if}
</button>

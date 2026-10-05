<script lang="ts">
  import Copy from '@lucide/svelte/icons/copy';
  import Check from '@lucide/svelte/icons/check';
  let { value, label = 'Copy' }: { value: string; label?: string } = $props();
  let done = $state(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      done = true;
      setTimeout(() => (done = false), 1500);
    } catch {
      /* clipboard blocked: nothing to do, the value is visible on the page */
    }
  }
</script>

<button
  type="button"
  onclick={copy}
  class="inline-grid size-7 place-items-center rounded-md text-faint transition hover:bg-surface-2 hover:text-fg"
  aria-label={done ? 'Copied' : label}
  title={done ? 'Copied' : label}
>
  {#if done}<Check size={14} />{:else}<Copy size={14} />{/if}
</button>

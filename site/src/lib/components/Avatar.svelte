<script lang="ts">
  // GitHub avatar, or the login's first letter when there's no image or it fails to load.
  let { url, login, size = 30 }: { url: string; login: string; size?: number } = $props();
  let failed = $state(false);
</script>

{#if url && !failed}
  <img src={url} alt="" width={size} height={size} onerror={() => (failed = true)}
       class="rounded-full border border-line bg-surface-2" style:width="{size}px" style:height="{size}px" />
{:else}
  <span aria-hidden="true" style:width="{size}px" style:height="{size}px"
        class="grid place-items-center rounded-full border border-line bg-surface-2 text-xs font-semibold uppercase text-muted">
    {login.slice(0, 1)}
  </span>
{/if}

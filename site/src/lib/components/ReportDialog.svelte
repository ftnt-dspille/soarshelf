<script lang="ts">
  // "Report a problem" for an item. Signed-in only: one report per person per
  // item, and enough reports flag the item for a maintainer (docs/api.md).
  import { page } from '$app/state';
  import { reportItem, loginUrl, ApiError } from '$lib/api';
  import { session } from '$lib/session.svelte';
  import Flag from '@lucide/svelte/icons/flag';
  import X from '@lucide/svelte/icons/x';
  import CircleCheck from '@lucide/svelte/icons/circle-check';

  let { slug }: { slug: string } = $props();

  let dialog = $state<HTMLDialogElement>();
  let reason = $state('');
  let busy = $state(false);
  let error = $state<string | null>(null);
  let done = $state(false);

  $effect(() => {
    session.load();
  });

  const MAX = 1000;
  const valid = $derived(reason.trim().length >= 10 && reason.length <= MAX);

  function open() {
    error = null;
    dialog?.showModal();
  }

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!valid || busy) return;
    busy = true;
    error = null;
    try {
      await reportItem(slug, reason.trim());
      done = true;
    } catch (err) {
      error = err instanceof ApiError ? (err.status === 409 ? 'You’ve already reported this item. Thanks.' : err.message) : 'Something went wrong.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="flex flex-wrap items-center gap-2 text-xs text-faint">
  <Flag size={13} aria-hidden="true" />Something wrong with this item?
  {#if session.me}
    <button type="button" onclick={open} class="font-medium text-accent-text hover:underline">Report a problem</button>
  {:else}
    <a href={loginUrl(page.url.pathname)} class="font-medium text-accent-text hover:underline" data-sveltekit-reload>Sign in to report</a>
  {/if}
</div>

<dialog
  bind:this={dialog}
  class="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-fg shadow-pop backdrop:bg-black/50 backdrop:backdrop-blur-sm"
  aria-labelledby="report-title"
>
  <div class="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
    <div>
      <h2 id="report-title" class="font-semibold">Report a problem</h2>
      <p class="mt-0.5 text-sm text-muted">Sensitive data, copied content, broken imports, anything that shouldn't be here.</p>
    </div>
    <button type="button" onclick={() => dialog?.close()} class="grid size-8 shrink-0 place-items-center rounded-md text-faint hover:bg-surface-2 hover:text-fg" aria-label="Close">
      <X size={16} />
    </button>
  </div>
  {#if done}
    <div class="px-5 py-8 text-center">
      <CircleCheck size={28} class="mx-auto text-ok" aria-hidden="true" />
      <p class="mt-3 font-medium">Thanks, we got it.</p>
      <p class="mt-1 text-sm text-muted">A maintainer will take a look.</p>
      <button type="button" onclick={() => dialog?.close()} class="mt-5 rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface-2">Close</button>
    </div>
  {:else}
    <form onsubmit={submit} class="px-5 py-4">
      <label for="report-reason" class="text-sm font-medium">What's wrong?</label>
      <textarea
        id="report-reason"
        bind:value={reason}
        rows="5"
        maxlength={MAX}
        aria-describedby="report-hint {error ? 'report-error' : ''}"
        class="mt-1.5 w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-accent/15"
        placeholder="For example: step 3 contains what looks like a real API key."
      ></textarea>
      <p id="report-hint" class="mt-1 flex justify-between text-xs text-faint">
        <span>At least 10 characters. Please don't paste the sensitive value itself.</span><span class="tabular-nums">{reason.length}/{MAX}</span>
      </p>
      {#if error}<p id="report-error" class="mt-3 rounded-lg bg-block-soft px-3 py-2 text-sm text-block" role="alert">{error}</p>{/if}
      <div class="mt-4 flex justify-end gap-2">
        <button type="button" onclick={() => dialog?.close()} class="rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface-2">Cancel</button>
        <button type="submit" disabled={!valid || busy} class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? 'Sending…' : 'Send report'}
        </button>
      </div>
    </form>
  {/if}
</dialog>

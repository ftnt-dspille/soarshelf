<script lang="ts">
  import { findingKey, type PreflightResult } from '$lib/preflight';
  import ShieldCheck from '@lucide/svelte/icons/shield-check';
  import ShieldAlert from '@lucide/svelte/icons/shield-alert';
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
  import CircleX from '@lucide/svelte/icons/circle-x';
  import EyeOff from '@lucide/svelte/icons/eye-off';
  import Undo2 from '@lucide/svelte/icons/undo-2';
  import LoaderCircle from '@lucide/svelte/icons/loader-circle';

  let { result, scanning, ignored = $bindable([]) }: { result: PreflightResult | null; scanning: boolean; ignored: string[] } = $props();

  // One credential can trip two rules (a key format and a "password" field); show it once per place.
  const blocks = $derived(
    (result?.findings ?? []).filter((f) => f.severity === 'block').filter((f, i, all) => all.findIndex((g) => g.location === f.location && g.detail.slice(0, 8) === f.detail.slice(0, 8)) === i)
  );
  const warns = $derived((result?.findings ?? []).filter((f) => f.severity === 'warn'));
  const open = $derived(warns.filter((f) => !ignored.includes(findingKey(f))));
  const hidden = $derived(warns.filter((f) => ignored.includes(findingKey(f))));
  let showHidden = $state(false);

  const ignore = (k: string) => (ignored = [...ignored, k]);
  const restore = (k: string) => (ignored = ignored.filter((x) => x !== k));
  const loc = (l?: string) => (l ? l.replace(/\.\[/g, '[') : '');
</script>

{#snippet row(f: import('$lib/secretScan').Finding, tone: 'block' | 'warn')}
  <li class="flex items-start gap-3 rounded-lg border border-line bg-surface px-3 py-2.5">
    {#if tone === 'block'}<CircleX size={16} class="mt-0.5 shrink-0 text-block" aria-hidden="true" />{:else}<TriangleAlert size={16} class="mt-0.5 shrink-0 text-warn" aria-hidden="true" />{/if}
    <div class="min-w-0 flex-1">
      <p class="text-sm font-medium">{f.title}</p>
      <p class="mt-0.5 font-mono text-xs [overflow-wrap:anywhere] text-muted">{f.detail}</p>
      {#if f.location}<p class="mt-0.5 text-[11px] [overflow-wrap:anywhere] text-faint">in {loc(f.location)}</p>{/if}
    </div>
    {#if tone === 'warn'}
      <button type="button" onclick={() => ignore(findingKey(f))} class="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted hover:bg-surface-2 hover:text-fg" title="I've looked at this and it's fine to publish">
        <EyeOff size={13} aria-hidden="true" />Ignore
      </button>
    {/if}
  </li>
{/snippet}

<div aria-live="polite" class="mt-3">
  {#if scanning}
    <p class="flex items-center gap-2 text-xs text-muted"><LoaderCircle size={14} class="animate-spin" aria-hidden="true" />Checking your file for credentials and private details…</p>
  {:else if result?.skipped}
    <p class="text-xs text-faint">{result.skipped}</p>
  {:else if result && !blocks.length && !open.length && !hidden.length}
    <p class="flex items-center gap-2 rounded-lg bg-ok-soft px-3 py-2 text-xs font-medium text-ok">
      <ShieldCheck size={14} aria-hidden="true" />Nothing sensitive found{result.files > 1 ? ` in ${result.files} files` : ''}. Checked here in your browser; nothing was uploaded.
    </p>
  {:else if result}
    <div class="space-y-3 rounded-xl border {blocks.length ? 'border-block/40' : 'border-warn/40'} bg-surface-2/50 p-4">
      <div class="flex items-start gap-2.5">
        <ShieldAlert size={18} class="mt-0.5 shrink-0 {blocks.length ? 'text-block' : 'text-warn'}" aria-hidden="true" />
        <div>
          <p class="text-sm font-semibold">
            {#if blocks.length}Remove {blocks.length === 1 ? 'this' : 'these'} before you submit{:else}Check {open.length === 1 ? 'this' : 'these'} before you submit{/if}
          </p>
          <p class="mt-0.5 text-xs text-muted">
            Found in your browser; nothing has been uploaded.
            {#if blocks.length}Credentials can't be published. Take {blocks.length === 1 ? 'it' : 'them'} out of the file and drop it again.{/if}
          </p>
        </div>
      </div>

      {#if blocks.length}
        <ul class="space-y-2" aria-label="Must be removed">
          {#each blocks as f (findingKey(f))}{@render row(f, 'block')}{/each}
        </ul>
      {/if}
      {#if open.length}
        <ul class="space-y-2" aria-label="To review">
          {#each open as f (findingKey(f))}{@render row(f, 'warn')}{/each}
        </ul>
      {/if}
      {#if hidden.length}
        <div>
          <button type="button" onclick={() => (showHidden = !showHidden)} class="text-xs font-medium text-muted hover:text-fg" aria-expanded={showHidden}>
            {hidden.length} ignored {showHidden ? '(hide)' : '(show)'}
          </button>
          {#if showHidden}
            <ul class="mt-2 space-y-2">
              {#each hidden as f (findingKey(f))}
                <li class="flex items-center gap-3 rounded-lg border border-line px-3 py-2 opacity-70">
                  <div class="min-w-0 flex-1"><p class="text-sm">{f.title}</p><p class="font-mono text-xs [overflow-wrap:anywhere] text-muted">{f.detail}</p></div>
                  <button type="button" onclick={() => restore(findingKey(f))} class="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted hover:bg-surface-2 hover:text-fg"><Undo2 size={13} aria-hidden="true" />Undo</button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
      {#if warns.length}
        <p class="text-xs text-faint">Ignoring a warning only hides it here. The same checks run again after you submit, and a maintainer may ask about anything left in.</p>
      {/if}
    </div>
  {/if}
</div>

<script lang="ts">
  import type { PlaybookNode } from '$lib/types';
  import { FAMILY_ICON, FAMILY_LABEL } from '$lib/icons';
  import { shapeArgs } from '$lib/args';
  import ArgValue from './ArgValue.svelte';
  import Jinja from './Jinja.svelte';
  import CopyButton from './CopyButton.svelte';
  import X from '@lucide/svelte/icons/x';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Braces from '@lucide/svelte/icons/braces';

  let {
    step,
    connectorLabel,
    onclose,
    onjump
  }: {
    step: PlaybookNode;
    connectorLabel: string | null;
    onclose: () => void;
    /** Select the step a decision branch leads to, by name. */
    onjump: (name: string) => void;
  } = $props();

  const Icon = $derived(FAMILY_ICON[step.family]);
  const a = $derived(shapeArgs(step.args));
  const restKeys = $derived(Object.keys(a.rest).length);
  // "Connector · Connector" reads badly; only add the family when it says something new.
  const kind = $derived(
    step.label.toLowerCase() === FAMILY_LABEL[step.family].toLowerCase() ? step.label : `${step.label} · ${FAMILY_LABEL[step.family]}`
  );
  let raw = $state(false);
</script>

<div class="flex items-start gap-3 border-b border-line p-4">
  <span
    class="grid size-9 shrink-0 place-items-center rounded-lg"
    style="color: var(--fam-{step.family}); background: color-mix(in srgb, var(--fam-{step.family}) 13%, transparent)"
    aria-hidden="true"><Icon size={17} /></span
  >
  <div class="min-w-0 flex-1">
    <p class="text-[11px] font-semibold tracking-wider text-faint uppercase">{kind}</p>
    <h4 class="mt-0.5 leading-snug font-semibold [overflow-wrap:anywhere]">{step.name}</h4>
  </div>
  <button
    type="button"
    onclick={onclose}
    class="grid size-7 shrink-0 place-items-center rounded-md text-faint hover:bg-surface-2 hover:text-fg"
    aria-label="Close inspector"><X size={15} /></button
  >
</div>

<div class="max-h-[540px] overflow-y-auto">
  {#if step.connector}
    <section class="border-b border-line p-4">
      <div class="rounded-lg border border-line bg-surface-2/60 p-3">
        <p class="text-sm font-semibold">{connectorLabel ?? step.connector}</p>
        <p class="mt-0.5 text-sm text-muted">
          {a.operationTitle ?? step.operation}
          {#if a.operationTitle && step.operation}<span class="ml-1 font-mono text-[11.5px] text-faint">{step.operation}</span>{/if}
        </p>
        {#if a.version}<p class="mt-2 text-xs text-faint">Built with v{a.version}</p>{/if}
      </div>
    </section>
  {/if}

  {#if a.branches.length}
    <section class="border-b border-line p-4">
      <h5 class="mb-2.5 text-[11px] font-semibold tracking-wider text-faint uppercase">Branches</h5>
      <ol class="space-y-2">
        {#each a.branches as b, i (i)}
          <li class="rounded-lg border border-line p-3">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold">{b.option}</span>
              {#if b.isDefault}<span class="rounded bg-surface-2 px-1.5 py-0.5 text-[10.5px] font-medium text-muted">otherwise</span>{/if}
            </div>
            {#if b.condition}<div class="mt-1.5"><Jinja value={b.condition} /></div>{/if}
            {#if b.target}
              <button
                type="button"
                onclick={() => onjump(b.target!)}
                class="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent-text hover:underline"
              >
                <ArrowRight size={12} aria-hidden="true" />{b.target}
              </button>
            {/if}
          </li>
        {/each}
      </ol>
    </section>
  {/if}

  {#if a.params}
    <section class="border-b border-line p-4">
      <h5 class="mb-2.5 text-[11px] font-semibold tracking-wider text-faint uppercase">Parameters</h5>
      <ArgValue value={a.params} />
    </section>
  {/if}

  {#if restKeys}
    <section class="border-b border-line p-4">
      <h5 class="mb-2.5 text-[11px] font-semibold tracking-wider text-faint uppercase">{step.connector || a.branches.length ? 'Other settings' : 'Settings'}</h5>
      <ArgValue value={a.rest} />
    </section>
  {/if}

  {#if a.truncated}
    <p class="border-b border-line p-4 text-sm text-muted">This step is large ({a.truncated}). Download the file to see all of it.</p>
  {:else if !a.params && !restKeys && !a.branches.length && !step.connector}
    <p class="border-b border-line p-4 text-sm text-faint">This step has no settings.</p>
  {/if}

  <div class="flex items-center justify-between px-4 py-3">
    <button
      type="button"
      onclick={() => (raw = !raw)}
      aria-expanded={raw}
      class="inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-fg"
    >
      <Braces size={13} aria-hidden="true" />{raw ? 'Hide' : 'Show'} raw JSON
    </button>
    <CopyButton value={JSON.stringify(step.args, null, 2)} label="Copy arguments" />
  </div>
  {#if raw}
    <pre class="mx-4 mb-4 max-h-72 overflow-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-[11.5px] leading-relaxed whitespace-pre text-fg">{JSON.stringify(step.args, null, 2)}</pre>
  {/if}
</div>

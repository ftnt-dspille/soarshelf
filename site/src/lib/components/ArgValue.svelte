<script lang="ts">
  import ArgValue from './ArgValue.svelte';
  import Jinja from './Jinja.svelte';
  import { humanizeKey } from '$lib/args';

  // One step-argument value, rendered by type. Recursive for objects/arrays.
  let { value, depth = 0 }: { value: unknown; depth?: number } = $props();

  const isPrim = (v: unknown) => v === null || ['string', 'number', 'boolean'].includes(typeof v);
  const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);

  // A query filter ({field, operator, value, ...plus form bookkeeping}) reads best as one line.
  const OPERATOR: Record<string, string> = {
    eq: '=', neq: '≠', like: 'contains', notlike: 'does not contain', in: 'in', notin: 'not in',
    gt: '>', gte: '≥', lt: '<', lte: '≤', isnull: 'is empty', between: 'between'
  };
  const isFilter = (v: unknown): v is { field: string; operator: string; value?: unknown } =>
    isObj(v) && typeof v.field === 'string' && typeof v.operator === 'string';

  /** Short enough to sit beside its label instead of under it. */
  const inline = (v: unknown) =>
    typeof v === 'boolean' || typeof v === 'number' ||
    (typeof v === 'string' && !v.includes('\n') && v.length <= 34) ||
    (Array.isArray(v) && v.length > 0 && v.length <= 6 && v.every((x) => isPrim(x) && String(x).length < 24));

  // A chain of single-key objects reads as one label ("Display conditions › Alerts") instead of
  // one indented level per key.
  const rows = $derived.by(() => {
    if (!isObj(value)) return [];
    const keys = Object.keys(value);
    return Object.entries(value).filter(([k]) => !(k.startsWith('_') && keys.includes(k.replace(/^_+/, '')))).map(([k, v]) => {
      let label = humanizeKey(k);
      let val: unknown = v;
      while (isObj(val) && Object.keys(val).length === 1) {
        const [ck, cv] = Object.entries(val)[0];
        label += ` › ${humanizeKey(ck)}`;
        val = cv;
      }
      return { key: k, label, value: val };
    });
  });
</script>

{#if value === null || value === undefined || value === ''}
  <span class="text-faint italic">empty</span>
{:else if typeof value === 'boolean'}
  <span class="rounded-md px-1.5 py-0.5 text-xs font-medium {value ? 'bg-ok-soft text-ok' : 'bg-surface-2 text-muted'}">{value ? 'Yes' : 'No'}</span>
{:else if typeof value === 'number'}
  <span class="font-mono text-[12.5px] text-fg tabular-nums">{value}</span>
{:else if typeof value === 'string'}
  {#if value.includes('\n') && value.length > 60}
    <Jinja {value} block />
  {:else if /\{[{%]/.test(value) || value.length > 48}
    <Jinja {value} />
  {:else}
    <span class="text-fg [overflow-wrap:anywhere]">{value}</span>
  {/if}
{:else if Array.isArray(value)}
  {#if !value.length}
    <span class="text-faint italic">none</span>
  {:else if value.every((v) => isPrim(v) && String(v).length < 40)}
    <span class="flex flex-wrap gap-1">
      {#each value as v, i (i)}
        <span class="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11.5px] text-fg">{String(v)}</span>
      {/each}
    </span>
  {:else if value.every(isFilter)}
    <ul class="space-y-1.5">
      {#each value as v, i (i)}
        <li class="rounded-lg border border-line bg-surface-2/60 px-2.5 py-2"><ArgValue value={v} depth={depth + 1} /></li>
      {/each}
    </ul>
  {:else}
    <ol class="space-y-2">
      {#each value as v, i (i)}
        <li class="rounded-lg border border-line bg-surface-2/60 p-2.5">
          <span class="mb-1 block text-[10.5px] font-semibold tracking-wider text-faint uppercase">Item {i + 1}</span>
          <ArgValue value={v} depth={depth + 1} />
        </li>
      {/each}
    </ol>
  {/if}
{:else if isFilter(value)}
  <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
    <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] [overflow-wrap:anywhere] text-fg">{value.field}</code>
    <span class="text-xs font-medium text-muted">{OPERATOR[value.operator] ?? value.operator}</span>
    {#if value.value !== undefined && value.value !== ''}<span class="min-w-0"><ArgValue value={value.value} depth={depth + 1} /></span>{/if}
  </div>
{:else if rows.length}
  {#if depth > 4}
    <code class="block overflow-auto font-mono text-[11.5px] whitespace-pre text-muted">{JSON.stringify(value, null, 2)}</code>
  {:else}
    <dl class="space-y-1.5 {depth ? 'border-l border-line pl-3' : ''}">
      {#each rows as r (r.key)}
        {#if inline(r.value)}
          <!-- Label and short value on one line. -->
          <div class="grid grid-cols-[minmax(0,38%)_minmax(0,1fr)] items-baseline gap-x-3">
            <dt class="text-[11.5px] font-medium text-muted [overflow-wrap:anywhere]" title={r.key}>{r.label}</dt>
            <dd class="min-w-0 text-[13px]"><ArgValue value={r.value} depth={depth + 1} /></dd>
          </div>
        {:else}
          <div>
            <dt class="text-[11.5px] font-medium text-muted" title={r.key}>{r.label}</dt>
            <dd class="mt-0.5 text-[13px]"><ArgValue value={r.value} depth={depth + 1} /></dd>
          </div>
        {/if}
      {/each}
    </dl>
  {/if}
{:else}
  <span class="text-faint italic">empty</span>
{/if}

<script lang="ts">
  import { browser } from '$app/environment';
  import { SITE } from '$lib/config';
  import { connectorLabels } from '$lib/data';
  import { TYPE_LABEL, formatBytes, formatDate } from '$lib/format';
  import type { SetupStep } from '$lib/types';
  import TypePill from '$lib/components/TypePill.svelte';
  import HubBadge from '$lib/components/HubBadge.svelte';
  import TrustBadge from '$lib/components/TrustBadge.svelte';
  import CopyButton from '$lib/components/CopyButton.svelte';
  import Markdown from '$lib/components/Markdown.svelte';
  import PlaybookViewer from '$lib/components/PlaybookViewer.svelte';
  import CheckList from '$lib/components/CheckList.svelte';
  import ReportDialog from '$lib/components/ReportDialog.svelte';
  import Download from '@lucide/svelte/icons/download';
  import Code from '@lucide/svelte/icons/code';
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
  import Info from '@lucide/svelte/icons/info';
  import Plug from '@lucide/svelte/icons/plug';
  import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';
  import Package from '@lucide/svelte/icons/package';
  import Database from '@lucide/svelte/icons/database';
  import Upload from '@lucide/svelte/icons/upload';
  import Zap from '@lucide/svelte/icons/zap';
  import type { Component } from 'svelte';

  let { data } = $props();
  const item = $derived(data.item);
  const labels = $derived(connectorLabels(data.index));
  const useCases = $derived(data.index.useCases.filter((u) => item.useCases.includes(u.id)));

  type Tab = 'overview' | 'playbooks' | 'setup' | 'dependencies' | 'checks';
  const issues = $derived(item.checks.filter((c) => c.severity === 'warn' || c.severity === 'block').length);
  const playbookTotal = $derived(item.collections.reduce((n, c) => n + c.playbooks.length, 0));
  const tabs = $derived(
    [
      { id: 'overview' as Tab, label: 'Overview', badge: null },
      playbookTotal ? { id: 'playbooks' as Tab, label: 'Playbooks', badge: String(playbookTotal) } : null,
      { id: 'setup' as Tab, label: 'Setup', badge: String(item.setup.length) },
      { id: 'dependencies' as Tab, label: 'Dependencies', badge: null },
      { id: 'checks' as Tab, label: 'Checks', badge: issues ? String(issues) : null }
    ].filter((t) => t !== null)
  );

  let tab = $state<Tab>('overview');
  // Which playbook the viewer opens on; set by links like #playbooks/0:2 (collection:playbook).
  let pbKey = $state('0:0');
  let done = $state<Record<number, boolean>>({});

  // Tab ↔ #hash so a tab can be linked directly.
  $effect(() => {
    if (!browser) return;
    const fromHash = () => {
      const [h, key] = location.hash.slice(1).split('/') as [Tab, string | undefined];
      if (tabs.some((t) => t.id === h)) tab = h;
      if (h === 'playbooks' && key && /^\d+:\d+$/.test(key)) pbKey = key;
    };
    fromHash();
    addEventListener('hashchange', fromHash);
    return () => removeEventListener('hashchange', fromHash);
  });
  function pick(t: Tab) {
    tab = t;
    history.replaceState(history.state, '', t === 'overview' ? location.pathname : `#${t}`);
  }
  function onTabKey(e: KeyboardEvent) {
    const i = tabs.findIndex((t) => t.id === tab);
    const n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
    if (n === null) return;
    e.preventDefault();
    const next = tabs[(n + tabs.length) % tabs.length];
    pick(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
  }

  const missing = $derived(item.dependencies.connectors.filter((c) => c.hub === 'missing'));
  const ext = $derived(item.download.filename.split('.').pop()?.toUpperCase() ?? '');

  const STEP_ICON: Record<SetupStep['kind'], Component> = {
    'install-connector': Plug,
    'configure-connector': SlidersHorizontal,
    'install-pack': Package,
    'custom-module': Database,
    import: Upload,
    activate: Zap,
    note: Info
  };

  const HUB_DEP: Record<string, { label: string; tone: string }> = {
    available: { label: 'On Content Hub', tone: 'text-ok bg-ok-soft' },
    'version-mismatch': { label: 'Version differs', tone: 'text-info bg-info-soft' },
    missing: { label: 'Not on Content Hub', tone: 'text-warn bg-warn-soft' }
  };
</script>

<svelte:head>
  <title>{item.title} · {SITE.name}</title>
  <meta name="description" content={item.summary} />
  <meta property="og:title" content={item.title} />
  <meta property="og:description" content={item.summary} />
</svelte:head>


<div class="border-b border-line">
  <div class="mx-auto max-w-7xl px-4 pt-8 pb-8 sm:px-6">
    <nav class="flex items-center gap-1.5 text-sm text-faint" aria-label="Breadcrumb">
      <a href="/browse" class="hover:text-fg">Browse</a><span aria-hidden="true">/</span>
      <a href="/browse?type={item.type}" class="hover:text-fg">{TYPE_LABEL[item.type]}s</a>
    </nav>

    <div class="mt-5 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <TypePill type={item.type} />
          <HubBadge status={item.hubStatus} />
          {#if item.hasCode}
            <span class="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted"><Code size={13} aria-hidden="true" />Contains code</span>
          {/if}
        </div>
        <h1 class="mt-4 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{item.title}</h1>
        <p class="mt-3 max-w-2xl text-base text-muted sm:text-lg">{item.summary}</p>
        <div class="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted">
          <span class="inline-flex items-center gap-2"><span class="font-medium text-fg">@{item.author.github}</span><TrustBadge trust={item.author.trust} /></span>
          <span>v{item.version}</span>
          {#if item.minVersion}<span>Platform {item.minVersion}+</span>{/if}
          <span>Published {formatDate(item.published)}</span>
          {#if item.updated !== item.published}<span>Updated {formatDate(item.updated)}</span>{/if}
        </div>
      </div>

      <div class="rounded-xl border border-line bg-surface p-5 shadow-card">
        <a
          href={item.download.path}
          download={item.download.filename}
          class="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-medium text-accent-fg transition hover:bg-accent-hover"
        >
          <Download size={17} aria-hidden="true" />Download {ext} · {formatBytes(item.download.bytes)}
        </a>
        <p class="mt-3 truncate font-mono text-xs text-faint" title={item.download.filename}>{item.download.filename}</p>
        <div class="mt-1 flex items-center gap-1">
          <span class="min-w-0 flex-1 truncate font-mono text-xs text-faint" title="SHA-256 {item.download.sha256}">sha256:{item.download.sha256}</span>
          <CopyButton value={item.download.sha256} label="Copy SHA-256" />
        </div>
        <p class="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
          Sanitized by the pipeline and shipped <strong class="font-medium text-fg">inactive</strong>. Follow the
          <button type="button" class="font-medium text-accent-text hover:underline" onclick={() => pick('setup')}>setup steps</button> before turning it on.
        </p>
      </div>
    </div>
  </div>

  <div class="mx-auto max-w-7xl px-4 sm:px-6">
    <div role="tablist" aria-label="Item sections" tabindex="-1" class="-mb-px flex gap-1 overflow-x-auto [scrollbar-width:none]" onkeydown={onTabKey}>
      {#each tabs as t (t.id)}
        <button
          type="button"
          role="tab"
          id="tab-{t.id}"
          aria-selected={tab === t.id}
          aria-controls="panel"
          tabindex={tab === t.id ? 0 : -1}
          onclick={() => pick(t.id)}
          class="inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition {tab === t.id
            ? 'border-accent text-fg'
            : 'border-transparent text-muted hover:text-fg'}"
        >
          {t.label}
          {#if t.badge}
            <span class="rounded-full px-1.5 text-[11px] tabular-nums {t.id === 'checks' ? 'bg-warn-soft text-warn' : 'bg-surface-2 text-muted'}">{t.badge}</span>
          {/if}
        </button>
      {/each}
    </div>
  </div>
</div>

<div id="panel" role="tabpanel" aria-labelledby="tab-{tab}" class="mx-auto max-w-7xl px-4 pt-8 sm:px-6">
  {#if tab === 'overview'}
    <div class="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="min-w-0 space-y-6">
        {#if missing.length}
          <div class="flex gap-3 rounded-xl border border-warn/30 bg-warn-soft p-4">
            <TriangleAlert size={18} class="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
            <div class="text-sm">
              <p class="font-semibold text-warn">Needs a connector that isn't on the Content Hub</p>
              <p class="mt-1 text-muted">
                {#each missing as m, i (m.name)}<code class="font-mono text-fg">{m.name}</code>{i < missing.length - 1 ? ', ' : ''}{/each}
                - you'll need to obtain this custom connector (or build an equivalent) before it will run.
              </p>
            </div>
          </div>
        {/if}
        <Markdown source={item.description} />
      </div>
      <aside class="space-y-6 text-sm">
        {#if item.connectors.length}
          <div>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-faint">Connectors</h2>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              {#each item.connectors as c (c)}
                <a href="/browse?conn={c}" class="rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:border-line-strong hover:text-fg">{labels.get(c) ?? c}</a>
              {/each}
            </div>
          </div>
        {/if}
        {#if item.triggers.length}
          <div>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-faint">Triggers</h2>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              {#each item.triggers as t (t)}<span class="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted"><Zap size={12} style="color: var(--fam-trigger)" aria-hidden="true" />{t}</span>{/each}
            </div>
          </div>
        {/if}
        {#if useCases.length}
          <div>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-faint">Use cases</h2>
            <ul class="mt-2.5 space-y-1.5">
              {#each useCases as u (u.id)}<li><a href="/browse?uc={u.id}" class="text-accent-text hover:underline">{u.label}</a></li>{/each}
            </ul>
          </div>
        {/if}
        {#if item.tags.length}
          <div>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-faint">Tags</h2>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              {#each item.tags as t (t)}<a href="/browse?q={encodeURIComponent(t)}" class="rounded-md bg-surface-2 px-2 py-1 font-mono text-xs text-muted hover:text-fg">#{t}</a>{/each}
            </div>
          </div>
        {/if}
        <dl class="grid grid-cols-2 gap-3 rounded-xl border border-line p-4">
          <div><dt class="text-xs text-faint">Playbooks</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.playbookCount}</dd></div>
          <div><dt class="text-xs text-faint">Steps</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.stepCount}</dd></div>
          <div><dt class="text-xs text-faint">Checks</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.checks.length}</dd></div>
          <div><dt class="text-xs text-faint">To review</dt><dd class="mt-0.5 font-semibold tabular-nums">{issues}</dd></div>
        </dl>
      </aside>
    </div>
  {:else if tab === 'playbooks'}
    {#if browser}
      <PlaybookViewer collections={item.collections} {labels} initialKey={pbKey} />
    {:else}
      <div class="grid h-[540px] place-items-center rounded-xl border border-line bg-surface text-sm text-faint">Loading viewer…</div>
    {/if}
  {:else if tab === 'setup'}
    <div class="max-w-3xl">
      <p class="text-muted">
        Work through these in order. New to importing? The <a href="/guide" class="font-medium text-accent-text hover:underline">setup guide</a> walks through each screen.
      </p>
      <ol class="mt-6 space-y-3">
        {#each item.setup as s, i (i)}
          {@const Icon = STEP_ICON[s.kind]}
          <li class="flex gap-4 rounded-xl border border-line bg-surface p-4 transition {done[i] ? 'opacity-60' : ''}">
            <label class="flex shrink-0 cursor-pointer items-start pt-0.5">
              <input type="checkbox" bind:checked={done[i]} class="size-4.5 accent-[var(--accent)]" aria-label="Mark step {i + 1} done" />
            </label>
            <div class="min-w-0 flex-1">
              <p class="flex items-center gap-2 text-sm font-semibold {done[i] ? 'line-through' : ''}">
                <span class="font-mono text-xs font-normal text-faint">{String(i + 1).padStart(2, '0')}</span>
                <Icon size={15} class="text-accent-text" aria-hidden="true" />{s.title}
              </p>
              <div class="mt-1 [&_.prose]:text-sm [&_.prose]:text-muted"><Markdown source={s.detail} /></div>
            </div>
          </li>
        {/each}
      </ol>
    </div>
  {:else if tab === 'dependencies'}
    <div class="space-y-10">
      <section>
        <h2 class="font-semibold">Connectors</h2>
        {#if item.dependencies.connectors.length}
          <div class="mt-4 overflow-x-auto rounded-xl border border-line">
            <table class="w-full min-w-[640px] text-sm">
              <thead class="bg-surface-2 text-left text-xs uppercase tracking-wider text-faint">
                <tr>
                  <th class="px-4 py-2.5 font-semibold">Connector</th>
                  <th class="px-4 py-2.5 font-semibold">Built with</th>
                  <th class="px-4 py-2.5 font-semibold">Content Hub</th>
                  <th class="px-4 py-2.5 font-semibold">Operations</th>
                  <th class="px-4 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line bg-surface">
                {#each item.dependencies.connectors as c (c.name)}
                  <tr class={c.hub === 'missing' ? 'bg-warn-soft/60' : ''}>
                    <td class="px-4 py-3"><span class="font-medium">{c.label}</span><span class="block font-mono text-xs text-faint">{c.name}</span></td>
                    <td class="px-4 py-3 font-mono text-xs">{c.version ?? '-'}</td>
                    <td class="px-4 py-3 font-mono text-xs">{c.hubVersion ?? '-'}</td>
                    <td class="px-4 py-3"><div class="flex flex-wrap gap-1">{#each c.operations as op (op)}<code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{op}</code>{/each}</div></td>
                    <td class="px-4 py-3">
                      <span class="inline-flex rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap {HUB_DEP[c.hub].tone}">{HUB_DEP[c.hub].label}</span>
                      {#if c.hub === 'missing'}<p class="mt-1.5 max-w-[16rem] text-xs text-warn">Not on the Content Hub - you'll need to obtain this custom connector.</p>{/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="mt-2 text-sm text-muted">No connector dependencies.</p>
        {/if}
      </section>

      <div class="grid gap-10 md:grid-cols-2">
        <section>
          <h2 class="font-semibold">Solution packs</h2>
          {#if item.dependencies.solutionPacks.length}
            <ul class="mt-4 divide-y divide-line rounded-xl border border-line bg-surface">
              {#each item.dependencies.solutionPacks as p (p.name)}
                <li class="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <span class="min-w-0 truncate"><span class="font-mono">{p.name}</span>{#if p.version}<span class="text-faint"> · {p.version}</span>{/if}</span>
                  <span class="rounded-md px-2 py-0.5 text-xs font-medium {HUB_DEP[p.hub].tone}">{HUB_DEP[p.hub].label}</span>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="mt-2 text-sm text-muted">None.</p>
          {/if}
        </section>
        <section>
          <h2 class="font-semibold">Modules</h2>
          {#if item.dependencies.modules.length}
            <ul class="mt-4 divide-y divide-line rounded-xl border border-line bg-surface">
              {#each item.dependencies.modules as m (m.name)}
                <li class="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <span class="font-mono">{m.name}</span>
                  <span class="rounded-md px-2 py-0.5 text-xs font-medium {m.stock ? 'bg-surface-2 text-muted' : 'bg-warn-soft text-warn'}">{m.stock ? 'Stock' : 'Custom'}</span>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="mt-2 text-sm text-muted">None.</p>
          {/if}
        </section>
      </div>
    </div>
  {:else if tab === 'checks'}
    <div class="max-w-3xl"><CheckList checks={item.checks} /></div>
  {/if}
  <div class="mt-12"><ReportDialog slug={item.slug} /></div>
</div>

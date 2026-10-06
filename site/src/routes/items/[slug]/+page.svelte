<script lang="ts">
  import { browser } from '$app/environment';
  import { SITE } from '$lib/config';
  import { connectorLabels } from '$lib/data';
  import { CODE_TYPES, TYPE_LABEL, formatBytes, formatDate } from '$lib/format';
  import type { ChangelogEntry, SetupStep } from '$lib/types';
  import ParamList from '$lib/components/ParamList.svelte';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
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
  import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
  import SquarePlus from '@lucide/svelte/icons/square-plus';
  import ExternalLink from '@lucide/svelte/icons/external-link';
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
  // And which step it selects: #playbooks/0:2/<step id>.
  let stepId = $state<string | null>(null);
  let done = $state<Record<number, boolean>>({});

  // Tab ↔ #hash so a tab can be linked directly.
  $effect(() => {
    if (!browser) return;
    const fromHash = () => {
      const [h, key, step] = location.hash.slice(1).split('/') as [Tab, string | undefined, string | undefined];
      if (tabs.some((t) => t.id === h)) tab = h;
      if (h === 'playbooks' && key && /^\d+:\d+$/.test(key)) {
        pbKey = key;
        const id = step ? decodeURIComponent(step) : '';
        stepId = /^[\w-]{1,80}$/.test(id) ? id : null;
        // A link to one step should land on the graph, not the page header.
        if (stepId) requestAnimationFrame(() => document.getElementById('panel')?.scrollIntoView({ block: 'start' }));
      }
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
  const ext = $derived(item.download?.filename.split('.').pop()?.toUpperCase() ?? '');
  // Connectors and widgets: the site lists their manifest; the code lives at the source.
  const isCode = $derived(CODE_TYPES.has(item.type));
  const source = $derived(item.source && /^https:\/\//.test(item.source) ? item.source : null);

  const STEP_ICON: Record<SetupStep['kind'], Component> = {
    'install-connector': Plug,
    'configure-connector': SlidersHorizontal,
    'install-widget': LayoutDashboard,
    'place-widget': SquarePlus,
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

  let opFilter = $state('');
  $effect(() => {
    void item.slug;
    opFilter = '';
  });
  const shownOps = $derived.by(() => {
    const q = opFilter.trim().toLowerCase();
    const ops = item.operations ?? [];
    if (!q) return ops;
    return ops.filter((o) =>
      [o.title, o.operation, o.description, ...(o.parameters ?? []).map((p) => p.title)].some((s) => s?.toLowerCase().includes(q))
    );
  });
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
        {#if item.displayName && item.displayName !== item.title}
          <p class="mt-4 text-lg font-semibold tracking-tight text-accent-text">{item.displayName}</p>
          <h1 class="mt-1 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{item.title}</h1>
        {:else}
          <h1 class="mt-4 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{item.title}</h1>
        {/if}
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
        {#if isCode && item.download}
          <a
            href={item.download.path}
            download={item.download.filename}
            class="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-medium text-accent-fg transition hover:bg-accent-hover"
          >
            <Download size={17} aria-hidden="true" />Download .tgz · {formatBytes(item.download.bytes)}
          </a>
          <p class="mt-3 truncate font-mono text-xs text-faint" title={item.download.filename}>{item.download.filename}</p>
          <div class="mt-1 flex items-center gap-1">
            <span class="min-w-0 flex-1 truncate font-mono text-xs text-faint" title="SHA-256 {item.download.sha256}">sha256:{item.download.sha256}</span>
            <CopyButton value={item.download.sha256} label="Copy SHA-256" />
          </div>
          {#if source}
            <a href={source} target="_blank" rel="noopener noreferrer nofollow" class="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent-text hover:underline">
              <ExternalLink size={13} aria-hidden="true" />Source repository
            </a>
          {/if}
          <p class="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
            Community code that runs on your platform. A maintainer reviewed this exact source; the download is rebuilt from it.
            Follow the
            <button type="button" class="font-medium text-accent-text hover:underline" onclick={() => pick('setup')}>setup steps</button> to install it.
          </p>
        {:else if isCode}
          {#if source}
            <a
              href={source}
              target="_blank"
              rel="noopener noreferrer nofollow"
              class="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-medium text-accent-fg transition hover:bg-accent-hover"
            >
              <ExternalLink size={17} aria-hidden="true" />View source
            </a>
            <p class="mt-3 truncate font-mono text-xs text-faint" title={source}>{source.replace(/^https:\/\//, '')}</p>
          {/if}
          <p class="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
            {TYPE_LABEL[item.type]} code runs on your platform and is <strong class="font-medium text-fg">not hosted here</strong>. Review it at the
            source, then follow the
            <button type="button" class="font-medium text-accent-text hover:underline" onclick={() => pick('setup')}>setup steps</button>.
          </p>
        {:else if item.download}
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
        {/if}
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

<div id="panel" role="tabpanel" aria-labelledby="tab-{tab}" class="mx-auto max-w-7xl scroll-mt-16 px-4 pt-8 sm:px-6">
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
        {#if item.screenshots?.length}
          <div class="grid gap-3 {item.screenshots.length > 1 ? 'sm:grid-cols-2' : ''}">
            {#each item.screenshots as shot (shot.path)}
              <a href={shot.path} target="_blank" rel="noopener" class="block overflow-hidden rounded-xl border border-line bg-surface-2">
                <img src={shot.path} alt="Screenshot: {shot.name}" width={shot.width} height={shot.height} loading="lazy" class="h-auto w-full" />
              </a>
            {/each}
          </div>
        {/if}
        <Markdown source={item.description} />
        {#if item.widget}
          <div class="rounded-xl border border-line p-5">
            <h2 class="text-sm font-semibold">{item.widget.title}</h2>
            {#if item.widget.subTitle}<p class="mt-1 text-sm text-muted">{item.widget.subTitle}</p>{/if}
            <dl class="mt-4 grid gap-4 text-sm sm:grid-cols-2">
              {#if item.widget.pages.length}
                <div>
                  <dt class="text-xs text-faint">Works on</dt>
                  <dd class="mt-1.5 flex flex-wrap gap-1.5">{#each item.widget.pages as pg (pg)}<span class="rounded-md bg-surface-2 px-2 py-0.5 text-xs text-muted">{pg}</span>{/each}</dd>
                </div>
              {/if}
              {#if item.widget.compatibility.length}
                <div>
                  <dt class="text-xs text-faint">Tested on platform</dt>
                  <dd class="mt-1.5 flex flex-wrap gap-1.5">{#each item.widget.compatibility as v (v)}<span class="rounded-md bg-surface-2 px-2 py-0.5 font-mono text-xs text-muted">{v}</span>{/each}</dd>
                </div>
              {/if}
              <div><dt class="text-xs text-faint">Widget name</dt><dd class="mt-1 font-mono text-xs">{item.widget.name}</dd></div>
              <div><dt class="text-xs text-faint">Version</dt><dd class="mt-1 font-mono text-xs">{item.widget.version}</dd></div>
            </dl>
          </div>
        {/if}
        {#if item.type === 'connector' && item.configuration?.length}
          <details class="group overflow-hidden rounded-xl border border-line">
            <summary class="flex cursor-pointer list-none items-center gap-2 px-5 py-3 hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
              <ChevronRight size={14} class="shrink-0 text-faint transition group-open:rotate-90" aria-hidden="true" />
              <h2 class="text-sm font-semibold">Configuration <span class="font-normal text-faint">· {item.configuration.length} field{item.configuration.length === 1 ? '' : 's'}</span></h2>
              <span class="ml-auto hidden truncate text-xs text-faint sm:block">{item.configuration.map((f) => f.title).join(', ')}</span>
            </summary>
            <div class="border-t border-line px-5 py-4 text-sm"><ParamList params={item.configuration} /></div>
          </details>
        {/if}
        {#if item.type === 'connector' && item.operations?.length}
          <div class="overflow-hidden rounded-xl border border-line">
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
              <h2 class="text-sm font-semibold">Operations <span class="font-normal text-faint">· {item.operations.length}</span></h2>
              {#if item.operations.length > 6}
                <input
                  type="search"
                  bind:value={opFilter}
                  placeholder="Filter operations"
                  aria-label="Filter operations"
                  class="h-8 w-full rounded-lg border border-line bg-surface px-2.5 text-sm placeholder:text-faint sm:w-56"
                />
              {/if}
            </div>
            <ul class="divide-y divide-line">
              {#each shownOps as op (op.operation)}
                <li>
                  <details class="group">
                    <summary class="flex cursor-pointer list-none items-baseline gap-3 px-5 py-2.5 text-sm hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
                      <ChevronRight size={14} class="shrink-0 translate-y-0.5 text-faint transition group-open:rotate-90" aria-hidden="true" />
                      <span class="min-w-0 flex-1 truncate">{op.title ?? op.operation}</span>
                      {#if op.parameters?.length}<span class="shrink-0 text-xs text-faint">{op.parameters.length} param{op.parameters.length === 1 ? '' : 's'}</span>{/if}
                      <code class="hidden shrink-0 font-mono text-xs text-faint sm:inline">{op.operation}</code>
                    </summary>
                    <div class="space-y-4 border-t border-line bg-surface-2/40 px-5 py-4 text-sm">
                      <code class="font-mono text-xs text-faint sm:hidden">{op.operation}</code>
                      {#if op.description}<p class="text-muted">{op.description}</p>{/if}
                      {#if op.parameters?.length}
                        <ParamList params={op.parameters} />
                      {:else}
                        <p class="text-faint">No parameters.</p>
                      {/if}
                      {#if op.output?.length}
                        <div class="flex flex-wrap items-center gap-1 text-xs">
                          <span class="text-faint">Returns</span>
                          {#each op.output as k (k)}<code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-muted">{k}</code>{/each}
                        </div>
                      {/if}
                    </div>
                  </details>
                </li>
              {:else}
                <li class="px-5 py-4 text-sm text-faint">No operation matches “{opFilter}”.</li>
              {/each}
            </ul>
          </div>
        {/if}
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
          {#if item.type === 'connector'}
            <div><dt class="text-xs text-faint">Operations</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.operations?.length ?? 0}</dd></div>
            <div><dt class="text-xs text-faint">Version</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.version}</dd></div>
          {:else if item.type === 'widget'}
            <div><dt class="text-xs text-faint">Pages</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.widget?.pages.length ?? 0}</dd></div>
            <div><dt class="text-xs text-faint">Version</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.version}</dd></div>
          {:else}
            <div><dt class="text-xs text-faint">Playbooks</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.playbookCount}</dd></div>
            <div><dt class="text-xs text-faint">Steps</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.stepCount}</dd></div>
          {/if}
          <div><dt class="text-xs text-faint">Checks</dt><dd class="mt-0.5 font-semibold tabular-nums">{item.checks.length}</dd></div>
          <div><dt class="text-xs text-faint">To review</dt><dd class="mt-0.5 font-semibold tabular-nums">{issues}</dd></div>
        </dl>
        {#if item.changelog?.length}
          <div>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-faint">Changelog</h2>
            {#snippet entry(e: ChangelogEntry)}
              <li>
                <p class="flex items-baseline justify-between gap-2"><span class="font-mono text-xs font-semibold">v{e.version}</span>{#if e.date}<span class="text-xs text-faint">{formatDate(e.date)}</span>{/if}</p>
                <p class="mt-0.5 text-muted">{e.notes}</p>
              </li>
            {/snippet}
            <ol class="mt-2.5 space-y-2.5 text-sm">
              {#each item.changelog.slice(0, 5) as e (e.version)}{@render entry(e)}{/each}
            </ol>
            {#if item.changelog.length > 5}
              <details class="mt-2.5 text-sm">
                <summary class="cursor-pointer text-xs text-accent-text">Older versions ({item.changelog.length - 5})</summary>
                <ol class="mt-2.5 space-y-2.5">
                  {#each item.changelog.slice(5) as e (e.version)}{@render entry(e)}{/each}
                </ol>
              </details>
            {/if}
          </div>
        {/if}
      </aside>
    </div>
  {:else if tab === 'playbooks'}
    {#if browser}
      <PlaybookViewer collections={item.collections} {labels} initialKey={pbKey} initialStep={stepId} />
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

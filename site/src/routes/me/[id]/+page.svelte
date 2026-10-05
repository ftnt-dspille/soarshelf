<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { SITE } from '$lib/config';
  import { formatDate } from '$lib/format';
  import { ApiError, getSubmission, loginUrl, type Submission } from '$lib/api';
  import { session } from '$lib/session.svelte';
  import StatusPill from '$lib/components/StatusPill.svelte';
  import CheckList from '$lib/components/CheckList.svelte';
  import Check from '@lucide/svelte/icons/check';
  import X from '@lucide/svelte/icons/x';
  import LoaderCircle from '@lucide/svelte/icons/loader-circle';
  import GitPullRequest from '@lucide/svelte/icons/git-pull-request';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import ArrowLeft from '@lucide/svelte/icons/arrow-left';
  import LogIn from '@lucide/svelte/icons/log-in';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';

  let { data } = $props();

  const POLL_MS = 4000;
  const POLL_FOR_MS = 5 * 60 * 1000;

  let sub = $state<Submission | null>(null);
  let error = $state<ApiError | null>(null);
  let signedOut = $state(false);
  let gaveUp = $state(false);
  let hidden = $state(false);
  let started = Date.now();

  async function load() {
    try {
      sub = await getSubmission(data.id);
      error = null;
    } catch (e) {
      error = e instanceof ApiError ? e : new ApiError(0, 'Could not load this submission.');
      if (error.status === 401) signedOut = true;
    }
  }

  onMount(() => {
    const onVis = () => {
      hidden = document.hidden;
      // Catch up straight away when the tab comes back, rather than after a full interval.
      if (!hidden && sub?.status === 'checking') load();
    };
    hidden = document.hidden;
    document.addEventListener('visibilitychange', onVis);
    session.load().then((me) => {
      if (!me) signedOut = true;
      else load();
    });
    return () => document.removeEventListener('visibilitychange', onVis);
  });

  // Poll while the checks are running; pause in background tabs, stop after 5 minutes.
  $effect(() => {
    if (!sub || sub.status !== 'checking' || hidden || gaveUp) return;
    if (Date.now() - started > POLL_FOR_MS) {
      gaveUp = true;
      return;
    }
    const t = setTimeout(load, POLL_MS);
    return () => clearTimeout(t);
  });

  function retry() {
    gaveUp = false;
    started = Date.now();
    load();
  }

  type StepState = 'done' | 'current' | 'todo' | 'failed';
  const timeline = $derived.by((): { label: string; state: StepState; note?: string }[] => {
    if (!sub) return [];
    const s = sub.status;
    const checked: StepState = s === 'checking' ? 'current' : s === 'error' ? 'failed' : 'done';
    const steps: { label: string; state: StepState; note?: string }[] = [
      { label: 'Uploaded', state: 'done', note: formatDate(sub.createdAt) },
      { label: 'Checked', state: checked, note: s === 'checking' ? 'Running now' : s === 'error' ? 'Pipeline error' : undefined }
    ];
    if (s === 'rejected') return [...steps, { label: 'Rejected', state: 'failed', note: 'Nothing was published' }];
    steps.push({
      label: s === 'publishing' ? 'Publishing' : 'In review',
      state: s === 'in-review' || s === 'publishing' ? 'current' : s === 'published' ? 'done' : 'todo',
      note: s === 'in-review' ? 'Waiting for a maintainer' : s === 'publishing' ? 'Merging automatically' : undefined
    });
    steps.push({ label: 'Published', state: s === 'published' ? 'done' : 'todo' });
    return steps;
  });

  const DECISION: Record<string, { title: string; tone: string }> = {
    publish: { title: 'Passed: publishing automatically', tone: 'border-ok/40 bg-ok-soft text-ok' },
    review: { title: 'Passed: a maintainer will review it', tone: 'border-warn/40 bg-warn-soft text-warn' },
    reject: { title: 'Rejected: blocking problems found', tone: 'border-block/40 bg-block-soft text-block' }
  };
</script>

<svelte:head>
  <title>{sub ? sub.title : 'Submission'} · {SITE.name}</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto max-w-5xl px-4 pt-10 sm:px-6">
  <a href="/me" class="inline-flex items-center gap-1.5 text-sm text-faint hover:text-fg"><ArrowLeft size={14} aria-hidden="true" />My submissions</a>

  {#if signedOut}
    <div class="mt-6 rounded-2xl border border-line bg-surface p-8 text-center">
      <p class="font-medium">Sign in to see this submission</p>
      <a href={loginUrl(page.url.pathname)} data-sveltekit-reload class="mt-4 inline-flex items-center gap-2 rounded-lg bg-fg px-4 py-2 text-sm font-medium text-bg hover:opacity-85"><LogIn size={15} aria-hidden="true" />Sign in with GitHub</a>
    </div>
  {:else if error && !sub}
    <div class="mt-6 rounded-2xl border border-line bg-surface p-8 text-center">
      <p class="font-medium">{error.status === 404 ? 'Submission not found' : 'Could not load this submission'}</p>
      <p class="mt-1 text-sm text-muted">{error.status === 404 ? 'It may belong to another account.' : error.message}</p>
      {#if error.status !== 404}<button type="button" onclick={retry} class="mt-4 rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface-2">Try again</button>{/if}
    </div>
  {:else if !sub}
    <div class="mt-6 space-y-4" aria-busy="true">
      <div class="h-10 w-2/3 animate-pulse rounded-lg bg-surface"></div>
      <div class="h-28 animate-pulse rounded-2xl border border-line bg-surface"></div>
    </div>
  {:else}
    <div class="mt-5 flex flex-wrap items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{sub.title}</h1>
          <StatusPill status={sub.status} />
        </div>
        <p class="mt-1.5 text-sm text-faint"><span class="font-mono">{sub.filename}</span> · {sub.meta.summary}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        {#if sub.prUrl}
          <a href={sub.prUrl} target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 rounded-lg border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface-2"><GitPullRequest size={15} aria-hidden="true" />Pull request</a>
        {/if}
        {#if sub.status === 'published' && sub.slug}
          <a href="/items/{sub.slug}" class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-fg hover:bg-accent-hover">View live <ArrowRight size={15} aria-hidden="true" /></a>
        {/if}
        {#if sub.status === 'rejected'}
          <a href="/submit" class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-fg hover:bg-accent-hover">Fix these and upload again</a>
        {/if}
      </div>
    </div>

    <!-- Timeline -->
    <ol class="mt-8 grid gap-3 {timeline.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-4'} rounded-2xl border border-line bg-surface p-4 sm:gap-0 sm:p-5" aria-label="Progress">
      {#each timeline as step, i (step.label)}
        <li class="relative flex items-center gap-3 sm:flex-col sm:items-start sm:gap-2" aria-current={step.state === 'current' ? 'step' : undefined}>
          {#if i < timeline.length - 1}
            <span class="absolute top-3.5 left-7 hidden h-px w-[calc(100%-2.25rem)] sm:block {step.state === 'done' ? 'bg-accent' : 'bg-line'}" aria-hidden="true"></span>
          {/if}
          <span
            class="relative z-10 grid size-7 shrink-0 place-items-center rounded-full border-2 {step.state === 'done'
              ? 'border-accent bg-accent text-accent-fg'
              : step.state === 'current'
                ? 'border-accent bg-surface text-accent-text'
                : step.state === 'failed'
                  ? 'border-block bg-block text-white'
                  : 'border-line bg-surface text-faint'}"
          >
            {#if step.state === 'done'}<Check size={14} aria-hidden="true" />{:else if step.state === 'failed'}<X size={14} aria-hidden="true" />{:else if step.state === 'current'}<LoaderCircle size={14} class="animate-spin" aria-hidden="true" />{:else}<span class="size-1.5 rounded-full bg-current" aria-hidden="true"></span>{/if}
          </span>
          <div class="min-w-0 sm:pr-4">
            <p class="text-sm font-medium {step.state === 'todo' ? 'text-faint' : ''}">{step.label}</p>
            {#if step.note}<p class="text-xs text-faint">{step.note}</p>{/if}
          </div>
        </li>
      {/each}
    </ol>

    {#if sub.status === 'checking'}
      <p class="mt-4 flex items-center gap-2 text-sm text-muted" aria-live="polite">
        {#if gaveUp}
          This is taking longer than usual. <button type="button" onclick={retry} class="inline-flex items-center gap-1 font-medium text-accent-text hover:underline"><RefreshCw size={13} aria-hidden="true" />Check again</button>
        {:else}
          <LoaderCircle size={14} class="animate-spin" aria-hidden="true" />Checks usually finish within a minute. This page updates on its own.
        {/if}
      </p>
    {:else if sub.status === 'error'}
      <p class="mt-4 rounded-lg bg-block-soft px-4 py-3 text-sm text-block" role="alert">The pipeline hit an error processing this file. Maintainers have been notified; you don't need to re-upload.</p>
    {/if}

    {#if sub.decision && DECISION[sub.decision]}
      {@const d = DECISION[sub.decision]}
      <div class="mt-8 rounded-2xl border p-5 {d.tone}">
        <p class="font-semibold">{d.title}</p>
        {#if sub.reasons.length}
          <ul class="mt-2 list-disc space-y-0.5 pl-5 text-sm">
            {#each sub.reasons as r, i (i)}<li>{r}</li>{/each}
          </ul>
        {/if}
      </div>
    {/if}

    {#if sub.checks.length}
      <section class="mt-10 max-w-3xl">
        <h2 class="mb-4 text-lg font-semibold">Check report</h2>
        <CheckList checks={sub.checks} />
      </section>
    {/if}
  {/if}
</div>

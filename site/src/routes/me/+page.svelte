<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { SITE } from '$lib/config';
  import { formatDate } from '$lib/format';
  import { ApiError, listSubmissions, loginUrl, type SubmissionSummary } from '$lib/api';
  import { session } from '$lib/session.svelte';
  import StatusPill from '$lib/components/StatusPill.svelte';
  import GitPullRequest from '@lucide/svelte/icons/git-pull-request';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Inbox from '@lucide/svelte/icons/inbox';
  import LogIn from '@lucide/svelte/icons/log-in';

  let items = $state<SubmissionSummary[] | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    const me = await session.load();
    if (!me) return;
    try {
      items = await listSubmissions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Could not load your submissions.';
    }
  });
</script>

<svelte:head>
  <title>My submissions · {SITE.name}</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 pt-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <h1 class="text-3xl font-semibold tracking-tight">My submissions</h1>
      <p class="mt-1 text-muted">Everything you've uploaded and where it is in the pipeline.</p>
    </div>
    {#if session.me}
      <a href="/submit" class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:bg-accent-hover">New submission</a>
    {/if}
  </div>

  <div class="mt-8">
    {#if !session.loaded || (session.me && !items && !error)}
      <div class="space-y-2" aria-busy="true">
        {#each [0, 1, 2] as i (i)}<div class="h-[72px] animate-pulse rounded-xl border border-line bg-surface"></div>{/each}
      </div>
    {:else if !session.me}
      <div class="rounded-2xl border border-line bg-surface p-8 text-center">
        <p class="font-medium">Sign in to see your submissions</p>
        <a href={loginUrl(page.url.pathname)} data-sveltekit-reload class="mt-4 inline-flex items-center gap-2 rounded-lg bg-fg px-4 py-2 text-sm font-medium text-bg hover:opacity-85"><LogIn size={15} aria-hidden="true" />Sign in with GitHub</a>
      </div>
    {:else if error}
      <p class="rounded-lg bg-block-soft px-4 py-3 text-sm text-block" role="alert">{error}</p>
    {:else if items && !items.length}
      <div class="rounded-2xl border border-dashed border-line p-10 text-center">
        <Inbox size={28} class="mx-auto text-faint" aria-hidden="true" />
        <p class="mt-3 font-medium">Nothing here yet</p>
        <p class="mt-1 text-sm text-muted">Share your first playbook. It takes a couple of minutes.</p>
        <a href="/submit" class="mt-5 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:bg-accent-hover">Upload a playbook</a>
      </div>
    {:else if items}
      <ul class="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {#each items as s (s.id)}
          <li class="group relative flex flex-col gap-3 px-5 py-4 transition hover:bg-surface-2/50 sm:flex-row sm:items-center">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <a href="/me/{s.id}" class="truncate font-medium after:absolute after:inset-0 group-hover:text-accent-text">{s.title}</a>
                <StatusPill status={s.status} />
              </div>
              <p class="mt-1 truncate text-xs text-faint">
                <span class="font-mono">{s.filename}</span> · submitted {formatDate(s.createdAt)}{#if s.updatedAt !== s.createdAt} · updated {formatDate(s.updatedAt)}{/if}
              </p>
            </div>
            <div class="relative z-10 flex shrink-0 items-center gap-3 text-sm">
              {#if s.prUrl}
                <a href={s.prUrl} target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-muted hover:text-fg"><GitPullRequest size={14} aria-hidden="true" />Pull request</a>
              {/if}
              {#if s.status === 'published' && s.slug}
                <a href="/items/{s.slug}" class="inline-flex items-center gap-1 font-medium text-accent-text hover:underline">View live <ArrowRight size={14} aria-hidden="true" /></a>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>

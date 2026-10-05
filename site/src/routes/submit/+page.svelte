<script lang="ts">
  import Avatar from '$lib/components/Avatar.svelte';
  import { onMount, tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { env } from '$env/dynamic/public';
  import { SITE } from '$lib/config';
  import { formatBytes } from '$lib/format';
  import { useCaseIcon } from '$lib/icons';
  import { ApiError, createSubmission, loginUrl } from '$lib/api';
  import { session } from '$lib/session.svelte';
  import { normaliseTag, validateDraft, type FieldErrors, type SubmitDraft } from '$lib/submitValidation';
  import Markdown from '$lib/components/Markdown.svelte';
  import CloudUpload from '@lucide/svelte/icons/cloud-upload';
  import FileBraces from '@lucide/svelte/icons/file-braces';
  import FileArchive from '@lucide/svelte/icons/file-archive';
  import X from '@lucide/svelte/icons/x';
  import LogIn from '@lucide/svelte/icons/log-in';
  import Lock from '@lucide/svelte/icons/lock';
  import ShieldCheck from '@lucide/svelte/icons/shield-check';
  import GitPullRequest from '@lucide/svelte/icons/git-pull-request';
  import CircleAlert from '@lucide/svelte/icons/circle-alert';
  import LoaderCircle from '@lucide/svelte/icons/loader-circle';
  import Check from '@lucide/svelte/icons/check';

  let { data } = $props();
  const useCases = $derived(data.index.useCases);

  // Cloudflare's documented always-pass test key, for local development.
  const TEST_SITE_KEY = '1x00000000000000000000AA';

  let draft = $state<SubmitDraft>({
    title: '',
    summary: '',
    description: '',
    useCases: [],
    tags: [],
    version: '1.0.0',
    minVersion: '',
    source: '',
    rightsConfirmed: false
  });
  let file = $state<File | null>(null);
  let submitted = $state(false); // show errors only after the first attempt
  let tagInput = $state('');
  let descTab = $state<'write' | 'preview'>('write');
  let dragging = $state(false);

  let token = $state<string | null>(null);
  let turnstileEl = $state<HTMLElement>();
  let turnstileFailed = $state(false);

  let uploading = $state(false);
  let progress = $state(0);
  let serverError = $state<ApiError | null>(null);

  // Errors appear after the first submit attempt, then track edits live.
  const shown = $derived<FieldErrors>(submitted ? validateDraft(draft, file) : {});

  onMount(() => {
    session.load();
  });

  // Render Turnstile once the form is on screen. The script is only loaded on this page.
  $effect(() => {
    if (!turnstileEl) return;
    const el = turnstileEl;
    let widget: string | undefined;
    const w = window as unknown as { turnstile?: Turnstile };
    const render = () => {
      if (!w.turnstile) return;
      widget = w.turnstile.render(el, {
        sitekey: env.PUBLIC_TURNSTILE_SITE_KEY || TEST_SITE_KEY,
        theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
        callback: (t: string) => (token = t),
        'expired-callback': () => (token = null),
        'error-callback': () => {
          turnstileFailed = true;
          token = null;
        }
      });
    };
    if (w.turnstile) render();
    else {
      const id = 'cf-turnstile-script';
      let s = document.getElementById(id) as HTMLScriptElement | null;
      if (!s) {
        s = document.createElement('script');
        s.id = id;
        s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        s.async = true;
        s.onerror = () => (turnstileFailed = true);
        document.head.appendChild(s);
      }
      s.addEventListener('load', render, { once: true });
    }
    return () => {
      if (widget && w.turnstile) w.turnstile.remove(widget);
    };
  });

  interface Turnstile {
    render(el: HTMLElement, opts: Record<string, unknown>): string;
    remove(id: string): void;
    reset(id?: string): void;
  }

  function pickFile(f: File | null | undefined) {
    if (!f) return;
    file = f;
    serverError = null;
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    pickFile(e.dataTransfer?.files?.[0]);
  }

  function toggleUseCase(id: string) {
    draft.useCases = draft.useCases.includes(id) ? draft.useCases.filter((u) => u !== id) : [...draft.useCases, id];
  }

  function addTag() {
    const t = normaliseTag(tagInput);
    tagInput = '';
    if (t && !draft.tags.includes(t) && draft.tags.length < 8) draft.tags = [...draft.tags, t];
  }

  function onTagKey(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    } else if (e.key === 'Backspace' && !tagInput && draft.tags.length) {
      draft.tags = draft.tags.slice(0, -1);
    }
  }

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    submitted = true;
    serverError = null;
    const first = Object.keys(validateDraft(draft, file))[0];
    if (first) {
      await tick();
      document.getElementById(`f-${first}`)?.focus();
      return;
    }
    if (!token) {
      serverError = new ApiError(400, turnstileFailed ? 'The bot check couldn’t load. Disable content blockers for this page and reload.' : 'Please complete the bot check below.');
      return;
    }
    uploading = true;
    progress = 0;
    try {
      const { id } = await createSubmission(
        file!,
        {
          title: draft.title.trim(),
          summary: draft.summary.trim(),
          description: draft.description.trim(),
          useCases: draft.useCases,
          tags: draft.tags,
          version: draft.version.trim(),
          minVersion: draft.minVersion.trim() || null,
          source: draft.source.trim() || null,
          rightsConfirmed: true
        },
        token,
        (f) => (progress = f)
      );
      await goto(`/me/${id}`);
    } catch (err) {
      serverError = err instanceof ApiError ? err : new ApiError(0, 'Upload failed. Please try again.');
      if (serverError.status === 401) session.me = null;
      // A Turnstile token is single-use.
      token = null;
      (window as unknown as { turnstile?: Turnstile }).turnstile?.reset();
    } finally {
      uploading = false;
    }
  }

  const steps = [
    { icon: LogIn, title: 'Sign in with GitHub', body: 'Only your public profile is used, to credit you and to stop spam.' },
    { icon: ShieldCheck, title: 'Automatic checks', body: 'Within a minute: secrets, private data, structure and Content Hub dependencies.' },
    { icon: GitPullRequest, title: 'Published', body: 'Clean submissions go live; anything flagged gets a quick human review first.' }
  ];

  const inputCls =
    'mt-1.5 w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg outline-none transition placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent/15';
  const border = (k: keyof FieldErrors) => (shown[k] ? 'border-block' : 'border-line');
</script>

<svelte:head>
  <title>Contribute · {SITE.name}</title>
</svelte:head>

{#snippet fieldError(k: keyof FieldErrors)}
  {#if shown[k]}<p id="e-{k}" class="mt-1.5 flex items-center gap-1.5 text-xs text-block"><CircleAlert size={13} aria-hidden="true" />{shown[k]}</p>{/if}
{/snippet}

<div class="mx-auto max-w-6xl px-4 pt-12 pb-8 sm:px-6">
  <h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">Share a playbook</h1>
  <p class="mt-2 max-w-2xl text-muted">
    Upload a playbook collection, solution pack or connector manifest you wrote. It's checked automatically and published once it passes.
  </p>
</div>

{#if !session.loaded}
  <div class="mx-auto max-w-6xl px-4 sm:px-6" aria-busy="true">
    <div class="h-72 animate-pulse rounded-2xl border border-line bg-surface"></div>
  </div>
{:else if !session.me}
  <div class="mx-auto max-w-6xl px-4 sm:px-6">
    <div class="rounded-2xl border border-line bg-surface p-6 sm:p-10">
      <ol class="grid gap-6 md:grid-cols-3">
        {#each steps as s, i (s.title)}
          <li>
            <span class="font-mono text-xs text-faint">0{i + 1}</span>
            <s.icon size={20} class="mt-2 text-accent-text" aria-hidden="true" />
            <h2 class="mt-2 font-semibold">{s.title}</h2>
            <p class="mt-1 text-sm leading-relaxed text-muted">{s.body}</p>
          </li>
        {/each}
      </ol>
      <div class="mt-8 flex flex-wrap items-center gap-4 border-t border-line pt-6">
        <a href={loginUrl(page.url.pathname)} data-sveltekit-reload class="inline-flex items-center gap-2 rounded-lg bg-fg px-4 py-2.5 text-sm font-medium text-bg transition hover:opacity-85">
          <LogIn size={16} aria-hidden="true" />Sign in with GitHub
        </a>
        <p class="text-sm text-muted">Prefer git? <a href="/guide#contributing" class="font-medium text-accent-text hover:underline">Open a pull request instead</a>.</p>
      </div>
    </div>
  </div>
{:else if !session.me.canUpload}
  <div class="mx-auto max-w-6xl px-4 sm:px-6">
    <div class="flex gap-3 rounded-2xl border border-warn/40 bg-warn-soft p-5 text-warn" role="status">
      <CircleAlert size={20} class="mt-0.5 shrink-0" aria-hidden="true" />
      <div>
        <p class="font-medium">You can't upload right now</p>
        <p class="mt-1 text-sm">{session.me.reason ?? 'Uploads are not available for this account.'}</p>
      </div>
    </div>
  </div>
{:else}
  <form class="mx-auto grid max-w-6xl gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_300px]" onsubmit={submit} novalidate>
    <div class="min-w-0 space-y-8">
      <!-- File -->
      <section>
        <h2 class="text-sm font-semibold">File</h2>
        <input
          id="f-file"
          type="file"
          accept=".json,.zip,application/json,application/zip"
          class="peer sr-only"
          aria-label="Choose a playbook export or solution pack"
          aria-describedby="file-hint {shown.file ? 'e-file' : ''}"
          onchange={(e) => pickFile((e.currentTarget as HTMLInputElement).files?.[0])}
        />
        <label
          for="f-file"
          ondragover={(e) => {
            e.preventDefault();
            dragging = true;
          }}
          ondragleave={() => (dragging = false)}
          ondrop={onDrop}
          class="mt-2 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition peer-focus-visible:border-accent peer-focus-visible:ring-4 peer-focus-visible:ring-accent/15 {dragging
            ? 'border-accent bg-accent-soft'
            : shown.file
              ? 'border-block/60 bg-surface'
              : 'border-line-strong bg-surface hover:border-accent/60'}"
        >
          {#if file}
            {@const Icon = file.name.toLowerCase().endsWith('.zip') ? FileArchive : FileBraces}
            <Icon size={28} class="text-accent-text" aria-hidden="true" />
            <span class="max-w-full truncate text-sm font-medium">{file.name}</span>
            <span class="text-xs text-faint">{formatBytes(file.size)} · click or drop to replace</span>
          {:else}
            <CloudUpload size={28} class="text-faint" aria-hidden="true" />
            <span class="text-sm font-medium">Drop your export here, or <span class="text-accent-text">browse</span></span>
            <span id="file-hint" class="text-xs text-faint">Playbook collection .json (up to 2 MB) or solution pack .zip (up to 20 MB)</span>
          {/if}
        </label>
        {@render fieldError('file')}
      </section>

      <!-- Listing -->
      <section class="space-y-5">
        <h2 class="text-sm font-semibold">Listing</h2>
        <div>
          <label for="f-title" class="text-sm font-medium">Title</label>
          <input id="f-title" bind:value={draft.title} maxlength="80" class="{inputCls} {border('title')}" placeholder="Set alert severity from IP reputation" aria-describedby="h-title {shown.title ? 'e-title' : ''}" />
          <p id="h-title" class="mt-1 text-xs text-faint">Say what it does. Don't lead with a product name.</p>
          {@render fieldError('title')}
        </div>

        <div>
          <div class="flex items-baseline justify-between">
            <label for="f-summary" class="text-sm font-medium">Summary</label>
            <span class="text-xs tabular-nums {draft.summary.length > 160 ? 'text-block' : 'text-faint'}">{draft.summary.length}/160</span>
          </div>
          <input id="f-summary" bind:value={draft.summary} class="{inputCls} {border('summary')}" placeholder="One line shown on cards and in search." aria-describedby={shown.summary ? 'e-summary' : undefined} />
          {@render fieldError('summary')}
        </div>

        <div>
          <div class="flex items-end justify-between">
            <label for="f-description" class="text-sm font-medium">Description <span class="font-normal text-faint">(markdown, optional)</span></label>
            <div class="flex rounded-lg border border-line p-0.5 text-xs" role="tablist" aria-label="Description editor">
              {#each [['write', 'Write'], ['preview', 'Preview']] as [id, label] (id)}
                <button type="button" role="tab" aria-selected={descTab === id} onclick={() => (descTab = id as 'write' | 'preview')} class="rounded-md px-2.5 py-1 font-medium transition {descTab === id ? 'bg-surface-2 text-fg' : 'text-muted hover:text-fg'}">{label}</button>
              {/each}
            </div>
          </div>
          {#if descTab === 'write'}
            <textarea
              id="f-description"
              bind:value={draft.description}
              rows="8"
              class="{inputCls} {border('description')} font-mono text-[13px] leading-relaxed"
              placeholder={'What it does, what to tune, and where to get any connector that isn’t on the Content Hub.'}
              aria-describedby={shown.description ? 'e-description' : undefined}
            ></textarea>
          {:else}
            <div class="mt-1.5 min-h-[12.5rem] rounded-lg border border-line bg-bg px-4 py-3">
              {#if draft.description.trim()}<Markdown source={draft.description} />{:else}<p class="text-sm text-faint">Nothing to preview yet.</p>{/if}
            </div>
          {/if}
          {@render fieldError('description')}
        </div>

        <fieldset aria-describedby="h-uc {shown.useCases ? 'e-useCases' : ''}">
          <legend class="text-sm font-medium">Use cases</legend>
          <p id="h-uc" class="mt-0.5 text-xs text-faint">Pick 1 to 3.</p>
          <div id="f-useCases" tabindex="-1" class="mt-2 flex flex-wrap gap-2 outline-none">
            {#each useCases as u (u.id)}
              {@const on = draft.useCases.includes(u.id)}
              {@const Icon = useCaseIcon(u.icon)}
              <button
                type="button"
                aria-pressed={on}
                disabled={!on && draft.useCases.length >= 3}
                onclick={() => toggleUseCase(u.id)}
                class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-40 {on
                  ? 'border-accent bg-accent-soft text-accent-text'
                  : 'border-line bg-surface text-muted hover:border-line-strong hover:text-fg'}"
              >
                {#if on}<Check size={14} aria-hidden="true" />{:else}<Icon size={14} aria-hidden="true" />{/if}{u.label}
              </button>
            {/each}
          </div>
          {@render fieldError('useCases')}
        </fieldset>

        <div>
          <label for="f-tags" class="text-sm font-medium">Tags <span class="font-normal text-faint">(optional, up to 8)</span></label>
          <div class="mt-1.5 flex flex-wrap items-center gap-1.5 rounded-lg border bg-bg px-2 py-1.5 transition focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15 {border('tags')}">
            {#each draft.tags as t (t)}
              <span class="inline-flex items-center gap-1 rounded-md bg-surface-2 py-0.5 pr-1 pl-2 font-mono text-xs">
                {t}
                <button type="button" onclick={() => (draft.tags = draft.tags.filter((x) => x !== t))} class="grid size-4 place-items-center rounded text-faint hover:text-fg" aria-label="Remove tag {t}"><X size={12} /></button>
              </span>
            {/each}
            <input
              id="f-tags"
              bind:value={tagInput}
              onkeydown={onTagKey}
              onblur={addTag}
              disabled={draft.tags.length >= 8}
              class="min-w-[8rem] flex-1 bg-transparent px-1 py-1 text-sm outline-none placeholder:text-faint"
              placeholder={draft.tags.length ? '' : 'ip, reputation… press Enter'}
              aria-describedby="h-tags {shown.tags ? 'e-tags' : ''}"
            />
          </div>
          <p id="h-tags" class="mt-1 text-xs text-faint">Lowercase letters, numbers and hyphens.</p>
          {@render fieldError('tags')}
        </div>
      </section>

      <!-- Details -->
      <section>
        <h2 class="text-sm font-semibold">Details</h2>
        <div class="mt-3 grid gap-5 sm:grid-cols-2">
          <div>
            <label for="f-version" class="text-sm font-medium">Version</label>
            <input id="f-version" bind:value={draft.version} class="{inputCls} {border('version')} font-mono" aria-describedby={shown.version ? 'e-version' : undefined} />
            {@render fieldError('version')}
          </div>
          <div>
            <label for="f-minVersion" class="text-sm font-medium">Minimum platform version <span class="font-normal text-faint">(optional)</span></label>
            <input id="f-minVersion" bind:value={draft.minVersion} class="{inputCls} {border('minVersion')} font-mono" placeholder="7.4.0" aria-describedby={shown.minVersion ? 'e-minVersion' : undefined} />
            {@render fieldError('minVersion')}
          </div>
          <div class="sm:col-span-2">
            <label for="f-source" class="text-sm font-medium">Source repository <span class="font-normal text-faint">(required for connectors)</span></label>
            <input id="f-source" type="url" bind:value={draft.source} class="{inputCls} {border('source')}" placeholder="https://github.com/you/your-connector" aria-describedby="h-source {shown.source ? 'e-source' : ''}" />
            <p id="h-source" class="mt-1 text-xs text-faint">We list a connector's manifest and link here. We never host connector code.</p>
            {@render fieldError('source')}
          </div>
        </div>
      </section>

      <!-- Confirm + submit -->
      <section class="space-y-5 border-t border-line pt-6">
        <div>
          <label class="flex items-start gap-3 text-sm">
            <input id="f-rightsConfirmed" type="checkbox" bind:checked={draft.rightsConfirmed} class="mt-0.5 size-4 shrink-0 accent-[var(--accent)]" aria-labelledby="rights-text" aria-describedby={shown.rightsConfirmed ? 'e-rightsConfirmed' : undefined} />
            <span id="rights-text">I wrote this or have the right to share it, and I license it under <a href="https://opensource.org/license/mit" class="font-medium text-accent-text hover:underline" rel="noopener noreferrer" target="_blank">MIT</a>.</span>
          </label>
          {@render fieldError('rightsConfirmed')}
        </div>

        <div bind:this={turnstileEl} class="min-h-[65px]"></div>

        <div class="flex gap-3 rounded-xl border border-line bg-surface-2/60 p-4 text-sm text-muted">
          <Lock size={16} class="mt-0.5 shrink-0 text-accent-text" aria-hidden="true" />
          <p>Your file goes to a private quarantine first. Nothing is public until it passes the checks.</p>
        </div>

        {#if serverError}
          <div class="rounded-lg bg-block-soft px-4 py-3 text-sm text-block" role="alert">
            {serverError.message}
            {#if serverError.existingId}<a href="/me/{serverError.existingId}" class="ml-1 font-medium underline">View that submission</a>{/if}
            {#if serverError.status === 401}<a href={loginUrl(page.url.pathname)} data-sveltekit-reload class="ml-1 font-medium underline">Sign in</a>{/if}
          </div>
        {/if}

        <div class="flex flex-wrap items-center gap-4">
          <button type="submit" disabled={uploading} class="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-accent-fg transition hover:bg-accent-hover disabled:cursor-wait disabled:opacity-70">
            {#if uploading}<LoaderCircle size={16} class="animate-spin" aria-hidden="true" />Uploading…{:else}Submit for checks{/if}
          </button>
          {#if uploading}
            <div class="h-1.5 w-40 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-label="Upload progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress * 100)}>
              <div class="h-full bg-accent transition-[width]" style="width: {Math.round(progress * 100)}%"></div>
            </div>
          {/if}
        </div>
      </section>
    </div>

    <aside class="space-y-4 lg:sticky lg:top-20 lg:self-start">
      <div class="rounded-2xl border border-line bg-surface p-5">
        <div class="flex items-center gap-3">
          <Avatar url={session.me.avatarUrl} login={session.me.login} size={36} />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold">{session.me.login}</p>
            <p class="text-xs text-faint">{session.me.uploadsToday} of {session.me.dailyLimit} uploads today</p>
          </div>
        </div>
      </div>
      <div class="rounded-2xl border border-line bg-surface p-5">
        <h2 class="text-sm font-semibold">What happens next</h2>
        <ol class="mt-3 space-y-3 text-sm text-muted">
          <li><span class="font-medium text-fg">1. Checks run</span> in about a minute. Owners, config links and stray values are stripped automatically.</li>
          <li><span class="font-medium text-fg">2. You see the report</span> on your submission page, the same one visitors see.</li>
          <li><span class="font-medium text-fg">3. It's published</span> straight away if it's clean and your account is trusted; otherwise a maintainer takes a look.</li>
        </ol>
        <a href="/guide#checks" class="mt-4 inline-block text-sm font-medium text-accent-text hover:underline">What we check</a>
      </div>
    </aside>
  </form>
{/if}

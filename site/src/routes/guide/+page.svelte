<script lang="ts">
  import { SITE, LIMITS } from '$lib/config';
  import { formatBytes } from '$lib/format';

  const toc = [
    { id: 'before', label: 'Before you import' },
    { id: 'connectors', label: 'Install connectors' },
    { id: 'configure', label: 'Configure connectors' },
    { id: 'import', label: 'Import a playbook' },
    { id: 'packs', label: 'Install a solution pack' },
    { id: 'activate', label: 'Review and activate' },
    { id: 'contributing', label: 'Contributing' },
    { id: 'checks', label: 'What we check' },
    { id: 'trust', label: 'Trust tiers' },
    { id: 'self-check', label: 'Check locally' }
  ];

  const checks = [
    ['Format', 'The file must be a playbook collection export, a solution pack zip, or a connector or widget manifest (info.json). Anything else is rejected.', 'Block'],
    ['Size', `Playbook JSON up to ${formatBytes(LIMITS.playbookBytes)}, solution pack zip up to ${formatBytes(LIMITS.packBytes)}. Zips are checked for path traversal, symlinks, nested archives and decompression bombs.`, 'Block'],
    ['Secrets', 'API keys, tokens, passwords, private keys, JWTs and credentials in URLs.', 'Block'],
    ['Private network details', 'RFC 1918 and other internal IP addresses, internal hostnames, and real email addresses. Documentation ranges and example.com are fine.', 'Review'],
    ['Ownership references', 'Users, teams, owners and connector configuration IDs are stripped automatically. You don’t need to clean them yourself.', 'Auto-fixed'],
    ['Official content', 'Exports that match published solution pack content are rejected: only share what you wrote.', 'Block'],
    ['Trademarks', 'Titles and descriptions can name products to describe compatibility, but can’t claim to be official or endorsed.', 'Review'],
    ['Code', 'Code-snippet steps, connectors and widgets are flagged and always reviewed by a person. Connector and widget code is never hosted here: items link to their source.', 'Review'],
    ['Content Hub dependencies', 'Each connector and operation is checked against the current Content Hub index so users see what they need before importing.', 'Info']
  ];

  const tiers = [
    ['New', 'Any GitHub account at least 30 days old. Up to 3 submissions a day.', 'Nothing. Every submission is reviewed by a maintainer.'],
    ['Contributor', '3 approved submissions and no strikes.', 'Playbooks that pass every check and have no code steps.'],
    ['Trusted', 'Promoted by a maintainer.', 'Playbooks and solution packs that pass every check. Connectors are still reviewed.'],
    ['Maintainer', 'Runs the project.', 'Reviews the queue. Connector code is always reviewed, even from maintainers.']
  ];
</script>

<svelte:head><title>Guide · {SITE.name}</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 pt-12 sm:px-6">
  <div class="grid grid-cols-1 gap-12 lg:grid-cols-[220px_minmax(0,1fr)]">
    <nav class="hidden lg:block" aria-label="On this page">
      <div class="sticky top-20">
        <p class="text-xs font-semibold uppercase tracking-wider text-faint">On this page</p>
        <ul class="mt-3 space-y-1 border-l border-line text-sm">
          {#each toc as t (t.id)}
            <li><a href="#{t.id}" class="-ml-px block border-l border-transparent py-1 pl-4 text-muted hover:border-line-strong hover:text-fg">{t.label}</a></li>
          {/each}
        </ul>
      </div>
    </nav>

    <article class="prose max-w-3xl min-w-0 [&_h2]:scroll-mt-20 [&_h2]:border-t [&_h2]:border-line [&_h2]:pt-10 [&_h2]:text-xl">
      <p class="font-mono text-sm text-accent-text" style="margin:0">Guide</p>
      <h1 class="text-4xl font-semibold tracking-tight" style="margin-top:0.4rem">Using what you download</h1>
      <p class="text-lg text-muted">
        Everything here is an export file you bring into your own SOAR platform (compatible with FortiSOAR 7.4 and later unless an item says otherwise).
        This guide covers the general flow; each item's <strong>Setup</strong> tab lists the exact steps for that item.
      </p>

      <h2 id="before">Before you import</h2>
      <ul>
        <li>Open the item's <strong>Dependencies</strong> tab. Every connector shows whether it's on the Content Hub.</li>
        <li>If a connector is marked <strong>Not on Content Hub</strong>, the playbook was built with a custom connector. You'll need that connector, or one that offers the same operations, before those steps can run.</li>
        <li>Check the platform version. Items list the minimum version they were built for.</li>
        <li>Try it in a non-production instance first. Treat community content like any third-party code.</li>
      </ul>

      <h2 id="connectors">Install connectors from the Content Hub</h2>
      <ol>
        <li>Open <strong>Content Hub</strong> and search for the connector by name.</li>
        <li>Install the version listed in the item's dependencies, or the latest if it says "On Content Hub".</li>
        <li>If an item shows <strong>Version differs</strong>, it was built against another version. It usually still works; check that the listed operations exist in your version.</li>
      </ol>

      <h2 id="configure">Configure connectors</h2>
      <p>
        Downloads never include connector configurations or credentials: they're stripped during publishing. Add a configuration with your own
        credentials and mark it as the <strong>default</strong> so connector steps pick it up without editing each step.
      </p>

      <h2 id="import">Import a playbook</h2>
      <ol>
        <li>Download the <code>.json</code> file from the item page. Optionally verify its SHA-256 shown under the download button.</li>
        <li>Go to <strong>Settings → Import Wizard</strong> and upload the file.</li>
        <li>Review the collections and playbooks being added. If a collection with the same name exists, choose whether to merge or replace.</li>
        <li>Finish the import.</li>
      </ol>

      <h2 id="packs">Install a solution pack</h2>
      <p>
        Solution packs bundle playbooks with modules, picklists or dashboards. Upload the <code>.zip</code> from <strong>Content Hub → Manage → Upload</strong> (or the Import Wizard for configuration exports).
        If the pack depends on other packs, install those first: they're listed under Dependencies.
      </p>

      <h2 id="activate">Review and activate</h2>
      <p>
        Every download is shipped <strong>inactive</strong> on purpose, so nothing fires the moment you import it. Open each playbook, check the
        trigger conditions and any record it updates, run it manually on a test record, then activate it.
      </p>
      <blockquote>Pay particular attention to items marked <em>Contains code</em>. A maintainer reviewed them, but read code steps yourself before turning them on.</blockquote>

      <h2 id="contributing">Contributing</h2>
      <p>You can share playbook collections, solution packs, connectors and widgets you wrote yourself. The easiest way is the <a href="/submit">upload page</a>:</p>
      <ol>
        <li><a href="/submit">Sign in with GitHub</a>. Only your public profile is used, to credit you and to limit spam.</li>
        <li>Drop in your export, give it a title, a one-line summary and a use case or two.</li>
        <li>The checks run within about a minute and you see the full report on your <a href="/me">submissions page</a>. Your file sits in a private quarantine until then; nothing is public before it passes.</li>
        <li>Clean submissions from established contributors publish automatically. Everything else gets a quick review by a maintainer.</li>
      </ol>
      <h3>Prefer git?</h3>
      <p>You can also open a pull request. Fork <a href={SITE.repo}>the repository</a>, add a folder <code>content/&lt;type&gt;s/&lt;slug&gt;/</code> (for example <code>content/playbooks/ip-enrichment/</code>) with a <code>meta.yaml</code> and the <em>cleaned</em> export from <code>soarshelf check --clean-out</code> (see <a href="#self-check">below</a>), then open the pull request. The <code>author</code> must be your GitHub handle and <code>author_id</code> your numeric GitHub id (<code>gh api users/&lt;handle&gt; --jq .id</code>); CI checks both.</p>
      <pre><code>title: Enrich source IPs with threat intel
summary: Scores alerts by source IP reputation and skips private addresses.
use_cases: [triage, enrichment]
tags: [enrichment, ip]
author: your-github-handle
author_id: 12345678
version: 1.0.0
min_version: 7.4.0
description: |
  Longer markdown description shown on the item page.</code></pre>
      <p>Please don't upload:</p>
      <ul>
        <li>Content you didn't write, including official solution packs or anything copied from a vendor or customer.</li>
        <li>Customer names, internal hostnames, real IPs or email addresses. Use <code>example.com</code> and documentation IP ranges.</li>
        <li>Credentials of any kind, even expired ones.</li>
        <li>Logos or vendor branding. Product names are fine when they describe what the item works with.</li>
      </ul>
      <p>By submitting you confirm you have the right to share the content and license it under the MIT license.</p>

      <h2 id="checks">What we check</h2>
      <p>Every submission runs through the same pipeline. Downloads are rebuilt from the parsed content, never served as the bytes you uploaded.</p>
    </article>
  </div>

  <div class="mt-6 lg:ml-[calc(220px+3rem)]">
    <div class="max-w-3xl overflow-x-auto rounded-xl border border-line">
      <table class="w-full min-w-[560px] text-sm">
        <thead class="bg-surface-2 text-left text-xs uppercase tracking-wider text-faint">
          <tr><th class="px-4 py-2.5 font-semibold">Check</th><th class="px-4 py-2.5 font-semibold">What it looks for</th><th class="px-4 py-2.5 font-semibold">Outcome</th></tr>
        </thead>
        <tbody class="divide-y divide-line bg-surface">
          {#each checks as [name, what, outcome] (name)}
            <tr>
              <td class="px-4 py-3 align-top font-medium whitespace-nowrap">{name}</td>
              <td class="px-4 py-3 align-top text-muted">{what}</td>
              <td class="px-4 py-3 align-top">
                <span
                  class="rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap {outcome === 'Block'
                    ? 'bg-block-soft text-block'
                    : outcome === 'Review'
                      ? 'bg-warn-soft text-warn'
                      : outcome === 'Auto-fixed'
                        ? 'bg-ok-soft text-ok'
                        : 'bg-info-soft text-info'}">{outcome}</span
                >
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="prose mt-2 max-w-3xl [&_h2]:scroll-mt-20 [&_h2]:border-t [&_h2]:border-line [&_h2]:pt-10 [&_h2]:text-xl">
      <h2 id="trust">Trust tiers</h2>
      <p>Clean submissions from established contributors can publish automatically. Everything else waits for a maintainer.</p>
    </div>
    <div class="mt-4 max-w-3xl overflow-x-auto rounded-xl border border-line">
      <table class="w-full min-w-[560px] text-sm">
        <thead class="bg-surface-2 text-left text-xs uppercase tracking-wider text-faint">
          <tr><th class="px-4 py-2.5 font-semibold">Tier</th><th class="px-4 py-2.5 font-semibold">How you get there</th><th class="px-4 py-2.5 font-semibold">Publishes automatically</th></tr>
        </thead>
        <tbody class="divide-y divide-line bg-surface">
          {#each tiers as [tier, how, auto] (tier)}
            <tr><td class="px-4 py-3 align-top font-medium">{tier}</td><td class="px-4 py-3 align-top text-muted">{how}</td><td class="px-4 py-3 align-top text-muted">{auto}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="prose mt-2 max-w-3xl [&_h2]:scroll-mt-20 [&_h2]:border-t [&_h2]:border-line [&_h2]:pt-10 [&_h2]:text-xl">
      <h2 id="self-check">Check locally before you submit</h2>
      <p>The pipeline is a small Python CLI in the repository. Run it on your export to see exactly what CI will report:</p>
      <pre><code>cd pipeline
uv run soarshelf check path/to/your-export.json</code></pre>
      <p>Anything marked <strong>block</strong> must be fixed. <strong>Review</strong> findings are fine if they're intended; a maintainer will look at them.</p>
    </div>
  </div>
</div>

<script lang="ts">
  import { SITE } from '$lib/config';
</script>

<svelte:head><title>About · {SITE.name}</title></svelte:head>

<article class="prose mx-auto max-w-3xl px-4 pt-12 sm:px-6">
  <p class="font-mono text-sm text-accent-text" style="margin:0">About</p>
  <h1 class="text-4xl font-semibold tracking-tight" style="margin-top:0.4rem">An independent shelf for community SOAR content</h1>
  <p class="text-lg text-muted">
    {SITE.name} is a community project for sharing playbooks, solution packs and connectors that people built for their own SOAR deployments.
  </p>

  <h2>Not affiliated with Fortinet</h2>
  <p>
    {SITE.name} is <strong>not affiliated with, endorsed by, or sponsored by Fortinet, Inc.</strong> FortiSOAR and other product names are trademarks of their
    respective owners. They are used here only to describe what community content is compatible with. Nothing on this site is official
    content, and nothing here is supported by any vendor.
  </p>

  <h2>Who owns the content</h2>
  <p>
    Each item belongs to the contributor who submitted it and is shared under the MIT license. Contributors confirm they wrote the content and
    have the right to share it. Official vendor content is not accepted: the pipeline rejects exports that match published solution packs.
  </p>

  <h2>Use at your own risk</h2>
  <p>
    Every submission is scanned and sanitized, and code is reviewed, but community content comes with no warranty. Test it in a non-production
    instance first, read anything marked <em>Contains code</em>, and only activate playbooks you understand.
  </p>

  <h2>Reporting and takedowns</h2>
  <p>
    If something here exposes sensitive data, infringes your rights, or is malicious, <a href="{SITE.issues}/new?title=Takedown%20request" rel="noopener noreferrer">open an issue</a>
    with the item's link. Use the "Report it" link at the bottom of any item page. Reported items can be pulled while they're reviewed.
    For anything that shouldn't be public, say so in the issue without including the sensitive details and a maintainer will follow up privately.
  </p>

  <h2>Source</h2>
  <p>
    The site, the checking pipeline and all published content live in <a href={SITE.repo} rel="noopener noreferrer">one public repository</a>, so every
    change is reviewable.
  </p>
</article>

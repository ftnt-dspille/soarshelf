<script lang="ts">
  import { SITE } from '$lib/config';
  import Logo from './Logo.svelte';
</script>

<footer class="mt-24 border-t border-line">
  <div class="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
    <div class="space-y-3">
      <Logo size={24} />
      <p class="max-w-sm text-sm text-muted">{SITE.tagline}</p>
    </div>
    <div>
      <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-faint">Explore</h2>
      <ul class="space-y-2 text-sm">
        <li><a class="text-muted hover:text-fg" href="/browse?type=playbook">Playbooks</a></li>
        <li><a class="text-muted hover:text-fg" href="/browse?type=solution-pack">Solution packs</a></li>
        <li><a class="text-muted hover:text-fg" href="/browse?type=connector">Connectors</a></li>
        <li><a class="text-muted hover:text-fg" href="/collections">Collections</a></li>
        <li><a class="text-muted hover:text-fg" href="/changes">Changes</a></li>
        <li><a class="text-muted hover:text-fg" href="/feed.xml">Atom feed</a></li>
      </ul>
    </div>
    <div>
      <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-faint">Learn</h2>
      <ul class="space-y-2 text-sm">
        <li><a class="text-muted hover:text-fg" href="/guide">Setup guide</a></li>
        <li><a class="text-muted hover:text-fg" href="/guide#contributing">Contributing</a></li>
        <li><a class="text-muted hover:text-fg" href="/guide#checks">What we check</a></li>
      </ul>
    </div>
    <div>
      <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-faint">Project</h2>
      <ul class="space-y-2 text-sm">
        <li><a class="text-muted hover:text-fg" href="/about">About</a></li>
        <li><a class="text-muted hover:text-fg" href={SITE.repo} rel="noopener noreferrer">Source</a></li>
        <li><a class="text-muted hover:text-fg" href={SITE.issues} rel="noopener noreferrer">Report content</a></li>
      </ul>
    </div>
  </div>
  <div class="border-t border-line">
    <p class="mx-auto max-w-7xl px-4 py-5 text-xs leading-relaxed text-faint sm:px-6">{SITE.disclaimer}</p>
  </div>
</footer>

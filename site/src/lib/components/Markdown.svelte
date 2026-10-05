<script lang="ts">
  import { renderMarkdown } from '$lib/markdown';
  let { source }: { source: string } = $props();
  const html = $derived(renderMarkdown(source));
</script>

<!-- renderMarkdown escapes raw HTML and filters link protocols; DOMPurify runs on top in the browser. -->
<div class="prose">{@html html}</div>

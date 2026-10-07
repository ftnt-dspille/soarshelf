<script lang="ts">
  // Renders a string with Jinja expressions highlighted. Text only: every
  // part is a text node, never HTML.
  let { value, block = false }: { value: string; block?: boolean } = $props();

  const parts = $derived(
    value.split(/(\{\{[\s\S]*?\}\}|\{%[\s\S]*?%\})/g).filter(Boolean).map((text) => ({ text, expr: /^\{[{%]/.test(text) }))
  );
</script>

{#if block}
  <code class="block max-h-64 overflow-auto rounded-lg border border-line bg-surface-2 px-3 py-2 font-mono text-[12px] leading-relaxed [overflow-wrap:anywhere] whitespace-pre-wrap text-fg"
    >{#each parts as p, i (i)}{#if p.expr}<span class="expr">{p.text}</span>{:else}{p.text}{/if}{/each}</code
  >
{:else}
  <code class="font-mono text-[12.5px] leading-relaxed [overflow-wrap:anywhere] whitespace-pre-wrap text-fg"
    >{#each parts as p, i (i)}{#if p.expr}<span class="expr">{p.text}</span>{:else}{p.text}{/if}{/each}</code
  >
{/if}

<style>
  .expr {
    color: var(--accent-text);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    border-radius: 4px;
    padding: 0 2px;
  }
</style>

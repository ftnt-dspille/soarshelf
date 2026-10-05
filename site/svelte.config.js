import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ pages: 'build', assets: 'build', fallback: '404.html', strict: true }),
    // Emitted as a <meta> tag with hashes for SvelteKit's inline bootstrap script.
    // frame-ancestors can't be set from <meta>; static/_headers covers it.
    csp: {
      mode: 'hash',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        // Svelte transitions and the graph canvas set style attributes at runtime.
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:'],
        'font-src': ['self'],
        'connect-src': ['self'],
        'object-src': ['none'],
        'base-uri': ['self'],
        'form-action': ['self']
      }
    },
    prerender: {
      // Item-page tabs are client-side #hash routes (e.g. #playbooks/0:1), not element ids.
      handleMissingId: ({ id, message }) => {
        if (/^(overview|playbooks|setup|dependencies|checks)(\/|$)/.test(id)) return;
        throw new Error(message);
      },
      // Downloads are written by the pipeline; the dev fixture has none, so don't fail on them.
      handleHttpError: ({ path, message }) => {
        if (path.startsWith('/downloads/')) return console.warn(`prerender: ${message}`);
        throw new Error(message);
      }
    }
  }
};

export default config;

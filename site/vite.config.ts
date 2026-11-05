import adapter from '@sveltejs/adapter-static';
import { sveltekit, type Config as KitConfig } from '@sveltejs/kit/vite';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { mockApi } from './mock-api.ts';

// MOCK_API=1 pnpm dev  -> in-process fake upload API (see mock-api.ts)
// pnpm dev             -> /api proxied to `wrangler dev` on :8787
const mock = process.env.MOCK_API === '1';

// SvelteKit 3: the former svelte.config.js rides the plugin call, flattened
// (no `kit:` namespace) and alongside the vite-plugin-svelte keys.
const sveltekit_config: KitConfig = {
  preprocess: vitePreprocess(),
  adapter: adapter({ pages: 'build', assets: 'build', fallback: '404.html', strict: true }),
  // Emitted as a <meta> tag with hashes for SvelteKit's inline bootstrap script.
  // frame-ancestors can't be set from <meta>; static/_headers covers it.
  csp: {
    mode: 'hash' as const,
    directives: {
      'default-src': ['self'],
      // Turnstile (bot check) on the upload page.
      'script-src': ['self', 'https://challenges.cloudflare.com'],
      'frame-src': ['https://challenges.cloudflare.com'],
      // Svelte transitions and the graph canvas set style attributes at runtime.
      'style-src': ['self', 'unsafe-inline'],
      // GitHub avatars of signed-in users.
      'img-src': ['self', 'data:', 'https://avatars.githubusercontent.com'],
      'font-src': ['self'],
      'connect-src': ['self'],
      'object-src': ['none'],
      'base-uri': ['self'],
      'form-action': ['self']
    }
  },
  prerender: {
    // Item-page tabs are client-side #hash routes (e.g. #playbooks/0:1), not element ids.
    handleMissingId: ({ id, message }: { id: string; message: string }) => {
      if (/^(overview|playbooks|setup|dependencies|checks)(\/|$)/.test(id)) return;
      throw new Error(message);
    },
    // Downloads are written by the pipeline; the dev fixture has none, so don't fail on them.
    handleHttpError: ({ path, message }: { path: string; message: string }) => {
      if (path.startsWith('/downloads/')) return console.warn(`prerender: ${message}`);
      // /api/* is the upload Worker, which only exists at runtime.
      if (path.startsWith('/api/')) return;
      throw new Error(message);
    }
  }
};

export default defineConfig({
  plugins: [tailwindcss(), ...(mock ? [mockApi()] : []), sveltekit(sveltekit_config)],
  server: mock ? {} : { proxy: { '/api': { target: 'http://127.0.0.1:8787', changeOrigin: false } } },
  test: { include: ['src/**/*.test.ts'], environment: 'node' }
});

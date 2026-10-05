import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { mockApi } from './mock-api';

// MOCK_API=1 pnpm dev  -> in-process fake upload API (see mock-api.ts)
// pnpm dev             -> /api proxied to `wrangler dev` on :8787
const mock = process.env.MOCK_API === '1';

export default defineConfig({
  plugins: [tailwindcss(), ...(mock ? [mockApi()] : []), sveltekit()],
  server: mock ? {} : { proxy: { '/api': { target: 'http://127.0.0.1:8787', changeOrigin: false } } },
  test: { include: ['src/**/*.test.ts'], environment: 'node' }
});

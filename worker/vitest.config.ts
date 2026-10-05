import { defineConfig } from 'vitest/config';
import { cloudflareTest, readD1Migrations } from '@cloudflare/vitest-pool-workers';

// Every outbound call the Worker makes is answered here, so tests never touch
// the network: Turnstile, contributors.yaml on GitHub, and the GitHub API.
function outbound(req: Request): Response {
  const url = new URL(req.url);
  if (url.hostname === 'challenges.cloudflare.com') {
    return Response.json({ success: true });
  }
  if (url.hostname === 'raw.githubusercontent.com') {
    return new Response('# test tiers\nboss: {trust: maintainer, id: 1}\npat: {trust: contributor, id: 2}\n');
  }
  if (url.hostname === 'api.github.com' || url.hostname === 'github.com') {
    return new Response(null, { status: 204 });
  }
  return new Response('unexpected outbound fetch: ' + req.url, { status: 599 });
}

export default defineConfig(async () => ({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: './wrangler.toml' },
      miniflare: {
        bindings: {
          TEST_MIGRATIONS: await readD1Migrations('migrations'),
          SITE_ORIGIN: 'https://shelf.test',
          REPO: 'acme/shelf',
          SESSION_SECRET: 'test-session-secret-that-is-long-enough',
          TURNSTILE_SECRET: 'test',
          INTERNAL_TOKEN: 'i'.repeat(40),
          GITHUB_APP_ID: '',
          DEV_LOGIN: '1'
        },
        outboundService: outbound
      }
    })
  ],
  test: { setupFiles: ['./test/setup.ts'] }
}));

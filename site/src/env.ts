import { defineEnvVars } from '@sveltejs/kit/env';

// Set at build time by CI (repo variable TURNSTILE_SITE_KEY -> PUBLIC_TURNSTILE_SITE_KEY).
// Optional: when absent (local builds, or CI before the variable is set) the
// submit page falls back to Cloudflare's always-pass test sitekey.
export const variables = defineEnvVars({
	PUBLIC_TURNSTILE_SITE_KEY: {
		public: true,
		static: true,
		schema: (value) => value || undefined,
		description: 'Cloudflare Turnstile sitekey for the upload form'
	}
});

import type { PageLoad } from './$types';

// Submission ids only exist at runtime, so this page is rendered in the
// browser and served through the static site's SPA fallback.
export const prerender = false;
export const ssr = false;

export const load: PageLoad = ({ params }) => ({ id: params.id });

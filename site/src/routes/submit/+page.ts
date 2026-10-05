import { loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

// Prerendered shell; who's signed in is checked in the browser.
export const load: PageLoad = async ({ fetch }) => ({ index: await loadIndex(fetch) });

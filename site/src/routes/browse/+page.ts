import { loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ index: await loadIndex(fetch) });

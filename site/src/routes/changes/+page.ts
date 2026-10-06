import { loadActivity } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ activity: await loadActivity(fetch) });

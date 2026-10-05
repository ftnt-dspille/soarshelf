import { loadIndex, loadItem } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const [item, index] = await Promise.all([loadItem(fetch, params.slug), loadIndex(fetch)]);
  return { item, index };
};

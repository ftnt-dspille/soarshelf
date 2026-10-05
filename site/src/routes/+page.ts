import { loadFeatured, loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  const [index, featured] = await Promise.all([loadIndex(fetch), loadFeatured(fetch)]);
  return { index, featured };
};

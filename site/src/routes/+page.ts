import { loadCollections, loadFeatured, loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  const [index, featured, collections] = await Promise.all([loadIndex(fetch), loadFeatured(fetch), loadCollections(fetch)]);
  return { index, featured, collections };
};

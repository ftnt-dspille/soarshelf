import { loadCollections, loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  const [index, collections] = await Promise.all([loadIndex(fetch), loadCollections(fetch)]);
  return { index, collections };
};

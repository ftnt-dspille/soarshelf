import { loadCollections, loadIndex, loadItem } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const [item, index, collections] = await Promise.all([
    loadItem(fetch, params.slug),
    loadIndex(fetch),
    loadCollections(fetch)
  ]);
  return { item, index, inCollections: collections.filter((c) => c.items.some((i) => i.slug === params.slug)) };
};

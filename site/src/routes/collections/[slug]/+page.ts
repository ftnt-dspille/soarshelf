import { error } from '@sveltejs/kit';
import { loadCollections, loadIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const [index, collections] = await Promise.all([loadIndex(fetch), loadCollections(fetch)]);
  const collection = collections.find((c) => c.slug === params.slug);
  if (!collection) error(404, 'Not found');
  return { index, collection };
};

import { error } from '@sveltejs/kit';
import type { Activity, Featured, ItemDetail, SiteIndex } from './types';

type Fetch = typeof fetch;

export async function loadIndex(fetch: Fetch): Promise<SiteIndex> {
  const res = await fetch('/data/index.json');
  if (!res.ok) error(500, 'Catalog index is missing. Run the pipeline build or restore the dev fixture.');
  return res.json();
}

export async function loadItem(fetch: Fetch, slug: string): Promise<ItemDetail> {
  // Slugs come from the URL; only allow the shape the pipeline produces.
  if (!/^[a-z0-9][a-z0-9-]{0,80}$/.test(slug)) error(404, 'Not found');
  const res = await fetch(`/data/items/${slug}.json`);
  if (res.status === 404) error(404, 'Not found');
  if (!res.ok) error(500, 'Could not load this item.');
  return res.json();
}

/** Map of connector machine name → display label from the index. */
export function connectorLabels(index: SiteIndex): Map<string, string> {
  return new Map(index.connectors.map((c) => [c.name, c.label]));
}

/** Site-wide change log. Optional like featured: an older build just shows nothing. */
export async function loadActivity(fetch: Fetch): Promise<Activity> {
  const res = await fetch('/data/activity.json');
  return res.ok ? res.json() : { generated: '', events: [] };
}

/** Home-page graphs. Optional: an older build without the file just shows none. */
export async function loadFeatured(fetch: Fetch): Promise<Featured> {
  const res = await fetch('/data/featured.json');
  return res.ok ? res.json() : { items: [], connectorLabels: {} };
}

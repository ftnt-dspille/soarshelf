import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { EntryGenerator } from './$types';
import type { SiteIndex } from '$lib/types';

// Prerender one page per item in the index the pipeline wrote (or the dev fixture).
export const entries: EntryGenerator = () => {
  const index = JSON.parse(readFileSync(resolve('static/data/index.json'), 'utf8')) as SiteIndex;
  return index.items.map((i) => ({ slug: i.slug }));
};

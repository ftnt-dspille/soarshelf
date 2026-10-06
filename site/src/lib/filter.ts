// Pure search + facet logic for /browse. No Svelte, no DOM: unit-tested in filter.test.ts.
import MiniSearch from 'minisearch';
import { byLastChange } from './format';
import type { ConnectorFacet, HubStatus, ItemSummary, ItemType, UseCase } from './types';

export type SortKey = 'relevance' | 'newest' | 'updated' | 'name';

export interface FilterState {
  q: string;
  types: ItemType[];
  useCases: string[];
  connectors: string[];
  hub: HubStatus[];
  triggers: string[];
  noCode: boolean;
  sort: SortKey;
}

export type FacetKey = 'types' | 'useCases' | 'connectors' | 'hub' | 'triggers';

export const EMPTY_FILTERS: FilterState = {
  q: '',
  types: [],
  useCases: [],
  connectors: [],
  hub: [],
  triggers: [],
  noCode: false,
  sort: 'relevance'
};

const ITEM_TYPES: ItemType[] = ['playbook', 'solution-pack', 'connector', 'widget'];
const HUB: HubStatus[] = ['complete', 'version-mismatch', 'needs-custom'];
const SORTS: SortKey[] = ['relevance', 'newest', 'updated', 'name'];

// URL param names are short so shared links stay readable.
const PARAM: Record<FacetKey, string> = {
  types: 'type',
  useCases: 'uc',
  connectors: 'conn',
  hub: 'hub',
  triggers: 'trigger'
};

function list(params: URLSearchParams, key: string): string[] {
  return (params.get(key) ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export function parseFilters(params: URLSearchParams): FilterState {
  const sort = params.get('sort') as SortKey;
  return {
    q: params.get('q') ?? '',
    types: list(params, PARAM.types).filter((t): t is ItemType => ITEM_TYPES.includes(t as ItemType)),
    useCases: list(params, PARAM.useCases),
    connectors: list(params, PARAM.connectors),
    hub: list(params, PARAM.hub).filter((h): h is HubStatus => HUB.includes(h as HubStatus)),
    triggers: list(params, PARAM.triggers),
    noCode: params.get('nocode') === '1',
    sort: SORTS.includes(sort) ? sort : 'relevance'
  };
}

export function serializeFilters(f: FilterState): string {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set('q', f.q.trim());
  for (const k of Object.keys(PARAM) as FacetKey[]) {
    if (f[k].length) p.set(PARAM[k], f[k].join(','));
  }
  if (f.noCode) p.set('nocode', '1');
  if (f.sort !== 'relevance') p.set('sort', f.sort);
  const s = p.toString();
  return s ? `?${s}` : '';
}

export function activeFilterCount(f: FilterState): number {
  return f.types.length + f.useCases.length + f.connectors.length + f.hub.length + f.triggers.length + (f.noCode ? 1 : 0);
}

export interface Search {
  /** slug → relevance score; null when the query is empty (everything matches). */
  scores(q: string): Map<string, number> | null;
}

export function createSearch(items: ItemSummary[], connectors: ConnectorFacet[], useCases: UseCase[]): Search {
  const connLabel = new Map(connectors.map((c) => [c.name, c.label]));
  const ucLabel = new Map(useCases.map((u) => [u.id, u.label]));
  const ms = new MiniSearch<Record<string, string>>({
    idField: 'slug',
    fields: ['title', 'displayName', 'summary', 'tags', 'connectors', 'triggers', 'useCases'],
    searchOptions: {
      boost: { title: 3, displayName: 3, connectors: 2, tags: 1.5 },
      prefix: true,
      fuzzy: 0.2,
      combineWith: 'AND'
    }
  });
  ms.addAll(
    items.map((i) => ({
      slug: i.slug,
      title: i.title,
      displayName: i.displayName ?? '',
      summary: i.summary,
      tags: i.tags.join(' '),
      connectors: i.connectors.map((c) => `${c} ${connLabel.get(c) ?? ''}`).join(' '),
      triggers: i.triggers.join(' '),
      useCases: i.useCases.map((u) => ucLabel.get(u) ?? u).join(' ')
    }))
  );
  return {
    scores(q) {
      const query = q.trim();
      if (!query) return null;
      let hits = ms.search(query);
      // Fall back to OR when every-word matching finds nothing.
      if (!hits.length) hits = ms.search(query, { combineWith: 'OR' });
      return new Map(hits.map((h) => [String(h.id), h.score]));
    }
  };
}

function matchesFacet(item: ItemSummary, f: FilterState, key: FacetKey): boolean {
  const sel = f[key] as string[];
  if (!sel.length) return true;
  switch (key) {
    case 'types':
      return sel.includes(item.type);
    case 'hub':
      return sel.includes(item.hubStatus);
    case 'useCases':
      return item.useCases.some((u) => sel.includes(u));
    case 'connectors':
      return item.connectors.some((c) => sel.includes(c));
    case 'triggers':
      return item.triggers.some((t) => sel.includes(t));
  }
}

/** Items matching every facet except `skip` (used for counts) plus the search and no-code toggle. */
function matches(item: ItemSummary, f: FilterState, scores: Map<string, number> | null, skip?: FacetKey): boolean {
  if (scores && !scores.has(item.slug)) return false;
  if (f.noCode && item.hasCode) return false;
  for (const k of Object.keys(PARAM) as FacetKey[]) {
    if (k !== skip && !matchesFacet(item, f, k)) return false;
  }
  return true;
}

export function applyFilters(items: ItemSummary[], f: FilterState, search: Search): ItemSummary[] {
  const scores = search.scores(f.q);
  const out = items.filter((i) => matches(i, f, scores));
  const byName = (a: ItemSummary, b: ItemSummary) => a.title.localeCompare(b.title);
  const byNewest = (a: ItemSummary, b: ItemSummary) => b.published.localeCompare(a.published) || byName(a, b);
  const byUpdated = (a: ItemSummary, b: ItemSummary) => byLastChange(a, b) || byNewest(a, b);
  if (f.sort === 'name') return out.sort(byName);
  if (f.sort === 'updated') return out.sort(byUpdated);
  if (f.sort === 'newest' || !scores) return out.sort(byNewest);
  return out.sort((a, b) => scores.get(b.slug)! - scores.get(a.slug)! || byName(a, b));
}

/**
 * Counts per facet value, computed against everything else that's selected
 * (so picking one connector still shows how many items the others would add).
 */
export function facetCounts(items: ItemSummary[], f: FilterState, search: Search): Record<FacetKey, Map<string, number>> {
  const scores = search.scores(f.q);
  const out = {} as Record<FacetKey, Map<string, number>>;
  for (const key of Object.keys(PARAM) as FacetKey[]) {
    const counts = new Map<string, number>();
    for (const item of items) {
      if (!matches(item, f, scores, key)) continue;
      const values =
        key === 'types' ? [item.type] : key === 'hub' ? [item.hubStatus] : (item[key] as string[]);
      for (const v of new Set(values)) counts.set(v, (counts.get(v) ?? 0) + 1);
    }
    out[key] = counts;
  }
  return out;
}

export function toggle<T extends string>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

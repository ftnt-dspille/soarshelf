import { describe, expect, it } from 'vitest';
import index from './fixtures/index.json';
import type { SiteIndex } from './types';
import {
  EMPTY_FILTERS,
  activeFilterCount,
  applyFilters,
  createSearch,
  facetCounts,
  matchedPlaybook,
  parseFilters,
  serializeFilters,
  toggle,
  type FilterState
} from './filter';

const idx = index as SiteIndex;
const search = createSearch(idx.items, idx.connectors, idx.useCases);
const run = (f: Partial<FilterState>) => applyFilters(idx.items, { ...EMPTY_FILTERS, ...f }, search).map((i) => i.slug);

describe('search', () => {
  it('returns everything, newest first, for an empty query', () => {
    const all = run({});
    expect(all).toHaveLength(idx.items.length);
    const dates = all.map((s) => idx.items.find((i) => i.slug === s)!.published);
    expect([...dates].sort().reverse()).toEqual(dates);
  });

  it('sorts by the latest change, updates first on the same day', () => {
    const oldest = [...idx.items].sort((a, b) => a.published.localeCompare(b.published))[0];
    const items = idx.items.map((i) =>
      i.slug === oldest.slug ? { ...i, lastChange: { kind: 'updated' as const, version: '9.9.9', date: '2999-01-01', notes: '' } } : i
    );
    const sorted = applyFilters(items, { ...EMPTY_FILTERS, sort: 'updated' }, createSearch(items, idx.connectors, idx.useCases));
    expect(sorted[0].slug).toBe(oldest.slug);
    expect(parseFilters(new URLSearchParams('sort=updated')).sort).toBe('updated');
  });

  it('filters and counts by live test result, from the URL too', () => {
    const [a, b] = idx.items;
    const items = idx.items.map((i) =>
      i.slug === a.slug
        ? { ...i, tested: { platform: '8.0.0', result: 'ran' as const } }
        : i.slug === b.slug
          ? { ...i, tested: { platform: '8.0.0', result: 'imported' as const } }
          : i
    );
    const s = createSearch(items, idx.connectors, idx.useCases);
    const f = { ...EMPTY_FILTERS, ...parseFilters(new URLSearchParams('tested=ran,bogus')) };
    expect(f.tested).toEqual(['ran']);
    expect(applyFilters(items, f, s).map((i) => i.slug)).toEqual([a.slug]);
    const counts = facetCounts(items, EMPTY_FILTERS, s).tested;
    expect([counts.get('ran'), counts.get('imported')]).toEqual([1, 1]);
    expect(serializeFilters(f)).toBe('?tested=ran');
  });

  it('matches connector labels and ranks title hits first', () => {
    expect(run({ q: 'virustotal' })[0]).toBe('vt-ip-enrichment');
    expect(run({ q: 'abuseipdb' })).toContain('abuseipdb-feed-ingest');
  });

  it('is typo- and prefix-tolerant', () => {
    expect(run({ q: 'phish' })).toContain('phishing-response-kit');
    expect(run({ q: 'phishnig' })).toContain('phishing-response-kit');
  });

  it('falls back to OR when no item has every word', () => {
    expect(run({ q: 'virustotal ticketing' }).length).toBeGreaterThan(0);
  });
});

describe('facets', () => {
  it('ORs within a facet and ANDs across facets', () => {
    expect(run({ types: ['playbook', 'connector'] })).not.toContain('phishing-response-kit');
    expect(run({ useCases: ['threat-intel'], types: ['playbook'] }).sort()).toEqual(['abuseipdb-feed-ingest', 'vt-ip-enrichment']);
  });

  it('filters by hub status and hides code steps', () => {
    expect(run({ hub: ['needs-custom'] }).sort()).toEqual(['incident-ticket-sync', 'shodan-lite-connector']);
    expect(run({ noCode: true })).not.toContain('phishing-response-kit');
  });

  it('counts a facet ignoring its own selection', () => {
    const f = { ...EMPTY_FILTERS, types: ['connector' as const] };
    const counts = facetCounts(idx.items, f, search);
    expect(counts.types.get('playbook')).toBe(3);
    expect(counts.useCases.get('threat-intel')).toBe(1);
  });
});

describe('url state', () => {
  it('round-trips through query params', () => {
    const f: FilterState = { ...EMPTY_FILTERS, q: 'ip rep', types: ['playbook'], connectors: ['virustotal', 'abuseipdb'], noCode: true, sort: 'newest' };
    const qs = serializeFilters(f);
    expect(parseFilters(new URLSearchParams(qs))).toEqual(f);
    expect(serializeFilters(EMPTY_FILTERS)).toBe('');
  });

  it('drops unknown enum values from hand-edited URLs', () => {
    const f = parseFilters(new URLSearchParams('type=playbook,evil&hub=nope&sort=x'));
    expect(f.types).toEqual(['playbook']);
    expect(f.hub).toEqual([]);
    expect(f.sort).toBe('relevance');
  });

  it('counts active filters and toggles values', () => {
    expect(activeFilterCount({ ...EMPTY_FILTERS, types: ['playbook'], noCode: true })).toBe(2);
    expect(toggle(['a', 'b'], 'a')).toEqual(['b']);
    expect(toggle(['a'], 'b')).toEqual(['a', 'b']);
  });
});

describe('playbook names', () => {
  const base = idx.items[0];
  const pack = { ...base, slug: 'pack', title: 'Tutorial pack', summary: 'Examples.', playbooks: [['Intro'], ['Dad Joke API Playbook', 'Other']] };
  const items = [...idx.items, pack];
  const s2 = createSearch(items, idx.connectors, idx.useCases);

  it('finds an item by a playbook inside it', () => {
    expect(applyFilters(items, { ...EMPTY_FILTERS, q: 'dad' }, s2).map((i) => i.slug)).toContain('pack');
  });

  it('does not match short words by a one-letter typo', () => {
    const bad = { ...base, slug: 'bad', title: 'Bad indicators', summary: 'x', playbooks: [] };
    const s3 = createSearch([pack, bad], idx.connectors, idx.useCases);
    expect(applyFilters([pack, bad], { ...EMPTY_FILTERS, q: 'dad' }, s3).map((i) => i.slug)).toEqual(['pack']);
  });

  it('names the playbook that matched, with its viewer position', () => {
    expect(matchedPlaybook(pack, 'dad joke')).toEqual({ name: 'Dad Joke API Playbook', key: '1:0' });
    // the title already explains the match, or nothing matched by name
    expect(matchedPlaybook(pack, 'tutorial')).toBeNull();
    expect(matchedPlaybook(pack, 'zebra')).toBeNull();
    expect(matchedPlaybook(base, 'dad')).toBeNull();
  });
});

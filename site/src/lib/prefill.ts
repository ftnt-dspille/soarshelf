// Read the listing details an upload already carries, so the uploader only
// has to confirm them: a playbook export's collection name and description,
// or a connector/widget manifest (info.json), loose or inside its .tgz.
// Runs in the browser; nothing here is trusted, the pipeline re-reads it all.

export type DetectedKind = 'playbook' | 'connector' | 'widget' | 'solution-pack';

export interface Prefill {
  kind: DetectedKind;
  name?: string;
  title?: string;
  summary?: string;
  version?: string;
  useCases?: string[];
}

/** First sentence, or the text cut at a word boundary, within `limit` characters. */
export function firstSentence(text: string, limit = 160): string {
  const t = text.replace(/\s+/g, ' ').trim();
  const end = t.indexOf('. ');
  if (end > 0 && end < limit) return t.slice(0, end + 1);
  if (t.length <= limit) return t;
  return t.slice(0, limit - 1).replace(/\s+\S*$/, '').replace(/[,;:]$/, '') + '…';
}

// Connector categories and descriptions -> the site's use cases (a guess the uploader can change).
const USE_CASE_HINTS: [RegExp, string][] = [
  [/threat intel|reputation|enrich|sandbox|malware analysis/i, 'enrichment'],
  [/firewall|network security|endpoint|edr|block|quarantine|isolat/i, 'containment'],
  [/vulnerab|scanner|cve|patch/i, 'vulnerability'],
  [/identity|directory|iam|active directory|okta|sso/i, 'identity'],
  [/ticket|itsm|case management|service ?desk/i, 'case-management'],
  [/email|smtp|chat|messag|notif|slack|teams/i, 'notification'],
  [/feed|ingest|rss|taxii|stix/i, 'ingestion'],
  [/siem|alert|triage/i, 'triage'],
  [/phish/i, 'phishing'],
  [/report|dashboard|chart|graph/i, 'reporting'],
  [/utilit|http|api|python|code/i, 'utility']
];

export function guessUseCases(text: string): string[] {
  const out: string[] = [];
  for (const [re, id] of USE_CASE_HINTS) if (re.test(text) && !out.includes(id)) out.push(id);
  return out.slice(0, 1);
}

type Json = Record<string, unknown>;
const s = (v: unknown) => (typeof v === 'string' ? v : '');

export function fromJson(data: unknown): Prefill | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const d = data as Json;
  if (d.type === 'workflow_collections' && Array.isArray(d.data)) {
    const c = (d.data[0] ?? {}) as Json;
    const pbs = Array.isArray(c.workflows) ? (c.workflows as Json[]) : [];
    const single = pbs.length === 1 ? pbs[0] : null;
    const title = s(single?.name) || s(c.name);
    const summary = s(single?.description) || s(c.description);
    return { kind: 'playbook', title: title.slice(0, 80), summary: summary ? firstSentence(summary) : undefined };
  }
  if (Array.isArray(d.operations)) {
    const text = `${s(d.category)} ${s(d.label)} ${s(d.description)}`;
    return {
      kind: 'connector',
      name: s(d.label) || s(d.name),
      title: (s(d.label) || s(d.name)).slice(0, 80),
      summary: s(d.description) ? firstSentence(s(d.description)) : undefined,
      version: s(d.version) || undefined,
      useCases: guessUseCases(text)
    };
  }
  const md = (d.metadata && typeof d.metadata === 'object' ? d.metadata : {}) as Json;
  if (s(d.name) && s(d.title) && d.metadata) {
    const desc = s(md.description) || s(d.subTitle);
    return {
      kind: 'widget',
      name: s(d.title),
      title: s(d.title).slice(0, 80),
      summary: desc ? firstSentence(desc) : undefined,
      version: s(d.version) || undefined,
      useCases: guessUseCases(`${s(d.title)} ${desc}`)
    };
  }
  return null;
}

/** The `<folder>/info.json` inside a (gzipped) tar, or null. */
export function infoFromTar(tar: Uint8Array): unknown {
  const dec = new TextDecoder();
  const field = (off: number, len: number) => dec.decode(tar.subarray(off, off + len)).replace(/\0.*$/s, '');
  let off = 0;
  let longName = '';
  while (off + 512 <= tar.length) {
    const name = field(off, 100);
    if (!name) break;
    const size = parseInt(field(off + 124, 12).trim() || '0', 8);
    const type = String.fromCharCode(tar[off + 156]);
    const prefix = field(off + 345, 155);
    const body = tar.subarray(off + 512, off + 512 + size);
    const path = longName || (prefix ? `${prefix}/${name}` : name);
    longName = '';
    if (type === 'L') longName = dec.decode(body).replace(/\0.*$/s, '');
    else if (type === 'x') {
      const m = /\d+ path=([^\n]*)\n/.exec(dec.decode(body));
      if (m) longName = m[1];
    } else if ((type === '0' || type === '\0') && /^(\.\/)?[^/]+\/info\.json$/.test(path)) {
      try {
        return JSON.parse(dec.decode(body));
      } catch {
        return null;
      }
    }
    off += 512 + Math.ceil(size / 512) * 512;
  }
  return null;
}

async function gunzip(file: File): Promise<Uint8Array> {
  const stream = file.stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function readListing(file: File): Promise<Prefill | null> {
  const name = file.name.toLowerCase();
  try {
    if (name.endsWith('.json')) return fromJson(JSON.parse(await file.text()));
    if (name.endsWith('.tgz') || name.endsWith('.tar.gz')) {
      if (file.size > 10 * 1024 * 1024) return null;
      return fromJson(infoFromTar(await gunzip(file)));
    }
    if (name.endsWith('.zip')) return { kind: 'solution-pack' };
  } catch {
    return null; // unreadable here; the pipeline gives the real error
  }
  return null;
}

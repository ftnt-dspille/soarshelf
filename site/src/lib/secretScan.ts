// Browser port of pipeline/src/soarshelf/checks/secrets.py, so a contributor sees credentials
// and environment details before anything is uploaded. It must give the same findings as the
// Python scanner: pipeline/tests/fixtures/secret_scan_cases.json (generated from the Python)
// is checked against this file in secretScan.test.ts. The server still runs its own scan and
// is the one that counts; this one only gives early warning.

export type FindingSeverity = 'block' | 'warn';

export interface Finding {
  id: string;
  severity: FindingSeverity;
  title: string;
  detail: string;
  /** Where in the file, e.g. "file.json › data.0.steps.[2].arguments.password". */
  location?: string;
}

const TOKENS: [string, string, RegExp][] = [
  ['private-key', 'Private key', /-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----/],
  ['aws-key', 'AWS access key ID', /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/],
  ['github-token', 'GitHub token', /\bgh[pousr]_[A-Za-z0-9]{36,}\b/],
  ['slack-token', 'Slack token', /\bxox[abprs]-[A-Za-z0-9-]{10,}/],
  ['google-key', 'Google API key', /\bAIza[0-9A-Za-z_-]{35}\b/],
  ['stripe-key', 'Stripe secret key', /\b[sr]k_live_[0-9A-Za-z]{16,}/],
  ['jwt', 'JSON Web Token', /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/],
  ['bearer', 'Bearer token', /\bBearer\s+[A-Za-z0-9._~+/-]{24,}=*/],
  ['url-credentials', 'Credentials in a URL', /[a-z][a-z0-9+.-]*:\/\/[^\s/:@{}]+:(?!\{\{)[^\s/@{}]+@/i]
];

const SECRET_KEY =
  /^(?:.*[_-])?(password|passwd|pwd|passphrase|secret|client[_-]?secret|api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token|token|private[_-]?key|secret[_-]?key)$/i;
const TEMPLATE = /\{\{.*?\}\}|\{%.*?%\}/gs;
const PLACEHOLDER = /^\s*(<[^>]+>|\$\{[^}]+\}|x{3,}|\*{3,}|changeme|your[_ -].*|example.*)\s*$/i;

const IPV4 = /(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(\/\d{1,2})?(?![\d.])/g;
const EMAIL = /\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g;
const INTERNAL_HOST = /\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:local|lan|internal|intranet|intra|corp|home|localdomain|ad)\b/gi;
const EXAMPLE_DOMAINS = /(^|\.)(example\.(com|org|net)|test|invalid|localhost)$/i;

const PUBLIC_RESOLVERS = new Set(['8.8.8.8', '8.8.4.4', '1.1.1.1', '1.0.0.1', '9.9.9.9', '208.67.222.222']);

// [network, prefix length]. Documentation and loopback space is skipped outright.
const DOC_NETS: [string, number][] = [
  ['192.0.2.0', 24],
  ['198.51.100.0', 24],
  ['203.0.113.0', 24],
  ['127.0.0.0', 8],
  ['0.0.0.0', 8]
];
// Python's ipaddress "private" ranges, plus carrier-grade NAT. Everything else is "public".
const NON_GLOBAL: [string, number][] = [
  ['0.0.0.0', 8],
  ['10.0.0.0', 8],
  ['100.64.0.0', 10],
  ['127.0.0.0', 8],
  ['169.254.0.0', 16],
  ['172.16.0.0', 12],
  ['192.0.0.0', 24],
  ['192.0.2.0', 24],
  ['192.168.0.0', 16],
  ['198.18.0.0', 15],
  ['198.51.100.0', 24],
  ['203.0.113.0', 24],
  ['240.0.0.0', 4],
  ['255.255.255.255', 32]
];

const SKIP_KEYS = new Set(['uuid', '@type', '@id', 'stepType', 'triggerStep', 'sourceStep', 'targetStep', 'step_iri', 'workflowReference', 'priority']);

const toInt = (ip: string) => ip.split('.').reduce((n, o) => n * 256 + Number(o), 0);
function inNet(ip: string, [net, bits]: [string, number]): boolean {
  const size = 2 ** (32 - bits);
  const base = Math.floor(toInt(net) / size) * size;
  const n = toInt(ip);
  return n >= base && n < base + size;
}

type Visit = (path: string[], key: string | null, value: string, structural: boolean) => void;

function walk(node: unknown, path: string[], visit: Visit, free = false): void {
  if (Array.isArray(node)) {
    node.forEach((v, i) => {
      if (typeof v === 'string') visit([...path, `[${i}]`], null, v, false);
      else walk(v, [...path, `[${i}]`], visit, free);
    });
  } else if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      const inner = free || k === 'arguments';
      if (typeof v === 'string') visit([...path, k], k, v, SKIP_KEYS.has(k) && !free);
      else walk(v, [...path, k], visit, inner);
    }
  }
}

const chars = (s: string) => Array.from(s);

function entropy(s: string): number {
  const cs = chars(s);
  const counts = new Map<string, number>();
  for (const c of cs) counts.set(c, (counts.get(c) ?? 0) + 1);
  let h = 0;
  for (const n of counts.values()) h -= (n / cs.length) * Math.log2(n / cs.length);
  return h;
}

const CANDIDATE = /[A-Za-z0-9+/_=-]{40,}/g;
const HEXISH = /^[0-9a-fA-F]+$/;

/** Base64 of an embedded image (logos, screenshots): long and random, not a secret. */
function isImage(s: string): boolean {
  if (s.length < 200) return false;
  const head = s.slice(0, 64);
  const clean = head.replace(/[^A-Za-z0-9+/]/g, '');
  let bin: string;
  try {
    bin = atob(clean + '='.repeat((4 - (clean.length % 4)) % 4));
  } catch {
    return false;
  }
  return ['\x89PNG', '\xff\xd8\xff', 'GIF8', '<svg', '<?xml', 'RIFF'].some((m) => bin.startsWith(m));
}

/** A long token with mixed character classes and high entropy. Pure hex is skipped (file hashes). */
function looksRandom(s: string): boolean {
  if (HEXISH.test(s)) return false;
  const classes = [/[a-z]/, /[A-Z]/, /\d/].filter((r) => r.test(s)).length;
  return classes === 3 && entropy(s) > 4.5;
}

function mask(s: string): string {
  const t = s.trim();
  const cs = chars(t);
  if (cs.length <= 8) return '*'.repeat(cs.length);
  return `${cs.slice(0, 4).join('')}…${cs.slice(-2).join('')} (${cs.length} chars)`;
}

/** Scan any JSON value. `where` prefixes each finding's location. */
export function scan(doc: unknown, where = ''): Finding[] {
  const found = new Map<string, Finding>();

  const hit = (id: string, severity: FindingSeverity, title: string, detail: string, path: string[]) => {
    const key = `${id}\u0000${detail}`;
    if (found.has(key)) return;
    const location = [where, path.join('.')].filter(Boolean).join(' › ');
    found.set(key, { id: `secrets.${id}`, severity, title, detail, ...(location ? { location } : {}) });
  };

  walk(doc, [], (path, key, value, structural) => {
    for (const [id, label, rx] of TOKENS) {
      const m = rx.exec(value);
      if (m) hit(id, 'block', `${label} found`, mask(m[0]), path);
    }
    if (structural) return; // heuristics below would flag UUIDs and IRIs

    const literal = value.replace(TEMPLATE, '').trim();
    if (key && SECRET_KEY.test(key) && literal && !PLACEHOLDER.test(literal) && chars(literal).length >= 6) {
      hit('literal-secret', 'block', `Literal value in '${key}'`, `${mask(value)} - reference a connector configuration or a variable instead.`, path);
    }

    for (const m of value.matchAll(CANDIDATE)) {
      if (!value.includes('{{') && looksRandom(m[0]) && !isImage(m[0])) {
        hit('high-entropy', 'warn', 'Possible secret (random-looking string)', mask(m[0]), path);
      }
    }

    for (const m of value.matchAll(IPV4)) {
      const ip = m[1];
      const cidr = m[2];
      if (ip.split('.').some((o) => o.length > 1 && o.startsWith('0'))) continue; // "01.02.03.04": a version, not an address
      if (DOC_NETS.some((n) => inNet(ip, n)) || PUBLIC_RESOLVERS.has(ip)) continue;
      if (cidr) continue; // network ranges in logic are normal
      const global = ip === '192.0.0.9' || ip === '192.0.0.10' || !NON_GLOBAL.some((n) => inNet(ip, n));
      if (global) {
        hit('public-ip', 'warn', 'Public IP address', `${ip} - use 192.0.2.x / 198.51.100.x / 203.0.113.x for examples.`, path);
      } else {
        hit('private-ip', 'warn', 'Internal IP address', ip, path);
      }
    }

    for (const m of value.matchAll(EMAIL)) {
      if (!EXAMPLE_DOMAINS.test(m[1])) hit('email', 'warn', 'Email address', m[0], path);
    }
    for (const m of value.matchAll(INTERNAL_HOST)) hit('internal-host', 'warn', 'Internal hostname', m[0], path);
  });

  return [...found.values()];
}

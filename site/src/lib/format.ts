import type { HubStatus, ItemType, NodeFamily, Severity, Trust } from './types';

export const TYPE_LABEL: Record<ItemType, string> = {
  playbook: 'Playbook',
  'solution-pack': 'Solution pack',
  connector: 'Connector',
  widget: 'Widget'
};

export const HUB_LABEL: Record<HubStatus, string> = {
  complete: 'All on Content Hub',
  'version-mismatch': 'Version differs',
  'needs-custom': 'Needs custom connector'
};

export const HUB_HINT: Record<HubStatus, string> = {
  complete: 'Every connector it uses is available on the Content Hub.',
  'version-mismatch': 'Built against a connector version that differs from the Content Hub.',
  'needs-custom': 'Uses a connector that is not on the Content Hub.'
};

export const TRUST_LABEL: Record<Trust, string> = {
  new: 'New contributor',
  contributor: 'Contributor',
  trusted: 'Trusted',
  maintainer: 'Maintainer'
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  block: 'Blocking',
  warn: 'Review',
  info: 'Info',
  pass: 'Passed'
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

export function plural(n: number, word: string, many = `${word}s`): string {
  return `${n} ${n === 1 ? word : many}`;
}

/** Trigger step labels from the pipeline, in words a visitor understands. */
export const TRIGGER_PLAIN: Record<string, string> = {
  'Manual trigger': 'Run manually',
  'On create': 'When a record is created',
  'On update': 'When a record is updated',
  'On delete': 'When a record is deleted',
  'Pre-create': 'Before a record is created',
  'Pre-update': 'Before a record is updated',
  'Pre-delete': 'Before a record is deleted',
  'API endpoint': 'Called through the API',
  Referenced: 'Called by another playbook',
  'Trigger block': 'Called by another playbook'
};

export const triggerPlain = (t: string) => TRIGGER_PLAIN[t] ?? t;

/** Step colours in words for a colour key (the inspector uses icons.ts FAMILY_LABEL). */
export const FAMILY_KEY: Record<NodeFamily, string> = {
  trigger: 'Trigger',
  connector: 'Connector action',
  decision: 'Decision',
  record: 'Record',
  code: 'Code (always reviewed)',
  human: 'Human input',
  reference: 'Calls a playbook',
  utility: 'Utility',
  end: 'End',
  other: 'Other'
};

/** Connectors every installation ships with; listing them tells a visitor nothing. */
/** Types whose code runs on the platform: listed by manifest, linked to source, never hosted. */
export const CODE_TYPES: ReadonlySet<ItemType> = new Set(['connector', 'widget']);

export const BUILTIN_CONNECTORS = new Set(['code-snippet', 'cyops_utilities']);

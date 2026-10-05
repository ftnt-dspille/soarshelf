import type { HubStatus, ItemType, Severity, Trust } from './types';

export const TYPE_LABEL: Record<ItemType, string> = {
  playbook: 'Playbook',
  'solution-pack': 'Solution pack',
  connector: 'Connector'
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

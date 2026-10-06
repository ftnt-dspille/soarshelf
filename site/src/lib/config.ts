// The one place the site's name and links live. Rename the project here.
export const SITE = {
  name: 'soarshelf',
  tagline: 'Community playbooks, solution packs and connectors for your SOAR platform.',
  description:
    'Browse, inspect and download community-built SOAR playbooks, solution packs and connectors. Every upload is scanned, sanitized and checked against the Content Hub.',
  repo: 'https://github.com/ftnt-dspille/soarshelf',
  get issues() {
    return `${this.repo}/issues`;
  },
  disclaimer:
    'Independent community project. Not affiliated with, endorsed by, or sponsored by Fortinet. Product names are trademarks of their respective owners.'
} as const;

export const LIMITS = {
  playbookBytes: 2 * 1024 * 1024,
  packBytes: 20 * 1024 * 1024,
  packageBytes: 10 * 1024 * 1024
} as const;

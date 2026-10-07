import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { scan } from './secretScan';

// Generated from the Python scanner (pipeline/tests/gen_secret_cases.py). The browser port has to agree.
const cases = JSON.parse(
  readFileSync(new URL('../../../pipeline/tests/fixtures/secret_scan_cases.json', import.meta.url), 'utf8')
) as { name: string; doc: unknown; where: string; expected: Record<string, unknown>[] }[];

describe('secretScan matches the Python scanner', () => {
  for (const c of cases) {
    it(c.name, () => {
      const got = scan(c.doc, c.where).map((f) => ({ ...f, severity: f.severity }));
      expect(got).toEqual(c.expected);
    });
  }
});

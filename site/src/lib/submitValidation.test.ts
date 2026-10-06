import { describe, expect, it } from 'vitest';
import { fileError, normaliseTag, validateDraft, type SubmitDraft } from './submitValidation';

const good: SubmitDraft = {
  title: 'Block malicious IPs',
  summary: 'Blocks IPs that score above the threshold.',
  description: '',
  useCases: ['containment'],
  tags: ['ip', 'block'],
  version: '1.0.0',
  changes: '',
  minVersion: '',
  source: '',
  rightsConfirmed: true
};
const f = (name: string, size: number) => new File([new Uint8Array(size)], name);

describe('validateDraft', () => {
  it('accepts a complete draft', () => {
    expect(validateDraft(good, f('pb.json', 100))).toEqual({});
  });

  it('enforces the SubmissionMeta limits', () => {
    const e = validateDraft(
      { ...good, title: 'abc', summary: 'short', useCases: [], tags: ['Bad Tag'], version: 'v1', minVersion: 'x', source: 'http://x.io', rightsConfirmed: false },
      null
    );
    expect(Object.keys(e).sort()).toEqual(['file', 'minVersion', 'rightsConfirmed', 'source', 'summary', 'tags', 'title', 'useCases', 'version']);
  });

  it('limits use cases to 3 and tags to 8', () => {
    expect(validateDraft({ ...good, useCases: ['a', 'b', 'c', 'd'] }, f('a.json', 1)).useCases).toBeTruthy();
    expect(validateDraft({ ...good, tags: Array.from({ length: 9 }, (_, i) => `t${i}`) }, f('a.json', 1)).tags).toBeTruthy();
  });

  it('caps the description at 5000 characters', () => {
    expect(validateDraft({ ...good, description: 'x'.repeat(5001) }, f('a.json', 1)).description).toBeTruthy();
  });
});

describe('fileError', () => {
  it('checks type and per-type size', () => {
    expect(fileError(f('a.json', 2 * 1024 * 1024))).toBeNull();
    expect(fileError(f('a.json', 2 * 1024 * 1024 + 1))).toMatch(/2 MB/);
    expect(fileError(f('pack.zip', 20 * 1024 * 1024 + 1))).toMatch(/20 MB/);
    expect(fileError(f('evil.exe', 10))).toMatch(/\.json/);
  });
});

describe('normaliseTag', () => {
  it('lowercases and hyphenates', () => {
    expect(normaliseTag('  Threat Intel_Feed! ')).toBe('threat-intel-feed');
  });
});

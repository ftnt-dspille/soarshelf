import { describe, expect, it } from 'vitest';
import { fitWidth, textWidth } from './textfit';

describe('fitWidth', () => {
  it('keeps text that fits', () => {
    expect(fitWidth('Done', 160, 15)).toBe('Done');
  });

  it('cuts by width, not by letter count', () => {
    const narrow = fitWidth('Fill till little list', 120, 15);
    const wide = fitWidth('MMMMMMMMMMMMMMMMMMMM', 120, 15);
    expect(narrow.length).toBeGreaterThan(wide.length);
  });

  it('never exceeds the width it was given', () => {
    for (const s of ['MICROSOFT MANAGEMENT ACTIVITY', 'Normalize Audit Records Fully', 'Ensure Audit Subscription']) {
      const out = fitWidth(s, 164, 11, 0.05);
      expect(textWidth(out, 11, 0.05)).toBeLessThanOrEqual(164);
      expect(out.endsWith('…') || out === s).toBe(true);
    }
  });
});

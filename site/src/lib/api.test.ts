import { describe, expect, it } from 'vitest';
import { friendlyError, loginUrl } from './api';

describe('friendlyError', () => {
  it('maps statuses to actionable messages', () => {
    expect(friendlyError(401, null).message).toMatch(/sign in/i);
    expect(friendlyError(413, null).message).toMatch(/20 MB/);
    expect(friendlyError(429, null).message).toMatch(/limit/i);
    expect(friendlyError(0, null).message).toMatch(/connection/i);
    expect(friendlyError(500, null).message).toMatch(/our side/i);
  });

  it('prefers the server message for 400/403/429', () => {
    expect(friendlyError(403, { error: 'GitHub account must be 30 days old' }).message).toBe('GitHub account must be 30 days old');
  });

  it('carries the existing id for duplicates', () => {
    const e = friendlyError(409, { error: 'dup', id: 'abc123' });
    expect(e.existingId).toBe('abc123');
    expect(e.status).toBe(409);
  });
});

describe('loginUrl', () => {
  it('only allows same-site next paths', () => {
    expect(loginUrl('/submit')).toBe('/api/auth/login?next=%2Fsubmit');
    expect(loginUrl('https://evil.example')).toBe('/api/auth/login?next=%2F');
    expect(loginUrl('//evil.example')).toBe('/api/auth/login?next=%2F');
  });
});

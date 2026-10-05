// Typed client for the upload API (docs/api.md). The Worker is served on the
// site's own origin under /api, so every call is same-origin.
import type { CheckResult } from './types';

export type TrustTier = 'new' | 'contributor' | 'trusted' | 'maintainer';

export interface Me {
  login: string;
  avatarUrl: string;
  trust: TrustTier;
  canUpload: boolean;
  reason: string | null;
  uploadsToday: number;
  dailyLimit: number;
}

export interface SubmissionMeta {
  title: string;
  summary: string;
  description: string;
  useCases: string[];
  tags: string[];
  version: string;
  minVersion: string | null;
  source: string | null;
  rightsConfirmed: true;
}

export type SubmissionStatus = 'checking' | 'rejected' | 'in-review' | 'publishing' | 'published' | 'error';

export interface SubmissionSummary {
  id: string;
  title: string;
  filename: string;
  status: SubmissionStatus;
  createdAt: string;
  updatedAt: string;
  prUrl: string | null;
  slug: string | null;
}

export interface Submission extends SubmissionSummary {
  meta: SubmissionMeta;
  decision: 'publish' | 'review' | 'reject' | null;
  reasons: string[];
  checks: CheckResult[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** For 409: the id of the submission that already has this file. */
    public existingId: string | null = null
  ) {
    super(message);
  }
}

/** Turn an API error response into something a person can act on. */
export function friendlyError(status: number, body: unknown): ApiError {
  const b = (body && typeof body === 'object' ? body : {}) as { error?: unknown; id?: unknown };
  const server = typeof b.error === 'string' && b.error.trim() ? b.error.trim() : null;
  switch (status) {
    case 400:
      return new ApiError(status, server ?? 'Some details need fixing before this can be submitted.');
    case 401:
      return new ApiError(status, 'Your session has expired. Sign in again to continue.');
    case 403:
      return new ApiError(status, server ?? 'Your account can’t upload right now.');
    case 409:
      return new ApiError(status, 'This exact file has already been submitted.', typeof b.id === 'string' ? b.id : null);
    case 413:
      return new ApiError(status, 'The file is too large. Playbooks can be up to 2 MB, solution packs up to 20 MB.');
    case 429:
      return new ApiError(status, server ?? 'You’ve reached today’s upload limit. Try again tomorrow.');
    case 404:
      return new ApiError(status, 'Not found.');
    default:
      return new ApiError(status, status === 0 ? 'Couldn’t reach the server. Check your connection and try again.' : 'Something went wrong on our side. Please try again.');
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { credentials: 'same-origin', ...init, headers: { accept: 'application/json', ...init?.headers } });
  } catch {
    throw friendlyError(0, null);
  }
  const body = res.headers.get('content-type')?.includes('json') ? await res.json().catch(() => null) : null;
  if (!res.ok) throw friendlyError(res.status, body);
  return body as T;
}

/** The signed-in user, or null when signed out or the API isn't reachable. */
export async function getMe(): Promise<Me | null> {
  try {
    const res = await fetch('/api/me', { credentials: 'same-origin', headers: { accept: 'application/json' } });
    if (!res.ok || !res.headers.get('content-type')?.includes('json')) return null;
    return (await res.json()) as Me;
  } catch {
    return null;
  }
}

export function loginUrl(next: string): string {
  // Same-site paths only: "//host" would be protocol-relative.
  return `/api/auth/login?next=${encodeURIComponent(/^\/(?![/\\])/.test(next) ? next : '/')}`;
}

export const logout = () => call<unknown>('/api/auth/logout', { method: 'POST' }).catch(() => null);
export const listSubmissions = () => call<SubmissionSummary[]>('/api/submissions');
export const getSubmission = (id: string) => call<Submission>(`/api/submissions/${encodeURIComponent(id)}`);
export const reportItem = (slug: string, reason: string) =>
  call<unknown>('/api/reports', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ slug, reason }) });

/** Upload with progress. XHR because fetch has no upload progress events. */
export function createSubmission(
  file: File,
  meta: SubmissionMeta,
  turnstile: string,
  onProgress?: (fraction: number) => void
): Promise<{ id: string }> {
  const form = new FormData();
  form.append('file', file, file.name);
  form.append('meta', JSON.stringify(meta));
  form.append('turnstile', turnstile);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/submissions');
    xhr.withCredentials = true;
    xhr.setRequestHeader('accept', 'application/json');
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onerror = () => reject(friendlyError(0, null));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300 && body && typeof (body as { id?: unknown }).id === 'string') {
        resolve(body as { id: string });
      } else {
        reject(friendlyError(xhr.status, body));
      }
    };
    xhr.send(form);
  });
}

export const STATUS_LABEL: Record<SubmissionStatus, string> = {
  checking: 'Checking',
  rejected: 'Rejected',
  'in-review': 'In review',
  publishing: 'Publishing',
  published: 'Published',
  error: 'Error'
};

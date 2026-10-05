// Client-side mirror of the SubmissionMeta limits in docs/api.md. The Worker
// re-validates everything; this only gives fast, specific feedback.
import { LIMITS } from './config';

export interface SubmitDraft {
  title: string;
  summary: string;
  description: string;
  useCases: string[];
  tags: string[];
  version: string;
  minVersion: string;
  source: string;
  rightsConfirmed: boolean;
}

export type FieldErrors = Partial<Record<keyof SubmitDraft | 'file', string>>;

export const TAG_RE = /^[a-z0-9-]{2,24}$/;
const VERSION_RE = /^\d+(\.\d+){0,3}([-+][0-9A-Za-z.-]+)?$/;

export function fileError(file: File | null): string | null {
  if (!file) return 'Choose a file to upload.';
  const name = file.name.toLowerCase();
  if (name.endsWith('.json')) {
    return file.size > LIMITS.playbookBytes ? 'Playbook files can be up to 2 MB.' : null;
  }
  if (name.endsWith('.zip')) {
    return file.size > LIMITS.packBytes ? 'Solution packs can be up to 20 MB.' : null;
  }
  return 'Upload a playbook export (.json) or a solution pack (.zip).';
}

export function validateDraft(d: SubmitDraft, file: File | null): FieldErrors {
  const e: FieldErrors = {};
  const fe = fileError(file);
  if (fe) e.file = fe;

  const title = d.title.trim();
  if (title.length < 4 || title.length > 80) e.title = 'Use 4 to 80 characters.';

  const summary = d.summary.trim();
  if (summary.length < 10 || summary.length > 160) e.summary = 'Use 10 to 160 characters.';

  if (d.description.length > 5000) e.description = 'Keep the description under 5,000 characters.';

  if (d.useCases.length < 1 || d.useCases.length > 3) e.useCases = 'Pick 1 to 3 use cases.';

  if (d.tags.length > 8) e.tags = 'Use at most 8 tags.';
  else if (d.tags.some((t) => !TAG_RE.test(t))) e.tags = 'Tags use a-z, 0-9 and hyphens, 2 to 24 characters.';

  if (!VERSION_RE.test(d.version.trim())) e.version = 'Use a version like 1.0.0.';
  if (d.minVersion.trim() && !VERSION_RE.test(d.minVersion.trim())) e.minVersion = 'Use a version like 7.4.0, or leave it empty.';

  const src = d.source.trim();
  if (src) {
    let ok = false;
    try {
      ok = new URL(src).protocol === 'https:';
    } catch {
      ok = false;
    }
    if (!ok) e.source = 'Use a full https:// link.';
  }

  if (!d.rightsConfirmed) e.rightsConfirmed = 'Confirm you have the right to share this.';
  return e;
}

/** Normalise a typed tag: lowercase, spaces/underscores to hyphens. */
export function normaliseTag(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

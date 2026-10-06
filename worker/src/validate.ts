/**
 * Cheap checks at the door. The full checks run in the pipeline; these just
 * keep obvious junk out of quarantine and give the uploader instant feedback.
 */

export const MAX_JSON = 2 * 1024 * 1024;
export const MAX_ZIP = 20 * 1024 * 1024;

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

type Result<T> = { ok: true; value: T } | { ok: false; error: string };

const str = (v: unknown) => (typeof v === 'string' ? v.trim() : '');

export function validateMeta(raw: unknown): Result<SubmissionMeta> {
  if (!raw || typeof raw !== 'object') return { ok: false, error: 'Missing listing details' };
  const m = raw as Record<string, unknown>;
  const title = str(m.title);
  const summary = str(m.summary);
  const description = str(m.description);
  const version = str(m.version) || '1.0.0';
  const minVersion = str(m.minVersion) || null;
  const source = str(m.source) || null;
  const useCases = Array.isArray(m.useCases) ? m.useCases.map(str) : [];
  const tags = Array.isArray(m.tags) ? m.tags.map((t) => str(t).toLowerCase()) : [];

  if (title.length < 4 || title.length > 80) return { ok: false, error: 'Title must be 4-80 characters' };
  if (summary.length < 10 || summary.length > 160) return { ok: false, error: 'Summary must be 10-160 characters' };
  if (description.length > 5000) return { ok: false, error: 'Description is longer than 5000 characters' };
  if (useCases.length < 1 || useCases.length > 3 || !useCases.every((u) => /^[a-z][a-z-]{1,30}$/.test(u)))
    return { ok: false, error: 'Pick 1-3 use cases' };
  if (tags.length > 8 || !tags.every((t) => /^[a-z0-9-]{2,24}$/.test(t)))
    return { ok: false, error: 'Up to 8 tags: lowercase letters, digits and dashes' };
  if (!/^\d+(\.\d+){0,3}([-+][\w.]+)?$/.test(version)) return { ok: false, error: 'Version must look like 1.0.0' };
  if (minVersion && !/^\d+(\.\d+){0,3}$/.test(minVersion))
    return { ok: false, error: 'Minimum platform version must look like 7.4.0' };
  if (source && (!/^https:\/\/[^\s]+$/.test(source) || source.length > 300))
    return { ok: false, error: 'Source must be an https URL' };
  if (m.rightsConfirmed !== true) return { ok: false, error: 'Confirm you have the right to share this' };

  return {
    ok: true,
    value: { title, summary, description, useCases, tags, version, minVersion, source, rightsConfirmed: true }
  };
}

export type FileKind = 'json' | 'zip';

/** Extension, size and magic bytes; JSON must at least parse. */
export function checkFile(name: string, bytes: ArrayBuffer): Result<FileKind> {
  const lower = name.toLowerCase();
  const u8 = new Uint8Array(bytes);
  if (lower.endsWith('.json')) {
    if (bytes.byteLength > MAX_JSON) return { ok: false, error: 'Playbook files can be up to 2 MB' };
    try {
      JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(u8));
    } catch {
      return { ok: false, error: 'This file is not valid JSON' };
    }
    return { ok: true, value: 'json' };
  }
  if (lower.endsWith('.zip')) {
    if (bytes.byteLength > MAX_ZIP) return { ok: false, error: 'Solution packs can be up to 20 MB' };
    if (!(u8[0] === 0x50 && u8[1] === 0x4b && u8[2] === 0x03 && u8[3] === 0x04))
      return { ok: false, error: 'This file is not a zip archive' };
    return { ok: true, value: 'zip' };
  }
  return { ok: false, error: 'Upload a playbook export or a connector/widget manifest (.json), or a solution pack (.zip)' };
}

/** Stored filename: keep it boring. */
export function cleanFilename(name: string): string {
  const base = name.split(/[\\/]/).pop() ?? 'upload';
  return base.replace(/[^\w.\-]+/g, '_').slice(0, 100) || 'upload';
}

// Read the files inside an upload in the browser: a gzipped tar (connector/widget) or a zip
// (solution pack). Only what the pre-flight scan needs: names and bytes, with size limits.
// Nothing here is trusted; the pipeline re-reads the real upload.

export interface Entry {
  path: string;
  data: Uint8Array;
}

export const MAX_ENTRY = 5 * 1024 * 1024;
export const MAX_ENTRIES = 2000;

const dec = new TextDecoder();

/** Regular files in an (already gunzipped) tar. */
export function tarEntries(tar: Uint8Array): Entry[] {
  const field = (off: number, len: number) => dec.decode(tar.subarray(off, off + len)).replace(/\0.*$/s, '');
  const out: Entry[] = [];
  let off = 0;
  let longName = '';
  while (off + 512 <= tar.length && out.length < MAX_ENTRIES) {
    const name = field(off, 100);
    if (!name) break;
    const size = parseInt(field(off + 124, 12).trim() || '0', 8);
    const type = String.fromCharCode(tar[off + 156]);
    const prefix = field(off + 345, 155);
    const body = tar.subarray(off + 512, off + 512 + size);
    const path = longName || (prefix ? `${prefix}/${name}` : name);
    longName = '';
    if (type === 'L') longName = dec.decode(body).replace(/\0.*$/s, '');
    else if (type === 'x') {
      const m = /\d+ path=([^\n]*)\n/.exec(dec.decode(body));
      if (m) longName = m[1];
    } else if ((type === '0' || type === '\0') && size <= MAX_ENTRY) out.push({ path: path.replace(/^\.\//, ''), data: body });
    off += 512 + Math.ceil(size / 512) * 512;
  }
  return out;
}

/** Inflate, giving up past MAX_ENTRY so a small file can't expand into a huge one. */
async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const reader = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
  const parts: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > MAX_ENTRY) {
      await reader.cancel();
      throw new Error('entry too large');
    }
    parts.push(value);
  }
  const out = new Uint8Array(total);
  let off = 0;
  for (const part of parts) {
    out.set(part, off);
    off += part.length;
  }
  return out;
}

/** Files in a zip (stored or deflated), read from the central directory. Skips what it can't read. */
export async function zipEntries(zip: Uint8Array): Promise<Entry[]> {
  const v = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
  let eocd = -1;
  for (let i = zip.length - 22; i >= Math.max(0, zip.length - 65557); i--) {
    if (v.getUint32(i, true) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) return [];
  const count = v.getUint16(eocd + 10, true);
  let p = v.getUint32(eocd + 16, true);
  const out: Entry[] = [];
  for (let n = 0; n < count && n < MAX_ENTRIES * 2; n++) {
    if (p + 46 > zip.length || v.getUint32(p, true) !== 0x02014b50) break;
    const method = v.getUint16(p + 10, true);
    const csize = v.getUint32(p + 20, true);
    const usize = v.getUint32(p + 24, true);
    const nameLen = v.getUint16(p + 28, true);
    const extraLen = v.getUint16(p + 30, true);
    const commentLen = v.getUint16(p + 32, true);
    const local = v.getUint32(p + 42, true);
    const path = dec.decode(zip.subarray(p + 46, p + 46 + nameLen));
    p += 46 + nameLen + extraLen + commentLen;
    if (path.endsWith('/') || usize > MAX_ENTRY || local + 30 > zip.length) continue;
    const start = local + 30 + v.getUint16(local + 26, true) + v.getUint16(local + 28, true);
    const raw = zip.subarray(start, start + csize);
    try {
      out.push({ path, data: method === 0 ? raw : method === 8 ? await inflateRaw(raw) : new Uint8Array() });
    } catch {
      /* unreadable entry: the pipeline reports it properly */
    }
    if (out.length >= MAX_ENTRIES) break;
  }
  return out;
}

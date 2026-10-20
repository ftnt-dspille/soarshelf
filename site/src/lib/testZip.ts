// Test helper: a minimal deflated zip, enough for archive.ts to read.
import { deflateRawSync, gzipSync } from 'node:zlib';

const enc = new TextEncoder();

export function zip(files: Record<string, string>): Uint8Array {
  const parts: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let off = 0;
  for (const [name, text] of Object.entries(files)) {
    const raw = enc.encode(text);
    const comp = deflateRawSync(raw);
    const n = enc.encode(name);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(8, 8, true);
    local.setUint32(18, comp.length, true);
    local.setUint32(22, raw.length, true);
    local.setUint16(26, n.length, true);
    parts.push(new Uint8Array(local.buffer), n, comp);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true);
    c.setUint16(10, 8, true);
    c.setUint32(20, comp.length, true);
    c.setUint32(24, raw.length, true);
    c.setUint16(28, n.length, true);
    c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), n);
    off += 30 + n.length + comp.length;
  }
  const cdSize = central.reduce((a, b) => a + b.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(10, Object.keys(files).length, true);
  end.setUint32(12, cdSize, true);
  end.setUint32(16, off, true);
  return Buffer.concat([...parts, ...central, new Uint8Array(end.buffer)]);
}

/** A minimal gzipped tar: ustar headers (name ≤ 100 chars), 512-byte blocks, two zero blocks. */
export function tgz(files: Record<string, string>): Uint8Array {
  const blocks: Uint8Array[] = [];
  for (const [name, text] of Object.entries(files)) {
    const data = enc.encode(text);
    const header = new Uint8Array(512);
    const write = (off: number, s: string, len: number) => {
      const b = enc.encode(s);
      header.set(b.subarray(0, Math.min(b.length, len)), off);
    };
    write(0, name, 100);
    write(100, '0000644\0', 8);
    write(108, '0000000\0', 8);
    write(116, '0000000\0', 8);
    write(124, data.length.toString(8).padStart(11, '0') + '\0', 12);
    write(136, '00000000000\0', 12);
    for (let i = 148; i < 156; i++) header[i] = 0x20;
    header[156] = 0x30; // typeflag '0' (regular file)
    write(257, 'ustar\0', 6);
    write(263, '00', 2);
    let sum = 0;
    for (const b of header) sum += b;
    write(148, sum.toString(8).padStart(6, '0') + '\0 ', 8);
    blocks.push(header);
    blocks.push(data);
    const pad = (512 - (data.length % 512)) % 512;
    if (pad) blocks.push(new Uint8Array(pad));
  }
  blocks.push(new Uint8Array(1024));
  const tar = Buffer.concat(blocks);
  return new Uint8Array(gzipSync(tar));
}

// Check a file for credentials and environment details in the browser, before it is uploaded.
// The server runs its own scan on every submission; this one only gives early warning, using
// a port of the same rules (see secretScan.ts).
import { tarEntries, zipEntries, type Entry } from './archive';
import { scan, type Finding } from './secretScan';

export interface PreflightResult {
  findings: Finding[];
  /** How many files were looked at. */
  files: number;
  /** Set when the file couldn't be checked here; the server still checks it. */
  skipped?: string;
}

const MAX_FILE = 25 * 1024 * 1024;

// Same stripping the pipeline does before it scans: these only describe the exporting box.
const WORKFLOW_DROP = ['@context', '@id', 'owners', 'versions', 'lastModifyDate', 'createDate', 'createUser', 'modifyDate', 'modifyUser', 'deletedAt', 'collection', 'playbookOrigin', 'id'];
const COLLECTION_DROP = ['@context', '@id', 'id', 'createDate', 'createUser', 'modifyDate', 'modifyUser', 'deletedAt'];

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);

/** Remove what the pipeline would strip anyway, so it isn't reported as the contributor's problem. */
export function withoutEnvironmentOnly(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(withoutEnvironmentOnly);
  if (!isObj(node)) return node;
  const out: Obj = {};
  const isWorkflow = Array.isArray(node.steps);
  const isCollection = Array.isArray(node.workflows) || node['@type'] === 'WorkflowCollection';
  for (const [k, v] of Object.entries(node)) {
    if ((isWorkflow && WORKFLOW_DROP.includes(k)) || (isCollection && COLLECTION_DROP.includes(k))) continue;
    out[k] = withoutEnvironmentOnly(v);
  }
  if (isObj(out.arguments)) {
    delete out.arguments.mock_result;
    if (typeof out.arguments.config === 'string') out.arguments.config = '';
  }
  return out;
}

const TEXT_SUFFIXES = ['.py', '.json', '.md', '.txt', '.rst', '.html', '.htm', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.css', '.scss', '.less', '.yaml', '.yml', '.cfg', '.ini', '.toml', '.csv', '.xml', '.svg', '.j2', '.jinja', '.sh', '.map'];
const TEXT_NAMES = ['license', 'licence', 'readme', 'notice', 'changelog', 'requirements', 'makefile'];
const JUNK_DIRS = ['__pycache__', '.git', '.idea', '.vscode', 'node_modules', '.pytest_cache'];

const baseName = (p: string) => p.slice(p.lastIndexOf('/') + 1).toLowerCase();
const isJunk = (path: string) => {
  const parts = path.toLowerCase().split('/');
  const last = parts[parts.length - 1];
  return parts.slice(0, -1).some((p) => JUNK_DIRS.includes(p) || p.startsWith('.')) || last.startsWith('.') || last === 'thumbs.db' || last.endsWith('.pyc');
};
const isText = (path: string) => {
  const b = baseName(path);
  return TEXT_SUFFIXES.some((s) => b.endsWith(s)) || b.split('.').some((part) => TEXT_NAMES.includes(part.split('-')[0]));
};
const isVendored = (path: string) => baseName(path).includes('.min.') || `/${path.toLowerCase()}`.includes('/vendor/') || `/${path.toLowerCase()}`.includes('/lib/');

const decode = (b: Uint8Array) => new TextDecoder('utf-8').decode(b);

function parseJson(data: Uint8Array): unknown | undefined {
  try {
    return JSON.parse(decode(data));
  } catch {
    return undefined;
  }
}

async function gunzip(file: File): Promise<Uint8Array> {
  const stream = file.stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function scanPackage(entries: Entry[]): Finding[] {
  const out: Finding[] = [];
  for (const { path, data } of entries) {
    if (isJunk(path) || !isText(path)) continue;
    const parts = path.split('/');
    if (parts.length === 2 && parts[1] === 'info.json') {
      const doc = parseJson(data);
      out.push(...scan(doc ?? {}, 'info.json'));
      continue;
    }
    let found = scan({ [path]: decode(data) });
    // Bundled libraries are full of long strings and sample addresses; only hard hits count there.
    if (isVendored(path) || !(path.endsWith('.py') || path.endsWith('.json'))) {
      found = found.filter((f) => f.severity === 'block' || f.id !== 'secrets.high-entropy');
    }
    out.push(...found);
  }
  return out;
}

export async function preflight(file: File): Promise<PreflightResult> {
  const name = file.name.toLowerCase();
  if (file.size > MAX_FILE) return { findings: [], files: 0, skipped: 'This file is too large to check here. It is still checked after you submit.' };
  try {
    if (name.endsWith('.json')) {
      const doc = parseJson(new Uint8Array(await file.arrayBuffer()));
      if (doc === undefined) return { findings: [], files: 0, skipped: 'This isn’t valid JSON, so there is nothing to check yet.' };
      return { findings: scan(withoutEnvironmentOnly(doc)), files: 1 };
    }
    if (name.endsWith('.zip')) {
      const entries = await zipEntries(new Uint8Array(await file.arrayBuffer()));
      const findings: Finding[] = [];
      let files = 0;
      for (const e of entries) {
        if (!e.path.toLowerCase().endsWith('.json') || isJunk(e.path)) continue;
        const doc = parseJson(e.data);
        if (doc === undefined) continue;
        files++;
        findings.push(...scan(withoutEnvironmentOnly(doc), e.path));
      }
      return { findings, files };
    }
    if (name.endsWith('.tgz') || name.endsWith('.tar.gz')) {
      const entries = tarEntries(await gunzip(file));
      const findings = scanPackage(entries);
      return { findings, files: entries.filter((e) => !isJunk(e.path) && isText(e.path)).length };
    }
  } catch {
    return { findings: [], files: 0, skipped: 'Couldn’t read this file here. It is still checked after you submit.' };
  }
  return { findings: [], files: 0, skipped: 'Unsupported file type.' };
}

/** A stable key for "ignore this one": the same finding in the same place. */
export const findingKey = (f: Finding) => `${f.id}|${f.detail}|${f.location ?? ''}`;

// One playbook from an item's download, in the playbook designer's clipboard format,
// so it can be pasted straight onto a designer canvas.
//
// The designer copies selected steps as {steps, groups, routes} JSON in text/plain.
// Each step carries its full step type (name, parent chain, icon) where an export only
// has the type's IRI, and each route carries its two steps as objects. On paste the
// designer gives everything new UUIDs and rewires routes and Decision / Manual Input
// branches, so the export's UUIDs can stay. The designer's own copy leaves out the
// trigger step; we keep it, and paste makes it the trigger of a playbook that has none
// (one that already has a trigger drops it with a warning).

import { zipEntries } from './archive';

type Obj = Record<string, unknown>;
type StepTypes = Record<string, Obj>;

const STEP_IRI = '/api/3/workflow_steps/';
const ROUTE_IRI = '/api/3/workflow_routes/';

const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const clone = <T>(v: T): T => structuredClone(v);
const tail = (iri: unknown) => (typeof iri === 'string' ? iri.slice(iri.lastIndexOf('/') + 1) : '');

/** The playbook with this uuid inside a download: a playbook export (.json) or a solution pack (.zip). */
export async function findWorkflow(bytes: Uint8Array, filename: string, uuid: string): Promise<Obj | null> {
  const parse = (b: Uint8Array): unknown => {
    try {
      return JSON.parse(new TextDecoder().decode(b));
    } catch {
      return null;
    }
  };
  if (filename.toLowerCase().endsWith('.zip')) {
    for (const e of await zipEntries(bytes)) {
      // playbooks/<collection>/<playbook>.json; files directly in playbooks/ are pack-level (tags.json).
      const parts = e.path.split('/');
      const name = parts.at(-1) ?? '';
      if (!parts.slice(0, -2).includes('playbooks') || parts.at(-2) === 'playbooks') continue;
      if (!name.endsWith('.json') || name === 'collection.metadata.json') continue;
      const w = parse(e.data);
      if (isObj(w) && w.uuid === uuid) return w;
    }
    return null;
  }
  const doc = parse(bytes);
  const collections = isObj(doc) && Array.isArray(doc.data) ? doc.data : [];
  for (const c of collections)
    for (const w of isObj(c) && Array.isArray(c.workflows) ? c.workflows : [])
      if (isObj(w) && w.uuid === uuid) return w;
  return null;
}

/** The clipboard document for one exported playbook, or null when the designer
 * couldn't paste it (an unknown step type, or a route to a missing step). */
export function toClipboard(workflow: Obj, types: StepTypes): Obj | null {
  const steps: Obj[] = [];
  const plain = new Map<string, Obj>();
  for (const raw of Array.isArray(workflow.steps) ? workflow.steps : []) {
    const type = isObj(raw) && typeof raw.stepType === 'string' ? types[raw.stepType] : undefined;
    if (!isObj(raw) || !type || typeof raw.uuid !== 'string') return null;
    const s: Obj = { '@id': STEP_IRI + raw.uuid, ...clone(raw), stepType: clone(type) };
    plain.set(raw.uuid, clone(s));
    s.parentTop = Math.trunc(Number(s.top) || 0);
    s.parentLeft = Math.trunc(Number(s.left) || 0);
    steps.push(s);
  }
  if (!steps.length) return null;

  // The designer refuses a second connection between the same two steps ("Duplicate
  // routes are not allowed") and stops adding routes there, so keep one per pair,
  // preferring a labelled branch over a plain one. An API import accepts both.
  const routes = new Map<string, Obj>();
  for (const raw of Array.isArray(workflow.routes) ? workflow.routes : []) {
    if (!isObj(raw)) return null;
    const src = plain.get(tail(raw.sourceStep));
    const dst = plain.get(tail(raw.targetStep));
    if (!src || !dst) return null;
    const key = `${src.uuid}>${dst.uuid}`;
    if (routes.has(key) && (routes.get(key)!.label || !raw.label)) continue;
    routes.set(key, { '@id': ROUTE_IRI + String(raw.uuid), ...clone(raw), sourceStep: clone(src), targetStep: clone(dst) });
  }
  return { steps, groups: clone(Array.isArray(workflow.groups) ? workflow.groups : []), routes: [...routes.values()] };
}

/** Clipboard text for one playbook of an item: fetches the item's download and the
 * step type table (both only when asked) and converts. */
export async function clipboardText(download: { path: string; filename: string }, uuid: string): Promise<string> {
  const [res, types] = await Promise.all([
    fetch(download.path),
    import('./stepTypes.json').then((m) => m.default as unknown as StepTypes)
  ]);
  if (!res.ok) throw new Error(`download ${res.status}`);
  const w = await findWorkflow(new Uint8Array(await res.arrayBuffer()), download.filename, uuid);
  const doc = w && toClipboard(w, types);
  if (!doc) throw new Error('this playbook can’t be converted');
  return JSON.stringify(doc);
}

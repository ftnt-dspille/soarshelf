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
//
// Steps can take the viewer's layout instead of the export's own coordinates, which
// are often a staircase or a pile; the viewer's step size is close to the designer's.

import { tgzEntries, zipEntries } from './archive';

type Obj = Record<string, unknown>;
type StepTypes = Record<string, Obj>;
type Rect = { x: number; y: number; w?: number; h?: number };
/** Where to put things: step uuid -> point, group uuid -> rect (notes and blocks). */
export type Placement = { steps: Map<string, Rect>; groups: Map<string, Rect> };

const STEP_IRI = '/api/3/workflow_steps/';
const ROUTE_IRI = '/api/3/workflow_routes/';

const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const clone = <T>(v: T): T => structuredClone(v);
const tail = (iri: unknown) => (typeof iri === 'string' ? iri.slice(iri.lastIndexOf('/') + 1) : '');

/** The playbook with this uuid inside a download: a playbook export (.json), a solution pack
 * (.zip), or a connector/widget pack (.tgz / .tar.gz). */
export async function findWorkflow(bytes: Uint8Array, filename: string, uuid: string): Promise<Obj | null> {
  const parse = (b: Uint8Array): unknown => {
    try {
      return JSON.parse(new TextDecoder().decode(b));
    } catch {
      return null;
    }
  };
  // Exactly one match, or nothing: two playbooks claiming one uuid means we can't
  // be sure the copy is the one the viewer showed.
  const only = (found: Obj[]) => (found.length === 1 ? found[0] : null);
  const name = filename.toLowerCase();
  const inCollections = (doc: unknown): Obj[] => {
    const collections = isObj(doc) && Array.isArray(doc.data) ? doc.data : [];
    const found: Obj[] = [];
    for (const c of collections)
      for (const w of isObj(c) && Array.isArray(c.workflows) ? c.workflows : [])
        if (isObj(w) && w.uuid === uuid) found.push(w);
    return found;
  };
  if (name.endsWith('.zip')) {
    // The pipeline's rule (process.py _pack): under the folder holding info.json,
    // playbooks/**.json with @type Workflow. Only those were sanitized and graphed.
    const entries = await zipEntries(bytes);
    const info = entries.find((e) => e.path.split('/').at(-1) === 'info.json' && e.path.split('/').length <= 2);
    if (!info) return null;
    const root = info.path.slice(0, -'info.json'.length);
    const found: Obj[] = [];
    for (const e of entries) {
      if (!e.path.startsWith(root + 'playbooks/') || !e.path.endsWith('.json')) continue;
      const w = parse(e.data);
      if (isObj(w) && w['@type'] === 'Workflow' && w.uuid === uuid) found.push(w);
    }
    return only(found);
  }
  if (name.endsWith('.tgz') || name.endsWith('.tar.gz')) {
    // Connector / widget pack: info.json at the pack root, workflows in one collection
    // file under playbooks/ (playbooks.json), same shape as a playbook export.
    const entries = await tgzEntries(bytes);
    const info = entries.find((e) => e.path.split('/').at(-1) === 'info.json' && e.path.split('/').length <= 2);
    if (!info) return null;
    const root = info.path.slice(0, -'info.json'.length);
    const found: Obj[] = [];
    for (const e of entries) {
      if (!e.path.startsWith(root + 'playbooks/') || !e.path.endsWith('.json')) continue;
      found.push(...inCollections(parse(e.data)));
    }
    return only(found);
  }
  return only(inCollections(parse(bytes)));
}

const MARGIN = 40;

/** The workflow's steps and groups moved to `place`, with the top-left item at the
 * margin. Null when it doesn't cover them all: then the export's own layout stays. */
function relaid(workflow: Obj, place: Placement): { steps: Map<string, Rect>; groups: Map<string, Rect> } | null {
  const steps = Array.isArray(workflow.steps) ? workflow.steps.filter(isObj) : [];
  const groups = Array.isArray(workflow.groups) ? workflow.groups.filter(isObj) : [];
  if (!steps.length || steps.some((s) => !place.steps.has(String(s.uuid)))) return null;
  // A block holds its steps; one the viewer didn't draw can't be rebuilt around them.
  const blocks = new Set(groups.filter((g) => g.type !== 'note').map((g) => String(g.uuid)));
  if (steps.some((s) => s.group && blocks.has(tail(s.group)) && !place.groups.has(tail(s.group)))) return null;
  const all = [...place.steps.entries(), ...place.groups.entries()];
  const dx = MARGIN - Math.min(...all.map(([, r]) => r.x));
  const dy = MARGIN - Math.min(...all.map(([, r]) => r.y));
  const move = (r: Rect) => ({ ...r, x: Math.round(r.x + dx), y: Math.round(r.y + dy) });
  return {
    steps: new Map([...place.steps].map(([k, r]) => [k, move(r)])),
    groups: new Map([...place.groups].map(([k, r]) => [k, move(r)]))
  };
}

/** The clipboard document for one exported playbook, or null when the designer
 * couldn't paste it (an unknown step type, or a route to a missing step). With
 * `place`, steps and notes take those positions instead of the export's. */
export function toClipboard(workflow: Obj, types: StepTypes, place?: Placement): Obj | null {
  const at = place ? relaid(workflow, place) : null;
  const groups: Obj[] = clone(Array.isArray(workflow.groups) ? workflow.groups.filter(isObj) : []);
  for (const g of groups) {
    const r = at?.groups.get(String(g.uuid));
    if (!r) continue;
    Object.assign(g, { left: String(r.x), top: String(r.y) });
    if (r.w) g.width = String(r.w);
    if (r.h) g.height = String(r.h);
  }
  const steps: Obj[] = [];
  const plain = new Map<string, Obj>();
  for (const raw of Array.isArray(workflow.steps) ? workflow.steps : []) {
    const type = isObj(raw) && typeof raw.stepType === 'string' ? types[raw.stepType] : undefined;
    if (!isObj(raw) || !type || typeof raw.uuid !== 'string') return null;
    const s: Obj = { '@id': STEP_IRI + raw.uuid, ...clone(raw), stepType: clone(type) };
    const p = at?.steps.get(raw.uuid);
    if (p) {
      // Inside a block, a step is positioned relative to the block.
      const b = typeof raw.group === 'string' ? at!.groups.get(tail(raw.group)) : undefined;
      s.left = String(p.x - (b?.x ?? 0));
      s.top = String(p.y - (b?.y ?? 0));
    }
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
  return { steps, groups, routes: [...routes.values()] };
}

/** Clipboard text for one playbook of an item: fetches the item's download and the
 * step type table (both only when asked) and converts. */
export async function clipboardText(download: { path: string; filename: string }, uuid: string, place?: Placement): Promise<string> {
  const [res, types] = await Promise.all([
    fetch(download.path),
    import('./stepTypes.json').then((m) => m.default as unknown as StepTypes)
  ]);
  if (!res.ok) throw new Error(`download ${res.status}`);
  const w = await findWorkflow(new Uint8Array(await res.arrayBuffer()), download.filename, uuid);
  const doc = w && toClipboard(w, types, place);
  if (!doc) throw new Error('this playbook can’t be converted');
  return JSON.stringify(doc);
}

import { describe, expect, it } from 'vitest';
import { findWorkflow, toClipboard } from './clipboard';
import stepTypes from './stepTypes.json';
import { tgz, zip } from './testZip';

const types = stepTypes as unknown as Record<string, Record<string, unknown>>;
const enc = new TextEncoder();
const T = {
  trigger: '/api/3/workflow_step_types/b348f017-9a94-471f-87f8-ce88b6a7ad62',
  setVar: '/api/3/workflow_step_types/04d0cf46-b6a8-42c4-8683-60a7eaa69e8f',
  decision: '/api/3/workflow_step_types/12254cf5-5db7-4b1a-8cb1-3af081924b28'
};
const step = (uuid: string, stepType: string, args: object = {}) => ({
  '@type': 'WorkflowStep', name: uuid, arguments: args, top: '120', left: '200.5', stepType, group: null, uuid
});
const route = (uuid: string, from: string, to: string, label: string | null = null) => ({
  '@type': 'WorkflowRoute', name: `${from} -> ${to}`, label, uuid,
  sourceStep: `/api/3/workflow_steps/${from}`, targetStep: `/api/3/workflow_steps/${to}`
});
const workflow = {
  name: 'Route', uuid: 'wf-1',
  steps: [
    step('start', T.trigger),
    step('branch', T.decision, { conditions: [{ option: 'hi', step_iri: '/api/3/workflow_steps/hi' }] }),
    step('hi', T.setVar)
  ],
  routes: [route('r1', 'start', 'branch'), route('r2', 'branch', 'hi', 'hi')],
  groups: []
};

describe('toClipboard', () => {
  it('builds the designer clipboard shape, trigger included', () => {
    const doc = toClipboard(workflow, types)!;
    const steps = doc.steps as Record<string, any>[];
    expect(steps.map((s) => s.uuid)).toEqual(['start', 'branch', 'hi']);
    expect(steps[0]['@id']).toBe('/api/3/workflow_steps/start');
    expect(steps[0].stepType.name).toBe('cybersponse.abstract_trigger');
    expect(steps[1].stepType.parent.name).toBe('RunScript');
    expect(steps[1]).toMatchObject({ parentTop: 120, parentLeft: 200, top: '120' });
    // branch targets stay as the export's IRIs; the designer rewires them on paste
    expect(steps[1].arguments.conditions[0].step_iri).toBe('/api/3/workflow_steps/hi');

    const routes = doc.routes as Record<string, any>[];
    expect(routes[1]['@id']).toBe('/api/3/workflow_routes/r2');
    expect(routes[1].sourceStep.uuid).toBe('branch');
    expect(routes[1].targetStep.stepType.name).toBe('SetVariable');
    expect(routes[1].sourceStep).not.toHaveProperty('parentTop');
    expect(doc.groups).toEqual([]);
  });

  it('keeps one route per pair of steps, preferring the labelled one', () => {
    const doc = toClipboard({ ...workflow, routes: [...workflow.routes, route('r3', 'branch', 'hi')] }, types)!;
    const routes = doc.routes as Record<string, any>[];
    expect(routes.map((r) => r.uuid)).toEqual(['r1', 'r2']);
    const flipped = toClipboard({ ...workflow, routes: [route('r0', 'branch', 'hi'), ...workflow.routes] }, types)!;
    expect((flipped.routes as Record<string, any>[]).map((r) => [r.uuid, r.label])).toEqual([['r2', 'hi'], ['r1', null]]);
  });

  it('leaves the input untouched', () => {
    const before = JSON.stringify(workflow);
    toClipboard(workflow, types);
    expect(JSON.stringify(workflow)).toBe(before);
  });

  it('refuses what the designer could not paste', () => {
    expect(toClipboard({ ...workflow, steps: [step('x', '/api/3/workflow_step_types/nope')] }, types)).toBeNull();
    expect(toClipboard({ ...workflow, routes: [route('r', 'start', 'gone')] }, types)).toBeNull();
    expect(toClipboard({ ...workflow, steps: [] }, types)).toBeNull();
  });
});

describe('toClipboard with the viewer layout', () => {
  const place = {
    steps: new Map([['start', { x: 100, y: -20 }], ['branch', { x: 100, y: 120 }], ['hi', { x: 400, y: 120 }]]),
    groups: new Map<string, { x: number; y: number; w: number; h: number }>()
  };

  it('moves steps to the layout, top-left at the margin', () => {
    const steps = toClipboard(workflow, types, place)!.steps as Record<string, any>[];
    expect(steps.map((s) => [s.left, s.top, s.parentLeft, s.parentTop])).toEqual([
      ['40', '40', 40, 40], ['40', '180', 40, 180], ['340', '180', 340, 180]
    ]);
  });

  it('places notes, and steps in a block relative to it', () => {
    const wf = {
      ...workflow,
      steps: workflow.steps.map((s) => (s.uuid === 'hi' ? { ...s, group: '/api/3/workflow_groups/blk' } : s)),
      groups: [{ uuid: 'n1', type: 'note', top: '9', left: '9', width: '346', height: '115' }, { uuid: 'blk', type: 'block', top: '0', left: '0' }]
    };
    const groups = new Map([['n1', { x: 380, y: -20, w: 240, h: 66 }], ['blk', { x: 386, y: 90, w: 264, h: 110 }]]);
    const doc = toClipboard(wf, types, { ...place, groups })!;
    expect(doc.groups).toEqual([
      { uuid: 'n1', type: 'note', top: '40', left: '320', width: '240', height: '66' },
      { uuid: 'blk', type: 'block', top: '150', left: '326', width: '264', height: '110' }
    ]);
    const hi = (doc.steps as Record<string, any>[]).find((s) => s.uuid === 'hi')!;
    expect([hi.left, hi.top]).toEqual(['14', '30']);
  });

  it("keeps the export's layout when the viewer's doesn't cover everything", () => {
    const partial = { steps: new Map([['start', { x: 0, y: 0 }]]), groups: new Map() };
    expect((toClipboard(workflow, types, partial)!.steps as Record<string, any>[])[0].left).toBe('200.5');
    const wf = { ...workflow, steps: workflow.steps.map((s) => ({ ...s, group: '/api/3/workflow_groups/blk' })), groups: [{ uuid: 'blk', type: 'block' }] };
    expect((toClipboard(wf, types, place)!.steps as Record<string, any>[])[0].left).toBe('200.5');
  });
});

describe('findWorkflow', () => {
  it('finds a playbook in a playbook export', async () => {
    const doc = { type: 'workflow_collections', data: [{ name: 'c', workflows: [{ uuid: 'other' }, workflow] }] };
    expect((await findWorkflow(enc.encode(JSON.stringify(doc)), 'x-1.0.0.json', 'wf-1'))?.name).toBe('Route');
    expect(await findWorkflow(enc.encode(JSON.stringify(doc)), 'x-1.0.0.json', 'missing')).toBeNull();
  });

  const wf = JSON.stringify({ '@type': 'Workflow', ...workflow });

  it('finds a playbook in a connector pack (.tgz)', async () => {
    const collection = JSON.stringify({ data: [{ workflows: [{ uuid: 'other' }, workflow] }] });
    const pack = tgz({
      'fortinet-fortiaigate/info.json': '{}',
      'fortinet-fortiaigate/playbooks/playbooks.json': collection
    });
    expect((await findWorkflow(pack, 'fortinet-fortiaigate_1.6.12.tgz', 'wf-1'))?.name).toBe('Route');
    expect(await findWorkflow(pack, 'x.tar.gz', 'missing')).toBeNull();
  });

  it('finds a playbook in a solution pack', async () => {
    const pack = zip({
      'export_1/info.json': '{}',
      'export_1/playbooks/tags.json': '{"uuid": "wf-1"}',
      'export_1/playbooks/Coll/collection.metadata.json': '{"name": "Coll"}',
      'export_1/playbooks/Coll/Route.json': wf
    });
    expect((await findWorkflow(pack, 'pack-1.0.0.zip', 'wf-1'))?.name).toBe('Route');
  });

  it('only reads what the pipeline sanitized, and refuses a uuid claimed twice', async () => {
    const decoy = JSON.stringify({ ...workflow, name: 'Decoy' });
    // not @type Workflow, or outside <root>/playbooks/: the pipeline never sanitized these
    const outside = zip({
      'export_1/info.json': '{}',
      'export_1/playbooks/Coll/A.json': decoy,
      'export_1/other/playbooks/Coll/B.json': JSON.stringify({ '@type': 'Workflow', ...workflow, name: 'Decoy' }),
      'export_1/playbooks/Coll/Route.json': wf
    });
    expect((await findWorkflow(outside, 'p.zip', 'wf-1'))?.name).toBe('Route');
    const twice = zip({ 'export_1/info.json': '{}', 'export_1/playbooks/C/a.json': wf, 'export_1/playbooks/C/b.json': wf });
    expect(await findWorkflow(twice, 'p.zip', 'wf-1')).toBeNull();
    const doc = { data: [{ workflows: [workflow] }, { workflows: [workflow] }] };
    expect(await findWorkflow(enc.encode(JSON.stringify(doc)), 'x.json', 'wf-1')).toBeNull();
  });
});

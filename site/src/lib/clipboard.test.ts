import { describe, expect, it } from 'vitest';
import { findWorkflow, toClipboard } from './clipboard';
import stepTypes from './stepTypes.json';
import { zip } from './testZip';

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

describe('findWorkflow', () => {
  it('finds a playbook in a playbook export', async () => {
    const doc = { type: 'workflow_collections', data: [{ name: 'c', workflows: [{ uuid: 'other' }, workflow] }] };
    expect((await findWorkflow(enc.encode(JSON.stringify(doc)), 'x-1.0.0.json', 'wf-1'))?.name).toBe('Route');
    expect(await findWorkflow(enc.encode(JSON.stringify(doc)), 'x-1.0.0.json', 'missing')).toBeNull();
  });

  const wf = JSON.stringify({ '@type': 'Workflow', ...workflow });

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

import { describe, expect, it } from 'vitest';
import { playbookRelations, roleOf } from './playbookRelations';
import type { Collection, Playbook, PlaybookNode } from './types';

const node = (id: string, reference?: string): PlaybookNode =>
  ({ id, name: id, label: 'Step', family: 'utility', x: 0, y: 0, args: {}, ...(reference ? { reference } : {}) }) as PlaybookNode;
const pb = (name: string, uuid: string, ...refs: string[]): Playbook => ({
  name, uuid, description: '', trigger: 'Manual trigger', edges: [], nodes: [node('s', undefined), ...refs.map((r, i) => node(`r${i}`, r))]
});
const coll = (name: string, ...playbooks: Playbook[]): Collection => ({ name, description: '', playbooks });

describe('playbookRelations', () => {
  // The export lists the child first, which is why the page used to open on it.
  const c = [coll('EDR', pb('Part 2', 'AAA'), pb('Part 1', 'bbb', 'aaa'), pb('Standalone', 'ccc'))];

  it('finds who calls whom, ignoring uuid case', () => {
    const r = playbookRelations(c);
    expect(r.calls.get('0:1')).toEqual([{ key: '0:0', name: 'Part 2' }]);
    expect(r.calledBy.get('0:0')).toEqual([{ key: '0:1', name: 'Part 1' }]);
  });

  it('puts parents first, standalone next, children last, otherwise keeping the export order', () => {
    expect(playbookRelations(c).order).toEqual([[1, 2, 0]]);
  });

  it('names each playbook as parent, child or neither', () => {
    const r = playbookRelations(c);
    expect([roleOf(r, '0:1'), roleOf(r, '0:0'), roleOf(r, '0:2')]).toEqual(['parent', 'child', null]);
  });

  it('a middle layer is both, and a chain runs top to bottom', () => {
    const r = playbookRelations([coll('X', pb('Leaf', 'l'), pb('Mid', 'm', 'l'), pb('Top', 't', 'm'))]);
    expect(roleOf(r, '0:1')).toBe('both');
    expect(r.order).toEqual([[2, 1, 0]]);
  });

  it('works across collections and ignores references to playbooks that are not in the item', () => {
    const r = playbookRelations([coll('A', pb('Top', 't', 'child', 'missing')), coll('B', pb('Child', 'child'))]);
    expect(r.calls.get('0:0')).toEqual([{ key: '1:0', name: 'Child' }]);
  });

  it('a playbook that references itself, or nothing, has no role', () => {
    const r = playbookRelations([coll('A', pb('Loop', 'x', 'x'), pb('Plain', 'y'))]);
    expect(roleOf(r, '0:0')).toBeNull();
    expect(r.order).toEqual([[0, 1]]);
  });
});

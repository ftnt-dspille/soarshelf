import { describe, expect, it } from 'vitest';
import { shapeArgs } from './args';

const START = {
  title: 'POC: Process EDR-related Alerts',
  resources: ['alerts'],
  route: '6cca52b4-85f8-4002-bab5-604daf85e461',
  __triggerLimit: true,
  inputVariables: [],
  triggerOnSource: true,
  triggerOnReplicate: false,
  noRecordExecution: false,
  executeButtonText: 'Execute',
  showToasterMessage: { visible: false, messageVisible: true },
  displayConditions: { alerts: { sort: [], limit: 30, logic: 'AND', filters: [] } }
};

describe('shapeArgs for a trigger', () => {
  it('shows what was chosen, not the defaults every trigger carries', () => {
    expect(shapeArgs(START, 'trigger').rest).toEqual({ title: 'POC: Process EDR-related Alerts', resources: ['alerts'], triggerOnSource: true });
  });

  it('keeps settings that differ from the default', () => {
    const r = shapeArgs({ ...START, executeButtonText: 'Check IP', noRecordExecution: true, displayConditions: { alerts: { filters: [{ field: 'severity' }], limit: 30 } } }, 'trigger').rest;
    expect(r.executeButtonText).toBe('Check IP');
    expect(r.noRecordExecution).toBe(true);
    expect(r.displayConditions).toEqual({ alerts: { filters: [{ field: 'severity' }], limit: 30 } });
  });

  it('does not treat a "route" argument on another kind of step as noise', () => {
    expect(shapeArgs({ route: 'custom' }, 'utility').rest).toEqual({ route: 'custom' });
  });
});

describe('shapeArgs for any step', () => {
  it('drops empty values at every level but keeps false and 0', () => {
    expect(shapeArgs({ a: '', b: [], c: {}, d: { e: [], f: false, g: 0 }, h: null }).rest).toEqual({ d: { f: false, g: 0 } });
  });
});

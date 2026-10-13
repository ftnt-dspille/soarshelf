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

const MANUAL_INPUT = {
  type: 'InputBased',
  input: { schema: { title: 'Pick one', description: '{{vars.found}}', inputVariables: [
    { name: 'ip', label: 'IP address', formType: 'text', required: true, _expanded: true },
    { name: 'note', formType: 'textarea' }
  ] } },
  record: '',
  agent_id: null,
  resources: 'alerts',
  is_approval: false,
  owner_detail: { isAssigned: false, emailRecipients: '' },
  isRecordLinked: false,
  response_mapping: {
    options: [
      { option: 'Block', primary: true, step_iri: '/api/3/workflow_steps/s-block' },
      { option: 'Skip', step_iri: '/api/3/workflow_steps/s-gone' }
    ],
    duplicateOption: false,
    customSuccessMessage: 'Awaiting Playbook resumed successfully.'
  },
  timeout: { days: 0, hours: 1, minutes: 30, step_iri: '/api/3/workflow_steps/s-block' },
  email_notification: { enabled: false, smtpParameters: [] },
  inline_channel_list: [],
  external_channel_list: ['/api/3/picklists/x'],
  unauthenticated_input: false,
  customEmailExternal: false,
  internal_email_subject: 'A FortiSOAR playbook is requesting your input'
};
const nameOf = (iri: unknown) => (iri === '/api/3/workflow_steps/s-block' ? 'Block IP' : null);

describe('shapeArgs for a manual input', () => {
  it('turns its buttons and timeout into responses that name their steps', () => {
    expect(shapeArgs(MANUAL_INPUT, 'human', nameOf).branches).toEqual([
      { option: 'Block', condition: null, target: 'Block IP', isDefault: false, primary: true },
      { option: 'Skip', condition: null, target: null, isDefault: false, primary: false },
      { option: 'No response in 1 h 30 min', condition: null, target: 'Block IP', isDefault: true }
    ]);
  });

  it('lifts out the form', () => {
    expect(shapeArgs(MANUAL_INPUT, 'human').form).toEqual({
      title: 'Pick one',
      description: '{{vars.found}}',
      fields: [
        { label: 'IP address', name: 'ip', type: 'text', required: true },
        { label: 'note', name: 'note', type: 'textarea', required: false }
      ]
    });
  });

  it('leaves only the settings that were chosen', () => {
    expect(shapeArgs(MANUAL_INPUT, 'human').rest).toEqual({ resources: 'alerts' });
    const r = shapeArgs({
      ...MANUAL_INPUT, type: 'DecisionBased', is_approval: true,
      owner_detail: { isAssigned: true },
      response_mapping: { ...MANUAL_INPUT.response_mapping, customSuccessMessage: 'Thanks' }
    }, 'human').rest;
    expect(r).toEqual({ responseType: 'Buttons only', resources: 'alerts', is_approval: true, owner_detail: { isAssigned: true }, successMessage: 'Thanks' });
  });
});

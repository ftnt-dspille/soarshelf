/**
 * Shaping step arguments for the inspector: lift out the parts that have their
 * own UI (connector identity, parameters, decision branches) and hide the
 * platform bookkeeping that means nothing to a reader.
 */

/** Keys shown elsewhere in the inspector, or internal to the platform. */
const HIDDEN = new Set([
  'connector', 'operation', 'operationTitle', 'version', 'name', 'config',
  'pickFromTenant', 'params', 'conditions', 'step_variables', 'step_iri', '_truncated'
]);

export interface Branch {
  option: string;
  condition: string | null;
  target: string | null;
  isDefault: boolean;
  /** A manual input's primary (highlighted) button. */
  primary?: boolean;
}

/** What a manual input asks: its prompt and the fields of its form. */
export interface InputForm {
  title: string | null;
  description: string | null;
  fields: { label: string; name: string; type: string | null; required: boolean }[];
}

export interface ShapedArgs {
  operationTitle: string | null;
  version: string | null;
  params: Record<string, unknown> | null;
  branches: Branch[];
  form: InputForm | null;
  rest: Record<string, unknown>;
  truncated: string | null;
}

const str = (v: unknown) => (typeof v === 'string' && v ? v : null);

const isEmpty = (v: unknown) =>
  v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v as object).length);

/** Drop empty values at every level: "none" and "empty" rows tell a reader nothing. */
function pruneEmpty(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(pruneEmpty).filter((x) => !isEmpty(x));
  if (v && typeof v === 'object') {
    const out = Object.fromEntries(Object.entries(v as Record<string, unknown>).map(([k, x]) => [k, pruneEmpty(x)]).filter(([, x]) => !isEmpty(x)));
    return out;
  }
  return v;
}

/** What every trigger step carries by default; showing it buries the settings that were chosen. */
function tidyTrigger(rest: Record<string, unknown>): Record<string, unknown> {
  const out = { ...rest };
  delete out.route;                                        // an internal id
  delete out.__triggerLimit;
  if (out.executeButtonText === 'Execute') delete out.executeButtonText;
  if (out.triggerOnReplicate === false) delete out.triggerOnReplicate;
  if (out.noRecordExecution === false) delete out.noRecordExecution;
  const toaster = out.showToasterMessage as { visible?: unknown; messageVisible?: unknown } | undefined;
  if (toaster && toaster.visible === false) delete out.showToasterMessage;
  // Display conditions with no filter on any module are the default (all records).
  const dc = out.displayConditions;
  if (dc && typeof dc === 'object') {
    const kept = Object.fromEntries(Object.entries(dc as Record<string, { filters?: unknown[] }>).filter(([, m]) => Array.isArray(m?.filters) && m.filters.length));
    if (Object.keys(kept).length) out.displayConditions = kept;
    else delete out.displayConditions;
  }
  return out;
}

const obj = (v: unknown): Record<string, unknown> =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};

const MI_SUCCESS = 'Awaiting Playbook resumed successfully.';
const MI_SUBJECT = 'A FortiSOAR playbook is requesting your input';

/** A manual input: its buttons become branches and its form gets its own section; what's
 * left drops the settings every manual input carries switched off, and internal ids. */
function shapeManualInput(args: Record<string, unknown>, nameOf: (iri: unknown) => string | null) {
  const rm = obj(args.response_mapping);
  const branches: Branch[] = (Array.isArray(rm.options) ? rm.options : []).map((o) => {
    const opt = obj(o);
    return { option: str(opt.option) ?? 'Option', condition: null, target: nameOf(opt.step_iri), isDefault: false, primary: opt.primary === true };
  });
  const timeout = obj(args.timeout);
  if (timeout.step_iri) {
    const span = [['days', 'd'], ['hours', 'h'], ['minutes', 'min']]
      .filter(([k]) => Number(timeout[k]) > 0).map(([k, u]) => `${timeout[k]} ${u}`).join(' ');
    branches.push({ option: span ? `No response in ${span}` : 'No response', condition: null, target: nameOf(timeout.step_iri), isDefault: true });
  }

  const schema = obj(obj(args.input).schema);
  const fields = (Array.isArray(schema.inputVariables) ? schema.inputVariables : []).map((v) => {
    const f = obj(v);
    return { label: str(f.label) ?? str(f.name) ?? 'Field', name: str(f.name) ?? '', type: str(f.formType) ?? str(f.type), required: f.required === true };
  });
  const form = str(schema.title) || str(schema.description) || fields.length
    ? { title: str(schema.title), description: str(schema.description), fields }
    : null;

  const rest: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) {
    if (['response_mapping', 'input', 'timeout', 'inline_channel_list', 'external_channel_list', 'agent_id', '_truncated'].includes(k)) continue;
    if (v === false || (k === 'type' && v === 'InputBased') || (k === 'internal_email_subject' && v === MI_SUBJECT)) continue;
    if (k === 'owner_detail' && obj(v).isAssigned !== true) continue;
    if (k === 'email_notification' && obj(v).enabled !== true) continue;
    rest[k === 'type' && v === 'DecisionBased' ? 'responseType' : k] = k === 'type' && v === 'DecisionBased' ? 'Buttons only' : v;
  }
  if (str(rm.customSuccessMessage) && rm.customSuccessMessage !== MI_SUCCESS) rest.successMessage = rm.customSuccessMessage;
  if (rm.duplicateOption === true) rest.duplicateOption = true;
  return { branches, form, rest };
}

/**
 * `nameOf` turns a step IRI into that step's name, for manual input buttons,
 * which point at their next step by IRI only.
 */
export function shapeArgs(args: Record<string, unknown>, family?: string, nameOf: (iri: unknown) => string | null = () => null): ShapedArgs {
  if (family === 'human' && args.response_mapping) {
    const mi = shapeManualInput(args, nameOf);
    return {
      operationTitle: null, version: null, params: null,
      branches: mi.branches, form: mi.form,
      rest: pruneEmpty(mi.rest) as Record<string, unknown>,
      truncated: str(args._truncated)
    };
  }
  const conditions = Array.isArray(args.conditions) ? args.conditions : [];
  const branches = conditions
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map((c) => ({
      option: str(c.option) ?? 'Branch',
      condition: str(c.condition),
      target: str(c.step_name),
      isDefault: c.default === true
    }));
  const params = args.params && typeof args.params === 'object' && !Array.isArray(args.params)
    ? (args.params as Record<string, unknown>)
    : null;
  return {
    operationTitle: str(args.operationTitle),
    version: str(args.version),
    params: params && Object.keys(params).length ? params : null,
    branches,
    form: null,
    rest: pruneEmpty(
      family === 'trigger' ? tidyTrigger(Object.fromEntries(Object.entries(args).filter(([k]) => !HIDDEN.has(k)))) : Object.fromEntries(Object.entries(args).filter(([k]) => !HIDDEN.has(k)))
    ) as Record<string, unknown>,
    truncated: str(args._truncated)
  };
}

/** "source_ip" → "Source ip", "checkboxFields" → "Checkbox fields". */
export function humanizeKey(k: string): string {
  const s = k
    .replace(/^_+/, '')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim()
    .toLowerCase();
  return s ? s[0].toUpperCase() + s.slice(1) : k;
}

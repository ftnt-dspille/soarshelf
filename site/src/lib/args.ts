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
}

export interface ShapedArgs {
  operationTitle: string | null;
  version: string | null;
  params: Record<string, unknown> | null;
  branches: Branch[];
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

export function shapeArgs(args: Record<string, unknown>, family?: string): ShapedArgs {
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

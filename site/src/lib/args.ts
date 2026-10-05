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

export function shapeArgs(args: Record<string, unknown>): ShapedArgs {
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
    rest: Object.fromEntries(Object.entries(args).filter(([k]) => !HIDDEN.has(k))),
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

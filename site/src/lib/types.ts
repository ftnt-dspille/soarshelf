// Mirrors docs/data-contract.md. The pipeline writes these shapes; the site only reads them.

export type ItemType = 'playbook' | 'solution-pack' | 'connector' | 'widget';
export type HubStatus = 'complete' | 'needs-custom' | 'version-mismatch' | 'none';
export type Trust = 'new' | 'contributor' | 'trusted' | 'maintainer';

export interface SiteIndex {
  generated: string;
  hubSnapshot: string;
  counts: Record<ItemType, number>;
  useCases: UseCase[];
  connectors: ConnectorFacet[];
  items: ItemSummary[];
}

export interface UseCase {
  id: string;
  label: string;
  description: string;
  icon: string;
}

export interface ConnectorFacet {
  name: string;
  label: string;
  category: string | null;
  onHub: boolean;
  count: number;
  /** The connector's own icon, from its package on this site (community connectors only). */
  icon?: string | null;
}

export interface ItemSummary {
  slug: string;
  type: ItemType;
  title: string;
  /** Connectors and widgets: their own name from the manifest ("AWS EC2 (Extended)"). */
  displayName?: string | null;
  summary: string;
  useCases: string[];
  tags: string[];
  connectors: string[];
  triggers: string[];
  playbookCount: number;
  stepCount: number;
  hubStatus: HubStatus;
  hasCode: boolean;
  author: { github: string; trust: Trust };
  version: string;
  minVersion: string | null;
  published: string;
  updated: string;
  /** Most recent change. Optional: builds before it existed don't carry it. */
  lastChange?: LastChange;
  /** Best live test of the current version, or null when it hasn't been tested. */
  tested?: Tested | null;
}

/** ran: the listed playbooks ran to completion on a live FortiSOAR. imported: the download imported cleanly. */
export type TestResult = 'ran' | 'imported';

export interface Tested {
  platform: string;
  result: TestResult;
}

export interface TestEntry extends Tested {
  /** Item version that was tested. */
  version: string;
  playbooks: string[];
  notes: string;
  /** True when this test covered the version and the exact file the site serves now. */
  current: boolean;
}

/** A curated, ordered list of items (data/collections.json). */
export interface CuratedCollection {
  slug: string;
  title: string;
  summary: string;
  description: string;
  featured: boolean;
  order: number;
  items: { slug: string; note: string }[];
}

export interface LastChange {
  kind: 'added' | 'updated';
  version: string;
  date: string;
  notes: string;
}

/** One line of the site-wide change log (data/activity.json), newest first. */
export interface ActivityEvent extends LastChange {
  slug: string;
  type: ItemType;
  title: string;
}

export interface Activity {
  generated: string;
  events: ActivityEvent[];
}

export interface ItemDetail extends ItemSummary {
  description: string;
  setup: SetupStep[];
  dependencies: {
    connectors: ConnectorDep[];
    solutionPacks: PackDep[];
    modules: ModuleDep[];
  };
  checks: CheckResult[];
  collections: Collection[];
  /** Null for a connector or widget listed by manifest only (its code stays in the source repo). */
  download: { path: string; filename: string; sha256: string; bytes: number } | null;
  /** Images from a connector or widget package, re-encoded by the pipeline. */
  screenshots?: { path: string; width: number; height: number; name: string }[];
  /** Repository of a connector or widget; their code is never hosted here. */
  source?: string | null;
  /** Connector manifests: the operations it offers. */
  operations?: ConnectorOperation[];
  /** Connector configuration fields (connectors only). */
  configuration?: ConnectorParam[] | null;
  /** Widget manifests. */
  widget?: WidgetInfo | null;
  /** Newest first; empty until the item's first update. */
  changelog?: ChangelogEntry[];
  /** Every live test, newest platform first, including tests of older versions. */
  tests?: TestEntry[];
}

export interface ChangelogEntry {
  version: string;
  date: string;
  notes: string;
}

export interface WidgetInfo {
  name: string;
  title: string;
  subTitle: string;
  version: string;
  description: string;
  publisher: string;
  pages: string[];
  compatibility: string[];
}

export interface SetupStep {
  kind:
    | 'install-connector'
    | 'configure-connector'
    | 'install-widget'
    | 'place-widget'
    | 'install-pack'
    | 'custom-module'
    | 'import'
    | 'activate'
    | 'note';
  title: string;
  detail: string;
}

export interface ConnectorDep {
  name: string;
  label: string;
  version: string | null;
  operations: string[];
  hub: 'available' | 'version-mismatch' | 'missing';
  hubVersion: string | null;
}

export interface PackDep {
  name: string;
  version: string | null;
  hub: 'available' | 'missing';
}

export interface ModuleDep {
  name: string;
  stock: boolean;
}

export type Severity = 'pass' | 'info' | 'warn' | 'block';

export interface CheckResult {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  location?: string;
}

export interface Collection {
  name: string;
  description: string;
  playbooks: Playbook[];
}

export interface Playbook {
  name: string;
  /** Lets a "reference a playbook" step in another playbook point at this one. */
  uuid?: string;
  description: string;
  trigger: string;
  nodes: PlaybookNode[];
  edges: PlaybookEdge[];
  /** Designer notes and blocks. Older builds have none. */
  groups?: PlaybookGroup[];
}

/** A designer note (tied to the step it sat closest to) or a block (a box around steps). */
export type PlaybookGroup =
  | { id: string; kind: 'note'; name: string; text: string; anchor: string }
  | { id: string; kind: 'block'; name: string; text: string; steps: string[] };

export type NodeFamily =
  | 'trigger'
  | 'connector'
  | 'decision'
  | 'record'
  | 'code'
  | 'human'
  | 'reference'
  | 'utility'
  | 'end'
  | 'other';

// Named PlaybookNode/PlaybookEdge (contract: Node/Edge) to avoid clashing with @xyflow/svelte's types.
export interface PlaybookNode {
  id: string;
  name: string;
  label: string;
  family: NodeFamily;
  x: number;
  y: number;
  connector?: string;
  operation?: string;
  /** The operation's display name from the export, when it has one. */
  operationTitle?: string;
  /** uuid of the playbook this step runs ("reference a playbook" steps). */
  reference?: string;
  args: Record<string, unknown>;
}

export interface PlaybookEdge {
  id: string;
  source: string;
  target: string;
  label: string | null;
}

/** `data/featured.json`: playbooks the pipeline picked for the home page. */
export interface Featured {
  items: FeaturedItem[];
  connectorLabels: Record<string, string>;
  connectorIcons?: Record<string, string>;
}

export interface FeaturedItem {
  slug: string;
  title: string;
  summary: string;
  type: ItemType;
  useCases: string[];
  connectors: string[];
  hubStatus?: HubStatus;
  /** "<collection>:<playbook>" index; deep-link with /items/<slug>#playbooks/<key>. */
  key: string;
  collection: string;
  playbook: Omit<Playbook, 'nodes'> & { nodes: Omit<PlaybookNode, 'args'>[] };
}

export interface ConnectorOperation {
  operation: string;
  title: string | null;
  description?: string;
  parameters?: ConnectorParam[];
  /** Top-level keys of the operation's output. */
  output?: string[];
}

/** A manifest parameter, trimmed by the pipeline. Hidden fields are left out. */
export interface ConnectorParam {
  name: string;
  title: string;
  type: string;
  required: boolean;
  description?: string;
  /** Default value; never published for passwords. */
  value?: string | boolean;
  options?: string[];
  /** Option -> the fields that choosing it reveals. */
  onchange?: Record<string, ConnectorParam[]>;
}

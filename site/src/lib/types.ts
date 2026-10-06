// Mirrors docs/data-contract.md. The pipeline writes these shapes; the site only reads them.

export type ItemType = 'playbook' | 'solution-pack' | 'connector';
export type HubStatus = 'complete' | 'needs-custom' | 'version-mismatch';
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
}

export interface ItemSummary {
  slug: string;
  type: ItemType;
  title: string;
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
  download: { path: string; filename: string; sha256: string; bytes: number };
}

export interface SetupStep {
  kind:
    | 'install-connector'
    | 'configure-connector'
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
  description: string;
  trigger: string;
  nodes: PlaybookNode[];
  edges: PlaybookEdge[];
}

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

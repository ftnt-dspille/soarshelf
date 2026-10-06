import type { Component } from 'svelte';
import Radar from '@lucide/svelte/icons/radar';
import Globe from '@lucide/svelte/icons/globe';
import Mail from '@lucide/svelte/icons/mail';
import Shield from '@lucide/svelte/icons/shield';
import Bug from '@lucide/svelte/icons/bug';
import Key from '@lucide/svelte/icons/key';
import Folder from '@lucide/svelte/icons/folder';
import Download from '@lucide/svelte/icons/download';
import Bell from '@lucide/svelte/icons/bell';
import Wrench from '@lucide/svelte/icons/wrench';
import Funnel from '@lucide/svelte/icons/funnel';
import Search from '@lucide/svelte/icons/search';
import ChartColumn from '@lucide/svelte/icons/chart-column';
import Zap from '@lucide/svelte/icons/zap';
import Plug from '@lucide/svelte/icons/plug';
import GitBranch from '@lucide/svelte/icons/git-branch';
import Database from '@lucide/svelte/icons/database';
import Code from '@lucide/svelte/icons/code';
import User from '@lucide/svelte/icons/user';
import CornerDownRight from '@lucide/svelte/icons/corner-down-right';
import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';
import Flag from '@lucide/svelte/icons/flag';
import Circle from '@lucide/svelte/icons/circle';
import Workflow from '@lucide/svelte/icons/workflow';
import Package from '@lucide/svelte/icons/package';
import Puzzle from '@lucide/svelte/icons/puzzle';
import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
import type { ItemType, NodeFamily } from './types';

// Generic icons only: no product logos or Content Hub artwork.
const USE_CASE_ICONS: Record<string, Component> = {
  radar: Radar,
  globe: Globe,
  mail: Mail,
  shield: Shield,
  bug: Bug,
  key: Key,
  folder: Folder,
  download: Download,
  bell: Bell,
  wrench: Wrench,
  // Names used by the pipeline's use-case taxonomy (pipeline config.USE_CASES).
  filter: Funnel,
  search: Search,
  user: User,
  chart: ChartColumn
};

export function useCaseIcon(name: string): Component {
  return USE_CASE_ICONS[name] ?? Circle;
}

export const FAMILY_ICON: Record<NodeFamily, Component> = {
  trigger: Zap,
  connector: Plug,
  decision: GitBranch,
  record: Database,
  code: Code,
  human: User,
  reference: CornerDownRight,
  utility: SlidersHorizontal,
  end: Flag,
  other: Circle
};

export const FAMILY_LABEL: Record<NodeFamily, string> = {
  trigger: 'Trigger',
  connector: 'Connector',
  decision: 'Decision',
  record: 'Record',
  code: 'Code',
  human: 'Human',
  reference: 'Reference',
  utility: 'Utility',
  end: 'End',
  other: 'Other'
};

export const TYPE_ICON: Record<ItemType, Component> = {
  playbook: Workflow,
  'solution-pack': Package,
  connector: Puzzle,
  widget: LayoutDashboard
};

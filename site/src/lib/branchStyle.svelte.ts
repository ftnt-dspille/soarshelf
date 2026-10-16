// How decision branches and the arrow glow are drawn. The defaults are what the site ships;
// the dev build adds a picker over the canvas to try the alternatives on a real playbook. `?branch=<variant>&spread=0&color=1&glow=0&sweep=trace&speed=slow` picks
// one from the URL.

import { GLOW_MODES, GLOW_SPEEDS, type GlowMode, type GlowSpeed } from './edgeGlow';

export const BRANCH_VARIANTS = {
  fan: 'Fan: curves from a fork marker',
  elbow: 'Elbow: fork, bar, square drops',
  exits: 'Exits: each branch leaves on its own',
  tree: 'Tree: straight diagonals from the fork',
  plain: 'Plain: like any other arrow'
} as const;

export type BranchVariant = keyof typeof BRANCH_VARIANTS;

interface BranchStyle {
  variant: BranchVariant;
  spread: boolean;
  /** Decision branches drawn in the decision's colour. */
  color: boolean;
  glow: boolean;
  sweep: GlowMode;
  speed: GlowSpeed;
}

function initial(): BranchStyle {
  const q = new URLSearchParams(typeof location === 'undefined' ? '' : location.search);
  const v = q.get('branch');
  const sweep = q.get('sweep');
  const speed = q.get('speed');
  return {
    variant: v && v in BRANCH_VARIANTS ? (v as BranchVariant) : 'elbow',
    spread: q.get('spread') !== '0',
    color: q.get('color') === '1',
    glow: q.get('glow') !== '0',
    sweep: GLOW_MODES.includes(sweep as GlowMode) ? (sweep as GlowMode) : 'cascade',
    speed: speed && speed in GLOW_SPEEDS ? (speed as GlowSpeed) : 'normal'
  };
}

export const branchStyle: BranchStyle = $state(initial());

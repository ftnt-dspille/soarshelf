// Which playbooks in an item call which, from "reference a playbook" steps that point at another
// playbook's uuid. A parent starts the work and calls children; a child is called by a parent.
import type { Collection } from './types';

export interface RelatedPlaybook {
  key: string;
  name: string;
}

export interface Relations {
  /** Playbooks this one calls, by "collection:playbook" key. */
  calls: Map<string, RelatedPlaybook[]>;
  /** Playbooks that call this one. */
  calledBy: Map<string, RelatedPlaybook[]>;
  /** Which playbook a reference step (by uuid) runs. */
  byUuid: Map<string, RelatedPlaybook>;
  /** Per collection: playbook indexes with parents first, then standalone ones, then children. */
  order: number[][];
}

export function playbookRelations(collections: Collection[]): Relations {
  const byUuid = new Map<string, RelatedPlaybook>();
  collections.forEach((c, ci) =>
    c.playbooks.forEach((p, pi) => {
      if (p.uuid) byUuid.set(p.uuid.toLowerCase(), { key: `${ci}:${pi}`, name: p.name });
    })
  );
  const calls = new Map<string, RelatedPlaybook[]>();
  const calledBy = new Map<string, RelatedPlaybook[]>();
  collections.forEach((c, ci) =>
    c.playbooks.forEach((p, pi) => {
      const key = `${ci}:${pi}`;
      for (const n of p.nodes) {
        const child = n.reference ? byUuid.get(n.reference.toLowerCase()) : undefined;
        if (!child || child.key === key) continue;
        const list = calls.get(key) ?? [];
        if (!list.some((x) => x.key === child.key)) calls.set(key, [...list, child]);
        const up = calledBy.get(child.key) ?? [];
        if (!up.some((x) => x.key === key)) calledBy.set(child.key, [...up, { key, name: p.name }]);
      }
    })
  );
  // How far below a top-level parent each called playbook sits (a cycle can't loop it forever).
  const depth = new Map<string, number>();
  const roots = [...calls.keys()].filter((k) => !calledBy.has(k));
  let frontier = roots;
  for (let d = 1; frontier.length && d <= collections.length * 50; d++) {
    const next: string[] = [];
    for (const k of frontier) {
      for (const c of calls.get(k) ?? []) {
        if ((depth.get(c.key) ?? 0) < d) {
          depth.set(c.key, d);
          next.push(c.key);
        }
      }
    }
    frontier = next;
  }
  // Parents first, then playbooks that call nothing and are not called, then children (shallowest first).
  const rank = (key: string) => (calledBy.has(key) ? 1 + (depth.get(key) ?? 1) : calls.has(key) ? 0 : 1);
  const order = collections.map((c, ci) =>
    c.playbooks
      .map((_, pi) => pi)
      .sort((a, b) => rank(`${ci}:${a}`) - rank(`${ci}:${b}`) || a - b)
  );
  return { calls, calledBy, byUuid, order };
}

/** "parent" if it only calls others, "child" if it is called, "both" for a middle layer. */
export function roleOf(rel: Relations, key: string): 'parent' | 'child' | 'both' | null {
  const up = rel.calledBy.has(key);
  const down = rel.calls.has(key);
  return up && down ? 'both' : down ? 'parent' : up ? 'child' : null;
}

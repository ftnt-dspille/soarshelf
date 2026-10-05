"""Build the site's data from ``content/``.

Layout::

    content/
      contributors.yaml            # github handle -> trust tier
      playbooks/<slug>/meta.yaml + one .json payload
      solution-packs/<slug>/meta.yaml + one .zip payload
      connectors/<slug>/meta.yaml + info.json

Content on the main branch has been approved (merged), so the build publishes
everything that has no blocking finding, and fails if anything does.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import config
from .hubindex import HubIndex
from .process import Processed, process

TYPE_DIRS = {"playbooks": "playbook", "solution-packs": "solution-pack", "connectors": "connector"}
SUMMARY_KEYS = ("slug", "type", "title", "summary", "useCases", "tags", "connectors", "triggers",
                "playbookCount", "stepCount", "hubStatus", "hasCode", "author", "version",
                "minVersion", "published", "updated")


TIERS = ("new", "contributor", "trusted", "maintainer")


def load_trust(content: Path) -> dict[str, tuple[str, int | None]]:
    """login -> (tier, numeric GitHub id) from contributors.yaml."""
    f = content / "contributors.yaml"
    data = yaml.safe_load(f.read_text()) if f.exists() else {}
    out: dict[str, tuple[str, int | None]] = {}
    for k, v in (data or {}).items():
        if isinstance(v, dict) and v.get("trust") in TIERS:
            uid = v.get("id")
            out[str(k).lower()] = (str(v["trust"]), uid if isinstance(uid, int) and not isinstance(uid, bool) else None)
        elif v in TIERS:
            out[str(k).lower()] = (str(v), None)
    return out


def tier_for(table: dict[str, tuple[str, int | None]], login: str, uid: int | None = None) -> str:
    """A tier only counts for the account it was granted to. Logins can be
    renamed and re-registered, so an entry without an id, or one whose id
    doesn't match the caller's, is 'new'. With ``uid=None`` (display only)
    an entry still needs an id to count."""
    tier, want = table.get(login.lower(), ("new", None))
    if want is None or (uid is not None and uid != want):
        return "new"
    return tier


def item_dirs(content: Path) -> list[tuple[str, Path]]:
    out = []
    for d, kind in TYPE_DIRS.items():
        for item in sorted((content / d).glob("*/meta.yaml")):
            out.append((kind, item.parent))
    return out


def payload_of(item: Path) -> Path:
    files = [p for p in item.iterdir() if p.is_file() and p.name != "meta.yaml" and not p.name.startswith(".")]
    if len(files) != 1:
        raise SystemExit(f"{item}: expected exactly one payload file next to meta.yaml, found {len(files)}")
    return files[0]


def process_item(item: Path, trust_map: dict[str, tuple[str, int | None]], hub: HubIndex) -> Processed:
    meta = yaml.safe_load((item / "meta.yaml").read_text()) or {}
    meta["slug"] = item.name
    uid = meta.get("author_id")
    trust = tier_for(trust_map, str(meta.get("author", "")), uid if isinstance(uid, int) else None)
    return process(meta, payload_of(item), trust, hub)


FEATURED_MAX = 6


def _interest(pb: dict[str, Any]) -> float:
    """How good a playbook looks as a front-page graph: varied step types and
    real branching, big enough to be interesting, small enough to read."""
    nodes, edges = pb["nodes"], pb["edges"]
    if not 4 <= len(nodes) <= 18:
        return 0.0
    out_degree: dict[str, int] = {}
    for e in edges:
        out_degree[e["source"]] = out_degree.get(e["source"], 0) + 1
    families = {n["family"] for n in nodes}
    branches = sum(1 for d in out_degree.values() if d > 1)
    return (3 * len(families) + 2 * branches + 0.5 * min(len(nodes), 12)
            + (2 if "connector" in families else 0) + (1 if any(e["label"] for e in edges) else 0))


def featured(details: list[tuple[dict[str, Any], dict[str, Any]]], hub: HubIndex) -> dict[str, Any]:
    """Pick the best playbook of each item, then the best items. ``meta.featured: true`` wins."""
    picks = []
    for detail, meta in details:
        # Templates have placeholder step names; only show one if it's pinned.
        if "template" in detail["tags"] and not meta.get("featured"):
            continue
        best = None
        for ci, coll in enumerate(detail["collections"]):
            for pi, pb in enumerate(coll["playbooks"]):
                score = _interest(pb)
                if score and (best is None or score > best[0]):
                    best = (score, ci, pi, coll, pb)
        if not best:
            continue
        score, ci, pi, coll, pb = best
        picks.append((score + (100 if meta.get("featured") else 0), {
            "slug": detail["slug"], "title": detail["title"], "summary": detail["summary"],
            "type": detail["type"], "useCases": detail["useCases"], "connectors": detail["connectors"],
            "key": f"{ci}:{pi}", "collection": coll["name"],
            "playbook": {
                "name": pb["name"], "description": pb["description"], "trigger": pb["trigger"],
                # The front page only draws the graph; arguments stay on the item page.
                "nodes": [{k: v for k, v in n.items() if k != "args"} for n in pb["nodes"]],
                "edges": pb["edges"],
            },
        }))
    picks.sort(key=lambda p: -p[0])
    chosen = [p for _, p in picks[:FEATURED_MAX]]
    names = {n["connector"] for f in chosen for n in f["playbook"]["nodes"] if n.get("connector")}
    return {"items": chosen,
            "connectorLabels": {c: (hub.connectors.get(c) or {}).get("label") or c for c in sorted(names)}}


def build(content: Path, out: Path) -> int:
    hub = HubIndex.load()
    trust_map = load_trust(content)
    data_dir, dl_dir = out / "data", out / "downloads"
    for d in (data_dir, dl_dir):
        if d.exists():
            shutil.rmtree(d)
    (data_dir / "items").mkdir(parents=True)

    summaries: list[dict[str, Any]] = []
    published: list[tuple[dict[str, Any], dict[str, Any]]] = []
    failures = 0
    for kind, item in item_dirs(content):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", item.name):
            failures += 1
            print(f"✗ {item.relative_to(content)}: folder name must be a slug ([a-z0-9-])")
            continue
        res = process_item(item, trust_map, hub)
        if res.decision == "reject":
            failures += 1
            print(f"✗ {item.relative_to(content)}")
            for r in res.reasons:
                print(f"    {r}")
            continue
        if res.detail["type"] != kind:
            failures += 1
            print(f"✗ {item.relative_to(content)}: payload is a {res.detail['type']}, folder says {kind}")
            continue
        detail = {k: v for k, v in res.detail.items() if not k.startswith("_")}
        (data_dir / "items" / f"{item.name}.json").write_text(json.dumps(detail, indent=1, ensure_ascii=False))
        (dl_dir / item.name).mkdir(parents=True)
        (dl_dir / item.name / res.filename).write_bytes(res.download)
        summaries.append({k: detail[k] for k in SUMMARY_KEYS})
        published.append((detail, yaml.safe_load((item / "meta.yaml").read_text()) or {}))
        print(f"✓ {item.relative_to(content)}")

    summaries.sort(key=lambda s: s["published"], reverse=True)
    used: dict[str, int] = {}
    for s in summaries:
        for c in s["connectors"]:
            used[c] = used.get(c, 0) + 1
    index = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hubSnapshot": hub.snapshot,
        "counts": {t: sum(1 for s in summaries if s["type"] == t) for t in TYPE_DIRS.values()},
        "useCases": [{"id": i, "label": l, "description": d, "icon": ic} for i, l, d, ic in config.USE_CASES],
        "connectors": sorted(
            ({"name": n, "label": (hub.connectors.get(n) or {}).get("label") or n,
              "category": (hub.connectors.get(n) or {}).get("category"),
              "onHub": n in hub.connectors, "count": c} for n, c in used.items()),
            key=lambda f: (-f["count"], f["label"].lower())),
        "items": summaries,
    }
    (data_dir / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    (data_dir / "featured.json").write_text(json.dumps(featured(published, hub), indent=1, ensure_ascii=False))
    print(f"\n{len(summaries)} published, {failures} failed → {out}")
    return 1 if failures else 0

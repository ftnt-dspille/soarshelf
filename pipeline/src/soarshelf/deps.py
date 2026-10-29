"""What a playbook needs installed, compared against the Content Hub snapshot."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import config
from .hubindex import HubIndex
from .model import CheckResult, ParsedCollection, Severity

_MODULE_IRI = re.compile(r"^/api/3/([a-z][a-z0-9_]*)")
_MODULE_BARE = re.compile(r"^([a-z][a-z0-9_]*)(?:\?|$)")


@dataclass
class ResolvedRef:
    """A reference step that points at a playbook another item ships."""
    location: str          # "collection › playbook › step" in the referencing item
    item: str              # slug of the item that ships the referenced playbook
    playbook: str          # the referenced playbook's name
    connectors: list[str]  # connectors the referenced playbook calls directly


@dataclass
class Dependencies:
    connectors: dict[str, dict[str, Any]] = field(default_factory=dict)   # name -> {version, operations, via}
    modules: set[str] = field(default_factory=set)
    packs: dict[str, str | None] = field(default_factory=dict)
    missing_refs: list[str] = field(default_factory=list)
    resolved_refs: list[ResolvedRef] = field(default_factory=list)


def _module_of(value: Any) -> str | None:
    if not isinstance(value, str) or "{{" in value:
        return None
    m = _MODULE_IRI.match(value) or _MODULE_BARE.match(value)
    if not m or m.group(1) in {"workflows", "workflow_steps", "picklists", "query"}:
        return None
    return m.group(1)


def collect(collections: list[ParsedCollection], known_workflow_ids: set[str],
            registry: dict[str, Any] | None = None) -> Dependencies:
    """What the playbooks need, directly and through reference steps.

    ``registry`` (from :mod:`soarshelf.refs`) maps playbook UUIDs other items
    ship to what those playbooks call; with it, a reference to another item's
    playbook pulls that playbook's connector needs into this item. Without it
    (single-upload flows) such references stay missing-reference warnings.
    """
    deps = Dependencies()
    refs: list[tuple[str, Any, Any, str]] = []
    for c in collections:
        for pb in c.playbooks:
            for s in pb.steps:
                a = s.arguments
                conn = a.get("connector")
                if isinstance(conn, str) and conn and "{{" not in conn:
                    entry = deps.connectors.setdefault(
                        conn, {"version": None, "operations": set(), "via": set()})
                    if isinstance(a.get("version"), str):
                        entry["version"] = a["version"]
                    if isinstance(a.get("operation"), str):
                        entry["operations"].add(a["operation"])
                for key in ("resource", "collection", "module", "collectionType"):
                    mod = _module_of(a.get(key))
                    if mod:
                        deps.modules.add(mod)
                res = a.get("resources")
                for r in [res] if isinstance(res, str) else res if isinstance(res, list) else []:
                    mod = _module_of(r)
                    if mod:
                        deps.modules.add(mod)
                ref = a.get("workflowReference")
                if isinstance(ref, str) and "{{" not in ref:
                    target = ref.rstrip("/").rsplit("/", 1)[-1].lower()
                    refs.append((c.name, pb, s, target))
    _resolve_refs(deps, refs, known_workflow_ids, registry)
    return deps


def _resolve_refs(deps: Dependencies, refs: list[tuple[str, Any, Any, str]],
                  known: set[str], registry: dict[str, Any] | None) -> None:
    """Resolve reference steps against the content tree's playbook registry.

    A reference to a playbook inside this payload was already fine. One pointing
    at a playbook another item ships pulls that playbook's connector needs into
    this item - transitively, so a chain of references ends up on the item that
    starts the chain. A connector reached this way is marked with the slugs of
    the items it came ``via``, and what resolves nowhere keeps its
    missing-reference warning.
    """
    for coll, pb, s, target in refs:
        if target in known:
            continue
        hit = (registry or {}).get(target)
        if hit is None:
            deps.missing_refs.append(f"{coll} › {pb.name} › {s.name}")
            continue
        deps.resolved_refs.append(ResolvedRef(f"{coll} › {pb.name} › {s.name}",
                                              hit.item, hit.name, sorted(hit.connectors)))
    seen = set(known)
    queue = [target for _, _, _, target in refs if target not in known]
    while queue:
        target = queue.pop()
        if target in seen:
            continue
        seen.add(target)
        hit = (registry or {}).get(target)
        if hit is None:
            continue
        for name in sorted(hit.connectors):
            entry = deps.connectors.setdefault(name, {"version": None, "operations": set(), "via": set()})
            entry["via"].add(hit.item)
            entry["operations"].update(hit.ops.get(name) or ())
            if entry["version"] is None and hit.version.get(name):
                entry["version"] = hit.version[name]
        queue.extend(t for t in hit.refs if t not in seen)


def _vt(v: str | None) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v or ""))


def connector_rows(deps: Dependencies, hub: HubIndex) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(deps.connectors):
        want = deps.connectors[name]
        on_hub = hub.connectors.get(name)
        if not on_hub:
            status = "missing"
        elif set(want["operations"]) - set(on_hub.get("operations") or []):
            status = "version-mismatch"      # uses operations the latest hub version lacks
        elif want["version"] and want["version"] not in (on_hub.get("versions") or [on_hub["version"]]) \
                and _vt(want["version"]) > _vt(on_hub["version"]):
            status = "version-mismatch"      # built on a newer version than the hub has
        else:
            status = "available"
        rows.append({
            "name": name,
            "label": (on_hub or {}).get("label") or name,
            "version": want["version"],
            "operations": sorted(want["operations"]),
            "hub": status,
            "hubVersion": (on_hub or {}).get("version"),
            "via": sorted(want.get("via") or []),
        })
    return rows


def declared_rows(rows: list[dict[str, Any]], names: list[str], hub: HubIndex) -> list[dict[str, Any]]:
    """Add author-declared connectors (meta.yaml ``connectors:``) to the rows.

    For dependencies an item's steps cannot show: work done inside a playbook
    this item references whose UUID resolves to nothing in the content tree, or
    alerts handed over by an upstream playbook that is not published here. A
    name the rows already have is left alone; one the hub lacks comes out
    ``missing`` like any other custom connector.
    """
    out = list(rows)
    have = {r["name"] for r in rows}
    for name in names:
        if not name or name in have:
            continue
        on_hub = hub.connectors.get(name)
        out.append({"name": name, "label": (on_hub or {}).get("label") or name,
                    "version": None, "operations": [], "via": [], "declared": True,
                    "hub": "available" if on_hub else "missing",
                    "hubVersion": (on_hub or {}).get("version")})
        have.add(name)
    return out


def checks(deps: Dependencies, rows: list[dict[str, Any]]) -> list[CheckResult]:
    out = []
    missing = [r["name"] for r in rows if r["hub"] == "missing"]
    mismatch = [r for r in rows if r["hub"] == "version-mismatch"]
    if missing:
        out.append(CheckResult("deps.custom-connector", Severity.WARN,
                               "Uses connectors that are not on the Content Hub",
                               ", ".join(missing) + ". Users will need to get these elsewhere; "
                               "link to their source in the description."))
    for r in mismatch:
        out.append(CheckResult("deps.connector-version", Severity.INFO,
                               f"Connector '{r['name']}' differs from the Content Hub version",
                               f"Built with {r['version'] or 'unknown'}, hub has {r['hubVersion']}. "
                               f"Operations used: {', '.join(r['operations'])}."))
    custom = sorted(deps.modules - config.CORE_MODULES)
    if custom:
        out.append(CheckResult("deps.custom-module", Severity.INFO, "Uses non-core modules",
                               ", ".join(custom) + " - these come from a solution pack or a custom module."))
    for where in deps.missing_refs:
        out.append(CheckResult("deps.missing-reference", Severity.WARN,
                               "References a playbook that is not included", "", where))
    if deps.resolved_refs:
        out.append(CheckResult("deps.reference-resolved", Severity.INFO,
                               "Calls playbooks that ship with other items",
                               "; ".join(f"{r.location} → {r.item} ({r.playbook})"
                                         for r in deps.resolved_refs)
                               + ". Import that item and install its connectors too."))
    if not out:
        out.append(CheckResult("deps.complete", Severity.PASS, "All dependencies are on the Content Hub"))
    return out


def hub_status(rows: list[dict[str, Any]]) -> str:
    """Whether the connectors an item USES can be had from the Content Hub.

    "none" when it uses no connectors (a connector or widget listing itself,
    or a playbook of built-in steps): there is nothing to say, so no badge.
    """
    if not rows:
        return "none"
    if any(r["hub"] == "missing" for r in rows):
        return "needs-custom"
    if any(r["hub"] == "version-mismatch" for r in rows):
        return "version-mismatch"
    return "complete"

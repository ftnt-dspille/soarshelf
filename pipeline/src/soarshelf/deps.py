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
class Dependencies:
    connectors: dict[str, dict[str, Any]] = field(default_factory=dict)   # name -> {version, operations}
    modules: set[str] = field(default_factory=set)
    packs: dict[str, str | None] = field(default_factory=dict)
    missing_refs: list[str] = field(default_factory=list)


def _module_of(value: Any) -> str | None:
    if not isinstance(value, str) or "{{" in value:
        return None
    m = _MODULE_IRI.match(value) or _MODULE_BARE.match(value)
    if not m or m.group(1) in {"workflows", "workflow_steps", "picklists", "query"}:
        return None
    return m.group(1)


def collect(collections: list[ParsedCollection], known_workflow_ids: set[str]) -> Dependencies:
    deps = Dependencies()
    for c in collections:
        for pb in c.playbooks:
            for s in pb.steps:
                a = s.arguments
                conn = a.get("connector")
                if isinstance(conn, str) and conn and "{{" not in conn:
                    entry = deps.connectors.setdefault(conn, {"version": None, "operations": set()})
                    if isinstance(a.get("version"), str):
                        entry["version"] = a["version"]
                    if isinstance(a.get("operation"), str):
                        entry["operations"].add(a["operation"])
                for key in ("resource", "collection", "module", "collectionType"):
                    mod = _module_of(a.get(key))
                    if mod:
                        deps.modules.add(mod)
                for r in a.get("resources") or []:
                    mod = _module_of(r)
                    if mod:
                        deps.modules.add(mod)
                ref = a.get("workflowReference")
                if isinstance(ref, str) and "{{" not in ref:
                    target = ref.rstrip("/").rsplit("/", 1)[-1]
                    if target not in known_workflow_ids:
                        deps.missing_refs.append(f"{c.name} › {pb.name} › {s.name}")
    return deps


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
        })
    return rows


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

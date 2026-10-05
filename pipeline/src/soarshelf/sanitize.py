"""Rebuild playbook JSON without environment-specific or personal data.

The download a visitor gets is always the output of this module, never the
uploaded bytes. Anything removed is reported as an ``info`` check so the
contributor can see what changed.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from .model import CheckResult, Severity

# Workflow keys that only describe the exporting environment.
_WORKFLOW_DROP = {
    "@context", "@id", "owners", "versions", "lastModifyDate", "createDate",
    "createUser", "modifyDate", "modifyUser", "deletedAt", "collection",
    "playbookOrigin", "id",
}
_COLLECTION_DROP = {"@context", "@id", "id", "createDate", "createUser",
                    "modifyDate", "modifyUser", "deletedAt"}
# Step arguments that hold authoring-time sample data or local record links.
_ARG_DROP = {"mock_result"}

# References to people/teams/users on the exporting box.
_PERSONAL_IRI = re.compile(r"/api/3/(people|teams|users|appliances)/[0-9a-f-]{36}")


class _Report:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


def _scrub_iris(node: Any, rep: _Report) -> Any:
    if isinstance(node, dict):
        return {k: _scrub_iris(v, rep) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub_iris(v, rep) for v in node]
    if isinstance(node, str) and _PERSONAL_IRI.search(node):
        rep.add("iri", len(_PERSONAL_IRI.findall(node)))
        return _PERSONAL_IRI.sub("", node)
    return node


def _workflow(wf: dict[str, Any], rep: _Report) -> dict[str, Any]:
    for k in _WORKFLOW_DROP & wf.keys():
        if wf[k] not in (None, [], ""):
            rep.add(f"workflow.{k}")
        del wf[k]
    if wf.get("isActive"):
        rep.add("deactivated")
    wf["isActive"] = False
    for step in wf.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step.pop("@id", None)
        step["status"] = None
        args = step.get("arguments")
        if not isinstance(args, dict):
            continue
        for k in _ARG_DROP & args.keys():
            del args[k]
            rep.add("mock")
        # A connector config UUID points at a configuration record on the
        # exporting box; the importer picks a default config when empty.
        if isinstance(args.get("config"), str) and args["config"]:
            args["config"] = ""
            rep.add("config")
    return wf


def sanitize_collections(doc: dict[str, Any]) -> tuple[dict[str, Any], list[CheckResult]]:
    """Return a cleaned copy of a ``workflow_collections`` export."""
    rep = _Report()
    out = copy.deepcopy(doc)
    for macro in out.get("macros") or []:
        if isinstance(macro, dict):
            for k in ("value", "default_value", "defaultValue"):
                if macro.get(k):
                    macro[k] = ""
                    rep.add("macro")
    for coll in out.get("data") or []:
        if not isinstance(coll, dict):
            continue
        for k in _COLLECTION_DROP & coll.keys():
            del coll[k]
        if coll.get("image"):
            coll["image"] = None
            rep.add("image")
        coll["workflows"] = [_workflow(w, rep) for w in coll.get("workflows") or [] if isinstance(w, dict)]
    out = _scrub_iris(out, rep)
    return out, _results(rep)


def sanitize_workflow(wf: dict[str, Any]) -> tuple[dict[str, Any], list[CheckResult]]:
    """Same as :func:`sanitize_collections` for one pack playbook file."""
    rep = _Report()
    out = _scrub_iris(_workflow(copy.deepcopy(wf), rep), rep)
    return out, _results(rep)


_MESSAGES = {
    "deactivated": ("Playbooks set to inactive",
                    "Downloads are always inactive so nothing fires before you review it."),
    "config": ("Connector configuration links removed",
               "Steps will use the default configuration of each connector on your system."),
    "iri": ("References to people and teams removed",
            "Owners, assignees and team links from the original system were stripped."),
    "macro": ("Global variable values cleared",
              "The variables are kept by name; set your own values after import."),
    "mock": ("Authoring sample data removed", ""),
    "image": ("Collection image removed", ""),
}


def _results(rep: _Report) -> list[CheckResult]:
    out = []
    for key, n in sorted(rep.counts.items()):
        if key.startswith("workflow."):
            continue
        title, detail = _MESSAGES.get(key, (key, ""))
        out.append(CheckResult(f"sanitize.{key}", Severity.INFO, f"{title} ({n})", detail))
    if any(k.startswith("workflow.") for k in rep.counts):
        out.append(CheckResult("sanitize.metadata", Severity.INFO, "Export metadata removed",
                               "Owners, version history and timestamps from the original system."))
    return out

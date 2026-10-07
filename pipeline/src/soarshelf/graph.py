"""Turn parsed playbooks into the viewer's node/edge graph."""
from __future__ import annotations

from typing import Any

from . import config
from .model import ParsedCollection
from .parse import route_ends

# Arguments too noisy or too large to be useful in the inspector.
_HIDE_ARGS = {"step_variables"}
_MAX_ARG_CHARS = 4000


def _args(args: dict[str, Any]) -> dict[str, Any]:
    import json
    out = {k: v for k, v in args.items() if k not in _HIDE_ARGS}
    text = json.dumps(out, ensure_ascii=False)
    if len(text) > _MAX_ARG_CHARS:
        return {"_truncated": f"{len(text)} characters - download the file for the full step."}
    return out


def trigger_label(pb) -> str:
    for s in pb.steps:
        if s.id == pb.trigger_step or s.type_uuid in config.TRIGGER_LABELS:
            label = config.TRIGGER_LABELS.get(s.type_uuid)
            if label:
                return label
    return "Unknown"


def collections_graph(collections: list[ParsedCollection]) -> list[dict[str, Any]]:
    out = []
    for c in collections:
        pbs = []
        for pb in c.playbooks:
            nodes = []
            for s in pb.steps:
                label, family = config.STEP_TYPES.get(s.type_uuid, ("Step", "other"))
                node: dict[str, Any] = {
                    "id": s.id, "name": s.name, "label": label, "family": family,
                    "x": s.x, "y": s.y, "args": _args(s.arguments),
                }
                if isinstance(s.arguments.get("connector"), str):
                    node["connector"] = s.arguments["connector"]
                    if family not in ("code",):
                        node["family"] = "connector"
                if isinstance(s.arguments.get("operation"), str) and node.get("connector"):
                    node["operation"] = s.arguments["operation"]
                    if isinstance(s.arguments.get("operationTitle"), str) and s.arguments["operationTitle"].strip():
                        node["operationTitle"] = s.arguments["operationTitle"].strip()
                nodes.append(node)
            ids = {n["id"] for n in nodes}
            edges = []
            for r in pb.routes:
                src, dst = route_ends(r)
                if src in ids and dst in ids:
                    edges.append({"id": str(r.get("uuid") or f"{src}-{dst}"), "source": src,
                                  "target": dst, "label": r.get("label") or None})
            pbs.append({"name": pb.name, "description": pb.description, "trigger": trigger_label(pb),
                        "nodes": nodes, "edges": edges})
        out.append({"name": c.name, "description": c.description, "playbooks": pbs})
    return out

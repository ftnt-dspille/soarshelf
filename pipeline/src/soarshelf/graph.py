"""Turn parsed playbooks into the viewer's node/edge graph."""
from __future__ import annotations

from typing import Any

from . import config
from .model import ParsedCollection, ParsedPlaybook
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


# A designer step's footprint, for finding the step a note sits beside.
_STEP_W, _STEP_H = 230, 54
_MAX_NOTE_CHARS = 1000


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _text(v: Any, limit: int) -> str:
    t = str(v or "").strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def _groups(pb: ParsedPlaybook) -> list[dict[str, Any]]:
    """The playbook's notes and blocks for the viewer. The viewer lays steps out
    itself, so a note can't keep its canvas position: it is tied to the step it
    sat closest to in the designer. A block lists the steps inside it."""
    blocks = {str(g.get("uuid")): g for g in pb.groups if g.get("type") != "note" and g.get("uuid")}

    def box(s) -> tuple[float, float, float, float]:
        g = blocks.get(s.group)        # steps inside a block are positioned relative to it
        x, y = s.x + (_num(g.get("left")) if g else 0), s.y + (_num(g.get("top")) if g else 0)
        return x, y, x + _STEP_W, y + _STEP_H

    def gap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        dx = max(0.0, a[0] - b[2], b[0] - a[2])
        dy = max(0.0, a[1] - b[3], b[1] - a[3])
        return (dx * dx + dy * dy) ** 0.5

    out: list[dict[str, Any]] = []
    for g in pb.groups:
        gid = str(g.get("uuid") or "")
        name, text = _text(g.get("name"), 120), _text(g.get("description"), _MAX_NOTE_CHARS)
        if not gid or not (name or text):
            continue
        members = [s.id for s in pb.steps if s.group == gid]
        if g.get("type") != "note" and members:
            out.append({"id": gid, "kind": "block", "name": name, "text": text, "steps": members})
            continue
        if not pb.steps:
            continue
        left, top = _num(g.get("left")), _num(g.get("top"))
        area = (left, top, left + _num(g.get("width")), top + _num(g.get("height")))
        near = min(pb.steps, key=lambda s: (gap(area, box(s)), s.y, s.x))
        out.append({"id": gid, "kind": "note", "name": name, "text": text, "anchor": near.id})
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
                ref = s.arguments.get("workflowReference")
                if isinstance(ref, str) and ref:
                    node["reference"] = ref.rstrip("/").rsplit("/", 1)[-1].lower()     # the child playbook's uuid
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
            pbs.append({"name": pb.name, "uuid": pb.uuid, "description": pb.description, "trigger": trigger_label(pb),
                        "nodes": nodes, "edges": edges, "groups": _groups(pb)})
        out.append({"name": c.name, "description": c.description, "playbooks": pbs})
    return out

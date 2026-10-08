"""Reduce export JSON to the playbook structure the checks and viewer use."""
from __future__ import annotations

from typing import Any

from .model import ParsedCollection, ParsedPlaybook, Step


def _tail(iri: Any) -> str:
    return str(iri or "").rstrip("/").rsplit("/", 1)[-1]


def _int(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_workflow(wf: dict[str, Any]) -> ParsedPlaybook:
    steps = []
    for s in wf.get("steps") or []:
        if not isinstance(s, dict):
            continue
        args = s.get("arguments")
        steps.append(Step(
            id=str(s.get("uuid") or _tail(s.get("@id"))),
            name=str(s.get("name") or ""),
            type_uuid=_tail(s.get("stepType")),
            arguments=args if isinstance(args, dict) else {},
            x=_int(s.get("left")),
            y=_int(s.get("top")),
            group=_tail(s.get("group")),
        ))
    return ParsedPlaybook(
        name=str(wf.get("name") or ""),
        description=str(wf.get("description") or ""),
        trigger_step=_tail(wf.get("triggerStep")) or None,
        steps=steps,
        routes=[r for r in wf.get("routes") or [] if isinstance(r, dict)],
        uuid=str(wf.get("uuid") or "").lower(),
        groups=[g for g in wf.get("groups") or [] if isinstance(g, dict)],
    )


def parse_collections(doc: dict[str, Any]) -> list[ParsedCollection]:
    out = []
    for c in doc.get("data") or []:
        if not isinstance(c, dict):
            continue
        out.append(ParsedCollection(
            name=str(c.get("name") or ""),
            description=str(c.get("description") or ""),
            playbooks=[parse_workflow(w) for w in c.get("workflows") or [] if isinstance(w, dict)],
        ))
    return out


def route_ends(route: dict[str, Any]) -> tuple[str, str]:
    return _tail(route.get("sourceStep")), _tail(route.get("targetStep"))

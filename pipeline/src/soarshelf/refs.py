"""Which playbooks the content tree ships, so cross-item references can resolve.

A reference step points at a playbook by UUID. When that playbook ships in the
same payload the pipeline already resolves the link; when it ships in another
item (sibling collections split across items, a connector's bundled samples),
the UUID alone says nothing - the pipeline could only warn that the reference
is missing, and miss everything the child playbook needs. ``scan`` maps every
playbook UUID in ``content/`` to the item that ships it and what its own steps
call, so ``deps.collect`` can pull a referenced playbook's connector
dependencies into the referencing item.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import ParsedPlaybook
from .parse import parse_collections, parse_workflow


@dataclass(frozen=True)
class RefTarget:
    """One shipped playbook: the item that carries it and what its steps call."""
    item: str                          # slug of the item that ships it
    name: str                          # the playbook's name
    connectors: frozenset[str]         # connector machine names its own steps call
    ops: dict[str, frozenset[str]]     # connector -> operations its steps call
    version: dict[str, str]            # connector -> version a step pins, last one wins
    refs: frozenset[str]               # playbook UUIDs its own reference steps point at


def _targets(item: str, playbooks: list[ParsedPlaybook]) -> list[tuple[str, RefTarget]]:
    """(UUID, RefTarget) for every playbook that has a UUID, the same extraction
    ``deps.collect`` does for a payload's own steps."""
    out = []
    for pb in playbooks:
        if not pb.uuid:
            continue
        connectors: set[str] = set()
        ops: dict[str, set[str]] = {}
        version: dict[str, str] = {}
        refs: set[str] = set()
        for s in pb.steps:
            a = s.arguments
            conn = a.get("connector")
            if isinstance(conn, str) and conn and "{{" not in conn:
                connectors.add(conn)
                if isinstance(a.get("operation"), str):
                    ops.setdefault(conn, set()).add(a["operation"])
                if isinstance(a.get("version"), str):
                    version[conn] = a["version"]
            ref = a.get("workflowReference")
            if isinstance(ref, str) and ref and "{{" not in ref:
                refs.add(ref.rstrip("/").rsplit("/", 1)[-1].lower())
        out.append((pb.uuid, RefTarget(item, pb.name, frozenset(connectors),
                                       {k: frozenset(v) for k, v in ops.items()}, version, frozenset(refs))))
    return out


def _playbooks_of(item: Path) -> list[ParsedPlaybook]:
    """The playbooks one content item ships, whatever kind it is.

    Same payload rules as ``build.payload_of``: a connector's source lives in
    ``package/``, a solution pack is one zip of per-playbook JSON files, a
    playbook item is a single JSON payload next to meta.yaml (playbook.yaml is
    the generated review view, not payload).
    """
    if (item / "package").is_dir():                    # connector source: bundled samples
        out: list[ParsedPlaybook] = []
        for f in sorted((item / "package").glob("*/playbooks/playbooks.json")):
            out += [pb for c in parse_collections(json.loads(f.read_text())) for pb in c.playbooks]
        return out
    files = [p for p in item.iterdir() if p.is_file() and p.name not in ("meta.yaml", "playbook.yaml")
             and not p.name.startswith(".")]
    if len(files) != 1:
        raise ValueError(f"expected one payload file next to meta.yaml, found {len(files)}")
    payload = files[0]
    if payload.suffix == ".zip":                       # solution pack: playbooks/<coll>/<name>.json
        out = []
        with zipfile.ZipFile(payload) as z:
            for name in sorted(z.namelist()):
                parts = name.split("/")
                if "playbooks" not in parts[:-2] or not name.endswith(".json"):
                    continue
                doc = json.loads(z.read(name))
                if isinstance(doc, dict) and doc.get("@type") == "Workflow":
                    out.append(parse_workflow(doc))
        return out
    doc: Any = json.loads(payload.read_text())
    return [pb for c in parse_collections(doc) for pb in c.playbooks]


def scan(content: Path) -> dict[str, RefTarget]:
    """UUID -> RefTarget for every playbook the content tree ships.

    Best effort: an item that fails to read is skipped with a note, and its
    references then behave as before (a missing-reference warning). A UUID two
    items ship keeps the first in sorted order; the review flow catches such
    duplication long before the site builds.
    """
    out: dict[str, RefTarget] = {}
    for kind_dir in ("playbooks", "solution-packs", "connectors"):
        base = content / kind_dir
        if not base.is_dir():
            continue
        for item in sorted(p for p in base.iterdir() if p.is_dir()):
            try:
                targets = _targets(item.name, _playbooks_of(item))
            except Exception as exc:               # noqa: BLE001 - the registry is best effort
                print(f"note: playbook registry skipped {item.name}: {str(exc)[:120]}")
                continue
            for uuid, target in targets:
                out.setdefault(uuid, target)
    return out

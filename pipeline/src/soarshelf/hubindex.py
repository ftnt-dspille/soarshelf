"""The Content Hub snapshot and official-content fingerprints.

Both files under ``pipeline/data/`` are generated and committed:

* ``hub-index.json`` - from the public Content Hub catalog: connector names,
  versions, categories and operation names, plus solution pack names and
  versions. Facts only: no descriptions, icons, documentation or code.
* ``official-fingerprints.json`` - SHA-256 hashes of the collection and
  playbook UUIDs and step structures found in official solution packs, so a
  re-upload of official content can be recognised without republishing it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
HUB_INDEX = DATA_DIR / "hub-index.json"
FINGERPRINTS = DATA_DIR / "official-fingerprints.json"


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def structure_key(steps: list[tuple[str, str]]) -> str:
    """Hash of a playbook's (step name, step type) multiset. Survives UUID
    regeneration, which is the cheap way to disguise a copied playbook."""
    norm = sorted(f"{n.strip().lower()}|{t}" for n, t in steps)
    return _h("\n".join(norm))


@dataclass
class HubIndex:
    snapshot: str
    connectors: dict[str, dict[str, Any]]
    packs: dict[str, dict[str, Any]]
    official_uuids: set[str] = field(default_factory=set)
    official_structures: dict[str, str] = field(default_factory=dict)  # hash -> pack label

    @classmethod
    def load(cls) -> HubIndex:
        hub = json.loads(HUB_INDEX.read_text())
        fp = json.loads(FINGERPRINTS.read_text()) if FINGERPRINTS.exists() else {}
        return cls(
            snapshot=hub["snapshot"],
            connectors=hub["connectors"],
            packs=hub["solutionPacks"],
            official_uuids=set(fp.get("uuids", [])),
            official_structures=fp.get("structures", {}),
        )

    def is_official_uuid(self, uuid: str) -> bool:
        return bool(uuid) and _h(uuid.lower()) in self.official_uuids


# --- builders (run by maintainers, output committed) --------------------------

CATALOG_URL = "https://repo.fortisoar.fortinet.com/content-hub/content-hub.json"


def _first(v: Any) -> str | None:
    if isinstance(v, list):
        return str(v[0]) if v else None
    return str(v) if v else None


def build_hub_index(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce the public Content Hub catalog to names, versions and operations."""
    connectors: dict[str, Any] = {}
    packs: dict[str, Any] = {}
    for e in catalog:
        if not isinstance(e, dict) or not e.get("name"):
            continue
        name = str(e["name"])
        if e.get("type") == "connector":
            connectors[name] = {
                "label": e.get("label") or name,
                "version": e.get("version"),
                "versions": list(e.get("availableVersions") or []),
                "category": _first(e.get("category")),
                "operations": sorted({str(o["operation"]) for o in e.get("operations") or []
                                      if isinstance(o, dict) and o.get("operation")}),
            }
        elif e.get("type") == "solutionpack":
            packs[name] = {"label": e.get("label") or name, "version": e.get("version"),
                           "versions": list(e.get("availableVersions") or [])}
    return {"snapshot": date.today().isoformat(), "source": CATALOG_URL,
            "connectors": dict(sorted(connectors.items())), "solutionPacks": dict(sorted(packs.items()))}


def fetch_catalog(source: str = CATALOG_URL) -> list[dict[str, Any]]:
    if source.startswith("https://"):
        import urllib.request
        with urllib.request.urlopen(source, timeout=60) as r:   # noqa: S310 - fixed https URL
            return json.loads(r.read())
    return json.loads(Path(source).read_text())


def build_fingerprints(pack_dirs: list[Path]) -> dict[str, Any]:
    """Walk unpacked official solution packs (``<pack>/<collection>/*.json``)."""
    uuids: set[str] = set()
    structures: dict[str, str] = {}
    for pack in pack_dirs:
        label = pack.name
        for f in pack.rglob("*.json"):
            try:
                doc = json.loads(f.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            if doc.get("@type") in ("WorkflowCollection", "Workflow") and doc.get("uuid"):
                uuids.add(_h(str(doc["uuid"]).lower()))
            if doc.get("@type") == "Workflow":
                steps = [(str(s.get("name") or ""), str(s.get("stepType") or "").rsplit("/", 1)[-1])
                         for s in doc.get("steps") or [] if isinstance(s, dict)]
                if len(steps) >= 3:          # tiny playbooks collide by accident
                    structures[structure_key(steps)] = label
    return {"uuids": sorted(uuids), "structures": dict(sorted(structures.items()))}

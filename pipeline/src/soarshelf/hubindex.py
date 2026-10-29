"""The Content Hub snapshot and official-content fingerprints.

Both files under ``pipeline/data/`` are generated and committed:

* ``hub-index.json`` - from the public Content Hub catalog: connector names,
  versions, categories, operation names and each connector's icon file, plus
  solution pack names and versions. Facts only: no descriptions, documentation
  or code.
* ``icons/`` - the connector icons the snapshot points at, downloaded once per
  refresh by ``soarshelf hub-icons`` and cleaned like an uploaded one
  (re-drawn PNG, no larger than 96px, no metadata). The build is offline: it
  only copies these files; it never downloads anything.
* ``official-fingerprints.json`` - SHA-256 hashes of the collection and
  playbook UUIDs and step structures found in official solution packs, so a
  re-upload of official content can be recognised without republishing it.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
HUB_INDEX = DATA_DIR / "hub-index.json"
FINGERPRINTS = DATA_DIR / "official-fingerprints.json"
ICON_DIR = DATA_DIR / "icons"


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
    widgets: dict[str, dict[str, Any]] = field(default_factory=dict)
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
            widgets=hub.get("widgets") or {},
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


def hub_index() -> HubIndex:
    """The committed snapshot (offline default), or a live-built index.

    ``SOARSHELF_HUB_LIVE`` makes checks fetch the public catalog at run time
    instead of reading the committed snapshot - the submission and build
    Actions set it, so what a submission is checked against is always
    current. Any failure to fetch (offline, hub down, malformed catalog)
    falls back to the committed snapshot with a note on stderr: a check
    must not fail because the Hub is unreachable.
    """
    import os
    import sys

    if os.environ.get("SOARSHELF_HUB_LIVE") not in ("1", "true", "yes"):
        return HubIndex.load()
    try:
        hub = build_hub_index(fetch_catalog())
        index = HubIndex(snapshot=hub["snapshot"], connectors=hub["connectors"],
                         packs=hub["solutionPacks"], widgets=hub.get("widgets") or {})
    except Exception as exc:  # noqa: BLE001 - network/format failures fall back
        print(f"note: live Content Hub fetch failed ({exc}); using the committed snapshot",
              file=sys.stderr)
        return HubIndex.load()
    if FINGERPRINTS.exists():
        fp = json.loads(FINGERPRINTS.read_text())
        index.official_uuids = set(fp.get("uuids", []))
        index.official_structures = fp.get("structures", {})
    return index


def build_hub_index(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce the public Content Hub catalog to names, versions and operations."""
    connectors: dict[str, Any] = {}
    packs: dict[str, Any] = {}
    widgets: dict[str, Any] = {}
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
                "icon": e.get("iconLarge"),
            }
        elif e.get("type") == "solutionpack":
            packs[name] = {"label": e.get("label") or name, "version": e.get("version"),
                           "versions": list(e.get("availableVersions") or [])}
        elif e.get("type") == "widget":
            widgets[name] = {"label": e.get("label") or name, "version": e.get("version")}
    return {"snapshot": date.today().isoformat(), "source": CATALOG_URL,
            "connectors": dict(sorted(connectors.items())), "solutionPacks": dict(sorted(packs.items())),
            "widgets": dict(sorted(widgets.items()))}


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


# --- connector icons (soarshelf hub-icons; the weekly hub refresh runs it) -------

_ICON_FILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,80}\.png")


def _fetch_icon(path: str) -> bytes:
    """One hub icon, from the host the public catalog lives on."""
    origin = f"https://{urlsplit(CATALOG_URL).netloc}"
    with urllib.request.urlopen(origin + path, timeout=30) as r:   # noqa: S310 - fixed https host
        return r.read(256 * 1024)          # icons are tiny; refuse anything large


def hub_icons(names: list[str] | set[str], out: Path = ICON_DIR,
              fetch=_fetch_icon, hub: HubIndex | None = None) -> dict[str, Any]:
    """Download and clean a hub connector icon for every name in ``names``.

    The snapshot records where each connector's icon lives; this fetches it there and
    re-draws it as a fresh PNG exactly like an uploaded connector icon (no metadata,
    anything hidden in the file is dropped). The directory mirrors what it is asked
    for: a connector the hub lists no icon for (or that isn't on the hub at all) gets
    no file, and a leftover file for it is removed.

    A connector that can't be fetched is skipped, not an error: the next refresh
    retries it, and the build just shows that connector without an icon.
    Returns a report with ``kept``, ``written``, ``removed`` and ``failed`` counts.
    """
    from .process import _clean_icon

    hub = hub if hub is not None else HubIndex.load()
    keep: set[str] = set()
    written = 0
    failed: list[str] = []
    for name in sorted(names):
        path = (hub.connectors.get(name) or {}).get("icon")
        if not (isinstance(path, str) and path.startswith("/content-hub/") and ".." not in path):
            continue                      # not on the hub, or the catalog names no icon
        keep.add(f"{name}.png")
        dest = out / f"{name}.png"
        try:
            png = _clean_icon(fetch(path))
        except Exception:                 # noqa: BLE001 - a bad download skips one icon
            failed.append(name)
            continue
        if png is None:
            failed.append(name)
            continue
        if not dest.is_file() or dest.read_bytes() != png:
            out.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(png)
            written += 1
    # The directory mirrors the names asked for; anything else is a leftover.
    removed = sorted(p.name for p in out.glob("*.png")
                    if _ICON_FILE.fullmatch(p.name) and p.name not in keep)
    for name in removed:
        (out / name).unlink()
    return {"kept": len(keep), "written": written, "removed": len(removed),
            "failed": failed,
            "no-icon": [n for n in sorted(names) if f"{n}.png" not in keep]}

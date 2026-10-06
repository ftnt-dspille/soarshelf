"""Run every check on one item and produce its published form.

``process(meta, payload_path, trust, hub)`` is the single entry point used by
both the CLI self-check and the site build. It returns the item detail
(docs/data-contract.md ``ItemDetail``, minus build-time fields) and the bytes
of the sanitized download.
"""
from __future__ import annotations

import hashlib
import io
import json
import posixpath
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyfsr.exports import Export, ExportError
from pyfsr.exports import Severity as PackSeverity

from . import config, deps as deps_mod, graph, policy, setup_guide
from .checks import brand, secrets, structure
from .hubindex import HubIndex
from .intake import Upload, load_json, read_upload
from .model import CheckResult, ParsedCollection, RejectedUpload, Severity, worst
from .parse import parse_collections, parse_workflow
from .sanitize import new_report, report_results, sanitize_collections, sanitize_workflow


@dataclass
class Processed:
    detail: dict[str, Any]
    download: bytes | None
    filename: str | None
    decision: str                  # "publish" | "review" | "reject"
    reasons: list[str]
    files: dict[str, bytes] | None = None     # package source to commit (connector/widget .tgz)
    assets: dict[str, bytes] | None = None    # extra files next to the download (screenshots)

    @property
    def checks(self) -> list[CheckResult]:
        return self.detail["_results"]


def _meta_checks(meta: dict[str, Any], kind: str, packaged: bool = False) -> list[CheckResult]:
    out = []
    for key in ("title", "summary", "use_cases"):
        if not meta.get(key):
            out.append(CheckResult("meta.required", Severity.BLOCK, f"meta.yaml is missing '{key}'"))
    bad = [u for u in meta.get("use_cases") or [] if u not in config.USE_CASE_IDS]
    if bad:
        out.append(CheckResult("meta.use-case", Severity.BLOCK, "Unknown use case",
                               f"{', '.join(bad)}. Valid: {', '.join(sorted(config.USE_CASE_IDS))}"))
    if len(str(meta.get("summary") or "")) > 160:
        out.append(CheckResult("meta.summary", Severity.WARN, "Summary is longer than 160 characters"))
    if (meta.get("license") or "MIT") != "MIT":
        out.append(CheckResult("meta.license", Severity.BLOCK, "Content must be shared under the MIT licence"))
    if kind in CODE_KINDS and not packaged and not str(meta.get("source") or "").startswith("https://"):
        out.append(CheckResult("meta.source", Severity.BLOCK, f"A {kind} manifest on its own needs a source URL",
                               f"Upload the {kind}'s .tgz instead, or set 'source' to its public repository."))
    return out + brand.listing(meta)


def _uuids_of(doc_collections: list[dict[str, Any]]) -> dict[str, str]:
    out = {}
    for c in doc_collections:
        if c.get("uuid"):
            out[str(c["uuid"])] = str(c.get("name") or "")
        for w in c.get("workflows") or []:
            if isinstance(w, dict) and w.get("uuid"):
                out[str(w["uuid"])] = f"{c.get('name')} › {w.get('name')}"
    return out


# --- per-type handlers ---------------------------------------------------------

# Item types whose payload is code that runs on the platform: listed by
# manifest with a source link, never hosted, always reviewed.
CODE_KINDS = ("connector", "widget")
_SAFE_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_REVIEW_NOTE = {
    False: "Only the manifest is published here; the code stays in the linked repository.",
    True: "The download is rebuilt from the reviewed source, so it is exactly what the reviewer read.",
}


def _package_checks(up: Upload) -> list[CheckResult]:
    from . import package

    files = up.members or {}
    results: list[CheckResult] = []
    for name, raw in sorted(files.items()):
        if not package.is_text(name) or name == f"{up.package_top}/info.json":   # the manifest is scanned already
            continue
        found = secrets.scan({name: raw.decode("utf-8", "replace")})
        # Bundled libraries are full of long strings and sample addresses; only hard hits count there.
        if package._vendored(name) or not name.endswith(".py") and not name.endswith(".json"):
            found = [r for r in found if r.severity is Severity.BLOCK or r.id != "secrets.high-entropy"]
        results += found
    results += package.review_hints(files)
    if up.kind == "widget":
        results += package.widget_lint(files, up.package_top or "")
    if up.dropped:
        results.append(CheckResult("package.dropped", Severity.INFO, "Build leftovers were left out",
                                   ", ".join(up.dropped[:5]) + (f" and {len(up.dropped) - 5} more" if len(up.dropped) > 5 else "")))
    return results

def _playbook(up: Upload) -> tuple[list[ParsedCollection], dict[str, str], list[CheckResult], bytes, Any]:
    clean, results = sanitize_collections(up.data)
    results += secrets.scan(clean)
    results += brand.content(clean)
    body = json.dumps(clean, indent=2, ensure_ascii=False).encode() + b"\n"
    return parse_collections(clean), _uuids_of(up.data.get("data") or []), results, body, clean.get("macros")


_REPO_DOC_SUFFIXES = (".md", ".txt", ".rst", ".png", ".jpg", ".jpeg", ".gif")
_REPO_DOC_NAMES = ("license", "licence", "notice", "authors", ".gitignore", ".gitattributes", ".editorconfig")
_ARCHIVES = (".zip", ".tgz", ".gz", ".tar", ".whl", ".exe", ".msi", ".sh", ".py", ".js")


def _is_repo_doc(name: str) -> bool:
    """README, LICENSE, git files and a docs/ folder: never published, so harmless."""
    low = name.lower()
    base = posixpath.basename(low)
    if base.endswith(_ARCHIVES):
        return False
    return ("/docs/" in f"/{low}" or base.endswith(_REPO_DOC_SUFFIXES)
            or base in _REPO_DOC_NAMES or base.split(".")[0] in _REPO_DOC_NAMES)


def _pack(up: Upload) -> tuple[list[ParsedCollection], dict[str, str], list[CheckResult], bytes, Any]:
    members = up.members or {}
    root = next(m for m in members if posixpath.basename(m) == "info.json" and m.count("/") <= 1)[:-len("info.json")]
    results: list[CheckResult] = []

    extra = sorted(m for m in members if not m.endswith(config.PACK_MEMBER_SUFFIXES))
    # A pack zipped from its repository carries docs and git files: drop them, don't reject.
    docs = [m for m in extra if _is_repo_doc(m)]
    extra = [m for m in extra if m not in docs]
    if docs:
        results.append(CheckResult("pack.ignored-files", Severity.INFO,
                                   "Documentation files were left out",
                                   f"Only the exported JSON is published. Ignored: {', '.join(docs[:5])}"
                                   + (f" and {len(docs) - 5} more" if len(docs) > 5 else "")))
    if extra:
        results.append(CheckResult("pack.installers", Severity.BLOCK,
                                   "Files that aren't part of a solution pack export",
                                   "Upload the exported JSON only, and list connectors and widgets as their own "
                                   f"items. Found: {', '.join(extra[:5])}"
                                   + (f" and {len(extra) - 5} more" if len(extra) > 5 else "")))

    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        tmp.write(up.raw)
        tmp.flush()
        try:
            with Export.open(tmp.name) as exp:
                for f in exp.problems():
                    sev = Severity.BLOCK if f.severity is PackSeverity.ERROR else Severity.INFO
                    results.append(CheckResult(f"pack.{f.code}", sev, f.message, "", f.path))
        except ExportError as exc:
            results.append(CheckResult("pack.format", Severity.BLOCK, "Not a valid solution pack", str(exc)))

    collections: dict[str, ParsedCollection] = {}
    uuids: dict[str, str] = {}
    rebuilt: dict[str, bytes] = {}
    # One tally for the whole pack, so 160 playbooks give one note each, not 160.
    pack_report = new_report()
    for name in sorted(members):
        if not name.endswith(".json"):
            continue
        rel = name[len(root):]
        doc = load_json(members[name], rel)
        if rel.startswith("playbooks/") and isinstance(doc, dict) and doc.get("@type") == "Workflow":
            coll_name = rel.split("/")[1]
            clean, _ = sanitize_workflow(doc, pack_report)
            if doc.get("uuid"):
                uuids[str(doc["uuid"])] = f"{coll_name} › {doc.get('name')}"
            collections.setdefault(coll_name, ParsedCollection(coll_name, "")).playbooks.append(parse_workflow(clean))
            doc = clean
        elif rel.endswith("collection.metadata.json") and isinstance(doc, dict) and doc.get("uuid"):
            uuids[str(doc["uuid"])] = str(doc.get("name") or "")
        results += secrets.scan(doc, rel)
        results += brand.content(doc)
        rebuilt[name] = json.dumps(doc, indent=2, ensure_ascii=False).encode() + b"\n"

    results += report_results(pack_report)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in rebuilt.items():
            zi = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data, zipfile.ZIP_DEFLATED)
    return list(collections.values()), uuids, results, buf.getvalue(), None


def _connector(up: Upload, hub: HubIndex) -> tuple[list[CheckResult], bytes, list[dict[str, Any]]]:
    m = up.data
    results = secrets.scan(m, "info.json")
    name = str(m.get("name") or "")
    if not name:
        results.append(CheckResult("connector.name", Severity.BLOCK, "Manifest has no 'name'"))
    if name in hub.connectors:
        results.append(CheckResult("connector.on-hub", Severity.WARN,
                                   "A connector with this name is on the Content Hub",
                                   "Rename it if it is a fork, so it can't be confused with the hub version."))
    ops = [_operation(o) for o in (m.get("operations") or [])[:300] if isinstance(o, dict)]
    # "type" marks the trimmed manifest as a connector when the build re-reads it.
    keep = {"type": "connector", **{k: m.get(k) for k in ("name", "label", "version", "description", "category", "publisher")}}
    keep["operations"] = ops
    keep["configuration"] = {"fields": _params((m.get("configuration") or {}).get("fields") if isinstance(m.get("configuration"), dict) else None)}
    results.append(CheckResult("connector.review", Severity.INFO, "Connector code is reviewed by a maintainer",
                               _REVIEW_NOTE[bool(up.package_top)]))
    return results, json.dumps(keep, indent=2, ensure_ascii=False).encode() + b"\n", ops


def _text(v: Any, limit: int) -> str:
    """Manifest text on one line, cut at a word with an ellipsis when it's too long."""
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        return ""
    s = " ".join(str(v).split())
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


# A default is shown only for types that can't hold a credential, and never for
# a field whose name or title looks like one, whatever its declared type.
_PLAIN_TYPES = {"select", "multiselect", "checkbox", "integer", "decimal", "datetime", "text", "textarea", "json"}
_SECRETISH = re.compile(r"pass|secret|token|api.?key|apikey|credential|auth|private|cert", re.I)


def _secret_field(p: dict[str, Any], kind: str) -> bool:
    return (kind.lower() not in _PLAIN_TYPES
            or bool(_SECRETISH.search(f"{p.get('name') or ''} {p.get('title') or ''}")))


def _params(raw: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Operation or configuration parameters, trimmed to what a reader needs.

    Keeps the manifest's own key names, so a trimmed manifest reads the same way
    again at build time. Hidden fields are dropped; a password's default never
    leaves the package. ``onchange`` maps an option to the fields it reveals.
    """
    out: list[dict[str, Any]] = []
    for p in (raw if isinstance(raw, list) else [])[:80]:
        if not isinstance(p, dict) or p.get("visible") is False or not p.get("name"):
            continue
        kind = _text(p.get("type"), 24) or "text"
        q: dict[str, Any] = {"name": _text(p.get("name"), 80), "title": _text(p.get("title"), 120) or _text(p.get("name"), 80),
                             "type": kind, "required": p.get("required") is True}
        desc = _text(p.get("description"), 600) or _text(p.get("tooltip"), 600)
        if desc:
            q["description"] = desc
        val = p.get("value")
        if not _secret_field(p, kind) and val not in (None, "", [], {}):
            q["value"] = val if isinstance(val, bool) else _text(val if isinstance(val, (str, int, float)) else json.dumps(val), 160)
        opts = [_text(o, 80) for o in p.get("options") or [] if isinstance(o, (str, int, float))] if isinstance(p.get("options"), list) else []
        if opts:
            q["options"] = opts[:40]
        if depth < 3 and isinstance(p.get("onchange"), dict):
            reveal = {_text(k, 80): _params(v, depth + 1) for k, v in list(p["onchange"].items())[:40]}
            reveal = {k: v for k, v in reveal.items() if k and v}
            if reveal:
                q["onchange"] = reveal
        out.append(q)
    return out


def _operation(o: dict[str, Any]) -> dict[str, Any]:
    op: dict[str, Any] = {"operation": o.get("operation"), "title": o.get("title")}
    desc = _text(o.get("description"), 400)
    if desc:
        op["description"] = desc
    params = _params(o.get("parameters"))
    if params:
        op["parameters"] = params
    out = o.get("output_schema")
    if isinstance(out, dict) and out:
        op["output"] = [_text(k, 80) for k in list(out)[:30]]
    elif isinstance(o.get("output"), list):    # a trimmed manifest, read again at build time
        op["output"] = [_text(k, 80) for k in o["output"][:30]]
    return op


def _widget(up: Upload, hub: HubIndex) -> tuple[list[CheckResult], bytes, dict[str, Any]]:
    """Widgets run in the platform's UI with the viewer's session, so like
    connectors only the manifest is listed; the code stays in its repository."""
    m = up.data
    results = secrets.scan(m, "info.json") + brand.content(m)
    name = str(m.get("name") or "")
    if name in hub.widgets:
        results.append(CheckResult("widget.on-hub", Severity.WARN,
                                   "A widget with this name is on the Content Hub",
                                   "Rename it if it is a fork, so it can't be confused with the hub version."))
    md = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}

    def strs(v: Any) -> list[str]:
        return [str(x)[:60] for x in v][:10] if isinstance(v, list) else []

    info = {
        "name": name[:80],
        "title": str(m.get("title") or "")[:120],
        "subTitle": str(m.get("subTitle") or "")[:200],
        "version": str(m.get("version") or "")[:20],
        "description": str(md.get("description") or "")[:2000],
        "publisher": str(md.get("publisher") or "")[:80],
        "pages": strs(md.get("pages")),
        "compatibility": strs(md.get("compatibility")),
    }
    results.append(CheckResult("widget.review", Severity.INFO, "Widget code is reviewed by a maintainer",
                               _REVIEW_NOTE[bool(up.package_top)]))
    # Published in the widget's own shape (plus "type"), so the build reads it back the same way.
    published = {"type": "widget", "name": info["name"], "title": info["title"], "subTitle": info["subTitle"],
                 "version": info["version"],
                 "metadata": {k: info[k] for k in ("description", "publisher", "pages", "compatibility")}}
    return results, json.dumps(published, indent=2, ensure_ascii=False).encode() + b"\n", info


def collections_of(payload: Path) -> list[ParsedCollection]:
    """Parse a published payload's playbooks without re-running the checks."""
    up = read_upload(payload)
    if up.kind == "playbook":
        return parse_collections(up.data)
    if up.kind != "solution-pack":
        return []
    out: dict[str, ParsedCollection] = {}
    for name, raw in sorted((up.members or {}).items()):
        parts = name.split("/")
        if "playbooks" not in parts[:-2] or not name.endswith(".json"):
            continue
        doc = load_json(raw, name)
        if isinstance(doc, dict) and doc.get("@type") == "Workflow":
            coll = parts[parts.index("playbooks") + 1]
            out.setdefault(coll, ParsedCollection(coll, "")).playbooks.append(parse_workflow(doc))
    return list(out.values())


# --- entry point ---------------------------------------------------------------

def process(meta: dict[str, Any], payload: Path, trust: str, hub: HubIndex) -> Processed:
    try:
        up = read_upload(payload)
    except RejectedUpload as exc:
        results = [exc.result]
        return Processed({"_results": results, "checks": [exc.result.to_dict()]}, None, None,
                         "reject", [exc.result.title])

    kind = up.kind
    packaged = bool(up.package_top)
    results = _meta_checks(meta, kind, packaged)
    collections: list[ParsedCollection] = []
    uuids: dict[str, str] = {}
    macros = None
    connector_ops: list[dict[str, Any]] = []
    widget: dict[str, Any] | None = None

    if kind == "playbook":
        collections, uuids, res, body, macros = _playbook(up)
    elif kind == "solution-pack":
        collections, uuids, res, body, macros = _pack(up)
    elif kind == "connector":
        res, body, connector_ops = _connector(up, hub)
    elif kind == "widget":
        res, body, widget = _widget(up, hub)
    results += res
    shots: list[dict[str, Any]] = []
    assets: dict[str, bytes] = {}
    if packaged:
        from . import package
        results += _package_checks(up)
        body = package.build_tgz(up.members or {})
        for i, (name, raw, w, h) in enumerate(package.screenshots(up.members or {}, up.package_top or "")):
            ext = posixpath.splitext(name)[1].lower()
            assets[f"shots/{i + 1}{ext}"] = raw
            shots.append({"file": f"shots/{i + 1}{ext}", "width": w, "height": h, "name": name})

    rows: list[dict[str, Any]] = []
    pack_rows: list[dict[str, Any]] = []
    deps = deps_mod.Dependencies()
    if kind not in CODE_KINDS:
        results += structure.run(collections)
        results += brand.provenance(collections, uuids, hub)
        known = {pb_id for pb_id in uuids}
        deps = deps_mod.collect(collections, known)
        rows = deps_mod.connector_rows(deps, hub)
        results += deps_mod.checks(deps, rows)
        if kind == "solution-pack":
            for d in up.data.get("dependencies") or []:
                if isinstance(d, dict) and d.get("type") == "solutionpack" and d.get("name"):
                    pack_rows.append({"name": d["name"], "version": d.get("version"),
                                      "hub": "available" if d["name"] in hub.packs else "missing"})

    if worst(results) is not Severity.BLOCK:
        results.append(CheckResult("secrets.clean", Severity.PASS, "No credentials found"))

    code = structure.code_steps(collections)
    playbooks = [pb for c in collections for pb in c.playbooks]
    slug = str(meta.get("slug") or "")
    ext = ".zip" if kind == "solution-pack" else ".json"
    filename = f"{slug or 'download'}{ext}"
    if packaged:
        # Manifest values name a file on disk: only plain characters, else fall back to the slug.
        name, ver = str(up.data.get("name") or ""), str(up.data.get("version") or "")
        ok = all(_SAFE_PART.fullmatch(v) and ".." not in v for v in (name, ver))
        filename = f"{name}_{ver}.tgz" if ok else f"{slug or 'download'}.tgz"
    hosted = kind not in CODE_KINDS or packaged
    display = None
    if kind == "connector":
        display = str(up.data.get("label") or up.data.get("name") or "")[:80]
    elif kind == "widget":
        display = str(up.data.get("title") or up.data.get("name") or "")[:80]

    detail: dict[str, Any] = {
        "slug": slug,
        "type": kind,
        "title": meta.get("title", ""),
        "displayName": display,
        "summary": meta.get("summary", ""),
        "description": meta.get("description", ""),
        "useCases": list(meta.get("use_cases") or []),
        "tags": [str(t).lower() for t in meta.get("tags") or []],
        "connectors": [r["name"] for r in rows] or ([up.data.get("name")] if kind == "connector" else []),
        "triggers": sorted({graph.trigger_label(pb) for pb in playbooks}),
        "playbookCount": len(playbooks),
        "stepCount": sum(len(pb.steps) for pb in playbooks),
        "hubStatus": deps_mod.hub_status(rows),
        "hasCode": bool(code),
        "author": {"github": meta.get("author", ""), "trust": trust},
        "version": str(meta.get("version") or (up.data.get("version") if kind != "playbook" else "") or "1.0.0"),
        "minVersion": meta.get("min_version") or (up.data.get("fsrMinCompatibility") if kind == "solution-pack" else None),
        "published": str(meta.get("published") or ""),
        "updated": str(meta.get("updated") or meta.get("published") or ""),
        "source": meta.get("source"),
        "changelog": _changelog(meta.get("changelog")),
        "setup": setup_guide.steps(kind, rows, pack_rows, deps, macros, playbooks, bool(code), meta, packaged),
        "dependencies": {
            "connectors": rows,
            "solutionPacks": pack_rows,
            "modules": [{"name": m, "stock": m in config.CORE_MODULES} for m in sorted(deps.modules)],
        },
        "operations": connector_ops,
        "configuration": _params(up.data["configuration"].get("fields"))
        if kind == "connector" and isinstance(up.data.get("configuration"), dict) else None,
        "widget": widget,
        "checks": [r.to_dict() for r in sorted(results, key=_order)],
        "collections": graph.collections_graph(collections),
        "download": {"path": f"/downloads/{slug}/{filename}", "filename": filename,
                     "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)} if hosted else None,
        "screenshots": [{**s_, "path": f"/downloads/{slug}/{s_['file']}"} for s_ in shots],
        "_results": results,
        "_collections": collections,
        "_name": str(up.data.get("name") or "") if kind in CODE_KINDS else "",
    }
    decision, reasons = policy.decide(results, trust=trust, kind=kind, has_code=bool(code))
    # A manifest-only listing still returns its trimmed info.json (what gets committed),
    # but detail["download"] is None, so the build does not offer it as a download.
    return Processed(detail, body, filename, decision, reasons,
                     files=dict(up.members or {}) if packaged else None, assets=assets or None)


def _changelog(raw: Any) -> list[dict[str, str]]:
    """meta.yaml ``changelog`` entries, newest first, as plain strings."""
    out = []
    for e in raw if isinstance(raw, list) else []:
        if isinstance(e, dict) and e.get("version"):
            out.append({"version": str(e["version"])[:20], "date": str(e.get("date") or "")[:10],
                        "notes": str(e.get("notes") or "")[:500]})
    return out[:50]


_SEV_ORDER = {"block": 0, "warn": 1, "info": 2, "pass": 3}


def _order(r: CheckResult) -> tuple[int, str]:
    return _SEV_ORDER[r.severity.value], r.id

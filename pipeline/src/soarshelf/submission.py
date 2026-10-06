"""Turn an uploaded file + its form data into a content item.

Run by the submission Action on a checkout of ``main``. The author is the
uploader's GitHub login as authenticated by the Worker; anything the form
says about authorship is ignored.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .build import load_trust, tier_for
from .hubindex import HubIndex
from .model import CheckResult, ParsedCollection, Severity
from .process import process

PAYLOAD_NAMES = {"playbook": "playbook.json", "solution-pack": "pack.zip", "connector": "info.json", "widget": "info.json"}
TYPE_DIRS = {"playbook": "playbooks", "solution-pack": "solution-packs", "connector": "connectors", "widget": "widgets"}

# Findings that cost the uploader a strike: they mean someone tried to
# publish a credential or somebody else's content.
STRIKE_PREFIXES = ("secrets.", "brand.copyright", "brand.endorsement", "provenance.")


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60].rstrip("-") or "item"


def unique_slug(content: Path, base: str) -> str:
    taken = {p.name for d in TYPE_DIRS.values() for p in (content / d).glob("*") if p.is_dir()}
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def fingerprints(collections: list[ParsedCollection]) -> set[str]:
    """Workflow uuids and step-structure hashes: what makes two playbooks the same."""
    from .hubindex import structure_key

    out: set[str] = set()
    for c in collections:
        for pb in c.playbooks:
            if pb.uuid:
                out.add(pb.uuid)
            if len(pb.steps) >= 3:
                out.add(structure_key([(st.name, st.type_uuid) for st in pb.steps]))
    return out


def published_playbooks(content: Path) -> dict[str, tuple[str, str]]:
    """Fingerprint -> (slug, author) for every playbook already on the site,
    standalone or inside a solution pack, so a re-upload can be recognised."""
    from .build import item_dirs, payload_of
    from .process import collections_of

    out: dict[str, tuple[str, str]] = {}
    for _kind, item in item_dirs(content):
        author = str((yaml.safe_load((item / "meta.yaml").read_text()) or {}).get("author") or "")
        try:
            colls = collections_of(payload_of(item))
        except Exception:  # a broken published item is the build's problem, not this upload's
            continue
        for key in fingerprints(colls):
            out.setdefault(key, (item.name, author))
    return out


def to_meta(form: dict[str, Any], author: str) -> dict[str, Any]:
    """Map the upload form (docs/api.md SubmissionMeta) onto meta.yaml."""
    def text(key: str, limit: int) -> str:
        return str(form.get(key) or "").strip()[:limit]

    meta: dict[str, Any] = {
        "title": text("title", 80),
        "summary": text("summary", 160),
        "description": text("description", 5000),
        "use_cases": [str(u) for u in (form.get("useCases") or [])][:3],
        "tags": [t for t in (str(x).lower() for x in (form.get("tags") or [])) if re.fullmatch(r"[a-z0-9-]{2,24}", t)][:8],
        "author": author,
        "version": text("version", 20),
        "min_version": text("minVersion", 20) or None,
        "license": "MIT",
        "published": date.today().isoformat(),
    }
    source = text("source", 300)
    if source:
        meta["source"] = source
    return meta


@dataclass
class IntakeResult:
    decision: str
    reasons: list[str]
    checks: list[dict[str, Any]]
    slug: str | None
    kind: str | None
    strike: bool
    written: Path | None
    update: bool = False
    previous_version: str | None = None
    version: str | None = None
    changes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "reasons": self.reasons, "checks": self.checks,
                "slug": self.slug, "type": self.kind, "strike": self.strike,
                "update": self.update, "previousVersion": self.previous_version,
                "version": self.version, "changes": self.changes}


def intake(file: Path, form: dict[str, Any], author: str, content: Path,
           hub: HubIndex | None = None, author_id: int | None = None) -> IntakeResult:
    if not form.get("rightsConfirmed"):
        return IntakeResult("reject", ["Rights confirmation is required"], [], None, None, False, None)

    hub = hub or HubIndex.load()
    meta = to_meta(form, author)
    slug = unique_slug(content, slugify(meta["title"]))
    meta["slug"] = slug
    if author_id is not None:
        meta["author_id"] = author_id
    trust = tier_for(load_trust(content), author, author_id) if author_id is not None else "new"

    res = process(meta, file, trust, hub)
    kind = res.detail.get("type")
    target, blocks = (None, [])
    if res.decision != "reject":
        target, blocks = _existing(res.detail, kind, content, author, author_id)
    previous = None
    if target is not None and not blocks:
        old = yaml.safe_load((target / "meta.yaml").read_text()) or {}
        previous = str(old.get("version") or "")
        own_version = "" if kind == "playbook" else str(res.detail.get("version") or "")   # packs/packages carry one
        meta, problem = _updated_meta(old, meta, own_version, form, previous)
        if problem:
            blocks = [problem]
        else:
            slug = meta["slug"] = target.name
            res = process(meta, file, trust, hub)   # again, so download paths use the item's slug
    results = res.detail["_results"]
    if blocks:
        results.extend(blocks)
        res.decision, res.reasons = "reject", [r.title for r in blocks]
        res.detail["checks"] = [r.to_dict() for r in blocks] + res.detail["checks"]
    strike = any(r.severity is Severity.BLOCK and r.id.startswith(STRIKE_PREFIXES)
                 and r.id not in _NO_STRIKE for r in results)
    update = target is not None and not blocks

    written = None
    if res.decision != "reject" and res.download is not None and kind in TYPE_DIRS:
        written = content / TYPE_DIRS[kind] / slug
        if update:
            shutil.rmtree(written)
        written.mkdir(parents=True)
        meta.pop("slug")
        meta["version"] = meta.get("version") or res.detail.get("version") or "1.0.0"
        (written / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
        if res.files:
            # Package source, committed file by file so the reviewer reads it in the pull request.
            for rel, raw in sorted(res.files.items()):
                dest = written / "package" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
        else:
            (written / PAYLOAD_NAMES[kind]).write_bytes(res.download)

    return IntakeResult(res.decision, res.reasons, res.detail["checks"], slug if written else None,
                        kind, strike, written, update=bool(update and written),
                        previous_version=previous if update else None,
                        version=meta.get("version") if written else None,
                        changes=(meta.get("changelog") or [{}])[0].get("notes") if update and written else None)


# Re-uploading or updating something already listed is not an attempt to pass off content.
_NO_STRIKE = {"provenance.duplicate-item", "provenance.update"}


def _block(id_: str, title: str, detail: str) -> CheckResult:
    return CheckResult(id_, Severity.BLOCK, title, detail)


def _existing(detail: dict[str, Any], kind: str | None, content: Path, author: str,
              author_id: int | None) -> tuple[Path | None, list[CheckResult]]:
    """The uploader's own item this upload is a new version of, or why it can't be published.

    Playbooks and packs are matched by their playbooks (uuids and step structure),
    connectors and widgets by their manifest name. Someone else's item is never
    replaced; an item without a recorded GitHub id can only be changed by a maintainer.
    """
    from .build import item_dirs

    items = item_dirs(content)
    hits: dict[Path, str] = {}
    if kind in ("connector", "widget"):
        name = detail.get("_name") or ""
        if name:
            hits = {item: k for k, item in items if k == kind and _manifest_name(item) == name}
    else:
        keys = fingerprints(detail.get("_collections") or [])
        known = published_playbooks(content) if keys else {}
        slugs = {known[k][0] for k in keys if k in known}
        hits = {item: k for k, item in items if item.name in slugs}
    if not hits:
        return None, []

    out: list[CheckResult] = []
    own: list[Path] = []
    for item, k in sorted(hits.items()):
        meta = yaml.safe_load((item / "meta.yaml").read_text()) or {}
        if str(meta.get("author") or "").lower() != author.lower():
            out.append(_block("provenance.duplicate-item", "Already published",
                              f"This is already on the site as '{item.name}' by another contributor."))
        elif not (isinstance(meta.get("author_id"), int) and meta["author_id"] == author_id):
            out.append(_block("provenance.update", "Can't update this item",
                              f"'{item.name}' is listed under your name but wasn't uploaded from your account. "
                              "Ask a maintainer to update it."))
        elif k != kind:
            out.append(_block("provenance.update", "Already published",
                              f"Part of this is already on the site as your {k} '{item.name}'. "
                              f"Upload a new version of that {k} instead."))
        else:
            own.append(item)
    if out:
        return None, out
    if len(own) > 1:
        names = ", ".join(f"'{i.name}'" for i in own)
        return None, [_block("provenance.update", "Matches more than one of your items",
                             f"This upload matches {names}. Update them one at a time.")]
    return own[0], []


def _manifest_name(item: Path) -> str:
    pkg = item / "package"
    paths = sorted(pkg.glob("*/info.json")) if pkg.is_dir() else [item / "info.json"]
    for p in paths:
        try:
            return str(json.loads(p.read_text()).get("name") or "")
        except (OSError, ValueError, AttributeError):
            continue
    return ""


def _version_key(v: str) -> tuple[int, ...] | None:
    m = re.match(r"^(\d+(?:\.\d+){0,3})", v)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _bump(v: str) -> str:
    key = _version_key(v)
    if key is None:
        return ""
    parts = list(key) + [0] * (3 - len(key))
    parts[-1] += 1
    return ".".join(str(x) for x in parts)


def _updated_meta(old: dict[str, Any], new: dict[str, Any], upload_version: str, form: dict[str, Any],
                  previous: str) -> tuple[dict[str, Any], CheckResult | None]:
    """meta.yaml for a new version: the form's values over the old ones, the first
    publish date kept, and a changelog entry for this version."""
    version = new.get("version") or ""
    if not version:
        # A package carries its own version; a playbook without one gets the next patch number.
        version = upload_version if upload_version and upload_version != previous else _bump(previous)
    a, b = _version_key(version), _version_key(previous)
    if not version or version == previous or (a is not None and b is not None and a <= b):
        return old, _block("provenance.update", "Version must go up",
                           f"Your item is at version {previous or 'unknown'}. Upload it with a higher version.")

    meta = dict(old)
    for k, v in new.items():
        if v not in (None, "", []):
            meta[k] = v
    meta["version"] = version
    meta["published"] = old.get("published") or new.get("published")
    meta["updated"] = date.today().isoformat()
    log = [e for e in (old.get("changelog") or []) if isinstance(e, dict)]
    if not log and previous:
        log = [{"version": previous, "date": str(old.get("published") or ""), "notes": "First published."}]
    notes = re.sub(r"\s+", " ", str(form.get("changes") or "")).strip()[:500] or "Updated."
    meta["changelog"] = [{"version": version, "date": meta["updated"], "notes": notes}, *log][:50]
    return meta, None


_ZW = "\u200b"


def _inert(text: str, limit: int = 300) -> str:
    """User-influenced text in a PR body: no @mentions, links or markup.

    Markup characters are dropped and a zero-width space breaks mentions,
    issue references and anything GitHub would autolink (scheme://, www.,
    bare domains, emails)."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text)[:limit])
    text = re.sub(r"[`*_\[\]<>|#~()!\\&;]", "", text)  # & ; : no HTML entities
    text = re.sub(r"[:.]", lambda m: _ZW + m.group(0) + _ZW, text).replace("@", "@" + _ZW)
    return text


_ICON = {"block": "✗", "warn": "!", "info": "·", "pass": "✓"}


def pr_body(report: dict[str, Any], login: str, submission_id: str) -> str:
    decision = report.get("decision")
    lines = [
        f"Submitted by **{_inert(login, 40)}** through the upload page (submission `{submission_id}`).",
        "",
        "**Auto-publish:** checks passed for this contributor's trust tier."
        if decision == "publish" else "**Needs review**",
        "",
    ]
    if report.get("update"):
        lines[1:1] = ["", f"**Update** of the uploader's own item: version {_inert(report.get('previousVersion') or '?', 20)}"
                          f" → {_inert(report.get('version') or '?', 20)}. Changes: {_inert(report.get('changes') or '')}"]
    for r in report.get("reasons") or []:
        lines.append(f"- {_inert(r)}")
    lines += ["", "<details><summary>Check results</summary>", ""]
    for c in report.get("checks") or []:
        loc = f" ({_inert(c.get('location', ''), 120)})" if c.get("location") else ""
        lines.append(f"- {_ICON.get(c.get('severity'), '?')} {_inert(c.get('title', ''))}{loc}")
    lines += ["", "</details>", "", "The file in this PR is the sanitized output of the pipeline, not the upload."]
    return "\n".join(lines) + "\n"

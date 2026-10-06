"""Turn an uploaded file + its form data into a content item.

Run by the submission Action on a checkout of ``main``. The author is the
uploader's GitHub login as authenticated by the Worker; anything the form
says about authorship is ignored.
"""
from __future__ import annotations

import json
import re
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
        "version": text("version", 20) or "1.0.0",
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

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "reasons": self.reasons, "checks": self.checks,
                "slug": self.slug, "type": self.kind, "strike": self.strike}


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
    results = res.detail["_results"]
    dupes = _already_published(res.detail.get("_collections") or [], content, author) if res.decision != "reject" else []
    if dupes:
        results.extend(dupes)
        res.decision, res.reasons = "reject", [r.title for r in dupes]
        res.detail["checks"] = [r.to_dict() for r in dupes] + res.detail["checks"]
    strike = any(r.severity is Severity.BLOCK and r.id.startswith(STRIKE_PREFIXES)
                 and r.id != "provenance.duplicate-item" for r in results)
    kind = res.detail.get("type")

    written = None
    if res.decision != "reject" and res.download is not None and kind in TYPE_DIRS:
        written = content / TYPE_DIRS[kind] / slug
        written.mkdir(parents=True)
        meta.pop("slug")
        (written / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
        (written / PAYLOAD_NAMES[kind]).write_bytes(res.download)

    return IntakeResult(res.decision, res.reasons, res.detail["checks"], slug if written else None,
                        kind, strike, written)


def _already_published(collections: list[ParsedCollection], content: Path, author: str) -> list[CheckResult]:
    """Playbooks that are already on the site, whatever the upload's type."""
    keys = fingerprints(collections)
    if not keys:
        return []
    known = published_playbooks(content)
    hits = {known[k] for k in keys if k in known}
    out = []
    for slug, owner in sorted(hits):
        if owner.lower() == author.lower():
            detail = f"You already published this as '{slug}'. Updating an existing item from the upload page is coming soon; for now open a pull request that changes it."
        else:
            detail = f"This is already on the site as '{slug}' by another contributor."
        out.append(CheckResult("provenance.duplicate-item", Severity.BLOCK, "Already published", detail))
    return out


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
    for r in report.get("reasons") or []:
        lines.append(f"- {_inert(r)}")
    lines += ["", "<details><summary>Check results</summary>", ""]
    for c in report.get("checks") or []:
        loc = f" ({_inert(c.get('location', ''), 120)})" if c.get("location") else ""
        lines.append(f"- {_ICON.get(c.get('severity'), '?')} {_inert(c.get('title', ''))}{loc}")
    lines += ["", "</details>", "", "The file in this PR is the sanitized output of the pipeline, not the upload."]
    return "\n".join(lines) + "\n"

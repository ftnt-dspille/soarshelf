"""Turn an uploaded file + its form data into a content item.

Run by the submission Action on a checkout of ``main``. The author is the
uploader's GitHub login as authenticated by the Worker; anything the form
says about authorship is ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .build import load_trust
from .hubindex import HubIndex
from .model import Severity
from .process import process

PAYLOAD_NAMES = {"playbook": "playbook.json", "solution-pack": "pack.zip", "connector": "info.json"}
TYPE_DIRS = {"playbook": "playbooks", "solution-pack": "solution-packs", "connector": "connectors"}

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
           hub: HubIndex | None = None) -> IntakeResult:
    if not form.get("rightsConfirmed"):
        return IntakeResult("reject", ["Rights confirmation is required"], [], None, None, False, None)

    hub = hub or HubIndex.load()
    meta = to_meta(form, author)
    slug = unique_slug(content, slugify(meta["title"]))
    meta["slug"] = slug
    trust = load_trust(content).get(author.lower(), "new")

    res = process(meta, file, trust, hub)
    results = res.detail["_results"]
    strike = any(r.severity is Severity.BLOCK and r.id.startswith(STRIKE_PREFIXES) for r in results)
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

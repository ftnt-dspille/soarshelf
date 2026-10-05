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

from .build import load_trust
from .hubindex import HubIndex
from .model import CheckResult, Severity
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


def published_playbooks(content: Path) -> dict[str, tuple[str, str]]:
    """Workflow uuid and step-structure hash -> (slug, author) for every
    playbook already on the site, so a re-upload can be recognised."""
    from .hubindex import structure_key
    from .parse import parse_collections

    out: dict[str, tuple[str, str]] = {}
    for meta_file in content.glob("playbooks/*/meta.yaml"):
        item = meta_file.parent
        author = str((yaml.safe_load(meta_file.read_text()) or {}).get("author") or "")
        try:
            doc = json.loads((item / "playbook.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for coll in doc.get("data") or []:
            for wf in coll.get("workflows") or []:
                if isinstance(wf, dict) and wf.get("uuid"):
                    out[str(wf["uuid"]).lower()] = (item.name, author)
        for c in parse_collections(doc):
            for pb in c.playbooks:
                if len(pb.steps) >= 3:
                    out[structure_key([(st.name, st.type_uuid) for st in pb.steps])] = (item.name, author)
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
    dupes = _already_published(file, content, author) if res.decision != "reject" else []
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


def _already_published(file: Path, content: Path, author: str) -> list[CheckResult]:
    """Playbooks that are already on the site, by uuid or step structure."""
    if file.suffix.lower() != ".json":
        return []
    from .hubindex import structure_key
    from .parse import parse_collections

    known = published_playbooks(content)
    if not known:
        return []
    doc = json.loads(file.read_text(encoding="utf-8-sig"))
    keys = [str(wf.get("uuid")).lower() for c in doc.get("data") or [] for wf in c.get("workflows") or []
            if isinstance(wf, dict) and wf.get("uuid")]
    keys += [structure_key([(st.name, st.type_uuid) for st in pb.steps])
             for c in parse_collections(doc) for pb in c.playbooks if len(pb.steps) >= 3]
    hits = {known[k] for k in keys if k in known}
    out = []
    for slug, owner in sorted(hits):
        if owner.lower() == author.lower():
            detail = f"You already published this as '{slug}'. Updating an existing item from the upload page is coming soon; for now open a pull request that changes it."
        else:
            detail = f"This is already on the site as '{slug}' by another contributor."
        out.append(CheckResult("provenance.duplicate-item", Severity.BLOCK, "Already published", detail))
    return out


def _inert(text: str, limit: int = 300) -> str:
    """User-influenced text in a PR body: no @mentions, links or markup."""
    text = str(text)[:limit].replace("\n", " ")
    text = re.sub(r"[`*_\[\]<>|#~]", "", text)
    return text.replace("@", "@\u200b")


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

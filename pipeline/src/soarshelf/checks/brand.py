"""Trademark use in listing text, and re-uploads of official content.

Naming a product to say what something works with ("blocks an IP on a
FortiGate") is fine. Implying the listing is official, or republishing the
vendor's own content, is not.
"""
from __future__ import annotations

import re
from typing import Any

from ..hubindex import HubIndex, structure_key
from ..model import CheckResult, ParsedCollection, Severity

_MARK = re.compile(r"\b(Forti[A-Z][A-Za-z-]*|Fortinet|FortiGuard|Security Fabric)\b")
_ENDORSE = re.compile(r"\b(official|certified|endorsed|approved|supported) (by )?(fortinet|forti\w+)\b"
                      r"|\b(fortinet|forti\w+)[- ](official|certified|approved)\b", re.I)
_NOTICE = re.compile(r"(copyright|\(c\)|©)\s*(\d{4}[\s,-]*)*\s*fortinet|fortinet,?\s+inc\.?|all rights reserved",
                     re.I)


def listing(meta: dict[str, Any]) -> list[CheckResult]:
    out: list[CheckResult] = []
    title = str(meta.get("title") or "")
    text = " ".join(str(meta.get(k) or "") for k in ("title", "summary", "description"))

    if _ENDORSE.search(text):
        out.append(CheckResult("brand.endorsement", Severity.BLOCK, "Listing claims vendor endorsement",
                               "This site is independent. Remove wording like 'official' or 'certified'."))
    marks = sorted(set(_MARK.findall(text)))
    if _MARK.match(title.strip()):
        out.append(CheckResult("brand.title", Severity.WARN, "Title starts with a product name",
                               "Lead with what the playbook does (e.g. 'Block malicious IPs on the firewall') "
                               "so it doesn't read as a vendor product."))
    if marks:
        out.append(CheckResult("brand.mentions", Severity.INFO, "Product names mentioned",
                               ", ".join(marks) + " - used to describe compatibility only."))
    return out


def content(doc: Any) -> list[CheckResult]:
    """Copyright notices inside the payload mean it was copied, not authored."""
    import json
    m = _NOTICE.search(json.dumps(doc, ensure_ascii=False))
    if m:
        return [CheckResult("brand.copyright", Severity.BLOCK, "Third-party copyright notice in content",
                            f"Found '{m.group(0)}'. Only share content you have the rights to.")]
    return []


def provenance(collections: list[ParsedCollection], uuids: dict[str, str], hub: HubIndex) -> list[CheckResult]:
    """``uuids`` maps playbook/collection uuid -> display path."""
    out: list[CheckResult] = []
    for uuid, where in uuids.items():
        if hub.is_official_uuid(uuid):
            out.append(CheckResult("provenance.official-uuid", Severity.BLOCK,
                                   "Official Content Hub content",
                                   "This is a copy of published vendor content. Link to it on the "
                                   "Content Hub instead of re-uploading it.", where))
    for c in collections:
        for pb in c.playbooks:
            if len(pb.steps) < 3:
                continue
            key = structure_key([(s.name, s.type_uuid) for s in pb.steps])
            pack = hub.official_structures.get(key)
            if pack:
                out.append(CheckResult("provenance.official-structure", Severity.BLOCK,
                                       "Matches an official playbook",
                                       f"Same steps as a playbook in the '{pack}' solution pack.",
                                       f"{c.name} › {pb.name}"))
    return out

"""Who gets auto-published. Every rule lives here so it can be read in one go.

| Tier        | Earned by                              | Auto-publishes when                                  |
|-------------|----------------------------------------|------------------------------------------------------|
| new         | default                                | never - always reviewed                              |
| contributor | 3 approved items, no strikes           | no warnings at all                                   |
| trusted     | promoted by a maintainer               | no warnings about secrets or environment details     |
| maintainer  | runs the site                          | no blocking findings                                 |

Whatever the tier: blocking findings reject; connectors and anything that
runs code always go to a human.

``trust`` must come from an authenticated identity (the uploader's GitHub
login, or the pull request author), never from the item's own meta.yaml.
"""
from __future__ import annotations

from .model import CheckResult, Severity

TIERS = ("new", "contributor", "trusted", "maintainer")


def decide(results: list[CheckResult], *, trust: str, kind: str, has_code: bool) -> tuple[str, list[str]]:
    # One reason per kind of problem: a pack with 50 official playbooks says so once.
    blocks = list(dict.fromkeys(r.title for r in results if r.severity is Severity.BLOCK))
    if blocks:
        return "reject", blocks
    if trust not in TIERS:
        trust = "new"

    reasons = []
    if kind in ("connector", "widget"):
        reasons.append(f"{kind.capitalize()}s are always reviewed")
    if has_code:
        reasons.append("Contains steps that run code")
    if trust == "maintainer":
        return ("review", reasons) if reasons else ("publish", [])
    if trust == "new":
        reasons.append("First submissions from new contributors are reviewed")
    warns = [r for r in results if r.severity is Severity.WARN]
    if trust == "contributor" and warns:
        reasons += [r.title for r in warns]
    if trust == "trusted":
        reasons += [r.title for r in warns if r.id.startswith(("secrets.", "provenance."))]
    reasons = list(dict.fromkeys(reasons))
    return ("review", reasons) if reasons else ("publish", [])

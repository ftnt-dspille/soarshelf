"""Pull-request gate: you can only add or change items credited to you.

Trust tiers are looked up by author, so an item's ``author`` must be the
GitHub account that actually submitted it. Maintainers and the submission
bot (which sets ``author`` from the uploader's authenticated login) may touch
any item.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .build import TYPE_DIRS, load_trust


def changed_items(changed: list[str]) -> set[str]:
    """``content/<type>/<slug>`` for every changed path inside an item."""
    out = set()
    for p in changed:
        parts = Path(p).parts
        if len(parts) >= 4 and parts[0] == "content" and parts[1] in TYPE_DIRS:
            out.add("/".join(parts[:3]))
    return out


def verify(repo: Path, changed: list[str], pr_author: str, bots: set[str],
           trust_repo: Path | None = None) -> list[str]:
    """``trust_repo`` is a checkout of the base branch: tiers must not come
    from the pull request itself, or it could promote its own author."""
    who = pr_author.lower()
    if who in {b.lower() for b in bots}:
        return []
    trust = load_trust((trust_repo or repo) / "content")
    if trust.get(who) == "maintainer":
        return []

    errors = []
    for item in sorted(changed_items(changed)):
        meta_file = repo / item / "meta.yaml"
        if not meta_file.exists():
            errors.append(f"{item}: removing an item needs a maintainer")
            continue
        meta = yaml.safe_load(meta_file.read_text()) or {}
        author = str(meta.get("author") or "")
        if author.lower() != who:
            errors.append(f"{item}: author is '{author}', but this pull request is from '{pr_author}'. "
                          "You can only add or change your own items.")
    return errors

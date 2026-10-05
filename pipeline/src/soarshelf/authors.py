"""Pull-request gate: you can only add or change items credited to you.

Trust tiers are looked up by author, so an item's ``author`` must be the
GitHub account that actually submitted it. Maintainers and the submission
bot (which sets ``author`` from the uploader's authenticated login) may touch
any item.

The gate never runs code from the pull request. CI checks out the base
branch, fetches the PR head as data, and reads the PR's files with
``git show`` (see ``git_reader``).
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .build import TYPE_DIRS, load_trust

MetaReader = Callable[[str], "dict[str, Any] | None"]


def changed_items(changed: list[str]) -> set[str]:
    """``content/<type>/<slug>`` for every changed path inside an item."""
    out = set()
    for p in changed:
        parts = Path(p).parts
        if len(parts) >= 4 and parts[0] == "content" and parts[1] in TYPE_DIRS:
            out.add("/".join(parts[:3]))
    return out


def file_reader(root: Path) -> MetaReader:
    def read(item: str) -> dict[str, Any] | None:
        f = root / item / "meta.yaml"
        return (yaml.safe_load(f.read_text()) or {}) if f.exists() else None
    return read


def git_reader(repo: Path, rev: str) -> MetaReader:
    """Read ``meta.yaml`` at a revision without checking it out."""
    def read(item: str) -> dict[str, Any] | None:
        out = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{item}/meta.yaml"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            return None
        loaded = yaml.safe_load(out.stdout)
        return loaded if isinstance(loaded, dict) else {}
    return read


def _author(meta: dict[str, Any]) -> str:
    return str(meta.get("author") or "").lower()


def verify(changed: list[str], pr_author: str, bots: set[str], trust_root: Path,
           base: MetaReader, head: MetaReader) -> list[str]:
    """``trust_root``/``base`` come from the base branch, ``head`` from the PR.

    Tiers must not come from the pull request itself, or it could promote
    its own author; and an existing item's base author must match too, or a
    PR could take over someone else's item by rewriting ``author``.
    """
    who = pr_author.lower()
    if who in {b.lower() for b in bots}:
        return []
    if load_trust(trust_root / "content").get(who) == "maintainer":
        return []

    errors = []
    for item in sorted(changed_items(changed)):
        before, after = base(item), head(item)
        if after is None:
            errors.append(f"{item}: removing an item needs a maintainer")
            continue
        if before is not None and _author(before) != who:
            errors.append(f"{item}: belongs to '{before.get('author')}'. You can only change your own items.")
            continue
        if _author(after) != who:
            errors.append(f"{item}: author is '{after.get('author')}', but this pull request is from "
                          f"'{pr_author}'. Set author to your GitHub login.")
    return errors

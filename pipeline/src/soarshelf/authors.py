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

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .build import TYPE_DIRS, load_trust, tier_for

MetaReader = Callable[[str], "dict[str, Any] | None"]


SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
# Paths under content/ that aren't items and need no author check.
CONTENT_FILES = {"content/contributors.yaml"}


def changed_items(changed: list[str]) -> tuple[set[str], list[str]]:
    """``content/<type>/<slug>`` for every changed item path, plus errors for
    content paths that can't be classified (unknown folder, odd slug)."""
    out, errors = set(), []
    for p in changed:
        if not p.startswith("content/") or p in CONTENT_FILES:
            continue
        parts = p.split("/")
        if len(parts) >= 4 and parts[1] in TYPE_DIRS and SLUG.match(parts[2]):
            out.add("/".join(parts[:3]))
        else:
            errors.append(f"{p!r}: not a valid item path (content/<type>/<slug>/..., slug [a-z0-9-])")
    return out, errors


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


def _same_account(meta: dict[str, Any], uid: int | None) -> bool:
    """Items record the uploader's numeric id; a reclaimed login has a new one."""
    want = meta.get("author_id")
    return want is None or (uid is not None and want == uid)


def verify(changed: list[str], pr_author: str, bots: set[str], trust_root: Path,
           base: MetaReader, head: MetaReader, pr_author_id: int | None = None) -> list[str]:
    """``trust_root``/``base`` come from the base branch, ``head`` from the PR.

    Tiers must not come from the pull request itself, or it could promote
    its own author; and an existing item's base author must match too, or a
    PR could take over someone else's item by rewriting ``author``.

    Logins can be renamed and re-registered, so the maintainer bypass needs
    ``pr_author_id`` to match contributors.yaml, and an item that records
    ``author_id`` only accepts changes from that account.
    """
    who = pr_author.lower()
    if who in {b.lower() for b in bots}:
        return []
    if pr_author_id is not None and tier_for(load_trust(trust_root / "content"), who, pr_author_id) == "maintainer":
        return []

    items, errors = changed_items(changed)
    for item in sorted(items):
        before, after = base(item), head(item)
        if after is None:
            errors.append(f"{item}: removing an item needs a maintainer")
            continue
        if before is not None and (_author(before) != who or not _same_account(before, pr_author_id)):
            errors.append(f"{item}: belongs to '{before.get('author')}'. You can only change your own items.")
            continue
        if not _same_account(after, pr_author_id):
            errors.append(f"{item}: author_id doesn't match your GitHub account. Remove it or set it to yours.")
            continue
        if _author(after) != who:
            errors.append(f"{item}: author is '{after.get('author')}', but this pull request is from "
                          f"'{pr_author}'. Set author to your GitHub login.")
    return errors

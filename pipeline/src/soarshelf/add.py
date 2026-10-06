"""``soarshelf add``: a maintainer adds an item from their own machine.

Runs the same intake as an upload through the site (every check, the same
sanitizing, the same files under ``content/``), without the upload form, its
Turnstile check or the daily limit. The result goes to main through a pull
request like any other change, so the author gate and CI still apply.

The source is a local file (playbook export, solution pack zip, connector or
widget ``.tgz`` or ``info.json``) or a GitHub URL. For a URL the folder holding
info.json is packaged like an uploaded .tgz (so the site offers a download),
and the URL becomes the item's ``source`` link:

    https://github.com/OWNER/REPO                    info.json found in the repo
    https://github.com/OWNER/REPO/tree/BRANCH/PATH   info.json under PATH
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_REPO_URL = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$")


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def github_identity() -> tuple[str, int]:
    """The signed-in ``gh`` account: the login and numeric id the item is credited to."""
    u = json.loads(_gh("api", "user"))
    return u["login"], int(u["id"])


def fetch_package(url: str, dest: Path) -> tuple[Path, str]:
    """Package the folder holding the repository's info.json as a .tgz at ``dest``.

    Returns (path, source url). The site rebuilds the download from this
    source, the same as for an uploaded .tgz.
    """
    import io
    import tarfile

    from .package import build_tgz

    m = _REPO_URL.match(url)
    if not m:
        raise SystemExit(f"not a GitHub repository URL: {url}")
    owner, repo, branch, sub = m.groups()
    info = json.loads(_gh("api", f"repos/{owner}/{repo}"))
    if info["private"]:
        raise SystemExit(f"{owner}/{repo} is private: the source link must be public")
    branch = branch or info["default_branch"]
    raw = subprocess.run(["gh", "api", f"repos/{owner}/{repo}/tarball/{branch}"], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        files = {}
        for i in tf.getmembers():
            if i.isfile():
                f = tf.extractfile(i)
                files[i.name.split("/", 1)[1]] = f.read() if f else b""
    prefix = f"{sub.strip('/')}/" if sub else ""
    found = sorted((n for n in files if n.startswith(prefix) and n.endswith("info.json")
                    and "node_modules/" not in n and "/dist/" not in f"/{n}" and "test" not in n.lower()),
                   key=lambda n: n.count("/"))
    if not found:
        raise SystemExit(f"no info.json in {owner}/{repo}{' under ' + sub if sub else ''}")
    folder = found[0][:-len("info.json")]
    manifest = json.loads(files[found[0]])
    top = str(manifest.get("name") or repo)
    picked = {f"{top}/{n[len(folder):]}": b for n, b in files.items() if n.startswith(folder)}
    dest.write_bytes(build_tgz(picked))
    return dest, url.rstrip("/")


def form_defaults(manifest: dict[str, Any]) -> dict[str, str]:
    """Listing fields a connector or widget manifest already carries."""
    title = manifest.get("label") or manifest.get("title") or manifest.get("name") or ""
    md = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
    summary = manifest.get("description") or manifest.get("subTitle") or md.get("description") or ""
    return {"title": str(title), "summary": _first_sentence(str(summary)),
            "version": str(manifest.get("version") or "")}


def _first_sentence(text: str, limit: int = 160) -> str:
    """The first sentence, or the text cut at a word boundary, within ``limit``."""
    text = " ".join(text.split())
    end = text.find(". ")
    if 0 < end < limit:
        return text[:end + 1]
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _manifest_of(file: Path) -> Any:
    """The connector/widget manifest in a .json or .tgz, if there is one."""
    if file.name.endswith(".json"):
        try:
            return json.loads(file.read_text())
        except ValueError:
            return None
    if file.name.endswith((".tgz", ".tar.gz")):
        from .package import normalise, read_tgz
        try:
            top, files, _ = normalise(read_tgz(file.read_bytes()))
            return json.loads(files[f"{top}/info.json"])
        except Exception:      # the intake reports what is wrong with it
            return None
    return None


def add(source: str, form: dict[str, Any], content: Path, *, dry_run: bool) -> tuple[Any, Path | None]:
    from .submission import intake

    login, uid = github_identity()
    with tempfile.TemporaryDirectory() as tmp:
        if source.startswith("https://"):
            file, link = fetch_package(source, Path(tmp) / "package.tgz")
            form.setdefault("source", link)
        else:
            file = Path(source)
        manifest = _manifest_of(file)
        if isinstance(manifest, dict) and ("operations" in manifest or "metadata" in manifest):
            for k, v in form_defaults(manifest).items():
                if v and not form.get(k):
                    form[k] = v
        form["rightsConfirmed"] = True

        target = content
        if dry_run:
            target = Path(tmp) / "content"
            shutil.copytree(content, target)
        res = intake(file, form, login, target, author_id=uid)
        return res, (None if dry_run else res.written)

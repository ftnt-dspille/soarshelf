"""Resolve a playbook from inline YAML, an absolute path, or a git repo.

Everything lands in the run's `project/` directory; the return value is the
playbook filename *relative to* that directory, which is what ansible-runner
wants.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from urllib.parse import urlsplit, urlunsplit

import yaml
from connectors.core.connector import ConnectorError

GIT_CLONE_TIMEOUT = 120


def _write_inline(project_dir: str, text: str) -> str:
    if not text or not text.strip():
        raise ConnectorError("Inline playbook is empty.")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConnectorError(f"Inline playbook is not valid YAML: {exc}") from exc
    if not isinstance(parsed, list):
        raise ConnectorError(
            "Inline playbook must be a YAML list of plays, "
            f"got {type(parsed).__name__}."
        )
    target = os.path.join(project_dir, "playbook.yml")
    with open(target, "w") as fh:
        yaml.safe_dump(parsed, fh, default_flow_style=False, sort_keys=False)
    return "playbook.yml"


def _copy_path(project_dir: str, path: str) -> str:
    if not os.path.isabs(path):
        raise ConnectorError(f"Playbook path must be absolute: {path}")
    if not os.path.isfile(path):
        raise ConnectorError(f"Playbook not found: {path}")
    name = os.path.basename(path)
    shutil.copy(path, os.path.join(project_dir, name))
    # Bring the playbook's neighbours (roles/, group_vars/, ...) along.
    src_dir = os.path.dirname(path)
    for sibling in ("roles", "group_vars", "host_vars", "files", "templates", "vars"):
        s = os.path.join(src_dir, sibling)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(project_dir, sibling), dirs_exist_ok=True)
    return name


def _inject_token(repo: str, token: str) -> str:
    parts = urlsplit(repo)
    if parts.scheme not in ("http", "https"):
        raise ConnectorError("A git token can only be used with an http(s) repo URL.")
    netloc = f"{token}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _clone(project_dir: str, repo: str, branch: str | None,
           playbook: str | None, token: str | None, ssh_key_path: str | None) -> str:
    if not playbook:
        raise ConnectorError("A playbook path within the repository is required for a git source.")
    if os.path.isabs(playbook) or ".." in playbook.split("/"):
        raise ConnectorError(f"Playbook path within the repository must be relative: {playbook}")

    if shutil.which("git") is None:
        raise ConnectorError(
            "git is not installed on the FortiSOAR node, so the 'git' source type "
            "is unavailable. Install git, or use the 'inline' or 'path' source type."
        )
    url = _inject_token(repo, token) if token else repo
    cmd = ["git", "clone", "--depth", "1", "--no-single-branch"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [url, project_dir]

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if ssh_key_path:
        env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key_path} -o IdentitiesOnly=yes"

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=GIT_CLONE_TIMEOUT, env=env,
        )
    except FileNotFoundError as exc:
        raise ConnectorError(
            "git is not installed on the FortiSOAR node, so the 'git' source type "
            "is unavailable. Install git, or use the 'inline' or 'path' source type."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ConnectorError(f"git clone timed out after {GIT_CLONE_TIMEOUT}s.") from exc
    if proc.returncode != 0:
        # Never echo the URL back — it may carry the token.
        raise ConnectorError(f"git clone failed (rc={proc.returncode}): {proc.stderr.strip()[:500]}")

    if not os.path.isfile(os.path.join(project_dir, playbook)):
        raise ConnectorError(f"Playbook '{playbook}' not found in the cloned repository.")
    return playbook


def resolve(params, project_dir: str, ssh_key_path: str | None = None) -> str:
    """Stage the playbook into project_dir; return its relative filename."""
    if params.source_type == "inline":
        return _write_inline(project_dir, params.playbook or "")
    if params.source_type == "path":
        return _copy_path(project_dir, params.playbook or "")
    if params.source_type == "git":
        return _clone(
            project_dir, params.git_repo or "", params.git_branch,
            params.playbook, params.git_token, ssh_key_path,
        )
    raise ConnectorError(f"Unsupported source type: {params.source_type}")

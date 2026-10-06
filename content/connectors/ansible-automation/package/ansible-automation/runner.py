"""ansible-runner wrapper: private_data_dir lifecycle, environment isolation,
credential handling, and result normalization.

Deliberately never shells out to `ansible-playbook`. The structured event
stream is the entire reason this connector exists.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
import uuid
from typing import Any

from connectors.core.connector import ConnectorError, get_logger

from .constants import (
    ANSIBLE_ROOT,
    COLLECTIONS_DIRNAME,
    KEYS_DIRNAME,
    KNOWN_HOSTS_FILENAME,
    LOGGER_NAME,
    RUNS_DIRNAME,
    STDOUT_TAIL_BYTES,
    TERMINAL_STATUSES,
)
from .models import HostResult, RunResult

logger = get_logger(LOGGER_NAME)


# --------------------------------------------------------------------------- paths


def ensure_root(config) -> str:
    """Create the connector-owned runtime tree. 0700 — it holds key material."""
    root = ANSIBLE_ROOT
    for path in (
        root,
        os.path.join(root, RUNS_DIRNAME),
        os.path.join(root, KEYS_DIRNAME),
        collections_path(config),
    ):
        try:
            os.makedirs(path, mode=0o700, exist_ok=True)
        except OSError as exc:
            raise ConnectorError(f"Cannot create Ansible runtime directory {path}: {exc}") from exc
    known_hosts = os.path.join(root, KNOWN_HOSTS_FILENAME)
    if not os.path.exists(known_hosts):
        open(known_hosts, "a").close()
        os.chmod(known_hosts, 0o600)
    if not os.access(root, os.W_OK):
        raise ConnectorError(f"Ansible runtime directory is not writable: {root}")
    return root


def collections_path(config) -> str:
    return config.collections_path or os.path.join(ANSIBLE_ROOT, COLLECTIONS_DIRNAME)


def ansible_bin_dir() -> str | None:
    """Directory holding the ansible-* console scripts.

    FortiSOAR installs connector dependencies under a `conn_pkgs` prefix (see
    the integrations venv's pip.conf), so the scripts do NOT sit next to
    sys.executable and are NOT on PATH. ansible-runner shells out to
    `ansible-playbook`, so without this every run returns rc=127.
    """
    try:
        import ansible  # noqa: PLC0415
    except ImportError:
        return None
    prefix = os.path.abspath(
        os.path.join(os.path.dirname(ansible.__file__), *([os.pardir] * 4))
    )
    candidate = os.path.join(prefix, "bin")
    if os.path.isdir(candidate):
        return candidate
    fallback = os.path.join(sys.prefix, "conn_pkgs", "bin")
    return fallback if os.path.isdir(fallback) else None


def run_dir(ident: str) -> str:
    return os.path.join(ANSIBLE_ROOT, RUNS_DIRNAME, ident)


def new_run(config) -> tuple[str, str]:
    """Create a fresh private_data_dir. Returns (ident, path)."""
    ensure_root(config)
    ident = uuid.uuid4().hex[:16]
    base = run_dir(ident)
    for sub in ("project", "inventory", "env", "artifacts"):
        os.makedirs(os.path.join(base, sub), mode=0o700, exist_ok=True)
    return ident, base


def reap_runs(config) -> int:
    """Delete run directories older than the configured retention. Best effort."""
    base = os.path.join(ANSIBLE_ROOT, RUNS_DIRNAME)
    if not os.path.isdir(base):
        return 0
    cutoff = time.time() - (config.run_retention_hours * 3600)
    removed = 0
    for name in os.listdir(base):
        path = os.path.join(base, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            logger.warning("could not reap run directory %s", name)
    return removed


# ---------------------------------------------------------------------- credentials


def write_key(config, base: str) -> str | None:
    """Write the configured private key 0600 inside the run dir.

    Run-scoped rather than long-lived: it is removed with the run directory,
    and by cleanup() even when artifacts are kept.
    """
    if not config.ssh_private_key:
        return None
    key_text = config.ssh_private_key.strip()
    if not key_text.endswith("\n"):
        key_text += "\n"
    path = os.path.join(base, "env", "ssh_key")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as fh:
        fh.write(key_text)
    return path


def passwords(config) -> dict:
    """runner `passwords` maps prompt regexes to answers — keeps secrets off argv."""
    out = {}
    if config.ssh_password:
        out[r"^SSH password:\s*$"] = config.ssh_password
    if config.become_password:
        out[r"^BECOME password.*:\s*$"] = config.become_password
    return out


def build_envvars(config, base: str) -> dict:
    """Explicit environment. The uwsgi environment is not inherited wholesale."""
    known_hosts = os.path.join(ANSIBLE_ROOT, KNOWN_HOSTS_FILENAME)
    env = {
        "ANSIBLE_COLLECTIONS_PATH": collections_path(config),
        "ANSIBLE_HOST_KEY_CHECKING": "True" if config.host_key_checking else "False",
        "ANSIBLE_RETRY_FILES_ENABLED": "False",
        "ANSIBLE_LOCAL_TEMP": os.path.join(base, "tmp"),
        "ANSIBLE_REMOTE_TEMP": "~/.ansible/tmp",
        "ANSIBLE_FORKS": str(config.forks),
        "ANSIBLE_NOCOLOR": "1",
        "ANSIBLE_DEPRECATION_WARNINGS": "False",
        "HOME": base,
    }
    bin_dir = ansible_bin_dir()
    if bin_dir:
        # ansible-runner shells out to ansible-playbook; conn_pkgs/bin is not on PATH.
        env["PATH"] = bin_dir + os.pathsep + os.environ.get(
            "PATH", "/usr/local/bin:/usr/bin:/bin")
    else:
        env["PATH"] = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    if config.host_key_checking:
        env["ANSIBLE_SSH_ARGS"] = (
            f"-o ControlMaster=auto -o ControlPersist=60s -o UserKnownHostsFile={known_hosts}"
        )
    os.makedirs(env["ANSIBLE_LOCAL_TEMP"], mode=0o700, exist_ok=True)
    return env


def cleanup(base: str, keep_artifacts: bool) -> None:
    """Always destroy key material; drop the whole run unless asked to keep it."""
    key_path = os.path.join(base, "env", "ssh_key")
    try:
        if os.path.exists(key_path):
            os.remove(key_path)
    except OSError:
        logger.warning("could not remove run-scoped ssh key")
    if not keep_artifacts:
        shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------------- results


def _read_stdout(base: str) -> str:
    path = os.path.join(base, "artifacts")
    if not os.path.isdir(path):
        return ""
    for ident in os.listdir(path):
        candidate = os.path.join(path, ident, "stdout")
        if os.path.isfile(candidate):
            with open(candidate, errors="replace") as fh:
                data = fh.read()
            return data[-STDOUT_TAIL_BYTES:]
    return ""


def _task_events(runner_obj) -> list[dict]:
    """Flatten runner events into something a playbook step can iterate."""
    tasks = []
    try:
        events = runner_obj.events
    except Exception:  # noqa: BLE001 - runner raises assorted things on a dead run
        return tasks
    for event in events:
        if event.get("event") not in (
            "runner_on_ok", "runner_on_failed", "runner_on_skipped",
            "runner_on_unreachable", "runner_item_on_ok", "runner_item_on_failed",
        ):
            continue
        data = event.get("event_data") or {}
        res = data.get("res") or {}
        tasks.append({
            "task": data.get("task"),
            "host": data.get("host"),
            "event": event.get("event"),
            "changed": bool(res.get("changed")),
            "failed": bool(res.get("failed")),
            "msg": res.get("msg"),
            "stdout": res.get("stdout"),
            "result": {k: v for k, v in res.items()
                       if k not in ("stdout", "stdout_lines", "stderr_lines", "invocation")},
        })
    return tasks


def normalize(runner_obj, ident: str, base: str, keep_artifacts: bool) -> dict:
    """Build the uniform RunResult. Never raises on a failed play."""
    stats = getattr(runner_obj, "stats", None) or {}
    hosts: dict[str, HostResult] = {}
    for name in set().union(*[set(v) for v in stats.values() if isinstance(v, dict)] or [set()]):
        hosts[name] = HostResult(
            ok=(stats.get("ok") or {}).get(name, 0),
            changed=(stats.get("changed") or {}).get(name, 0),
            failures=(stats.get("failures") or {}).get(name, 0),
            unreachable=(stats.get("dark") or {}).get(name, 0),
            skipped=(stats.get("skipped") or {}).get(name, 0),
            rescued=(stats.get("rescued") or {}).get(name, 0),
            ignored=(stats.get("ignored") or {}).get(name, 0),
        )

    def total(key: str) -> int:
        return sum((stats.get(key) or {}).values())

    result = RunResult(
        ident=ident,
        status=getattr(runner_obj, "status", "unknown"),
        rc=getattr(runner_obj, "rc", None),
        ok=total("ok"),
        changed=total("changed"),
        failed=total("failures"),
        unreachable=total("dark"),
        skipped=total("skipped"),
        hosts=hosts,
        tasks=_task_events(runner_obj),
        stdout_tail=_read_stdout(base),
        artifacts_path=base if keep_artifacts else None,
    )
    return result.model_dump()


def status_from_disk(ident: str) -> dict:
    """Read a run's state without holding the runner object (async polling)."""
    base = run_dir(ident)
    if not os.path.isdir(base):
        raise ConnectorError(f"No such run: {ident}")
    artifacts = os.path.join(base, "artifacts")
    payload: dict[str, Any] = {"ident": ident, "status": "unknown", "rc": None}
    if not os.path.isdir(artifacts):
        return payload
    for entry in os.listdir(artifacts):
        adir = os.path.join(artifacts, entry)
        for field, cast in (("status", str), ("rc", int)):
            fpath = os.path.join(adir, field)
            if os.path.isfile(fpath):
                with open(fpath) as fh:
                    raw = fh.read().strip()
                try:
                    payload[field] = cast(raw)
                except ValueError:
                    payload[field] = raw
        spath = os.path.join(adir, "stats")
        if os.path.isfile(spath):
            try:
                with open(spath) as fh:
                    payload["stats"] = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass
    payload["is_terminal"] = payload.get("status") in TERMINAL_STATUSES
    payload["stdout_tail"] = _read_stdout(base)
    return payload

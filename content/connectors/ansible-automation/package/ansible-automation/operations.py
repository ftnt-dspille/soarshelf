"""Operation implementations.

Contract: a failed Ansible task is a *result* (status/rc in the payload), not an
exception. ConnectorError is reserved for connector-level failures — bad config,
unwritable runtime root, missing playbook, git failure, timeout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from connectors.core.connector import ConnectorError, get_logger

from . import inventory as inventory_mod
from . import runner as runner_mod
from . import sources
from .constants import LOGGER_NAME, MIN_CORE_VERSION
from .models import Config, ModuleParams, PlaybookParams, RoleParams

logger = get_logger(LOGGER_NAME)

GALAXY_TIMEOUT = 300


def _config(config: dict) -> Config:
    try:
        return Config(**(config or {}))
    except Exception as exc:  # noqa: BLE001 - surface pydantic detail as connector error
        raise ConnectorError(f"Invalid connector configuration: {exc}") from exc


def _params(model, params: dict):
    try:
        return model(**(params or {}))
    except Exception as exc:  # noqa: BLE001
        raise ConnectorError(f"Invalid operation parameters: {exc}") from exc


def _import_runner():
    try:
        import ansible_runner  # noqa: PLC0415 - deliberately lazy
    except ImportError as exc:
        raise ConnectorError(
            "ansible-runner is not installed in the integrations environment. "
            "Reinstall the connector so its requirements.txt is applied."
        ) from exc
    return ansible_runner


def _core_version() -> str:
    try:
        import ansible.release  # noqa: PLC0415
    except ImportError as exc:
        raise ConnectorError(
            "ansible-core is not installed in the integrations environment. "
            "Reinstall the connector so its requirements.txt is applied."
        ) from exc
    return ansible.release.__version__


def _venv_bin(name: str) -> str:
    """Resolve a CLI shipped by ansible-core, never the workflow venv's copy.

    FortiSOAR installs connector dependencies under a `conn_pkgs` prefix (see
    the integrations venv's pip.conf), so the console scripts do NOT land next
    to sys.executable. Derive the prefix from the installed package itself,
    which is correct regardless of how the venv is laid out.
    """
    candidates = []
    try:
        import ansible  # noqa: PLC0415
        # <prefix>/lib/pythonX.Y/site-packages/ansible/__init__.py -> <prefix>/bin
        prefix = os.path.abspath(
            os.path.join(os.path.dirname(ansible.__file__), *([os.pardir] * 4))
        )
        candidates.append(os.path.join(prefix, "bin", name))
    except ImportError:
        pass
    candidates.append(os.path.join(sys.prefix, "conn_pkgs", "bin", name))
    candidates.append(os.path.join(os.path.dirname(sys.executable), name))

    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which(name)
    if not found:
        raise ConnectorError(
            f"{name} not found in the integrations environment. "
            "Reinstall the connector so its requirements.txt is applied."
        )
    return found


def _ensure_bin_on_path() -> None:
    """Put conn_pkgs/bin on the *process* PATH.

    ansible-runner resolves `ansible-playbook` with shutil.which against
    os.environ at run() time; conn_pkgs/bin is not on the uwsgi worker's PATH,
    so without this a cold worker's first run returns rc=127 ("The command was
    not found or was not executable"). Idempotent.
    """
    bin_dir = runner_mod.ansible_bin_dir()
    if not bin_dir:
        return
    current = os.environ.get("PATH", "")
    if bin_dir not in current.split(os.pathsep):
        os.environ["PATH"] = bin_dir + os.pathsep + current


# Run once at import so the PATH is correct before the first handler in a
# freshly recycled worker, not just from the first _execute onward.
try:
    _ensure_bin_on_path()
except Exception:  # noqa: BLE001 - never let a PATH tweak break import
    pass


def _execute(cfg: Config, p, *, playbook=None, module=None, module_args=None,
             role=None) -> dict:
    ansible_runner = _import_runner()
    _ensure_bin_on_path()
    runner_mod.reap_runs(cfg)
    ident, base = runner_mod.new_run(cfg)
    keep = p.keep_artifacts
    key_path = None

    try:
        key_path = runner_mod.write_key(cfg, base)
        project = os.path.join(base, "project")

        playbook_file = None
        if playbook is not None:
            playbook_file = sources.resolve(playbook, project, key_path)
        if role is not None:
            if p.roles_path and os.path.isdir(p.roles_path):
                shutil.copytree(p.roles_path, os.path.join(project, "roles"),
                                dirs_exist_ok=True)

        inv = inventory_mod.normalize(p.inventory, cfg.default_inventory)
        inv = inventory_mod.apply_connection_vars(inv, cfg)

        kwargs = {
            "private_data_dir": base,
            "ident": ident,
            "inventory": inv,
            "envvars": runner_mod.build_envvars(cfg, base),
            "extravars": p.extra_vars or None,
            "verbosity": p.verbosity if p.verbosity is not None else cfg.verbosity,
            "quiet": True,
            "cancel_callback": None,
        }
        if key_path:
            kwargs["ssh_key"] = cfg.ssh_private_key
        pw = runner_mod.passwords(cfg)
        if pw:
            kwargs["passwords"] = pw
        if p.limit:
            kwargs["limit"] = p.limit
        if p.tags:
            kwargs["tags"] = ",".join(p.tags)
        if p.skip_tags:
            kwargs["skip_tags"] = ",".join(p.skip_tags)

        cmdline = []
        if p.check_mode:
            cmdline.append("--check")
        if p.diff:
            cmdline.append("--diff")
        if cmdline:
            kwargs["cmdline"] = " ".join(cmdline)

        if playbook_file is not None:
            kwargs["playbook"] = playbook_file
        elif module is not None:
            kwargs["module"] = module
            kwargs["host_pattern"] = p.hosts or "all"
            if module_args:
                kwargs["module_args"] = module_args
        elif role is not None:
            kwargs["role"] = role
            kwargs["host_pattern"] = p.hosts or "all"
            if p.roles_path:
                kwargs["roles_path"] = os.path.join(project, "roles")

        timeout = p.timeout if p.timeout is not None else cfg.default_timeout

        if not p.wait:
            # Async: hand back the ident immediately, poll with get_run_status.
            thread, runner_obj = ansible_runner.run_async(**kwargs)
            keep = True
            return {
                "ident": ident,
                "status": getattr(runner_obj, "status", "starting"),
                "is_terminal": False,
                "artifacts_path": base,
                "message": "Run started. Poll with get_run_status.",
            }

        kwargs["timeout"] = timeout
        runner_obj = ansible_runner.run(**kwargs)
        result = runner_mod.normalize(runner_obj, ident, base, keep)
        if result.get("status") == "timeout":
            result["message"] = f"Run exceeded the {timeout}s timeout and was terminated."
        return result
    finally:
        if p.wait:
            runner_mod.cleanup(base, keep)
        elif key_path and os.path.exists(key_path):
            # Async runs keep their directory but must not keep key material
            # once the runner has read it.
            pass


# ------------------------------------------------------------------- operations


def run_playbook(config: dict, params: dict) -> dict:
    cfg = _config(config)
    p = _params(PlaybookParams, params)
    return _execute(cfg, p, playbook=p)


def run_module(config: dict, params: dict) -> dict:
    cfg = _config(config)
    p = _params(ModuleParams, params)
    return _execute(cfg, p, module=p.module, module_args=p.module_args)


def run_role(config: dict, params: dict) -> dict:
    cfg = _config(config)
    p = _params(RoleParams, params)
    return _execute(cfg, p, role=p.role)


def get_run_status(config: dict, params: dict) -> dict:
    _config(config)
    ident = (params or {}).get("ident")
    if not ident:
        raise ConnectorError("Parameter 'ident' is required.")
    return runner_mod.status_from_disk(ident)


def get_run_artifacts(config: dict, params: dict) -> dict:
    _config(config)
    ident = (params or {}).get("ident")
    if not ident:
        raise ConnectorError("Parameter 'ident' is required.")
    base = runner_mod.run_dir(ident)
    if not os.path.isdir(base):
        raise ConnectorError(f"No such run: {ident}")
    payload = runner_mod.status_from_disk(ident)
    artifacts = os.path.join(base, "artifacts")
    events: list[dict] = []
    facts: dict = {}
    if os.path.isdir(artifacts):
        for entry in os.listdir(artifacts):
            edir = os.path.join(artifacts, entry, "job_events")
            if os.path.isdir(edir):
                import json  # noqa: PLC0415
                for fname in sorted(os.listdir(edir)):
                    try:
                        with open(os.path.join(edir, fname)) as fh:
                            events.append(json.load(fh))
                    except (json.JSONDecodeError, OSError):
                        continue
            fdir = os.path.join(artifacts, entry, "fact_cache")
            if os.path.isdir(fdir):
                import json  # noqa: PLC0415
                for host in os.listdir(fdir):
                    try:
                        with open(os.path.join(fdir, host)) as fh:
                            facts[host] = json.load(fh)
                    except (json.JSONDecodeError, OSError):
                        continue
    payload["events"] = events
    payload["fact_cache"] = facts
    return payload


def cancel_run(config: dict, params: dict) -> dict:
    _config(config)
    ident = (params or {}).get("ident")
    if not ident:
        raise ConnectorError("Parameter 'ident' is required.")
    base = runner_mod.run_dir(ident)
    if not os.path.isdir(base):
        raise ConnectorError(f"No such run: {ident}")
    # ansible-runner honours a `cancel` marker written into the private data dir
    # via its pid file; terminate the process group it recorded.
    pidfile = os.path.join(base, "pid")
    if not os.path.isfile(pidfile):
        return {"ident": ident, "canceled": False,
                "message": "Run has no live process; it may already be finished."}
    with open(pidfile) as fh:
        pid = int(fh.read().strip())
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return {"ident": ident, "canceled": False, "message": "Process already exited."}
    except OSError as exc:
        raise ConnectorError(f"Could not cancel run {ident}: {exc}") from exc
    return {"ident": ident, "canceled": True}


def validate_playbook(config: dict, params: dict) -> dict:
    cfg = _config(config)
    p = _params(PlaybookParams, params)
    runner_mod.ensure_root(cfg)
    ident, base = runner_mod.new_run(cfg)
    try:
        project = os.path.join(base, "project")
        name = sources.resolve(p, project, None)
        cmd = [_venv_bin("ansible-playbook"), "--syntax-check", name]
        env = dict(os.environ)
        env.update(runner_mod.build_envvars(cfg, base))
        proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                              timeout=60, env=env)
        return {
            "valid": proc.returncode == 0,
            "rc": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        raise ConnectorError("Syntax check timed out.") from exc
    finally:
        runner_mod.cleanup(base, keep_artifacts=False)


def list_collections(config: dict, params: dict) -> dict:
    cfg = _config(config)
    runner_mod.ensure_root(cfg)
    env = dict(os.environ)
    env["ANSIBLE_COLLECTIONS_PATH"] = runner_mod.collections_path(cfg)
    proc = subprocess.run([_venv_bin("ansible-galaxy"), "collection", "list"],
                          capture_output=True, text=True, timeout=60, env=env)
    collections = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "Collection")):
            continue
        parts = line.split()
        if len(parts) == 2 and "." in parts[0]:
            collections.append({"name": parts[0], "version": parts[1]})
    return {
        "collections_path": runner_mod.collections_path(cfg),
        "count": len(collections),
        "collections": collections,
    }


def install_collection(config: dict, params: dict) -> dict:
    cfg = _config(config)
    name = (params or {}).get("collection")
    if not name:
        raise ConnectorError("Parameter 'collection' is required.")
    runner_mod.ensure_root(cfg)
    path = runner_mod.collections_path(cfg)
    cmd = [_venv_bin("ansible-galaxy"), "collection", "install", name, "-p", path]
    if (params or {}).get("force"):
        cmd.append("--force")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=GALAXY_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise ConnectorError(f"Collection install timed out after {GALAXY_TIMEOUT}s.") from exc
    if proc.returncode != 0:
        raise ConnectorError(
            f"Collection install failed (rc={proc.returncode}): {proc.stderr.strip()[:500]}"
        )
    return {"installed": name, "collections_path": path, "stdout": proc.stdout.strip()}


def list_modules(config: dict, params: dict) -> dict:
    cfg = _config(config)
    runner_mod.ensure_root(cfg)
    env = dict(os.environ)
    env["ANSIBLE_COLLECTIONS_PATH"] = runner_mod.collections_path(cfg)
    proc = subprocess.run([_venv_bin("ansible-doc"), "--list", "--type", "module"],
                          capture_output=True, text=True, timeout=180, env=env)
    modules = []
    for line in proc.stdout.splitlines():
        name = line.split()[0] if line.strip() else ""
        if name and not name.startswith("["):
            modules.append(name)
    filter_text = (params or {}).get("filter")
    if filter_text:
        modules = [m for m in modules if filter_text.lower() in m.lower()]
    return {"count": len(modules), "modules": sorted(modules)}


def check_health(config: dict) -> bool:
    cfg = _config(config)
    version = _core_version()
    _import_runner()
    parsed = tuple(int(x) for x in version.split(".")[:2])
    if parsed < MIN_CORE_VERSION:
        raise ConnectorError(
            f"ansible-core {version} is below the required "
            f"{'.'.join(str(v) for v in MIN_CORE_VERSION)}."
        )
    runner_mod.ensure_root(cfg)
    logger.info("ansible-automation healthy: ansible-core %s", version)
    return True

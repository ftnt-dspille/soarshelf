"""Inventory normalization.

A step may hand over an INI string, a YAML string, a dict, a list of hosts, or
nothing at all (in which case the connector configuration's default is used).
ansible-runner accepts a dict or a raw string, so the job here is to decide
which and to inject connection credentials from config without ever putting a
secret on the command line.
"""

from __future__ import annotations

from typing import Any

import yaml


def _hosts_from_list(hosts: list) -> dict:
    return {"all": {"hosts": {str(h): {} for h in hosts}}}


def normalize(raw: Any, default: str | None = None) -> Any:
    """Return something ansible-runner accepts as `inventory`.

    dict  -> passed through (runner writes it as YAML)
    list  -> wrapped into an `all` group
    str   -> YAML if it parses to a mapping, otherwise handed over as INI text
    None  -> the configured default, else implicit localhost
    """
    if raw in (None, "", {}, []):
        raw = default
    if raw in (None, ""):
        return {"all": {"hosts": {"localhost": {"ansible_connection": "local"}}}}

    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return _hosts_from_list(raw)

    text = str(raw)
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return text
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return _hosts_from_list(parsed)
    return text


def apply_connection_vars(inventory: Any, config) -> Any:
    """Inject ansible_user / become settings as group vars on `all`.

    Only applied when the inventory is a mapping — an operator who hands over
    raw INI is assumed to be specifying connection details themselves. The SSH
    key and passwords are *not* injected here: the key goes to a run-scoped
    file referenced by `ssh_key` and passwords go through runner's `passwords`
    channel, so neither is ever written into inventory or argv.
    """
    if not isinstance(inventory, dict):
        return inventory

    group_vars: dict[str, Any] = {}
    if config.ssh_username:
        group_vars["ansible_user"] = config.ssh_username
    if config.become:
        group_vars["ansible_become"] = True
        group_vars["ansible_become_method"] = config.become_method
        if config.become_user:
            group_vars["ansible_become_user"] = config.become_user
    # Injected whenever configured, independent of the become toggle, because a
    # play may request `become: true` itself. Ansible only consumes the runner
    # prompt secret with --ask-become-pass, so a non-interactive run needs it as
    # a var. It lands in the run-scoped inventory file (owner-only), not argv.
    if config.become_password:
        group_vars["ansible_become_password"] = config.become_password
    if not group_vars:
        return inventory

    inventory = dict(inventory)
    all_group = dict(inventory.get("all") or {})
    existing = dict(all_group.get("vars") or {})
    # Inventory-supplied values win over connector defaults.
    group_vars.update(existing)
    all_group["vars"] = group_vars
    if "hosts" not in all_group and "children" not in all_group:
        all_group["hosts"] = {"localhost": {"ansible_connection": "local"}}
    inventory["all"] = all_group
    return inventory

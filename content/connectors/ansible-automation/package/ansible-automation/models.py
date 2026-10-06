"""pydantic v2 models for connector config, operation params, and results.

Django-free. The 8.0 integrations runtime ships pydantic 2.13; 7.6.x ships 2.11.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import DEFAULT_FORKS, DEFAULT_RETENTION_HOURS, DEFAULT_TIMEOUT


def _coerce_mapping(value: Any) -> dict:
    """FSR playbook steps hand over dicts *or* JSON strings. Accept both."""
    if value in (None, "", {}):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"expected a JSON object, got unparseable string: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("expected a JSON object")
        return parsed
    raise ValueError(f"expected a mapping or JSON string, got {type(value).__name__}")


def _coerce_list(value: Any) -> list[str]:
    """Accept a list, or a comma-separated string (how the UI sends tags)."""
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    raise ValueError(f"expected a list or comma-separated string, got {type(value).__name__}")


class Config(BaseModel):
    """Connector configuration. Secrets arrive already decrypted by FSR."""

    model_config = ConfigDict(extra="ignore")

    default_inventory: str | None = None
    ssh_username: str | None = None
    ssh_private_key: str | None = None
    ssh_password: str | None = None
    become: bool = False
    become_method: str = "sudo"
    become_user: str | None = None
    become_password: str | None = None
    host_key_checking: bool = True
    collections_path: str | None = None
    default_timeout: int = DEFAULT_TIMEOUT
    forks: int = DEFAULT_FORKS
    verbosity: int = 0
    run_retention_hours: int = DEFAULT_RETENTION_HOURS

    @field_validator("verbosity", mode="before")
    @classmethod
    def _verbosity(cls, v: Any) -> int:
        # The UI select sends strings; "Default" means "no explicit level".
        if v in (None, "", "Default"):
            return 0
        return int(v)

    @field_validator("default_timeout", "forks", "run_retention_hours", mode="before")
    @classmethod
    def _ints(cls, v: Any) -> Any:
        if v in (None, ""):
            raise ValueError("must be an integer")
        return int(v)


class ExecuteParams(BaseModel):
    """Params shared by run_playbook / run_module / run_role."""

    model_config = ConfigDict(extra="ignore")

    inventory: Any = None
    hosts: str = "all"
    extra_vars: dict = Field(default_factory=dict)
    limit: str | None = None
    tags: list[str] = Field(default_factory=list)
    skip_tags: list[str] = Field(default_factory=list)
    check_mode: bool = False
    diff: bool = False
    verbosity: int | None = None
    timeout: int | None = None
    wait: bool = True
    keep_artifacts: bool = False

    @field_validator("extra_vars", mode="before")
    @classmethod
    def _extra_vars(cls, v: Any) -> dict:
        return _coerce_mapping(v)

    @field_validator("tags", "skip_tags", mode="before")
    @classmethod
    def _tags(cls, v: Any) -> list[str]:
        return _coerce_list(v)

    @field_validator("verbosity", "timeout", mode="before")
    @classmethod
    def _opt_ints(cls, v: Any) -> Any:
        # "Default" is the select's null value: fall back to the connector config.
        if v in (None, "", "Default"):
            return None
        return int(v)

    @field_validator("check_mode", "diff", "wait", "keep_artifacts", mode="before")
    @classmethod
    def _bools(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower() in ("true", "yes", "1")
        if v is None:
            return False
        return v


class PlaybookParams(ExecuteParams):
    source_type: Literal["inline", "path", "git"] = "inline"
    playbook: str | None = None          # inline YAML, or a path, or path-within-repo for git
    git_repo: str | None = None
    git_branch: str | None = None
    git_token: str | None = None


class ModuleParams(ExecuteParams):
    module: str
    module_args: str | None = None


class RoleParams(ExecuteParams):
    role: str
    roles_path: str | None = None


class HostResult(BaseModel):
    ok: int = 0
    changed: int = 0
    failures: int = 0
    unreachable: int = 0
    skipped: int = 0
    rescued: int = 0
    ignored: int = 0


class RunResult(BaseModel):
    """Uniform return shape for every execute operation.

    A failed Ansible task is a *result*, not an exception: playbook authors
    branch on `status` / `failed`, they do not scrape stdout.
    """

    model_config = ConfigDict(extra="allow")

    ident: str
    status: str
    rc: int | None = None
    ok: int = 0
    changed: int = 0
    failed: int = 0
    unreachable: int = 0
    skipped: int = 0
    hosts: dict[str, HostResult] = Field(default_factory=dict)
    tasks: list[dict] = Field(default_factory=list)
    stdout_tail: str = ""
    artifacts_path: str | None = None

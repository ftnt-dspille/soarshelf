"""Shared result types. Field names mirror docs/data-contract.md."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    PASS = "pass"
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


_RANK = {Severity.PASS: 0, Severity.INFO: 1, Severity.WARN: 2, Severity.BLOCK: 3}


@dataclass
class CheckResult:
    id: str
    severity: Severity
    title: str
    detail: str = ""
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        if self.location is None:
            d.pop("location")
        return d


def worst(results: list[CheckResult]) -> Severity:
    return max((r.severity for r in results), key=_RANK.__getitem__, default=Severity.PASS)


class RejectedUpload(Exception):
    """Raised by intake when a file must not be processed any further."""

    def __init__(self, result: CheckResult) -> None:
        super().__init__(result.title)
        self.result = result


@dataclass
class Step:
    """One playbook step, reduced to what the checks and the viewer need."""
    id: str
    name: str
    type_uuid: str
    arguments: dict[str, Any]
    x: int = 0
    y: int = 0
    group: str = ""     # uuid of the block the step sits in; its x/y are then relative to the block


@dataclass
class ParsedPlaybook:
    name: str
    description: str
    trigger_step: str | None
    steps: list[Step]
    routes: list[dict[str, Any]]
    uuid: str = ""
    groups: list[dict[str, Any]] = field(default_factory=list)   # notes and blocks, as exported


@dataclass
class ParsedCollection:
    name: str
    description: str
    playbooks: list[ParsedPlaybook] = field(default_factory=list)

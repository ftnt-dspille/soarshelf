"""Shape limits, code execution and graph integrity."""
from __future__ import annotations

from .. import config
from ..model import CheckResult, ParsedCollection, Severity
from ..parse import route_ends


def code_steps(collections: list[ParsedCollection]) -> list[str]:
    """Display paths of steps that run arbitrary code on the platform."""
    out = []
    for c in collections:
        for pb in c.playbooks:
            for s in pb.steps:
                family = config.STEP_TYPES.get(s.type_uuid, ("", "other"))[1]
                if family == "code" or s.arguments.get("connector") in config.CODE_CONNECTORS:
                    out.append(f"{pb.name} › {s.name}")
    return out


def run(collections: list[ParsedCollection]) -> list[CheckResult]:
    out: list[CheckResult] = []
    playbooks = [(c, pb) for c in collections for pb in c.playbooks]

    if not playbooks:
        return [CheckResult("structure.empty", Severity.BLOCK, "No playbooks found")]
    if len(playbooks) > config.MAX_PLAYBOOKS:
        out.append(CheckResult("structure.too-many", Severity.BLOCK,
                               f"{len(playbooks)} playbooks (limit {config.MAX_PLAYBOOKS})"))

    for c, pb in playbooks:
        where = f"{c.name} › {pb.name}"
        if len(pb.steps) > config.MAX_STEPS_PER_PLAYBOOK:
            out.append(CheckResult("structure.too-many-steps", Severity.BLOCK,
                                   f"{len(pb.steps)} steps (limit {config.MAX_STEPS_PER_PLAYBOOK})", "", where))
        ids = {s.id for s in pb.steps}
        if pb.trigger_step and pb.trigger_step not in ids:
            out.append(CheckResult("structure.trigger", Severity.WARN, "Trigger step is missing", "", where))
        dangling = sum(1 for r in pb.routes if not set(route_ends(r)) <= ids)
        if dangling:
            out.append(CheckResult("structure.routes", Severity.WARN,
                                   f"{dangling} route(s) point at missing steps", "", where))
        unknown = sorted({s.type_uuid for s in pb.steps if s.type_uuid not in config.STEP_TYPES})
        if unknown:
            out.append(CheckResult("structure.step-type", Severity.WARN, "Unrecognised step types",
                                   ", ".join(unknown), where))

    code = code_steps(collections)
    if code:
        out.append(CheckResult("structure.code", Severity.WARN, "Runs code on the platform",
                               "Code steps are always reviewed by a maintainer: " + "; ".join(code[:10])
                               + (f" and {len(code) - 10} more" if len(code) > 10 else "")))
    if not out:
        out.append(CheckResult("structure.ok", Severity.PASS, "Playbook structure is valid"))
    return out

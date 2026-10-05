"""Generate the per-item setup checklist from what the checks found."""
from __future__ import annotations

from typing import Any

from .config import CORE_MODULES


def _step(kind: str, title: str, detail: str = "") -> dict[str, str]:
    return {"kind": kind, "title": title, "detail": detail}


def steps(kind: str, connectors: list[dict[str, Any]], packs: list[dict[str, Any]], deps: Any,
          macros: Any, playbooks: list[Any], has_code: bool, meta: dict[str, Any]) -> list[dict[str, str]]:
    if kind == "connector":
        return [
            _step("note", "Review the source first",
                  f"Read the code at [{meta.get('source')}]({meta.get('source')}) before installing. "
                  "Connectors run with the platform's privileges."),
            _step("install-connector", "Build and install the connector",
                  "Follow the repository's build instructions, then upload the package from "
                  "**Content Hub › Manage**."),
            _step("configure-connector", "Add a configuration",
                  "Enter the credentials for your environment and run the health check."),
        ]

    out: list[dict[str, str]] = []
    for p in packs:
        if p["hub"] == "available":
            out.append(_step("install-pack", f"Install the {p['name']} solution pack",
                             "It's on the Content Hub. Install it before this item."))
        else:
            out.append(_step("install-pack", f"Get the {p['name']} solution pack",
                             "It isn't on the Content Hub. Check the description for where to find it."))

    for c in connectors:
        ops = ", ".join(f"`{o}`" for o in c["operations"]) or "none"
        if c["hub"] == "missing":
            out.append(_step("install-connector", f"Get the {c['label']} connector",
                             f"**Not on the Content Hub.** You'll need this custom connector "
                             f"(built with {c['version'] or 'an unknown version'}). Operations used: {ops}."))
        else:
            note = ""
            if c["hub"] == "version-mismatch":
                note = (f" This item was built with {c['version']}; the hub has {c['hubVersion']}. "
                        "Check the operations below exist in the version you install.")
            out.append(_step("install-connector", f"Install the {c['label']} connector",
                             f"Find **{c['label']}** on the Content Hub and install it.{note} "
                             f"Operations used: {ops}."))
        out.append(_step("configure-connector", f"Configure {c['label']} and set a default",
                         "Connector configuration links are removed from downloads, so each step uses "
                         "the connector's **default** configuration."))

    custom = sorted(m for m in deps.modules if m not in CORE_MODULES)
    if custom:
        out.append(_step("custom-module", "Make sure these modules exist",
                         ", ".join(f"`{m}`" for m in custom)
                         + " aren't core modules. Install the solution pack that provides them, "
                           "or create them in **Module Editor**."))

    names = [m.get("name") for m in macros or [] if isinstance(m, dict) and m.get("name")]
    if names:
        out.append(_step("note", "Set global variables",
                         "Values were cleared from the download. Set: " + ", ".join(f"`{n}`" for n in names)))

    if kind == "solution-pack":
        out.append(_step("import", "Upload the solution pack",
                         "Open **Content Hub › Manage**, upload the zip, then install it."))
    else:
        out.append(_step("import", "Import the playbook collection",
                         "Open **Settings › Import Wizard**, upload the JSON file and review "
                         "the summary before importing."))

    if has_code:
        out.append(_step("note", "Read the code steps",
                         "This item contains steps that run code on your platform. Read them before activating."))

    triggered = sorted({p.name for p in playbooks if getattr(p, "trigger_step", None)})
    out.append(_step("activate", "Review and activate",
                     "Downloads are always **inactive**. Open each playbook, check it suits your "
                     "environment, then activate the ones you want"
                     + (f" ({len(triggered)} playbook{'s' if len(triggered) != 1 else ''})." if triggered else ".")))
    return out

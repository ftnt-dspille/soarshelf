"""Limits, taxonomy and step-type knowledge. Change policy here, not in the checks."""
from __future__ import annotations

# --- Upload limits -----------------------------------------------------------

MAX_PLAYBOOK_BYTES = 2 * 1024 * 1024
MAX_PACK_BYTES = 20 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_UNCOMPRESSED = 100 * 1024 * 1024
MAX_ZIP_RATIO = 100            # per member; higher looks like a zip bomb
MAX_JSON_DEPTH = 64
MAX_PLAYBOOKS = 200
MAX_STEPS_PER_PLAYBOOK = 500

# Members a solution pack may contain. Anything else is dropped from the
# rebuilt download and reported. Connector tarballs are not allowed in packs:
# connector code is reviewed and listed separately.
PACK_MEMBER_SUFFIXES = (".json",)

# --- Use-case taxonomy -------------------------------------------------------
# (id, label, description, icon). Display order is list order.

USE_CASES: list[tuple[str, str, str, str]] = [
    ("triage", "Alert triage", "Classify, deduplicate and prioritise incoming alerts.", "filter"),
    ("enrichment", "Threat intel enrichment", "Look up IPs, domains, hashes and URLs against intel sources.", "search"),
    ("phishing", "Phishing response", "Analyse reported emails and clean up mailboxes.", "mail"),
    ("containment", "Containment", "Block indicators, isolate hosts, disable accounts.", "shield"),
    ("vulnerability", "Vulnerability management", "Ingest scan results and drive remediation.", "bug"),
    ("identity", "Identity & access", "Account lifecycle, MFA resets, privilege reviews.", "user"),
    ("case-management", "Case management", "Incident creation, escalation, SLAs and hand-offs.", "folder"),
    ("ingestion", "Data ingestion", "Pull alerts, events and feeds into the platform.", "download"),
    ("notification", "Notification & ticketing", "Email, chat and ticketing integrations.", "bell"),
    ("reporting", "Reporting", "Metrics, summaries and scheduled reports.", "chart"),
    ("utility", "Utilities", "Reusable building blocks and helper playbooks.", "wrench"),
]
USE_CASE_IDS = {u[0] for u in USE_CASES}

# --- Step types ----------------------------------------------------------------
# uuid -> (label, family). Family drives node colour in the viewer.

STEP_TYPES: dict[str, tuple[str, str]] = {
    "f414d039-bb0d-4e59-9c39-a8f1e880b18a": ("Manual trigger", "trigger"),
    "ea155646-3821-4542-9702-b246da430a8d": ("On create", "trigger"),
    "9300bf69-5063-486d-b3a6-47eb9da24872": ("On update", "trigger"),
    "ef350fda-1771-477a-8f90-16f68cd7e5cb": ("On delete", "trigger"),
    "aed55d18-1974-4743-b061-7f5a4292e657": ("Pre-create", "trigger"),
    "0d375573-1c17-47bb-9790-934cff200ec4": ("Pre-update", "trigger"),
    "a987479e-9c96-46b0-9598-7f0b35e16ad2": ("Pre-delete", "trigger"),
    "df26c7a2-4166-4ca5-91e5-548e24c01b5f": ("API endpoint", "trigger"),
    "b348f017-9a94-471f-87f8-ce88b6a7ad62": ("Referenced", "trigger"),
    "0f2e6d50-9cb9-403f-9990-85dc5fbb571d": ("Trigger block", "trigger"),
    "0bfed618-0316-11e7-93ae-92361f002671": ("Connector", "connector"),
    "1fdd14cc-d6b4-4335-a3af-ab49c8ed2fd8": ("Code snippet", "code"),
    "0109f35d-090b-4a2b-bd8a-94cbc3508562": ("Utilities", "utility"),
    "ee73e569-2188-43fe-a7f0-1964ba82a4de": ("Utility function", "utility"),
    "04d0cf46-b6a8-42c4-8683-60a7eaa69e8f": ("Set variable", "utility"),
    "9dcc4bf5-b6cf-4a5c-b545-1fac3b9e33e6": ("Set result", "end"),
    "6832e556-b9c7-497a-babe-feda3bd27dbf": ("Wait", "utility"),
    "12254cf5-5db7-4b1a-8cb1-3af081924b28": ("Decision", "decision"),
    "dc61b68b-4967-4e82-b4ed-a1315aa81998": ("Manual decision", "human"),
    "dc6ac63d-c5a5-472f-9eb4-6b18473a98b8": ("Manual task", "human"),
    "fc04082a-d7dc-4299-96fb-6837b1baa0fe": ("Manual input", "human"),
    "6832e556-b9c7-497a-babe-feda3bd27dcg": ("Approval", "human"),
    "a19333c2-c822-11ed-afa1-0242ac120002": ("Approval", "human"),
    "2597053c-e718-44b4-8394-4d40fe26d357": ("Create record", "record"),
    "b593663d-7d13-40ce-a3a3-96dece928722": ("Update record", "record"),
    "b593663d-7d13-40ce-a3a3-96dece928770": ("Find records", "record"),
    "7b221880-716b-4726-a2ca-5e568d330b3e": ("Ingest bulk feed", "record"),
    "74932bdc-b8b6-4d24-88c4-1a4dfbc524f3": ("Reference a playbook", "reference"),
    "ab3b2e02-5e77-4ed6-8ebd-580f390063a5": ("Remote playbook", "reference"),
    "9f85dabc-dbc8-4d0a-905d-c99b2ef06b71": ("Reference block", "reference"),
    "b593663d-7d13-40ce-a3a3-96dece928728": ("Map playbook", "reference"),
    "949779e9-c4c2-4652-9ad2-c1875be6be54": ("API call", "utility"),
    "4c0019b2-055c-44d0-968c-678a0c2d762e": ("Send email", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928778": ("Send email", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928789": ("Fetch email", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928723": ("Download file", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928724": ("File from string", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928796": ("Attachment from file", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928725": ("SFTP", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928726": ("Remote command", "code"),
    "b593663d-7d13-40ce-a3a3-96dece928745": ("Database connector", "utility"),
    "b593663d-7d13-40ce-a3a3-96dece928799": ("Database query", "utility"),
    "b104e839-fc31-48b3-8c50-7e9433f33d79": ("Set API keys", "utility"),
}

TRIGGER_LABELS = {u: v[0] for u, v in STEP_TYPES.items() if v[1] == "trigger"}

# Connectors whose operations run arbitrary code on the platform. A playbook
# using any of these gets hasCode=true and always goes to human review.
CODE_CONNECTORS = {"code-snippet", "code-runner", "jscode-snippet", "ssh"}

# Core modules every installation has. Anything else a playbook writes to
# comes from a solution pack or is custom and needs explaining in the setup.
CORE_MODULES = {
    "agents", "alerts", "announcements", "appliances", "approvals", "assets",
    "attachments", "campaigns", "comments", "communication", "companies",
    "devices", "events", "hunt", "incidents", "indicators", "keys",
    "leave_schedules", "managers", "metafield_templates", "mitre_groups",
    "mitre_mitigations", "mitre_software", "mitre_sub_techniques",
    "mitre_tactics", "mitre_techniques", "people", "routers", "saved_reports",
    "scans", "scenario", "scripts", "shifts", "sla_template", "tasks",
    "tenants", "threat_actors", "threat_intel_feeds", "threat_intel_reports",
    "vulnerabilities", "warrooms", "workspaces",
}

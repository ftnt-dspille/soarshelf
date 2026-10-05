import copy
import json

import pytest

from soarshelf.hubindex import HubIndex

CONNECTOR = "0bfed618-0316-11e7-93ae-92361f002671"
SET_VAR = "04d0cf46-b6a8-42c4-8683-60a7eaa69e8f"
MANUAL = "f414d039-bb0d-4e59-9c39-a8f1e880b18a"
CODE = "1fdd14cc-d6b4-4335-a3af-ab49c8ed2fd8"

_DOC = {
    "type": "workflow_collections",
    "macros": [],
    "data": [{
        "@type": "WorkflowCollection",
        "name": "Enrichment",
        "description": "",
        "uuid": "11111111-1111-4111-8111-111111111111",
        "image": None,
        "workflows": [{
            "@type": "Workflow",
            "name": "Enrich IP",
            "description": "",
            "isActive": True,
            "uuid": "22222222-2222-4222-8222-222222222222",
            "owners": ["/api/3/teams/33333333-3333-4333-8333-333333333333"],
            "triggerStep": "/api/3/workflow_steps/aaaaaaaa-0000-4000-8000-000000000001",
            "steps": [
                {"@type": "WorkflowStep", "name": "Start", "stepType": f"/api/3/workflow_step_types/{MANUAL}",
                 "uuid": "aaaaaaaa-0000-4000-8000-000000000001", "left": "20", "top": "20",
                 "arguments": {"resources": ["alerts"], "title": "Enrich"}},
                {"@type": "WorkflowStep", "name": "Lookup", "stepType": f"/api/3/workflow_step_types/{CONNECTOR}",
                 "uuid": "aaaaaaaa-0000-4000-8000-000000000002", "left": "20", "top": "140",
                 "arguments": {"connector": "virustotal", "operation": "get_ip_reputation", "version": "3.0.0",
                               "config": "44444444-4444-4444-8444-444444444444",
                               "params": {"ip": "{{ vars.input.records[0].sourceIp }}"}}},
                {"@type": "WorkflowStep", "name": "Save", "stepType": f"/api/3/workflow_step_types/{SET_VAR}",
                 "uuid": "aaaaaaaa-0000-4000-8000-000000000003", "left": "20", "top": "260",
                 "arguments": {"verdict": "{{ vars.steps.Lookup.data }}"}},
            ],
            "routes": [
                {"sourceStep": "/api/3/workflow_steps/aaaaaaaa-0000-4000-8000-000000000001",
                 "targetStep": "/api/3/workflow_steps/aaaaaaaa-0000-4000-8000-000000000002", "uuid": "r1"},
                {"sourceStep": "/api/3/workflow_steps/aaaaaaaa-0000-4000-8000-000000000002",
                 "targetStep": "/api/3/workflow_steps/aaaaaaaa-0000-4000-8000-000000000003", "uuid": "r2"},
            ],
        }],
    }],
}


@pytest.fixture
def doc():
    return copy.deepcopy(_DOC)


@pytest.fixture
def hub():
    return HubIndex(
        snapshot="2026-01-01",
        connectors={"virustotal": {"label": "VirusTotal", "version": "3.0.0", "versions": ["2.0.0", "3.0.0"],
                                   "category": "Threat Intelligence",
                                   "operations": ["get_ip_reputation", "get_file_reputation"]}},
        packs={"sOARFramework": {"label": "SOAR Framework", "version": "1.0.0"}},
    )


@pytest.fixture
def meta():
    return {"slug": "enrich-ip", "title": "Enrich alert source IPs", "summary": "Looks up the source IP.",
            "use_cases": ["enrichment"], "author": "someone", "published": "2026-01-01"}


@pytest.fixture
def write_json(tmp_path):
    def _w(obj, name="playbook.json"):
        p = tmp_path / name
        p.write_text(json.dumps(obj))
        return p
    return _w

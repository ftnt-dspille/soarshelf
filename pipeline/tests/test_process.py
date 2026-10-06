import json

from soarshelf import policy
from soarshelf.checks import brand
from soarshelf.hubindex import _h
from soarshelf.model import CheckResult, Severity
from soarshelf.process import process
from soarshelf.sanitize import sanitize_collections

from .conftest import CODE


def test_sanitize_strips_environment(doc):
    doc["macros"] = [{"name": "SOC_EMAIL", "value": "real@acme.com"}]
    clean, results = sanitize_collections(doc)
    wf = clean["data"][0]["workflows"][0]
    assert "owners" not in wf
    assert wf["isActive"] is False
    assert wf["steps"][1]["arguments"]["config"] == ""
    assert clean["macros"][0]["value"] == ""
    assert {"sanitize.deactivated", "sanitize.config", "sanitize.macro"} <= {r.id for r in results}
    assert doc["data"][0]["workflows"][0]["isActive"] is True        # input untouched


def test_people_iris_scrubbed(doc):
    doc["data"][0]["workflows"][0]["steps"][2]["arguments"]["assignee"] = \
        "/api/3/people/55555555-5555-4555-8555-555555555555"
    clean, results = sanitize_collections(doc)
    assert clean["data"][0]["workflows"][0]["steps"][2]["arguments"]["assignee"] == ""
    assert "sanitize.iri" in {r.id for r in results}


def test_clean_playbook_end_to_end(doc, hub, meta, write_json):
    res = process(meta, write_json(doc), "contributor", hub)
    d = res.detail
    assert res.decision == "publish", res.reasons
    assert d["hubStatus"] == "complete"
    assert d["connectors"] == ["virustotal"]
    assert d["triggers"] == ["Manual trigger"]
    assert d["collections"][0]["playbooks"][0]["nodes"][1]["family"] == "connector"
    assert len(d["collections"][0]["playbooks"][0]["edges"]) == 2
    downloaded = json.loads(res.download)
    assert downloaded["data"][0]["workflows"][0]["isActive"] is False
    assert [s["kind"] for s in d["setup"]] == ["install-connector", "configure-connector", "import", "activate"]


def test_new_contributor_always_reviewed(doc, hub, meta, write_json):
    assert process(meta, write_json(doc), "new", hub).decision == "review"


def test_secret_rejects(doc, hub, meta, write_json):
    doc["data"][0]["workflows"][0]["steps"][1]["arguments"]["params"]["apikey"] = "0123456789abcdefLIVE"
    res = process(meta, write_json(doc), "maintainer", hub)
    assert res.decision == "reject"


def test_custom_connector_flagged(doc, hub, meta, write_json):
    doc["data"][0]["workflows"][0]["steps"][1]["arguments"]["connector"] = "acme-internal-cmdb"
    res = process(meta, write_json(doc), "contributor", hub)
    assert res.detail["hubStatus"] == "needs-custom"
    assert res.detail["dependencies"]["connectors"][0]["hub"] == "missing"
    assert res.decision == "review"


def test_unknown_operation_is_version_mismatch(doc, hub, meta, write_json):
    doc["data"][0]["workflows"][0]["steps"][1]["arguments"]["operation"] = "brand_new_op"
    assert process(meta, write_json(doc), "trusted", hub).detail["hubStatus"] == "version-mismatch"


def test_code_step_needs_review(doc, hub, meta, write_json):
    step = doc["data"][0]["workflows"][0]["steps"][2]
    step["stepType"] = f"/api/3/workflow_step_types/{CODE}"
    step["arguments"] = {"connector": "code-snippet", "operation": "python_inline_code_editor",
                         "params": {"python_function": "print(1)"}}
    res = process(meta, write_json(doc), "trusted", hub)
    assert res.detail["hasCode"] is True
    assert res.decision == "review"


def test_official_uuid_rejected(doc, hub, meta, write_json):
    hub.official_uuids = {_h("22222222-2222-4222-8222-222222222222")}
    res = process(meta, write_json(doc), "maintainer", hub)
    assert res.decision == "reject"
    assert "Official Content Hub content" in res.reasons


def test_copyright_notice_rejected(doc, hub, meta, write_json):
    doc["data"][0]["description"] = "Copyright (c) 2024 Fortinet, Inc. All rights reserved."
    assert process(meta, write_json(doc), "maintainer", hub).decision == "reject"


def test_listing_brand_rules():
    sev = lambda m: {r.id: r.severity for r in brand.listing(m)}
    assert sev({"title": "Official Fortinet phishing playbook"})["brand.endorsement"] is Severity.BLOCK
    assert sev({"title": "FortiGate blocker"})["brand.title"] is Severity.WARN
    assert sev({"title": "Block IPs", "summary": "Pushes blocks to a FortiGate"})["brand.mentions"] is Severity.INFO


def test_meta_required_and_use_case(doc, hub, write_json):
    res = process({"slug": "x", "use_cases": ["nonsense"]}, write_json(doc), "maintainer", hub)
    ids = {c["id"] for c in res.detail["checks"]}
    assert {"meta.required", "meta.use-case"} <= ids and res.decision == "reject"


def test_policy_tiers():
    warn = [CheckResult("secrets.email", Severity.WARN, "Email address")]
    other = [CheckResult("deps.custom-connector", Severity.WARN, "Custom")]
    assert policy.decide([], trust="new", kind="playbook", has_code=False)[0] == "review"
    assert policy.decide([], trust="contributor", kind="playbook", has_code=False)[0] == "publish"
    assert policy.decide(other, trust="contributor", kind="playbook", has_code=False)[0] == "review"
    assert policy.decide(other, trust="trusted", kind="playbook", has_code=False)[0] == "publish"
    assert policy.decide(warn, trust="trusted", kind="playbook", has_code=False)[0] == "review"
    assert policy.decide([], trust="trusted", kind="connector", has_code=False)[0] == "review"
    assert policy.decide(warn, trust="maintainer", kind="playbook", has_code=False)[0] == "publish"
    assert policy.decide([], trust="maintainer", kind="connector", has_code=False)[0] == "review"
    assert policy.decide([], trust="maintainer", kind="playbook", has_code=True)[0] == "review"
    assert policy.decide([], trust="bogus", kind="playbook", has_code=False)[0] == "review"


def test_reasons_are_not_repeated():
    from soarshelf.model import CheckResult, Severity
    from soarshelf.policy import decide
    many = [CheckResult("provenance.official", Severity.BLOCK, "Official Content Hub content")] * 5
    assert decide(many, trust="new", kind="playbook", has_code=False) == ("reject", ["Official Content Hub content"])


def _zip_pack(path, doc, extra=()):
    import zipfile
    coll = doc["data"][0]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("pk/info.json", json.dumps({"name": "pk", "version": "1.0.0"}))
        for wf in coll["workflows"]:
            zf.writestr(f"pk/playbooks/{coll['name']}/{wf['name']}.json", json.dumps({**wf, "@type": "Workflow"}))
        for name in extra:
            zf.writestr(f"pk/{name}", "x")
    return path


def test_pack_repo_docs_are_ignored_not_rejected(doc, hub, meta, tmp_path):
    res = process(meta, _zip_pack(tmp_path / "p.zip", doc, ["README.md", "LICENSE", ".gitignore", "docs/changelog.md"]),
                  "maintainer", hub)
    ids = {r.id: r for r in res.checks}
    assert "pack.installers" not in ids
    assert ids["pack.ignored-files"].severity is Severity.INFO


def test_pack_with_other_files_rejected(doc, hub, meta, tmp_path):
    res = process(meta, _zip_pack(tmp_path / "p.zip", doc, ["README.md", "setup.exe"]), "maintainer", hub)
    assert res.decision == "reject"
    blocked = [r for r in res.checks if r.id == "pack.installers"]
    assert len(blocked) == 1 and "setup.exe" in blocked[0].detail and "README" not in blocked[0].detail


def test_official_copies_reported_once_per_check(doc, hub, meta, write_json):
    wfs = doc["data"][0]["workflows"]
    hub.official_uuids = {_h(w["uuid"]) for w in wfs}
    res = process(meta, write_json(doc), "maintainer", hub)
    found = [r for r in res.checks if r.id.startswith("provenance.")]
    assert len(found) == 1
    assert str(len(wfs)) in found[0].detail


def test_pack_notes_are_tallied_once(doc, hub, meta, tmp_path):
    res = process(meta, _zip_pack(tmp_path / "p.zip", doc), "maintainer", hub)
    ids = [r.id for r in res.checks if r.id.startswith("sanitize.")]
    assert len(ids) == len(set(ids))


def test_installer_in_docs_folder_still_blocks(doc, hub, meta, tmp_path):
    res = process(meta, _zip_pack(tmp_path / "p.zip", doc, ["docs/shot.png", "docs/tool.zip"]), "maintainer", hub)
    blocked = [r for r in res.checks if r.id == "pack.installers"]
    assert blocked and "tool.zip" in blocked[0].detail and "shot.png" not in blocked[0].detail

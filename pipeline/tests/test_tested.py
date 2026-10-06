import json

import pytest
import yaml

from soarshelf import verify
from soarshelf.build import curated
from soarshelf.process import _tested, _tests

MANUAL = "f414d039-bb0d-4e59-9c39-a8f1e880b18a"  # manual trigger step type
V1 = {"platform": "8.0.0", "version": "1.0.0", "result": "ran", "playbooks": ["A"]}


def test_tests_drop_bad_entries_and_sort_newest_platform_first():
    meta = {"tested": [
        {"platform": "7.6.5", "version": "1.0.0", "result": "imported"},
        V1,
        {"platform": "8.0.0", "version": "1.0.0", "result": "passed"},   # unknown result
        {"version": "1.0.0", "result": "ran"},                            # no platform
        "8.0.0",
    ]}
    assert [(t["platform"], t["result"]) for t in _tests(meta)] == [("8.0.0", "ran"), ("7.6.5", "imported")]
    assert _tests({"tested": "yes"}) == []


def test_tested_only_vouches_for_the_current_version():
    tests = _tests({"tested": [V1, {"platform": "8.0.0", "version": "1.1.0", "result": "imported"}]})
    assert _tested(tests, "1.0.0") == {"platform": "8.0.0", "result": "ran"}
    assert _tested(tests, "1.1.0") == {"platform": "8.0.0", "result": "imported"}
    assert _tested(tests, "2.0.0") is None


def test_process_carries_tests(doc, hub, meta, write_json):
    from soarshelf.process import process

    meta["tested"] = [V1]
    detail = process(meta, write_json(doc), "contributor", hub).detail
    assert detail["tested"] == {"platform": "8.0.0", "result": "ran"}
    assert detail["tests"][0]["playbooks"] == ["A"]


def _write(content, name, body):
    (content / "collections").mkdir(exist_ok=True)
    (content / "collections" / f"{name}.yaml").write_text(yaml.safe_dump(body))


def test_curated_keeps_order_and_reports_missing_items(tmp_path):
    published = {"a": {}, "b": {}}
    _write(tmp_path, "start", {"title": "Start", "summary": "s", "featured": True,
                               "items": ["b", {"slug": "a", "note": "then this"}, "b"]})
    _write(tmp_path, "gone", {"title": "Gone", "summary": "s", "items": ["a", "removed-item"]})
    _write(tmp_path, "Bad Name", {"title": "x", "summary": "s", "items": ["a"]})
    lists, errors = curated(tmp_path, published)
    assert [c["slug"] for c in lists] == ["start", "gone"]          # featured first
    assert [i["slug"] for i in lists[0]["items"]] == ["b", "a"]     # order kept, duplicate dropped
    assert lists[0]["items"][1]["note"] == "then this"
    assert any("removed-item" in e for e in errors)
    assert any("Bad Name" in e for e in errors)


def test_curated_without_folder_is_empty(tmp_path):
    assert curated(tmp_path, {}) == ([], [])


def test_scratch_copy_renames_and_regenerates_only_export_uuids(doc):
    (copy,), names = verify.scratch_copy(doc["data"], {"Enrich IP"})
    text = json.dumps(copy)
    for old in ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222",
                "aaaaaaaa-0000-4000-8000-000000000001"):
        assert old not in text
    # platform objects keep their ids: step types, teams, connector configs
    assert MANUAL in text and "33333333-3333-4333-8333-333333333333" in text
    assert "44444444-4444-4444-8444-444444444444" in text
    assert copy["name"].startswith(verify.PREFIX)
    wf = copy["workflows"][0]
    assert names == {"Enrich IP": wf["uuid"]}
    assert wf["isActive"] is True                                  # manual trigger, asked to run
    # routes still point at the renamed steps
    step_iris = {f"/api/3/workflow_steps/{s['uuid']}" for s in wf["steps"]}
    assert {r["sourceStep"] for r in wf["routes"]} <= step_iris


def test_scratch_copy_never_switches_on_record_triggers(doc):
    from soarshelf import config

    on_create = next(k for k, v in config.TRIGGER_LABELS.items() if v == "On create")
    doc["data"][0]["workflows"][0]["steps"][0]["stepType"] = f"/api/3/workflow_step_types/{on_create}"
    (copy,), _ = verify.scratch_copy(doc["data"], set())
    assert copy["workflows"][0]["isActive"] is False
    with pytest.raises(verify.VerifyError, match="On create"):
        verify.scratch_copy(doc["data"], {"Enrich IP"})


def test_record_replaces_same_version_and_never_downgrades(tmp_path):
    (tmp_path / "meta.yaml").write_text(yaml.safe_dump({"title": "x", "version": "1.0.0"}))
    verify.record(tmp_path, {"platform": "8.0.0", "version": "1.0.0", "result": "imported", "playbooks": []})
    verify.record(tmp_path, {**V1}, "Called with base 7.")
    verify.record(tmp_path, {"platform": "8.0.0", "version": "1.0.0", "result": "imported", "playbooks": []})
    tested = yaml.safe_load((tmp_path / "meta.yaml").read_text())["tested"]
    assert tested == [{**V1, "notes": "Called with base 7."}]

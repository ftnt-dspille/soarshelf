"""Enhanced forks of Content Hub connectors -- the ``enhances`` declaration.

The shelf initially declined anything duplicated from the Content Hub.
Enhanced forks of hub connectors are welcome now, on the condition they
declare themselves: ``meta.yaml: enhances: {connector, version, changes}``.
The pipeline then links the hub original and measures the operation-level
difference, so a user can tell whether the hub original is enough.
"""
import json

from soarshelf.hubindex import HubIndex
from soarshelf.process import _meta_checks, process
from soarshelf.submission import to_meta
from soarshelf.model import Severity

HUB_OPS = ("get_events", "add_record_to_collection")


def _hub(ops=HUB_OPS, version="2.1.0"):
    return HubIndex(snapshot="2026-11-04", connectors={"splunk": {
        "label": "Splunk", "version": version, "versions": ["2.0.0", version],
        "category": "SIEM", "operations": list(ops),
        "help": "https://docs.fortinet.com/splunk-x"}}, packs={})


def _conn(name="splunk", version="2.1.1", ops=HUB_OPS + ("ban",)):
    return {"name": name, "label": name, "version": version, "description": "d.",
            "configuration": {"fields": []},
            "operations": [{"operation": o, "title": o.replace("_", " ")} for o in ops]}


def _meta(**over):
    m = {"slug": "enhanced-splunk", "title": "Splunk with an extra block operation",
         "summary": "Splunk plus a ban operation.", "use_cases": ["containment"],
         "author": "someone", "published": "2026-11-04",
         "source": "https://github.com/someone/connector-splunk-plus"}
    m.update(over)
    return m


def _ids(res):
    return [c["id"] for c in res.detail["checks"]]


def _run(write_json, hub=None, conn=None, **meta_over):
    res = process(_meta(**meta_over), write_json(conn or _conn(), "info.json"), "contributor", hub or _hub())
    return res


def test_fork_declared_links_original_and_measures_delta(write_json):
    res = _run(write_json, enhances={"connector": "splunk", "version": "2.0.0",
                                    "changes": "Adds a ban operation."})
    ids = _ids(res)
    assert "connector.on-hub" not in ids            # declared: no undecclared-name warning
    assert "connector.enhanced" in ids
    assert res.detail["enhanced"] == {
        "connector": "splunk", "label": "Splunk", "hubVersion": "2.1.0", "baseVersion": "2.0.0",
        "sameName": True, "added": [{"name": "ban", "title": "ban"}], "removed": [], "hubCount": 2,
        "url": "https://docs.fortinet.com/splunk-x", "changes": "Adds a ban operation."}


def test_renamed_fork_is_not_an_in_place_upgrade(write_json):
    res = _run(write_json, conn=_conn(name="splunk-extended"),
               enhances={"connector": "splunk", "changes": "Same ops, plus a ban."})
    assert res.detail["enhanced"]["sameName"] is False
    assert "connector.enhanced.version" not in _ids(res)      # different name: version order is moot


def test_fork_declaration_is_forgiving_of_title_case(write_json):
    res = _run(write_json, enhances={"connector": "Splunk", "changes": "Ban op."})
    assert "connector.enhances-unknown" not in _ids(res)
    assert res.detail["enhanced"]["connector"] == "splunk"


def test_hub_name_without_declares_warns_and_keeps_listing_plain(write_json):
    res = _run(write_json)                                    # no enhances block, package name is on the hub
    ids = _ids(res)
    assert "connector.on-hub" in ids
    onhub = next(c for c in res.detail["checks"] if c["id"] == "connector.on-hub")
    assert onhub["severity"] == "warn"
    assert "enhances" in onhub["detail"]
    assert res.detail["enhanced"] is None


def test_unknown_hub_connector_is_blocked(write_json):
    res = _run(write_json, enhances={"connector": "splonk", "changes": "Typo of splunk."})
    assert res.decision == "reject"
    unknown = next(c for c in res.detail["checks"] if c["id"] == "connector.enhances-unknown")
    assert unknown["severity"] == "block"
    assert "Did you mean 'splunk'?" in unknown["detail"]
    assert res.detail["enhanced"] is None


def test_exact_same_operations_warns_the_original_may_be_enough(write_json):
    res = _run(write_json, conn=_conn(ops=HUB_OPS), enhances={"connector": "splunk"})
    ids = _ids(res)
    assert "connector.enhanced.no-delta" in ids
    assert "connector.enhanced.no-notes" in ids
    assert res.detail["enhanced"]["added"] == [] and res.detail["enhanced"]["removed"] == []


def test_same_name_fork_below_the_hub_version_warns(write_json):
    res = _run(write_json, conn=_conn(version="2.1.0"),      # equal, not above
               enhances={"connector": "splunk"})
    assert "connector.enhanced.version" in _ids(res)


def test_enhances_shape_gate():
    def _shape(enh, kind="connector"):
        meta = {"title": "T", "summary": "S long enough", "use_cases": ["enrichment"],
                "source": "https://github.com/a/b"}
        if enh is not None:
            meta["enhances"] = enh
        return [c for c in _meta_checks(meta, kind) if c.id.startswith("meta.enhances")]

    assert _shape(None) == []                                    # absent: not an error either way

    for bad in ("s", {}, {"version": "1.0.0"}):
        r = _shape(bad)
        assert r and all(c.id == "meta.enhances" and c.severity is Severity.BLOCK for c in r), bad

    assert _shape({"connector": "aws"}) == []                    # known-good: quiet

    assert any(c.id == "meta.enhances.version" for c in _shape({"connector": "aws", "version": "v1"}))
    assert any(c.id == "meta.enhances.changes" for c in _shape({"connector": "aws", "changes": "x" * 501}))
    wrong_kind = _shape({"connector": "aws"}, kind="playbook")
    assert any(c.id == "meta.enhances" and c.severity is Severity.WARN for c in wrong_kind)


def test_to_meta_maps_the_form_block_and_drops_empty_parts():
    meta = to_meta({"enhances": {"connector": " Splunk ", "version": " 2.0.0 ", "changes": " Ban op. "}}, "me")
    assert meta["enhances"] == {"connector": "splunk", "version": "2.0.0", "changes": "Ban op."}
    sparse = to_meta({"enhances": {"connector": "", "version": "1"}}, "me")
    assert "enhances" not in sparse
    quiet = to_meta({"enhances": {"connector": "splunk"}}, "me")
    assert quiet["enhances"] == {"connector": "splunk"}

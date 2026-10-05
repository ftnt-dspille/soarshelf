import json

import yaml

from soarshelf.submission import intake, slugify, to_meta

FORM = {"title": "Enrich alert source IPs!", "summary": "Looks up the source IP.", "description": "x",
        "useCases": ["enrichment"], "tags": ["ip", "BAD TAG", "virustotal"], "version": "1.2.0",
        "minVersion": None, "source": None, "rightsConfirmed": True, "author": "someone-else"}


def _content(tmp_path, maintainers=()):
    c = tmp_path / "content"
    (c / "playbooks").mkdir(parents=True)
    (c / "contributors.yaml").write_text(yaml.safe_dump({m: "maintainer" for m in maintainers}))
    return c


def test_slugify():
    assert slugify("Enrich alert source IPs!") == "enrich-alert-source-ips"
    assert slugify("!!!") == "item"


def test_to_meta_uses_authenticated_author_and_cleans_tags():
    m = to_meta(FORM, "alice")
    assert m["author"] == "alice" and m["tags"] == ["ip", "virustotal"] and m["license"] == "MIT"


def test_intake_writes_cleaned_item(tmp_path, doc, hub, write_json):
    content = _content(tmp_path)
    res = intake(write_json(doc), FORM, "alice", content, hub)
    assert res.decision == "review" and res.slug == "enrich-alert-source-ips"
    item = content / "playbooks" / res.slug
    meta = yaml.safe_load((item / "meta.yaml").read_text())
    assert meta["author"] == "alice"
    stored = json.loads((item / "playbook.json").read_text())
    assert stored["data"][0]["workflows"][0]["isActive"] is False      # cleaned, not raw
    # same title again gets a fresh slug
    assert intake(write_json(doc), FORM, "alice", content, hub).slug == "enrich-alert-source-ips-2"


def test_reject_writes_nothing_and_strikes(tmp_path, doc, hub, write_json):
    content = _content(tmp_path)
    doc["data"][0]["workflows"][0]["steps"][1]["arguments"]["params"]["apikey"] = "0123456789abcdefLIVE"
    res = intake(write_json(doc), FORM, "alice", content, hub)
    assert res.decision == "reject" and res.strike and res.written is None
    assert not any((content / "playbooks").iterdir())


def test_rights_required(tmp_path, doc, hub, write_json):
    res = intake(write_json(doc), {**FORM, "rightsConfirmed": False}, "alice", _content(tmp_path), hub)
    assert res.decision == "reject"

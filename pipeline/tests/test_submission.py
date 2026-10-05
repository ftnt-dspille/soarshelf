import json

import yaml

from soarshelf.submission import intake, slugify, to_meta

FORM = {"title": "Enrich alert source IPs!", "summary": "Looks up the source IP.", "description": "x",
        "useCases": ["enrichment"], "tags": ["ip", "BAD TAG", "virustotal"], "version": "1.2.0",
        "minVersion": None, "source": None, "rightsConfirmed": True, "author": "someone-else"}


def _content(tmp_path, maintainers=()):
    c = tmp_path / "content"
    (c / "playbooks").mkdir(parents=True)
    (c / "contributors.yaml").write_text(yaml.safe_dump({m: {"trust": "maintainer", "id": 1} for m in maintainers}))
    return c


def _pack(path, doc):
    """Minimal solution pack holding doc's first collection."""
    import zipfile
    coll = doc["data"][0]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("pk/info.json", json.dumps({"name": "pk", "version": "1.0.0"}))
        for wf in coll["workflows"]:
            zf.writestr(f"pk/playbooks/{coll['name']}/{wf['name']}.json", json.dumps({**wf, "@type": "Workflow"}))
    return path


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
    # a different playbook with the same title gets a fresh slug
    other = json.loads(json.dumps(doc))
    wf = other["data"][0]["workflows"][0]
    wf["uuid"] = "77777777-7777-4777-8777-777777777777"
    for st in wf["steps"]:
        st["name"] += " v2"
    assert intake(write_json(other), FORM, "alice", content, hub).slug == "enrich-alert-source-ips-2"


def test_reject_writes_nothing_and_strikes(tmp_path, doc, hub, write_json):
    content = _content(tmp_path)
    doc["data"][0]["workflows"][0]["steps"][1]["arguments"]["params"]["apikey"] = "0123456789abcdefLIVE"
    res = intake(write_json(doc), FORM, "alice", content, hub)
    assert res.decision == "reject" and res.strike and res.written is None
    assert not any((content / "playbooks").iterdir())


def test_rights_required(tmp_path, doc, hub, write_json):
    res = intake(write_json(doc), {**FORM, "rightsConfirmed": False}, "alice", _content(tmp_path), hub)
    assert res.decision == "reject"


def test_pr_body_neutralises_user_text():
    from soarshelf.submission import pr_body
    body = pr_body({"decision": "review", "reasons": ["Contains steps that run code"],
                    "checks": [{"severity": "warn", "title": "Email address", "location": "PB › @everyone [x](http://evil)"}]},
                   "alice", "a" * 32)
    assert "@\u200beveryone" in body and "](http" not in body and "Needs review" in body


def test_reupload_of_published_item_is_rejected(tmp_path, doc, hub, write_json):
    content = _content(tmp_path)
    first = intake(write_json(doc), FORM, "alice", content, hub)
    assert first.written
    again = intake(write_json(doc), {**FORM, "title": "Totally new name"}, "mallory", content, hub)
    assert again.decision == "reject" and not again.strike
    assert any(c["id"] == "provenance.duplicate-item" and "another contributor" in c["detail"] for c in again.checks)
    # renamed steps but same uuids still match; same structure with fresh uuids too
    doc2 = json.loads(json.dumps(doc))
    doc2["data"][0]["workflows"][0]["uuid"] = "99999999-9999-4999-8999-999999999999"
    assert intake(write_json(doc2), {**FORM, "title": "Another"}, "mallory", content, hub).decision == "reject"


def test_trust_needs_matching_github_id(tmp_path, doc, hub, write_json):
    content = _content(tmp_path, maintainers=("boss",))
    real = intake(write_json(doc), FORM, "boss", content, hub, author_id=1)
    assert yaml.safe_load((real.written / "meta.yaml").read_text())["author_id"] == 1
    # same login, different account (renamed and re-registered): treated as new
    from soarshelf.build import load_trust, tier_for
    table = load_trust(content)
    assert tier_for(table, "boss", 1) == "maintainer" and tier_for(table, "boss", 999) == "new"


def test_duplicate_found_inside_published_pack(tmp_path, doc, hub, write_json):
    content = _content(tmp_path)
    item = content / "solution-packs" / "some-pack"
    item.mkdir(parents=True)
    (item / "meta.yaml").write_text(yaml.safe_dump({"author": "alice"}))
    _pack(item / "pack.zip", doc)
    res = intake(write_json(doc), FORM, "mallory", content, hub, author_id=666)
    assert res.decision == "reject"
    assert any(c["id"] == "provenance.duplicate-item" and "some-pack" in c["detail"] for c in res.checks)


def test_duplicate_check_covers_pack_uploads(tmp_path, doc, hub, write_json):
    from soarshelf.process import collections_of
    from soarshelf.submission import _already_published
    content = _content(tmp_path)
    assert intake(write_json(doc), FORM, "alice", content, hub, author_id=2).written
    found = _already_published(collections_of(_pack(tmp_path / "up.zip", doc)), content, "mallory")
    assert found and "another contributor" in found[0].detail


def test_inert_breaks_links():
    from soarshelf.submission import _inert
    for raw in ["see https://evil.example/x", "www.evil.example", "evil.example", "mail bob@evil.example",
                "![x](javascript:alert(1))", "fixes #12", "&#64;everyone", "evil&#46;example"]:
        out = _inert(raw)
        for bad in ["://", "www.", "evil.example", "@evil", "](", "#12"]:
            assert bad not in out, (raw, out)

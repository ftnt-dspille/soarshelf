from xml.dom import minidom

from soarshelf.build import activity, atom_feed
from soarshelf.process import _last_change, process


def _detail(slug, published, changelog=None, version="1.0.0"):
    return {"slug": slug, "type": "playbook", "title": slug.title(), "displayName": None,
            "version": version, "published": published, "updated": published, "changelog": changelog or []}


def test_download_name_carries_the_version(doc, hub, meta, write_json):
    meta["version"] = "1.2.0"
    res = process(meta, write_json(doc), "contributor", hub)
    assert res.filename.endswith("-1.2.0.json")
    assert res.detail["download"]["path"].endswith("-1.2.0.json")


def test_last_change():
    assert _last_change({"version": "1.0.0", "published": "2026-01-01"})["kind"] == "added"
    log = [{"version": "1.1.0", "date": "2026-02-01", "notes": "Fixed X."},
           {"version": "1.0.0", "date": "2026-01-01", "notes": "First published."}]
    last = _last_change({"version": "1.1.0", "published": "2026-01-01", "changelog": log})
    assert last == {"kind": "updated", "version": "1.1.0", "date": "2026-02-01", "notes": "Fixed X."}


def test_activity_orders_and_splits_events():
    log = [{"version": "1.0.1", "date": "2026-03-01", "notes": "Fix."},
           {"version": "1.0.0", "date": "2026-01-01", "notes": "First published."}]
    events = activity([_detail("a", "2026-01-01", log, "1.0.1"), _detail("b", "2026-03-01"),
                       _detail("c", "2026-02-01")])
    assert [(e["slug"], e["kind"], e["version"]) for e in events] == [
        ("a", "updated", "1.0.1"),   # same day as b's addition: updates first
        ("b", "added", "1.0.0"),
        ("c", "added", "1.0.0"),
        ("a", "added", "1.0.0"),     # first release comes from the changelog's last entry
    ]


def test_atom_feed_is_valid_xml_and_escaped():
    events = activity([_detail("x", "2026-01-01")])
    events[0]["title"] = "A <b> & C"
    feed = atom_feed(events, "2026-01-02T00:00:00+00:00")
    dom = minidom.parseString(feed)
    assert dom.getElementsByTagName("title")[1].firstChild.data == "A <b> & C: Added"

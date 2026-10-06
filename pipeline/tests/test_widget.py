from soarshelf.hubindex import HubIndex
from soarshelf.process import process

WIDGET = {
    "name": "riskGauge",
    "title": "Risk Gauge",
    "subTitle": "Show a record's risk score as a gauge",
    "version": "1.0.0",
    "metadata": {"description": "A gauge.", "pages": ["View Panel", "Dashboard"], "certified": "No",
                 "publisher": "Someone", "compatibility": ["7.6.0"]},
    "development": False,
}
META = {"slug": "risk-gauge", "title": "Risk gauge widget", "summary": "Shows risk as a gauge.",
        "use_cases": ["triage"], "author": "someone", "published": "2026-01-01",
        "source": "https://github.com/someone/widget-risk-gauge"}


def test_widget_listed_by_manifest_and_always_reviewed(hub, write_json):
    res = process(META, write_json(WIDGET, "info.json"), "maintainer", hub)
    assert res.detail["type"] == "widget"
    assert res.decision == "review" and "Widgets are always reviewed" in res.reasons
    w = res.detail["widget"]
    assert w["pages"] == ["View Panel", "Dashboard"] and w["compatibility"] == ["7.6.0"]
    assert b"development" not in res.download            # only the listed fields are kept
    assert [s["kind"] for s in res.detail["setup"]][:2] == ["note", "install-widget"]


def test_widget_needs_source(hub, write_json):
    res = process({**META, "source": None}, write_json(WIDGET, "info.json"), "maintainer", hub)
    assert res.decision == "reject" and any(c["id"] == "meta.source" for c in res.detail["checks"])


def test_widget_named_like_hub_widget_warns(write_json):
    hub = HubIndex(snapshot="x", connectors={}, packs={}, widgets={"riskGauge": {"label": "Risk Gauge"}})
    res = process(META, write_json(WIDGET, "info.json"), "maintainer", hub)
    assert any(c["id"] == "widget.on-hub" for c in res.detail["checks"])


def test_connector_manifest_is_not_a_widget(hub, write_json):
    conn = {"name": "x", "title": "X", "metadata": {}, "operations": [], "configuration": {}}
    assert process({**META, "source": "https://e.example/x"}, write_json(conn, "info.json"), "new", hub).detail["type"] == "connector"


CONNECTOR = {"name": "feedreader", "label": "Feed Reader", "version": "1.0.4", "description": "Reads feeds.",
             "category": "Threat Intelligence", "publisher": "Community", "configuration": {"fields": []},
             "operations": [{"operation": "list_feeds", "title": "List feeds"}, {"operation": "get_items", "title": "Get items"}]}


def _roundtrip(manifest, meta, hub, tmp_path):
    """Publish, then read the published manifest back the way the site build does."""
    first = process(meta, _write(tmp_path / "up.json", manifest), "maintainer", hub)
    published = tmp_path / "published" / "info.json"
    published.parent.mkdir()
    published.write_bytes(first.download)
    return first, process(meta, published, "maintainer", hub)


def _write(path, obj):
    import json
    path.write_text(json.dumps(obj))
    return path


def test_published_widget_manifest_reads_back_the_same(hub, tmp_path):
    first, again = _roundtrip(WIDGET, META, hub, tmp_path)
    assert again.detail["type"] == "widget" and again.detail["widget"] == first.detail["widget"]
    assert again.decision == first.decision


def test_published_connector_manifest_reads_back_the_same(hub, tmp_path):
    meta = {**META, "source": "https://github.com/someone/connector-feedreader"}
    first, again = _roundtrip(CONNECTOR, meta, hub, tmp_path)
    assert again.detail["type"] == "connector" and again.detail["operations"] == first.detail["operations"]
    assert [o["operation"] for o in again.detail["operations"]] == ["list_feeds", "get_items"]

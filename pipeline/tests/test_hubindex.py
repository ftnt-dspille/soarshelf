"""The hub index provider: snapshot by default, live fetch when asked for."""
from __future__ import annotations

import io
import json
from unittest import mock

import pytest
from PIL import Image

from soarshelf import hubindex
from soarshelf.hubindex import hub_index


@pytest.fixture
def catalog_entry():
    return [{
        "name": "example-connector",
        "type": "connector",
        "label": "Example Connector",
        "version": "1.0.0",
        "availableVersions": ["1.0.0"],
        "category": ["Utility"],
        "operations": [{"operation": "get_thing"}],
        "iconLarge": "/content-hub/example-connector-1.0.0/100/images/large.png",
    }]


def _png():
    out = io.BytesIO()
    Image.new("RGB", (80, 80), (10, 120, 200)).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def icon_hub():
    return hubindex.HubIndex(
        snapshot="2026-10-29",
        connectors={
            "iconed": {"label": "Iconed", "icon": "/content-hub/iconed-1.0.0/9/images/large.png"},
            "not-listed": {"label": "Not Listed", "icon": None},
            "bad-path": {"label": "Bad Path", "icon": "/content-hub/../../secret.png"},
        },
        packs={},
    )


def test_default_is_the_committed_snapshot(monkeypatch):
    # No env var: the committed snapshot file, and the catalog is never fetched.
    monkeypatch.delenv("SOARSHELF_HUB_LIVE", raising=False)
    fetched = mock.Mock(side_effect=AssertionError("must not fetch"))
    with mock.patch.object(hubindex, "fetch_catalog", fetched):
        index = hub_index()
    assert isinstance(index, hubindex.HubIndex)
    assert index.snapshot  # whatever main's snapshot says
    fetched.assert_not_called()


def test_live_fetch_builds_a_current_index(monkeypatch, catalog_entry):
    monkeypatch.setenv("SOARSHELF_HUB_LIVE", "1")
    with mock.patch.object(hubindex, "fetch_catalog", return_value=catalog_entry):
        index = hub_index()
    assert "example-connector" in index.connectors
    assert index.connectors["example-connector"]["operations"] == ["get_thing"]
    assert index.connectors["example-connector"]["icon"] == "/content-hub/example-connector-1.0.0/100/images/large.png"
    # Fingerprints still come from the committed file: they need pack contents,
    # which the catalog does not carry.
    assert isinstance(index.official_uuids, set)


def test_live_fetch_failure_falls_back_to_the_snapshot(monkeypatch, capsys):
    monkeypatch.setenv("SOARSHELF_HUB_LIVE", "1")
    with mock.patch.object(hubindex, "fetch_catalog",
                           side_effect=OSError("hub unreachable")):
        index = hub_index()
    assert isinstance(index, hubindex.HubIndex)
    assert index.snapshot  # the committed snapshot, not a live date
    assert "hub unreachable" in capsys.readouterr().err


def test_snapshot_file_stays_the_offline_source_of_truth():
    hub = json.loads(hubindex.HUB_INDEX.read_text())
    assert hub["snapshot"] == hub_index().snapshot


# --- hub icons (soarshelf hub-icons) --------------------------------------------


def test_hub_icons_download_clean_and_prune(tmp_path, icon_hub):
    (tmp_path / "stale.png").write_bytes(_png())       # a connector no one references anymore
    report = hubindex.hub_icons(["iconed", "not-listed", "bad-path", "unstale-never-asked"],
                                out=tmp_path, fetch=lambda path: _png(), hub=icon_hub)
    # Only a connector whose hub listing names an icon gets a file.
    assert (tmp_path / "iconed.png").read_bytes().startswith(b"\x89PNG")
    assert report["kept"] == 1 and report["written"] == 1 and report["removed"] == 1
    assert report["failed"] == []
    assert set(report["no-icon"]) == {"not-listed", "bad-path", "unstale-never-asked"}
    assert not (tmp_path / "stale.png").exists()       # mirrored: not asked for → removed
    assert not (tmp_path / "bad-path.png").exists()    # an unsafe path is never fetched


def test_hub_icons_refetch_only_what_changed(tmp_path, icon_hub):
    fetch = mock.Mock(side_effect=[_png(), _png()])
    hubindex.hub_icons(["iconed"], out=tmp_path, fetch=fetch, hub=icon_hub)
    assert hubindex.hub_icons(["iconed"], out=tmp_path, fetch=fetch, hub=icon_hub)["written"] == 0
    assert fetch.call_count == 2                        # the hub is still checked weekly; nothing is rewritten


def test_hub_icons_a_failed_fetch_skips_one_connector_not_the_run(tmp_path, icon_hub):
    icon_hub.connectors["other"] = {"label": "Other", "icon": "/content-hub/other-1.0.0/1/images/large.png"}

    def fetch(path):
        if "other" not in path:
            raise OSError("hub unreachable")
        return _png()

    report = hubindex.hub_icons(["iconed", "other"], out=tmp_path, fetch=fetch, hub=icon_hub)
    assert report["failed"] == ["iconed"]
    assert (tmp_path / "other.png").is_file()
    assert not (tmp_path / "iconed.png").is_file()


def test_hub_icons_a_file_that_cannot_be_an_icon_is_rejected_not_stored(tmp_path, icon_hub):
    report = hubindex.hub_icons(["iconed"], out=tmp_path,
                                fetch=lambda path: b"<svg><script>alert(1)</script></svg>", hub=icon_hub)
    assert report["failed"] == ["iconed"]
    assert not (tmp_path / "iconed.png").is_file()

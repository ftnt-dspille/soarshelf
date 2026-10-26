"""The hub index provider: snapshot by default, live fetch when asked for."""
from __future__ import annotations

import json
from unittest import mock

import pytest

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
    }]


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

"""Unit tests for classify_assets.

Strategy:
  * Helpers (`_list_lakehouse_tables`, `_find_entity_guid`, `_classify`,
    `_process_tables`) are tested directly — they do all the real work.
  * `main()` is tested as an integration of the helpers, with each helper
    monkeypatched to return canned results.
  * All HTTP is faked with `responses`. No real Azure calls.
"""
from __future__ import annotations

import json as _json
from unittest.mock import MagicMock, patch

import pytest
import responses

from classify_assets.handler import (
    _classify,
    _find_entity_guid,
    _list_lakehouse_tables,
    _process_tables,
    _read_sensitivity,
    classify_assets_impl,
)


# ---- _list_lakehouse_tables -------------------------------------------------


@responses.activate
def test_list_lakehouse_tables_returns_leaf_dirs(workspace_id, lakehouse_id):
    responses.get(
        f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}",
        json={
            "paths": [
                {"name": f"{lakehouse_id}/Tables/appointments", "isDirectory": "true"},
                {"name": f"{lakehouse_id}/Tables/claims", "isDirectory": "true"},
                # File, not dir — must be skipped
                {"name": f"{lakehouse_id}/Tables/_README.md", "isDirectory": "false"},
                # Nested dir (schema-style) — must be skipped (no '/' in leaf)
                {"name": f"{lakehouse_id}/Tables/dbo/patients", "isDirectory": "true"},
            ]
        },
    )
    tables = _list_lakehouse_tables()
    assert sorted(tables) == ["appointments", "claims"]


@responses.activate
def test_list_lakehouse_tables_empty(workspace_id):
    responses.get(
        f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}",
        json={"paths": []},
    )
    assert _list_lakehouse_tables() == []


@responses.activate
def test_list_lakehouse_tables_propagates_http_error(workspace_id):
    responses.get(
        f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}",
        status=403,
        json={"error": "forbidden"},
    )
    with pytest.raises(Exception):
        _list_lakehouse_tables()


# ---- _read_sensitivity ------------------------------------------------------


def test_read_sensitivity_returns_property():
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {"data-sensitivity": "Confidential"}
    with patch("classify_assets.handler.DeltaTable", return_value=fake_dt):
        assert _read_sensitivity("appointments") == "Confidential"


def test_read_sensitivity_underscore_fallback():
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {"data_sensitivity": "Public"}
    with patch("classify_assets.handler.DeltaTable", return_value=fake_dt):
        assert _read_sensitivity("t") == "Public"


def test_read_sensitivity_missing_returns_none():
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {}
    with patch("classify_assets.handler.DeltaTable", return_value=fake_dt):
        assert _read_sensitivity("t") is None


def test_read_sensitivity_table_not_found_returns_none():
    from deltalake.exceptions import TableNotFoundError

    with patch("classify_assets.handler.DeltaTable", side_effect=TableNotFoundError("nope")):
        assert _read_sensitivity("missing") is None


def test_read_sensitivity_swallows_unexpected_exception():
    with patch("classify_assets.handler.DeltaTable", side_effect=RuntimeError("boom")):
        assert _read_sensitivity("t") is None


# ---- _find_entity_guid ------------------------------------------------------


@responses.activate
def test_find_entity_guid_matches_by_name_and_lakehouse(purview_url, lakehouse_id):
    responses.post(
        f"{purview_url}/datamap/api/search/query",
        json={
            "value": [
                {
                    "name": "appointments",
                    "id": "guid-correct",
                    "qualifiedName": (
                        f"https://app.fabric.microsoft.com/groups/ws/lakehouses/"
                        f"{lakehouse_id}/tables/appointments"
                    ),
                },
                # Same name but in a different lakehouse — must be skipped
                {
                    "name": "appointments",
                    "id": "guid-wrong",
                    "qualifiedName": (
                        "https://app.fabric.microsoft.com/groups/ws/lakehouses/"
                        "OTHER/tables/appointments"
                    ),
                },
            ]
        },
    )
    assert _find_entity_guid("appointments") == "guid-correct"


@responses.activate
def test_find_entity_guid_falls_back_to_name_only_match(purview_url):
    responses.post(
        f"{purview_url}/datamap/api/search/query",
        json={
            "value": [
                {"name": "claims", "id": "guid-only-name", "qualifiedName": "elsewhere"},
            ]
        },
    )
    # No qualifiedName matches LAKEHOUSE_ID -> falls back to name-only match
    assert _find_entity_guid("claims") == "guid-only-name"


@responses.activate
def test_find_entity_guid_no_hits_returns_none(purview_url):
    responses.post(f"{purview_url}/datamap/api/search/query", json={"value": []})
    assert _find_entity_guid("nothing") is None


@responses.activate
def test_find_entity_guid_falls_back_to_legacy_endpoint_on_404(purview_url):
    responses.post(
        f"{purview_url}/datamap/api/search/query",
        status=404,
        json={"error": "not found"},
    )
    responses.post(
        f"{purview_url}/catalog/api/search/query",
        json={"value": [{"name": "t", "id": "g1", "qualifiedName": "x"}]},
    )
    assert _find_entity_guid("t") == "g1"


@responses.activate
def test_find_entity_guid_query_body_uses_object_type_only(purview_url):
    """Regression test: the discovery API rejects assetType as an array,
    and the actual Fabric Lakehouse table assetType is "Fabric" not
    "Fabric Lakehouse". Body must filter only by objectType=Tables."""
    responses.post(f"{purview_url}/datamap/api/search/query", json={"value": []})
    _find_entity_guid("appointments")
    sent_body = responses.calls[0].request.body
    parsed = _json.loads(sent_body)
    assert parsed["filter"] == {"objectType": "Tables"}
    assert parsed["keywords"] == "appointments"


# ---- _classify --------------------------------------------------------------


@responses.activate
def test_classify_post_succeeds(purview_url):
    responses.post(
        f"{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications",
        status=204,
    )
    _classify("g1", "Sensitivity.Confidential")


@responses.activate
def test_classify_put_on_409_conflict(purview_url):
    """If POST returns 409 (already classified), function retries via PUT."""
    url = f"{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications"
    responses.post(url, status=409, json={"error": "conflict"})
    responses.put(url, status=204)
    _classify("g1", "Sensitivity.Public")


@responses.activate
def test_classify_raises_on_500(purview_url):
    """5xx triggers the urllib3 Retry adapter; eventually raise_for_status."""
    url = f"{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications"
    for _ in range(10):
        responses.post(url, status=500, json={"error": "boom"})
    with pytest.raises(Exception):
        _classify("g1", "Sensitivity.Public")


# ---- _process_tables --------------------------------------------------------


def test_process_tables_classifies_when_sensitivity_present(monkeypatch):
    monkeypatch.setattr("classify_assets.handler._read_sensitivity", lambda t: "Public")
    monkeypatch.setattr("classify_assets.handler._find_entity_guid", lambda t: "guid-" + t)
    classify_calls = []
    monkeypatch.setattr(
        "classify_assets.handler._classify",
        lambda guid, name: classify_calls.append((guid, name)),
    )
    summary = _process_tables(["appointments", "claims"])
    assert summary == {
        "total": 2,
        "classified": 2,
        "skipped_no_property": 0,
        "skipped_no_entity": 0,
        "errors": 0,
    }
    assert classify_calls == [
        ("guid-appointments", "Sensitivity.Public"),
        ("guid-claims", "Sensitivity.Public"),
    ]


def test_process_tables_skips_no_property(monkeypatch):
    monkeypatch.setattr("classify_assets.handler._read_sensitivity", lambda t: None)
    monkeypatch.setattr(
        "classify_assets.handler._find_entity_guid",
        lambda t: pytest.fail("should not look up entity when no property"),
    )
    monkeypatch.setattr(
        "classify_assets.handler._classify",
        lambda *_: pytest.fail("should not classify"),
    )
    summary = _process_tables(["t1"])
    assert summary["skipped_no_property"] == 1
    assert summary["classified"] == 0


def test_process_tables_skips_unknown_sensitivity_value(monkeypatch):
    monkeypatch.setattr("classify_assets.handler._read_sensitivity", lambda t: "TopSecret")
    monkeypatch.setattr(
        "classify_assets.handler._classify",
        lambda *_: pytest.fail("should not classify"),
    )
    summary = _process_tables(["t1"])
    assert summary["skipped_no_property"] == 1


def test_process_tables_skips_when_entity_not_found(monkeypatch):
    monkeypatch.setattr("classify_assets.handler._read_sensitivity", lambda t: "Confidential")
    monkeypatch.setattr("classify_assets.handler._find_entity_guid", lambda t: None)
    monkeypatch.setattr(
        "classify_assets.handler._classify",
        lambda *_: pytest.fail("should not classify"),
    )
    summary = _process_tables(["t1"])
    assert summary["skipped_no_entity"] == 1


def test_process_tables_counts_errors_and_continues(monkeypatch):
    monkeypatch.setattr("classify_assets.handler._read_sensitivity", lambda t: "Public")
    monkeypatch.setattr("classify_assets.handler._find_entity_guid", lambda t: "g")

    def boom(_g, _n):
        raise RuntimeError("purview down")

    monkeypatch.setattr("classify_assets.handler._classify", boom)
    summary = _process_tables(["t1", "t2"])
    assert summary == {
        "total": 2,
        "classified": 0,
        "skipped_no_property": 0,
        "skipped_no_entity": 0,
        "errors": 2,
    }


def test_process_tables_sensitivity_lookup_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(
        "classify_assets.handler._read_sensitivity", lambda t: "  HIGHLY CONFIDENTIAL  "
    )
    monkeypatch.setattr("classify_assets.handler._find_entity_guid", lambda t: "g")
    captured = []
    monkeypatch.setattr("classify_assets.handler._classify", lambda g, n: captured.append(n))
    _process_tables(["t1"])
    assert captured == ["Sensitivity.HighlyConfidential"]


# ---- classify_assets_impl() (Event Hub trigger) ----------------------------


def test_impl_runs_full_flow_on_successful_scan(monkeypatch, fake_eh_events):
    monkeypatch.setattr(
        "classify_assets.handler._list_lakehouse_tables", lambda: ["t1", "t2"]
    )
    processed = []

    def fake_process(tables):
        processed.append(list(tables))
        return {
            "total": 2,
            "classified": 2,
            "skipped_no_property": 0,
            "skipped_no_entity": 0,
            "errors": 0,
        }

    monkeypatch.setattr("classify_assets.handler._process_tables", fake_process)
    classify_assets_impl(fake_eh_events)
    assert processed == [["t1", "t2"]]


def test_impl_handles_empty_lakehouse(monkeypatch, fake_eh_events):
    monkeypatch.setattr("classify_assets.handler._list_lakehouse_tables", lambda: [])
    monkeypatch.setattr(
        "classify_assets.handler._process_tables",
        lambda tables: {
            "total": 0, "classified": 0, "skipped_no_property": 0,
            "skipped_no_entity": 0, "errors": 0,
        },
    )
    classify_assets_impl(fake_eh_events)


def test_impl_skips_when_no_successful_events(monkeypatch, make_eh_event):
    """If the batch has events but none represent a successful scan, skip the
    classification pass entirely."""
    listed = []
    monkeypatch.setattr(
        "classify_assets.handler._list_lakehouse_tables",
        lambda: listed.append("called") or [],
    )
    failed_event = make_eh_event(
        {"properties": {"resultType": "Failed", "scanName": "x"}}
    )
    classify_assets_impl([failed_event])
    assert listed == [], "should not list tables when no successful scans"


def test_impl_runs_when_batch_has_no_parseable_events(monkeypatch, make_eh_event):
    """If we couldn't parse anything (parsed == []), still run the pass — we
    can't tell what we missed, so be safe and re-classify."""
    monkeypatch.setattr("classify_assets.handler._list_lakehouse_tables", lambda: [])
    called = []
    monkeypatch.setattr(
        "classify_assets.handler._process_tables",
        lambda tables: called.append(True) or {
            "total": 0, "classified": 0, "skipped_no_property": 0,
            "skipped_no_entity": 0, "errors": 0,
        },
    )
    bad_event = make_eh_event("not-json-at-all")
    classify_assets_impl([bad_event])
    assert called == [True]


def test_impl_accepts_records_wrapper(monkeypatch, make_eh_event):
    """Diagnostic logs often arrive wrapped in {records: [...]}."""
    monkeypatch.setattr(
        "classify_assets.handler._list_lakehouse_tables", lambda: ["t"]
    )
    processed = []
    monkeypatch.setattr(
        "classify_assets.handler._process_tables",
        lambda tables: processed.append(list(tables)) or {
            "total": 1, "classified": 1, "skipped_no_property": 0,
            "skipped_no_entity": 0, "errors": 0,
        },
    )
    wrapped = make_eh_event(
        {"records": [{"properties": {"resultType": "Succeeded"}}]}
    )
    classify_assets_impl([wrapped])
    assert processed == [["t"]]


# ---- function_app.py smoke test --------------------------------------------


def test_function_app_module_imports_cleanly():
    """v2 host indexes by importing function_app.py. If that import fails (bad
    decorator args, missing settings, etc.), no functions get registered. This
    guards against deploy-time-only failures."""
    import importlib

    mod = importlib.import_module("function_app")
    assert hasattr(mod, "app"), "function_app must expose `app = func.FunctionApp()`"
    assert hasattr(mod, "classify_assets"), "decorated function should be present"

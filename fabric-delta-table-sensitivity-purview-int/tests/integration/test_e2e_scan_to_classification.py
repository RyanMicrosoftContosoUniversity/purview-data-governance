"""End-to-end test: trigger a real Purview scan and verify the full pipeline
attaches a Sensitivity.* classification to the scanned table entity.

Flow tested:
  1. fixture table exists in OneLake with TBLPROPERTY data-sensitivity='public'
  2. POST scan:run on the Fabric data source
  3. wait for scan run -> Succeeded
  4. Purview emits ScanStatusLogEvent -> diag setting -> Event Hub
  5. Function classify_assets receives EH event, reads TBLPROPERTY, calls Atlas
  6. assert: Sensitivity.Public is attached to the fixture table's entity

This is the *only* test that proves the wiring between Purview, Event Hub,
the Function App's MI auth, app_settings, and the Atlas API actually works
end-to-end. Unit tests cover the function logic; this covers everything else.

Cost: ~5-10 minutes per run. Default-off in the pipeline (toggle via the
`runIntegrationTests` parameter).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

import pytest
import requests
from deltalake import DeltaTable
from deltalake.exceptions import TableNotFoundError

logger = logging.getLogger(__name__)

ONELAKE_DFS = "onelake.dfs.fabric.microsoft.com"


# ---- Low-level helpers ----------------------------------------------------


def _token(credential, resource: str) -> str:
    return credential.get_token(f"{resource}/.default").token


def _storage_opts(credential) -> dict:
    return {
        "bearer_token": _token(credential, "https://storage.azure.com"),
        "use_fabric_endpoint": "true",
    }


def _atlas_headers(credential) -> dict:
    return {
        "Authorization": f"Bearer {_token(credential, 'https://purview.azure.net')}",
        "Content-Type": "application/json",
    }


def _table_uri(workspace_id: str, lakehouse_id: str, table: str) -> str:
    # OneLake REJECTS mixing a workspace GUID with a friendly lakehouse name
    # (HTTP 400 FriendlyNameSupportDisabled). Use GUIDs for both segments.
    # No `.Lakehouse` suffix is needed (or allowed) when addressing by GUID.
    return (
        f"abfss://{workspace_id}@{ONELAKE_DFS}/{lakehouse_id}"
        f"/Tables/{table}"
    )


# ---- Setup: verify the pre-created fixture Delta table -------------------


def _verify_fixture_table(
    credential, workspace_id: str, lakehouse_id: str, table: str, sensitivity: str
) -> None:
    """Read-only check that the pre-created fixture table exists with the
    expected `data-sensitivity` TBLPROPERTY.

    The fixture table is NOT created by the test — the delta-rs / Rust kernel
    rejects custom TBLPROPERTIES like `data-sensitivity` ("Error parsing
    property"). Production sets these via Spark SQL `ALTER TABLE ... SET
    TBLPROPERTIES` from a Fabric notebook (see
    `src/notebook/create_sensitivity_tables.ipynb`), which goes through
    Spark's Delta writer and bypasses the kernel's strict validation.

    To set up: run that notebook against the source lakehouse to create
    `<table>` with `data-sensitivity = '<sensitivity>'`, OR add a row for it
    to the notebook's TABLES list.
    """
    uri = _table_uri(workspace_id, lakehouse_id, table)
    opts = _storage_opts(credential)
    try:
        dt = DeltaTable(uri, storage_options=opts)
    except TableNotFoundError:
        pytest.fail(
            f"Fixture table '{table}' not found in lakehouse {lakehouse_id}. "
            f"Pre-create it once via src/notebook/create_sensitivity_tables.ipynb "
            f"with data-sensitivity='{sensitivity}'. See tests/integration/README.md."
        )
    config = dt.metadata().configuration or {}
    existing = config.get("data-sensitivity") or config.get("data_sensitivity")
    if (existing or "").strip().lower() != sensitivity.lower():
        pytest.fail(
            f"Fixture table '{table}' exists but data-sensitivity={existing!r} "
            f"(expected {sensitivity!r}). Re-run the notebook to fix the "
            f"TBLPROPERTY, or pick a different fixture_sensitivity in conftest."
        )
    logger.info(
        "Fixture table %s OK (data-sensitivity=%s)", table, existing
    )


# ---- Purview scan API -----------------------------------------------------


def _trigger_scan(
    credential, scan_root: str, data_source: str, scan_name: str, run_id: str
) -> None:
    # `scan_root` from `az purview account show` already ends in `/scan` for
    # Unified Purview accounts (e.g. https://{tenant}-api.purview-service.microsoft.com/scan).
    # Path here is `/datasources/...` -- do NOT prepend another `/scan/`.
    url = (
        f"{scan_root}/datasources/{data_source}/scans/{scan_name}/runs/{run_id}"
        f"?api-version=2023-09-01"
    )
    logger.info("POST %s", url)
    r = requests.post(url, headers=_atlas_headers(credential), timeout=60)
    if r.status_code == 403:
        pytest.fail(
            f"403 from {url}: the test identity needs *Data Source Administrator* "
            f"on the Purview collection that owns data source '{data_source}'. "
            f"Grant via Purview portal -> Data Map -> Collections -> "
            f"Role assignments. Response body: {r.text[:500]}"
        )
    if r.status_code not in (200, 202):
        pytest.fail(f"Failed to trigger scan ({r.status_code}) at {url}: {r.text[:1000]}")


def _wait_for_scan(
    credential,
    scan_root: str,
    data_source: str,
    scan_name: str,
    run_id: str,
    timeout_s: int,
    poll_s: int,
) -> str:
    """Poll until status is terminal. Returns final status string."""
    url = (
        f"{scan_root}/datasources/{data_source}/scans/{scan_name}/runs/{run_id}"
        f"?api-version=2023-09-01"
    )
    deadline = time.time() + timeout_s
    last_status = "unknown"
    while time.time() < deadline:
        r = requests.get(url, headers=_atlas_headers(credential), timeout=30)
        if r.status_code == 404:
            logger.info("Scan run not yet visible (404), retrying...")
        else:
            r.raise_for_status()
            last_status = r.json().get("status", "unknown")
            logger.info("Scan run status: %s", last_status)
            if last_status in (
                "Succeeded",
                "Failed",
                "Canceled",
                "Cancelled",
                "PartialSucceeded",
            ):
                return last_status
        time.sleep(poll_s)
    pytest.fail(
        f"Scan run {run_id} did not complete within {timeout_s}s (last status: {last_status})"
    )


# ---- Purview Atlas API ----------------------------------------------------


def _find_entity_guid(
    credential, catalog_root: str, table_name: str, lakehouse_name: str
) -> Optional[str]:
    """Search Atlas for an entity with this name belonging to this lakehouse."""
    url = f"{catalog_root}/datamap/api/search/query?api-version=2023-09-01"
    body = {
        "keywords": table_name,
        "limit": 50,
        "filter": {"objectType": "Tables"},
    }
    r = requests.post(url, headers=_atlas_headers(credential), json=body, timeout=30)
    r.raise_for_status()
    hits = r.json().get("value", [])
    candidates = [
        h
        for h in hits
        if (h.get("name") or "").lower() == table_name.lower()
        and lakehouse_name.lower() in (h.get("qualifiedName") or "").lower()
    ]
    if not candidates:
        candidates = [
            h for h in hits if (h.get("name") or "").lower() == table_name.lower()
        ]
    if not candidates:
        return None
    return candidates[0].get("id") or candidates[0].get("guid")


def _get_entity_classifications(credential, catalog_root: str, guid: str) -> list[dict]:
    url = (
        f"{catalog_root}/datamap/api/atlas/v2/entity/guid/{guid}"
        f"?api-version=2023-09-01"
    )
    r = requests.get(url, headers=_atlas_headers(credential), timeout=30)
    r.raise_for_status()
    entity = r.json().get("entity") or {}
    return entity.get("classifications") or []


def _remove_classification(
    credential, catalog_root: str, guid: str, classification_name: str
) -> None:
    url = (
        f"{catalog_root}/datamap/api/atlas/v2/entity/guid/{guid}"
        f"/classification/{classification_name}?api-version=2023-09-01"
    )
    r = requests.delete(url, headers=_atlas_headers(credential), timeout=30)
    if r.status_code in (200, 204, 404):
        return
    logger.warning("Could not remove classification %s: %s %s", classification_name, r.status_code, r.text[:300])


# ---- The test ------------------------------------------------------------


def test_e2e_scan_classifies_fixture_table(
    integration_config, az_credential, purview_endpoints
):
    cfg = integration_config
    expected_classification = "Sensitivity.Public"

    # ---- 1. Verify pre-created fixture table exists with correct TBLPROPERTY ----
    _verify_fixture_table(
        az_credential,
        cfg["workspace_id"],
        cfg["lakehouse_id"],
        cfg["fixture_table_name"],
        cfg["fixture_sensitivity"],
    )

    # ---- 2. Pre-clean: remove any stale Sensitivity.* classifications ----
    existing_guid = _find_entity_guid(
        az_credential,
        purview_endpoints["catalog_root"],
        cfg["fixture_table_name"],
        cfg["lakehouse_name"],
    )
    if existing_guid:
        logger.info(
            "Pre-clean: removing any Sensitivity.* on existing entity %s", existing_guid
        )
        for c in _get_entity_classifications(
            az_credential, purview_endpoints["catalog_root"], existing_guid
        ):
            name = c.get("typeName", "")
            if name.startswith("Sensitivity."):
                _remove_classification(
                    az_credential, purview_endpoints["catalog_root"], existing_guid, name
                )

    # ---- 3. Trigger scan ----
    run_id = cfg["scan_run_id"]
    logger.info("Triggering scan run %s on %s/%s", run_id, cfg["data_source_name"], cfg["scan_name"])
    _trigger_scan(
        az_credential,
        purview_endpoints["scan_root"],
        cfg["data_source_name"],
        cfg["scan_name"],
        run_id,
    )

    # ---- 4. Wait for scan to complete ----
    status = _wait_for_scan(
        az_credential,
        purview_endpoints["scan_root"],
        cfg["data_source_name"],
        cfg["scan_name"],
        run_id,
        cfg["scan_timeout_s"],
        cfg["poll_interval_s"],
    )
    assert status in ("Succeeded", "PartialSucceeded"), (
        f"Scan run {run_id} finished with non-success status: {status}"
    )

    # ---- 5. Wait for function to classify the entity ----
    deadline = time.time() + cfg["classification_timeout_s"]
    guid = None
    classifications: list[dict] = []
    while time.time() < deadline:
        guid = _find_entity_guid(
            az_credential,
            purview_endpoints["catalog_root"],
            cfg["fixture_table_name"],
            cfg["lakehouse_name"],
        )
        if guid:
            classifications = _get_entity_classifications(
                az_credential, purview_endpoints["catalog_root"], guid
            )
            names = [c.get("typeName", "") for c in classifications]
            logger.info("Entity %s classifications: %s", guid, names)
            if expected_classification in names:
                break
        time.sleep(cfg["poll_interval_s"])

    # ---- 6. Assert ----
    assert guid, (
        f"No Atlas entity found for fixture table '{cfg['fixture_table_name']}' "
        f"after scan succeeded. Possible causes: scan didn't index Tables, "
        f"data source isn't pointed at workspace '{cfg['workspace_id']}', "
        f"or Purview ingestion is lagging."
    )
    names = [c.get("typeName", "") for c in classifications]
    assert expected_classification in names, (
        f"Function did not attach {expected_classification} to entity {guid} "
        f"within {cfg['classification_timeout_s']}s. Found classifications: {names}. "
        f"Check Application Insights for the function 'classify_assets' to see "
        f"if it received the EH event and what it did with it. "
        f"Scan runId for cross-reference: {run_id}"
    )
    logger.info(
        "PASS: scan %s -> entity %s -> classification %s",
        run_id,
        guid,
        expected_classification,
    )

    # ---- 7. Best-effort cleanup (don't fail test) ----
    try:
        _remove_classification(
            az_credential, purview_endpoints["catalog_root"], guid, expected_classification
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cleanup failed (non-fatal): %s", exc)


# Make ruff happy — `uuid` imported but only used transitively via cfg.
_ = uuid

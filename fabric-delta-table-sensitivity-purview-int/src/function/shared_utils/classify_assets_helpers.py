"""Helpers for the `classify_assets` Event-Hub-triggered function.

These are the leaf operations used by `classify_assets_impl`:
  * `_list_lakehouse_tables` — enumerate Delta-table folders via OneLake DFS.
  * `_read_sensitivity`      — pull `data-sensitivity` from the Delta log.
  * `_find_entity_guid`      — locate the Purview Atlas entity for a table.
  * `_is_already_classified` — recognize the Purview/Atlas "already attached"
    response shape (the API returns either 409 or a 400 with a specific body).
  * `_classify`              — POST a classification (idempotent on typeName).
  * `_process_tables`        — orchestrate the four helpers above across a list
    of tables and emit a summary dict.

All shared cross-handler state (auth, HTTP session, config, event parsing)
lives in `purview_classification_utils`. This module only adds the
classify-side workflow on top.

Test note: `_process_tables` looks up `_read_sensitivity`, `_find_entity_guid`
and `_classify` via this module's globals at call time. Tests that exercise
`_process_tables` must therefore patch them on
`classify_assets.classify_assets_helpers.*`. Tests that exercise
`classify_assets_impl` patch on `classify_assets.handler.*` since the
entrypoint resolves these names through the handler module.
"""

from __future__ import annotations

import logging
from typing import Iterable

import requests
from deltalake import DeltaTable
from deltalake.exceptions import TableNotFoundError

from shared_utils.purview_classification_utils import (
    ATLAS_BASE,
    LAKEHOUSE_ID,
    LEVEL_MAP,
    NAMESPACE,
    ONELAKE_DFS,
    PURVIEW_ENDPOINT,
    WORKSPACE_ID,
    atlas_headers as _atlas_headers,
    bearer as _bearer,
    http as _http,
    storage_options as _storage_options,
)


def _list_lakehouse_tables() -> list[str]:
    """
    List Delta-table folder names under <lakehouse>/Tables.

    Uses the OneLake DFS filesystem-list API. Returns leaf table names only
    (no schema prefix; lakehouse is non-schema-enabled).
    """
    token = _bearer('https://storage.azure.com')
    list_url = (
        f'https://{ONELAKE_DFS}/{WORKSPACE_ID}'
        f'?directory={LAKEHOUSE_ID}/Tables&recursive=false&resource=filesystem'
    )
    resp = _http.get(list_url, headers={'Authorization': f'Bearer {token}'}, timeout=30)
    resp.raise_for_status()
    paths = resp.json().get('paths', [])
    table_names = []
    prefix = f'{LAKEHOUSE_ID}/Tables/'
    for p in paths:
        name = p.get('name', '')
        if name.startswith(prefix) and str(p.get('isDirectory', '')).lower() == 'true':
            leaf = name[len(prefix) :]
            if '/' not in leaf:
                table_names.append(leaf)
    return table_names


def _read_sensitivity(table_name: str) -> str | None:
    """
    Read `data-sensitivity` from the Delta log for a single table.
    """
    uri = f'abfss://{WORKSPACE_ID}@{ONELAKE_DFS}/{LAKEHOUSE_ID}/Tables/{table_name}'
    try:
        dt = DeltaTable(uri, storage_options=_storage_options())
        config = dt.metadata().configuration or {}
        return config.get('data-sensitivity') or config.get('data_sensitivity')
    except TableNotFoundError:
        logging.warning('Table not found at %s', uri)
        return None
    except Exception as exc:  # noqa: BLE001
        logging.exception('Failed to read Delta log for table %s: %s', table_name, exc)
        return None


def _find_entity_guid(table_name: str) -> str | None:
    """
    Find the Atlas entity GUID for a given lakehouse table.

    Uses Purview's discovery/query API scoped to the workspace + lakehouse.
    """
    body = {
        'keywords': table_name,
        'limit': 25,
        'filter': {'objectType': 'Tables'},
    }
    url = f'{PURVIEW_ENDPOINT}/datamap/api/search/query?api-version=2023-09-01'
    resp = _http.post(url, headers=_atlas_headers(), json=body, timeout=30)
    if resp.status_code == 404:
        url = f'{PURVIEW_ENDPOINT}/catalog/api/search/query?api-version=2022-08-01-preview'
        resp = _http.post(url, headers=_atlas_headers(), json=body, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get('value', [])
    candidates = [
        h
        for h in hits
        if h.get('name', '').lower() == table_name.lower()
        and (LAKEHOUSE_ID in (h.get('qualifiedName') or ''))
    ]
    if not candidates:
        candidates = [
            h for h in hits if h.get('name', '').lower() == table_name.lower()
        ]
    if not candidates:
        return None
    return candidates[0].get('id') or candidates[0].get('guid')


def _is_already_classified(resp: requests.Response, classification_name: str) -> bool:
    """
    Detect Purview's 'already attached' response across API variants.
    Atlas v2 spec returns 409 Conflict, but Purview Unified returns 400 with
    errorCode ATLAS-400-00-01A and 'already associated with classification' in
    the message body.
    """
    if resp.status_code == 409:
        return True
    if resp.status_code == 400:
        try:
            payload = resp.json()
        except ValueError:
            return False
        msg = (payload.get('errorMessage') or '').lower()
        if (
            'already associated with classification' in msg
            and classification_name.lower() in msg
        ):
            return True
    return False


def _classify(entity_guid: str, classification_name: str) -> None:
    """
    Attach a classification to an Atlas entity (idempotent on typeName).
    """
    body = [{'typeName': classification_name, 'propagate': True}]
    url = f'{ATLAS_BASE}/entity/guid/{entity_guid}/classifications'
    resp = _http.post(url, headers=_atlas_headers(), json=body, timeout=30)
    if _is_already_classified(resp, classification_name):
        logging.info(
            'Entity %s already classified as %s; no-op.',
            entity_guid,
            classification_name,
        )
        return
    if not resp.ok:
        logging.error(
            'Classify failed: %s %s -> %s body=%s',
            resp.request.method,
            url,
            resp.status_code,
            resp.text[:1000],
        )
    resp.raise_for_status()


def _process_tables(tables: Iterable[str]) -> dict:
    """
    Process a list of tables, classify them based on their sensitivity, and
    return a summary of the classification results.
    """
    summary = {
        'total': 0,
        'classified': 0,
        'skipped_no_property': 0,
        'skipped_no_entity': 0,
        'errors': 0,
    }
    for table in tables:
        summary['total'] += 1
        try:
            sensitivity = _read_sensitivity(table)
            if not sensitivity:
                logging.info(
                    'Table %s: no data-sensitivity TBLPROPERTY; skipping.', table
                )
                summary['skipped_no_property'] += 1
                continue
            level_key = sensitivity.strip().lower()
            suffix = LEVEL_MAP.get(level_key)
            if not suffix:
                logging.warning(
                    "Table %s: unknown sensitivity '%s'; skipping.", table, sensitivity
                )
                summary['skipped_no_property'] += 1
                continue
            classification_name = f'{NAMESPACE}.{suffix}'
            guid = _find_entity_guid(table)
            if not guid:
                logging.warning(
                    'Table %s: no Atlas entity found; cannot classify.', table
                )
                summary['skipped_no_entity'] += 1
                continue
            _classify(guid, classification_name)
            logging.info(
                'Table %s: classified entity %s with %s',
                table,
                guid,
                classification_name,
            )
            summary['classified'] += 1
        except Exception as exc:  # noqa: BLE001
            logging.exception('Table %s: error processing: %s', table, exc)
            summary['errors'] += 1
    return summary

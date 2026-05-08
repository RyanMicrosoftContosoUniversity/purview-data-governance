"""Event-Hub-triggered Function: classify Fabric lakehouse tables in Purview
based on the Delta `data-sensitivity` TBLPROPERTY.

Trigger:
    Microsoft.Purview ScanStatusLogEvent diagnostic logs streamed from the
    Purview account's diagnostic settings into an Event Hub. We filter to
    successful scans inside the function (diag pipeline doesn't support
    payload-based filters).

Flow:
1. Trigger:  Purview emits a ScanStatusLogEvent (diagnostic log) when a scan completes
2.  Diagnostic setting on Purview streams this to an Event Hub
3.  Function fires when it sees this log land
4. Filter:  If no event in the batch of logs has Status [Succeeded, Completed, PartiallySucceeded] nothing happens
5.  If it does, function app calls OneLake DFS API to list folders under <workspace>/<lakehouse>/Tables using the
functions Managed Identity token for storage.azure.com
6.  Operations for each table:
 - Read the _delta_log to get the table's data-sensitivity TBLPROPERTY (highly confidential, confidential, general, public)
 - Maps it to a classification catalog typedef name (like Sensitivity.HighlyConfidential)
 - Seaches Purview's catalog for the matching Atlas entity (by table name and lakehouse ID)
 - POSTs the classification onto the entity via Purview's Atlas API
    Example: POST /catalog/api/atlas/v2/entity/guid/{guid}/classifications
 - If classification label is already attached --> 400 returned as already classified
7. Logs a CLASSIFY_SUMMARY to app insights
"""

from __future__ import annotations
import json
import logging
import os
from typing import Iterable, List
import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from deltalake import DeltaTable
from deltalake.exceptions import TableNotFoundError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

### CONFIGURATION FROM FUNCTION APP SETTINGS / ENVIRONMENT VARIABLES #############################################################

WORKSPACE_ID = os.environ['SOURCE_WORKSPACE_ID']
LAKEHOUSE_ID = os.environ['SOURCE_LAKEHOUSE_ID']
LAKEHOUSE_NAME = os.environ['SOURCE_LAKEHOUSE_NAME']
PURVIEW_ACCOUNT = os.environ['PURVIEW_ACCOUNT']
NAMESPACE = os.environ.get('CLASSIFICATION_NAMESPACE', 'Sensitivity')
LEVEL_MAP = {
    k.strip().lower(): v
    for k, v in json.loads(os.environ['SENSITIVITY_LEVEL_MAP_JSON']).items()
}

PURVIEW_ENDPOINT = (
    os.environ.get('PURVIEW_ENDPOINT', '').rstrip('/')
    or f'https://{PURVIEW_ACCOUNT}.purview.azure.com'
)
ATLAS_BASE = f'{PURVIEW_ENDPOINT}/catalog/api/atlas/v2'
ONELAKE_DFS = 'onelake.dfs.fabric.microsoft.com'

_credential = DefaultAzureCredential()


def _build_session() -> requests.Session:
    """
    Session with retries for transient TLS / 5xx errors (the new Purview
    Unified endpoint is flaky on initial TLS handshakes).
    """
    s = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['GET', 'POST', 'PUT']),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s


_http = _build_session()


# --- Helpers -----------------------------------------------------------------


def _bearer(resource: str) -> str:
    """
    Acquire an AAD access token for the given resource scope.
    """
    scope = resource.rstrip('/') + '/.default'
    return _credential.get_token(scope).token


def _atlas_headers() -> dict:
    return {
        'Authorization': f'Bearer {_bearer("https://purview.azure.net")}',
        'Content-Type': 'application/json',
    }


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
    storage_token = _bearer('https://storage.azure.com')
    uri = f'abfss://{WORKSPACE_ID}@{ONELAKE_DFS}/{LAKEHOUSE_ID}/Tables/{table_name}'
    try:
        dt = DeltaTable(
            uri,
            storage_options={
                'bearer_token': storage_token,
                'use_fabric_endpoint': 'true',
            },
        )
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

    # --- Function entrypoint -----------------------------------------------------


_SUCCESS_STATUSES = {'succeeded', 'completed', 'partiallysucceeded'}


def _is_successful_scan(payload: dict) -> bool:
    """Return True if a diagnostic-log row represents a successful scan event.

    Purview ScanStatusLogEvent diagnostic rows have the scan outcome under
    `properties.resultType` (newer schema) or `data.status` (legacy/EG
    payload). We accept either to stay tolerant across pipeline versions.
    """
    if not isinstance(payload, dict):
        return False
    candidates = []
    props = payload.get('properties')
    if isinstance(props, dict):
        candidates.append(props.get('resultType'))
        candidates.append(props.get('status'))
    data = payload.get('data')
    if isinstance(data, dict):
        candidates.append(data.get('status'))
        candidates.append(data.get('resultType'))
    candidates.append(payload.get('status'))
    candidates.append(payload.get('resultType'))
    return any(
        isinstance(c, str) and c.strip().lower() in _SUCCESS_STATUSES
        for c in candidates
    )


def classify_assets_impl(events: List[func.EventHubEvent]) -> None:
    """
    Triggered by Purview ScanStatusLogEvent rows streamed via diagnostic
    settings into an Event Hub.

    Diagnostic settings can't filter on payload, so we filter here: if no event
    in the batch corresponds to a successful scan, we no-op. Otherwise we
    re-classify the entire configured lakehouse — sensitivity tags can be
    added/changed at any time, so a full pass is the safest behaviour. The
    per-table classification call is a no-op when the typeName is already
    attached.
    """
    if not isinstance(events, list):
        events = [events]

    parsed: list[dict] = []
    for ev in events:
        try:
            body = ev.get_body().decode('utf-8')
        except Exception:  # noqa: BLE001
            continue
            # Diagnostic rows arrive either as a single JSON object or as a
            # newline-delimited / `records`-wrapped batch.
        try:
            doc = json.loads(body)
        except ValueError:
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed.append(json.loads(line))
                except ValueError:
                    logging.warning('Skipping non-JSON event body line: %.200s', line)
            continue
        if isinstance(doc, dict) and isinstance(doc.get('records'), list):
            parsed.extend(r for r in doc['records'] if isinstance(r, dict))
        elif isinstance(doc, list):
            parsed.extend(r for r in doc if isinstance(r, dict))
        elif isinstance(doc, dict):
            parsed.append(doc)

    logging.info(
        'classify_assets EH batch: events=%d parsed=%d', len(events), len(parsed)
    )

    successful = [p for p in parsed if _is_successful_scan(p)]
    if parsed and not successful:
        logging.info(
            'No successful-scan events in batch; skipping classification pass.'
        )
        return

    for p in successful[:5]:
        props = p.get('properties') if isinstance(p.get('properties'), dict) else {}
        logging.info(
            'scan event: op=%s result=%s scan=%s source=%s',
            p.get('operationName'),
            (props.get('resultType') or props.get('status') or p.get('status')),
            (props.get('scanName') or p.get('scanName')),
            (props.get('dataSource') or p.get('dataSource')),
        )

    tables = _list_lakehouse_tables()
    logging.info('Discovered %d tables under lakehouse %s', len(tables), LAKEHOUSE_NAME)

    summary = _process_tables(tables)
    logging.info('CLASSIFY_SUMMARY %s', json.dumps(summary))

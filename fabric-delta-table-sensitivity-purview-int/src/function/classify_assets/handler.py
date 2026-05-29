"""
Event-Hub-triggered Function: classify Fabric lakehouse tables in Purview
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
from typing import List
import azure.functions as func

from shared_utils.purview_classification_utils import (
    LAKEHOUSE_NAME,
    parse_event_documents as _parse_event_documents,
)

from shared_utils.classify_assets_helpers import (  # noqa: F401  (re-export surface)
    _classify,
    _find_entity_guid,
    _is_already_classified,
    _list_lakehouse_tables,
    _process_tables,
    _read_sensitivity,
)


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

    parsed = _parse_event_documents(events)

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

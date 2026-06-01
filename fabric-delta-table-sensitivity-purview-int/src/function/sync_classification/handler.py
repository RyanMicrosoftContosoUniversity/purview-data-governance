"""Event-Hub-triggered Function: sync Purview sensitivity classifications back
onto Fabric Delta table `data-sensitivity` TBLPROPERTY values.

Trigger:
    Purview Atlas ENTITY_NOTIFICATION_V2 events emitted to the BYO notification
    Event Hub. We filter cheaply inside the function to the configured source
    workspace + lakehouse and only classification-affecting operation types.

Flow:
1. Trigger: Purview emits entity/classification notifications to Event Hub.
2. Filter: keep only operations that can affect classifications and whose
   qualifiedName targets the configured workspace + lakehouse.
3. De-duplicate by entity GUID within the Event Hub batch.
4. Re-read each entity from Purview Atlas (event payload may be stale).
5. Resolve the desired Delta `data-sensitivity` value from the entity's current
   Sensitivity.* classifications, or `DELETED_SENSITIVITY_VALUE` when none
   remain.
6. Read the current Delta table property and skip if already in sync.
7. Update the Delta table property and log a RESYNC_SUMMARY line.
"""

from __future__ import annotations

import json
import logging
from typing import List

import azure.functions as func

# Re-exported so existing tests that patch `sync_classification.handler.DeltaTable`
# (and any future ones) keep working without reaching into shared_utils.
from deltalake import DeltaTable  # noqa: F401

from shared_utils.purview_classification_utils import (
    parse_event_documents as _parse_event_documents,
)
from shared_utils.sync_classification_helpers import (
    RELEVANT_OPERATIONS as _RELEVANT_OPERATIONS,
    _entity_guid,
    _entity_ref,
    _is_in_scope_qualified_name,
    _process_entity_guids,
    _qualified_name,
)


def sync_classification_impl(events: List[func.EventHubEvent]) -> None:
    """
    Triggered by Purview Atlas ENTITY_NOTIFICATION_V2 events streamed to the
    BYO atlas-notifications Event Hub.

    The event payload can be stale or out-of-order, so qualifying notifications
    are only used to identify candidate entity GUIDs. Each GUID is then re-read
    from Purview and the current classifications are treated as the source of
    truth before updating the corresponding Delta table property.
    """
    if not isinstance(events, list):
        events = [events]

    parsed = _parse_event_documents(events)
    summary = {
        'total': len(parsed),
        'in_scope': 0,
        'updated': 0,
        'skipped_out_of_scope': 0,
        'skipped_already_in_sync': 0,
        'skipped_no_entity': 0,
        'errors': 0,
    }
    logging.info(
        'sync_classification EH batch: events=%d parsed=%d', len(events), len(parsed)
    )

    unique_guids: list[str] = []
    seen_guids: set[str] = set()
    for payload in parsed:
        operation_type = str(payload.get('operationType') or '').strip().lower()
        if operation_type not in _RELEVANT_OPERATIONS:
            summary['skipped_out_of_scope'] += 1
            continue
        entity_ref = _entity_ref(payload)
        qualified_name = _qualified_name(entity_ref)
        guid = _entity_guid(entity_ref)
        if (
            not qualified_name
            or not _is_in_scope_qualified_name(qualified_name)
            or not guid
        ):
            summary['skipped_out_of_scope'] += 1
            continue
        if guid not in seen_guids:
            seen_guids.add(guid)
            unique_guids.append(guid)

    processed_summary = _process_entity_guids(unique_guids)
    summary.update(processed_summary)
    logging.info('RESYNC_SUMMARY %s', json.dumps(summary))

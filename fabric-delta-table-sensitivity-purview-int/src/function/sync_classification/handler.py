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
import os
from typing import Iterable, List
import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from deltalake import DeltaTable
from deltalake.exceptions import CommitFailedError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

### CONFIGURATION FROM FUNCTION APP SETTINGS / ENVIRONMENT VARIABLES #############################################################

WORKSPACE_ID = os.environ['SOURCE_WORKSPACE_ID']
LAKEHOUSE_ID = os.environ['SOURCE_LAKEHOUSE_ID']
LAKEHOUSE_NAME = os.environ['SOURCE_LAKEHOUSE_NAME']
PURVIEW_ACCOUNT = os.environ['PURVIEW_ACCOUNT']
NAMESPACE = os.environ.get('CLASSIFICATION_NAMESPACE', 'Sensitivity')
_RAW_LEVEL_MAP = json.loads(os.environ['SENSITIVITY_LEVEL_MAP_JSON'])
LEVEL_MAP = {k.strip().lower(): v for k, v in _RAW_LEVEL_MAP.items()}
INVERSE_LEVEL_MAP = {
    str(v).strip().lower(): str(k).strip() for k, v in _RAW_LEVEL_MAP.items()
}
SEVERITY_ORDER = json.loads(
    os.environ.get(
        'SENSITIVITY_SEVERITY_ORDER_JSON',
        '["HighlyConfidential", "Confidential", "General", "Public"]',
    )
)
SEVERITY_RANK = {
    str(value).strip().lower(): index for index, value in enumerate(SEVERITY_ORDER)
}
DELETED_SENSITIVITY_VALUE = os.environ.get('DELETED_SENSITIVITY_VALUE', 'None')

PURVIEW_ENDPOINT = (
    os.environ.get('PURVIEW_ENDPOINT', '').rstrip('/')
    or f'https://{PURVIEW_ACCOUNT}.purview.azure.com'
)
ONELAKE_DFS = 'onelake.dfs.fabric.microsoft.com'
_RELEVANT_OPERATIONS = {
    'entity_create',
    'entity_update',
    'classification_add',
    'classification_update',
    'classification_delete',
}

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


def _storage_options() -> dict[str, str]:
    return {
        'bearer_token': _bearer('https://storage.azure.com'),
        'use_fabric_endpoint': 'true',
    }


def _parse_event_documents(events: List[func.EventHubEvent]) -> list[dict]:
    parsed: list[dict] = []
    for ev in events:
        try:
            body = ev.get_body().decode('utf-8')
        except Exception:  # noqa: BLE001
            continue
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
    return parsed


def _entity_ref(payload: dict) -> dict:
    entity = payload.get('entity') if isinstance(payload.get('entity'), dict) else None
    if entity:
        return entity
    entity_ref = (
        payload.get('entityRef') if isinstance(payload.get('entityRef'), dict) else None
    )
    return entity_ref or {}


def _qualified_name(entity_ref: dict) -> str:
    attrs = (
        entity_ref.get('attributes')
        if isinstance(entity_ref.get('attributes'), dict)
        else {}
    )
    return str(attrs.get('qualifiedName') or entity_ref.get('qualifiedName') or '')


def _entity_guid(entity_ref: dict) -> str:
    return str(entity_ref.get('guid') or '').strip()


def _is_in_scope_qualified_name(qualified_name: str) -> bool:
    qn = qualified_name.strip().lower()
    return WORKSPACE_ID.lower() in qn and LAKEHOUSE_ID.lower() in qn


def _entity_get_url(guid: str) -> str:
    return f'{PURVIEW_ENDPOINT}/datamap/api/atlas/v2/entity/guid/{guid}?api-version=2023-09-01'


def _legacy_entity_get_url(guid: str) -> str:
    return f'{PURVIEW_ENDPOINT}/catalog/api/atlas/v2/entity/guid/{guid}'


def _get_entity(guid: str) -> dict | None:
    url = _entity_get_url(guid)
    resp = _http.get(url, headers=_atlas_headers(), timeout=30)
    if resp.status_code == 404:
        url = _legacy_entity_get_url(guid)
        resp = _http.get(url, headers=_atlas_headers(), timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _entity_from_document(document: dict) -> dict:
    entity = (
        document.get('entity') if isinstance(document.get('entity'), dict) else None
    )
    return entity or document


def _table_name(entity: dict) -> str | None:
    attrs = (
        entity.get('attributes') if isinstance(entity.get('attributes'), dict) else {}
    )
    name = attrs.get('name')
    return str(name).strip() if name else None


def _normalize(value: str | None) -> str:
    return (value or '').strip().lower()


def _matching_sensitivity_classifications(classifications: Iterable[dict]) -> list[str]:
    prefix = f'{NAMESPACE}.'.lower()
    matched: list[str] = []
    for classification in classifications:
        if not isinstance(classification, dict):
            continue
        type_name = classification.get('typeName')
        if isinstance(type_name, str) and type_name.strip().lower().startswith(prefix):
            matched.append(type_name.strip())
    return matched


def _classification_target_value(type_name: str) -> str:
    suffix = type_name.split('.', 1)[1] if '.' in type_name else type_name
    mapped = INVERSE_LEVEL_MAP.get(suffix.strip().lower())
    if not mapped:
        raise ValueError(f'No data-sensitivity mapping for classification {type_name}')
    return mapped


def _choose_target_value(entity: dict, guid: str) -> str:
    classifications = entity.get('classifications')
    matches = _matching_sensitivity_classifications(classifications or [])
    if not matches:
        return DELETED_SENSITIVITY_VALUE
    if len(matches) == 1:
        return _classification_target_value(matches[0])

    def _rank(type_name: str) -> tuple[int, str]:
        suffix = type_name.split('.', 1)[1] if '.' in type_name else type_name
        return (
            SEVERITY_RANK.get(suffix.strip().lower(), len(SEVERITY_RANK) + 100),
            suffix.lower(),
        )

    chosen = sorted(matches, key=_rank)[0]
    logging.warning(
        'Entity %s: multiple %s classifications %s; choosing %s',
        guid,
        NAMESPACE,
        matches,
        chosen,
    )
    return _classification_target_value(chosen)


def _delta_uri(table_name: str) -> str:
    return f'abfss://{WORKSPACE_ID}@{ONELAKE_DFS}/{LAKEHOUSE_ID}/Tables/{table_name}'


def _open_delta_table(table_name: str) -> DeltaTable:
    return DeltaTable(_delta_uri(table_name), storage_options=_storage_options())


def _current_data_sensitivity(dt: DeltaTable) -> str | None:
    config = dt.metadata().configuration or {}
    return config.get('data-sensitivity') or config.get('data_sensitivity')


def _set_data_sensitivity(dt: DeltaTable, value: str) -> None:
    dt.alter.set_table_properties({'data-sensitivity': value})


def _set_data_sensitivity_with_retry(table_name: str, value: str) -> None:
    dt = _open_delta_table(table_name)
    try:
        _set_data_sensitivity(dt, value)
    except CommitFailedError:
        logging.warning(
            'Table %s: Delta commit conflict while setting data-sensitivity; retrying once.',
            table_name,
        )
        dt = _open_delta_table(table_name)
        _set_data_sensitivity(dt, value)


def _process_entity_guids(entity_guids: Iterable[str]) -> dict:
    summary = {
        'in_scope': 0,
        'updated': 0,
        'skipped_already_in_sync': 0,
        'skipped_no_entity': 0,
        'errors': 0,
    }
    for guid in entity_guids:
        summary['in_scope'] += 1
        try:
            document = _get_entity(guid)
            if not document:
                logging.warning('Entity %s: not found in Purview; skipping.', guid)
                summary['skipped_no_entity'] += 1
                continue
            entity = _entity_from_document(document)
            table_name = _table_name(entity)
            if not table_name:
                logging.warning('Entity %s: missing attributes.name; skipping.', guid)
                summary['skipped_no_entity'] += 1
                continue
            target_value = _choose_target_value(entity, guid)
            current_value = _current_data_sensitivity(_open_delta_table(table_name))
            if _normalize(current_value) == _normalize(target_value):
                logging.info(
                    'Table %s entity %s already in sync with data-sensitivity=%s; skipping.',
                    table_name,
                    guid,
                    target_value,
                )
                summary['skipped_already_in_sync'] += 1
                continue
            _set_data_sensitivity_with_retry(table_name, target_value)
            logging.info(
                'Table %s: updated data-sensitivity to %s from entity %s',
                table_name,
                target_value,
                guid,
            )
            summary['updated'] += 1
        except Exception as exc:  # noqa: BLE001
            logging.exception('Entity %s: error syncing classification: %s', guid, exc)
            summary['errors'] += 1
    return summary


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

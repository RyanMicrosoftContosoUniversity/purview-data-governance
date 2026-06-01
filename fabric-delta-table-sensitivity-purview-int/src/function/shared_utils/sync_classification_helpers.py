"""Helpers for the sync_classification handler.

Contains the sync-specific configuration (severity ordering, inverse level map,
relevant operations) plus all helpers used to resolve, compare, and write
Delta `data-sensitivity` values from Purview Atlas entity notifications.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable

from deltalake import DeltaTable
from deltalake.exceptions import CommitFailedError

from shared_utils.purview_classification_utils import (
    LAKEHOUSE_ID,
    NAMESPACE,
    ONELAKE_DFS,
    PURVIEW_ENDPOINT,
    WORKSPACE_ID,
    atlas_headers as _atlas_headers,
    http as _http,
    storage_options as _storage_options,
)


### CONFIGURATION (sync-specific) #############################################

_RAW_LEVEL_MAP = json.loads(os.environ['SENSITIVITY_LEVEL_MAP_JSON'])
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

RELEVANT_OPERATIONS = {
    'entity_create',
    'entity_update',
    'classification_add',
    'classification_update',
    'classification_delete',
}


# --- Helpers -----------------------------------------------------------------


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

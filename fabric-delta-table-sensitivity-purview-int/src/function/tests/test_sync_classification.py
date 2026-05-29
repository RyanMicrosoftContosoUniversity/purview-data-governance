from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock, patch

import responses

from sync_classification.handler import sync_classification_impl


def _summary_from_caplog(caplog):
    for record in caplog.records:
        if record.message.startswith('RESYNC_SUMMARY '):
            return json.loads(record.message.split(' ', 1)[1])
    raise AssertionError('RESYNC_SUMMARY not found in logs')


def _entity_payload(workspace_id, lakehouse_id, guid='g1', operation_type='CLASSIFICATION_ADD'):
    return {
        'operationType': operation_type,
        'entity': {
            'guid': guid,
            'attributes': {
                'qualifiedName': (
                    f'https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/'
                    f'{lakehouse_id}/tables/appointments'
                )
            },
        },
    }


def _entity_document(workspace_id, lakehouse_id, type_names, table_name='appointments'):
    return {
        'entity': {
            'guid': 'g1',
            'attributes': {
                'name': table_name,
                'qualifiedName': (
                    f'https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/'
                    f'{lakehouse_id}/tables/{table_name}'
                ),
            },
            'classifications': [{'typeName': name} for name in type_names],
        }
    }


@responses.activate
def test_sync_impl_skips_out_of_scope_qualified_name(make_eh_event, caplog):
    caplog.set_level('INFO')
    event = make_eh_event(
        {
            'operationType': 'CLASSIFICATION_ADD',
            'entity': {
                'guid': 'g1',
                'attributes': {'qualifiedName': 'https://example.invalid/other/lakehouse/table'},
            },
        }
    )

    sync_classification_impl([event])

    assert len(responses.calls) == 0
    assert _summary_from_caplog(caplog)['skipped_out_of_scope'] == 1


@responses.activate
def test_sync_impl_skips_irrelevant_operation_type(workspace_id, lakehouse_id, make_eh_event, caplog):
    caplog.set_level('INFO')
    event = make_eh_event(
        _entity_payload(workspace_id, lakehouse_id, operation_type='RELATIONSHIP_CREATE')
    )

    sync_classification_impl([event])

    assert len(responses.calls) == 0
    assert _summary_from_caplog(caplog)['skipped_out_of_scope'] == 1


@responses.activate
def test_sync_impl_updates_delta_property_from_single_classification(
    purview_url, workspace_id, lakehouse_id, make_eh_event, caplog
):
    caplog.set_level('INFO')
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json=_entity_document(workspace_id, lakehouse_id, ['Sensitivity.Confidential']),
    )
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': 'public'}

    with patch('sync_classification.handler.DeltaTable', return_value=fake_dt) as delta_table:
        sync_classification_impl([make_eh_event(_entity_payload(workspace_id, lakehouse_id))])

    delta_table.assert_called()
    fake_dt.alter.set_table_properties.assert_called_once_with(
        {'data-sensitivity': 'confidential'}
    )
    assert _summary_from_caplog(caplog)['updated'] == 1


@responses.activate
def test_sync_impl_skips_when_table_already_in_sync(
    purview_url, workspace_id, lakehouse_id, make_eh_event, caplog
):
    caplog.set_level('INFO')
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json=_entity_document(workspace_id, lakehouse_id, ['Sensitivity.Confidential']),
    )
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': ' Confidential '}

    with patch('sync_classification.handler.DeltaTable', return_value=fake_dt):
        sync_classification_impl([make_eh_event(_entity_payload(workspace_id, lakehouse_id))])

    fake_dt.alter.set_table_properties.assert_not_called()
    assert _summary_from_caplog(caplog)['skipped_already_in_sync'] == 1


@responses.activate
def test_sync_impl_chooses_highest_severity_when_multiple_match(
    purview_url, workspace_id, lakehouse_id, make_eh_event, caplog
):
    caplog.set_level('INFO')
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json=_entity_document(
            workspace_id,
            lakehouse_id,
            ['Sensitivity.Public', 'Sensitivity.HighlyConfidential'],
        ),
    )
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': 'public'}

    with patch('sync_classification.handler.DeltaTable', return_value=fake_dt):
        sync_classification_impl([make_eh_event(_entity_payload(workspace_id, lakehouse_id))])

    fake_dt.alter.set_table_properties.assert_called_once_with(
        {'data-sensitivity': 'highly confidential'}
    )
    assert 'multiple Sensitivity classifications' in caplog.text


@responses.activate
def test_sync_impl_uses_deleted_value_when_no_sensitivity_classification(
    purview_url, workspace_id, lakehouse_id, make_eh_event, caplog
):
    caplog.set_level('INFO')
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json=_entity_document(workspace_id, lakehouse_id, ['Glossary.Term']),
    )
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': 'public'}

    with patch('sync_classification.handler.DeltaTable', return_value=fake_dt):
        sync_classification_impl([make_eh_event(_entity_payload(workspace_id, lakehouse_id))])

    fake_dt.alter.set_table_properties.assert_called_once_with({'data-sensitivity': 'None'})
    assert _summary_from_caplog(caplog)['updated'] == 1


@responses.activate
def test_sync_impl_deduplicates_guids_within_batch(
    purview_url, workspace_id, lakehouse_id, make_eh_event, caplog
):
    caplog.set_level('INFO')
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json=_entity_document(workspace_id, lakehouse_id, ['Sensitivity.Confidential']),
    )
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': 'public'}

    with patch('sync_classification.handler.DeltaTable', return_value=fake_dt):
        sync_classification_impl(
            [
                make_eh_event(_entity_payload(workspace_id, lakehouse_id, guid='g1')),
                make_eh_event(
                    _entity_payload(
                        workspace_id,
                        lakehouse_id,
                        guid='g1',
                        operation_type='CLASSIFICATION_UPDATE',
                    )
                ),
                make_eh_event(
                    _entity_payload(
                        workspace_id,
                        lakehouse_id,
                        guid='g1',
                        operation_type='ENTITY_UPDATE',
                    )
                ),
            ]
        )

    assert len(responses.calls) == 1
    fake_dt.alter.set_table_properties.assert_called_once_with(
        {'data-sensitivity': 'confidential'}
    )
    summary = _summary_from_caplog(caplog)
    assert summary['total'] == 3
    assert summary['in_scope'] == 1


def test_function_app_registers_sync_classification_trigger():
    mod = importlib.import_module('function_app')
    assert hasattr(mod, 'sync_classification')

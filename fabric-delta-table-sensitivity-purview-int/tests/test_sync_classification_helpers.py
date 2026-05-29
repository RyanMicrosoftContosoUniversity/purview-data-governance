"""Unit tests for shared_utils.sync_classification_helpers.

Targets each helper directly. End-to-end coverage of
`sync_classification_impl` lives in `test_sync_classification.py`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import responses
from deltalake.exceptions import CommitFailedError

from shared_utils import sync_classification_helpers as helpers


# ---- _entity_ref ------------------------------------------------------------


def test_entity_ref_prefers_entity_key():
    payload = {'entity': {'guid': 'g1'}, 'entityRef': {'guid': 'g2'}}
    assert helpers._entity_ref(payload) == {'guid': 'g1'}


def test_entity_ref_falls_back_to_entityref():
    payload = {'entityRef': {'guid': 'g2'}}
    assert helpers._entity_ref(payload) == {'guid': 'g2'}


def test_entity_ref_returns_empty_dict_when_missing():
    assert helpers._entity_ref({}) == {}


def test_entity_ref_ignores_non_dict_values():
    assert helpers._entity_ref({'entity': 'string', 'entityRef': None}) == {}


# ---- _qualified_name / _entity_guid -----------------------------------------


def test_qualified_name_reads_from_attributes():
    ref = {'attributes': {'qualifiedName': 'qn1'}}
    assert helpers._qualified_name(ref) == 'qn1'


def test_qualified_name_falls_back_to_top_level():
    assert helpers._qualified_name({'qualifiedName': 'qn2'}) == 'qn2'


def test_qualified_name_returns_empty_string_when_missing():
    assert helpers._qualified_name({}) == ''


def test_entity_guid_strips_whitespace():
    assert helpers._entity_guid({'guid': '  g1  '}) == 'g1'


def test_entity_guid_returns_empty_string_when_missing():
    assert helpers._entity_guid({}) == ''


# ---- _is_in_scope_qualified_name -------------------------------------------


def test_is_in_scope_requires_both_ids(workspace_id, lakehouse_id):
    qn = f'https://x/{workspace_id}/lakehouses/{lakehouse_id}/tables/t'
    assert helpers._is_in_scope_qualified_name(qn) is True


def test_is_in_scope_rejects_when_workspace_missing(lakehouse_id):
    assert helpers._is_in_scope_qualified_name(f'/lakehouses/{lakehouse_id}/t') is False


def test_is_in_scope_rejects_when_lakehouse_missing(workspace_id):
    assert helpers._is_in_scope_qualified_name(f'/{workspace_id}/other/t') is False


# ---- _normalize -------------------------------------------------------------


def test_normalize_handles_none():
    assert helpers._normalize(None) == ''


def test_normalize_lowercases_and_strips():
    assert helpers._normalize('  Confidential  ') == 'confidential'


# ---- _matching_sensitivity_classifications ---------------------------------


def test_matching_sensitivity_classifications_filters_by_namespace():
    inputs = [
        {'typeName': 'Sensitivity.Public'},
        {'typeName': 'Glossary.PII'},
        {'typeName': 'sensitivity.confidential'},
        'not-a-dict',
        {},
    ]
    assert helpers._matching_sensitivity_classifications(inputs) == [
        'Sensitivity.Public',
        'sensitivity.confidential',
    ]


# ---- _classification_target_value ------------------------------------------


def test_classification_target_value_maps_namespaced_type():
    assert helpers._classification_target_value('Sensitivity.Public') == 'public'


def test_classification_target_value_raises_on_unknown_type():
    with pytest.raises(ValueError):
        helpers._classification_target_value('Sensitivity.Unknown')


# ---- _choose_target_value ---------------------------------------------------


def test_choose_target_value_returns_deleted_when_no_match():
    entity = {'classifications': [{'typeName': 'Glossary.PII'}]}
    assert helpers._choose_target_value(entity, 'g1') == helpers.DELETED_SENSITIVITY_VALUE


def test_choose_target_value_single_match():
    entity = {'classifications': [{'typeName': 'Sensitivity.Confidential'}]}
    assert helpers._choose_target_value(entity, 'g1') == 'confidential'


def test_choose_target_value_picks_highest_severity_on_multi(caplog):
    caplog.set_level('WARNING')
    entity = {
        'classifications': [
            {'typeName': 'Sensitivity.Public'},
            {'typeName': 'Sensitivity.HighlyConfidential'},
            {'typeName': 'Sensitivity.General'},
        ]
    }
    assert helpers._choose_target_value(entity, 'g1') == 'highly confidential'
    assert 'multiple Sensitivity classifications' in caplog.text


# ---- _table_name / _entity_from_document -----------------------------------


def test_table_name_reads_from_attributes():
    assert helpers._table_name({'attributes': {'name': '  patients  '}}) == 'patients'


def test_table_name_returns_none_when_missing():
    assert helpers._table_name({'attributes': {}}) is None
    assert helpers._table_name({}) is None


def test_entity_from_document_unwraps_entity_envelope():
    doc = {'entity': {'guid': 'g1'}}
    assert helpers._entity_from_document(doc) == {'guid': 'g1'}


def test_entity_from_document_returns_document_when_no_envelope():
    doc = {'guid': 'g1'}
    assert helpers._entity_from_document(doc) == doc


# ---- _get_entity ------------------------------------------------------------


@responses.activate
def test_get_entity_returns_json_when_found(purview_url):
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json={'entity': {'guid': 'g1'}},
    )
    assert helpers._get_entity('g1') == {'entity': {'guid': 'g1'}}


@responses.activate
def test_get_entity_falls_back_to_legacy_url(purview_url):
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json={}, status=404,
    )
    responses.get(
        f'{purview_url}/catalog/api/atlas/v2/entity/guid/g1',
        json={'entity': {'guid': 'g1', 'legacy': True}},
    )
    assert helpers._get_entity('g1') == {'entity': {'guid': 'g1', 'legacy': True}}


@responses.activate
def test_get_entity_returns_none_when_both_urls_404(purview_url):
    responses.get(
        f'{purview_url}/datamap/api/atlas/v2/entity/guid/g1?api-version=2023-09-01',
        json={}, status=404,
    )
    responses.get(
        f'{purview_url}/catalog/api/atlas/v2/entity/guid/g1',
        json={}, status=404,
    )
    assert helpers._get_entity('g1') is None


# ---- _current_data_sensitivity / set helpers --------------------------------


def test_current_data_sensitivity_handles_both_key_names():
    dt = MagicMock()
    dt.metadata.return_value.configuration = {'data-sensitivity': 'Public'}
    assert helpers._current_data_sensitivity(dt) == 'Public'
    dt.metadata.return_value.configuration = {'data_sensitivity': 'Public'}
    assert helpers._current_data_sensitivity(dt) == 'Public'
    dt.metadata.return_value.configuration = None
    assert helpers._current_data_sensitivity(dt) is None


def test_set_data_sensitivity_calls_alter():
    dt = MagicMock()
    helpers._set_data_sensitivity(dt, 'public')
    dt.alter.set_table_properties.assert_called_once_with({'data-sensitivity': 'public'})


def test_set_data_sensitivity_with_retry_retries_once_on_commit_conflict(caplog):
    caplog.set_level('WARNING')
    first = MagicMock()
    first.alter.set_table_properties.side_effect = CommitFailedError('conflict')
    second = MagicMock()
    with patch.object(helpers, '_open_delta_table', side_effect=[first, second]):
        helpers._set_data_sensitivity_with_retry('patients', 'public')
    first.alter.set_table_properties.assert_called_once()
    second.alter.set_table_properties.assert_called_once_with(
        {'data-sensitivity': 'public'}
    )
    assert 'Delta commit conflict' in caplog.text


def test_set_data_sensitivity_with_retry_propagates_repeated_failure():
    dt = MagicMock()
    dt.alter.set_table_properties.side_effect = CommitFailedError('conflict')
    with patch.object(helpers, '_open_delta_table', return_value=dt):
        with pytest.raises(CommitFailedError):
            helpers._set_data_sensitivity_with_retry('patients', 'public')


# ---- _process_entity_guids --------------------------------------------------


def test_process_entity_guids_updates_when_out_of_sync():
    document = {
        'entity': {
            'guid': 'g1',
            'attributes': {'name': 'patients'},
            'classifications': [{'typeName': 'Sensitivity.Confidential'}],
        }
    }
    dt = MagicMock()
    dt.metadata.return_value.configuration = {'data-sensitivity': 'public'}
    with (
        patch.object(helpers, '_get_entity', return_value=document),
        patch.object(helpers, '_open_delta_table', return_value=dt),
    ):
        summary = helpers._process_entity_guids(['g1'])
    dt.alter.set_table_properties.assert_called_once_with(
        {'data-sensitivity': 'confidential'}
    )
    assert summary['updated'] == 1
    assert summary['in_scope'] == 1


def test_process_entity_guids_skips_when_entity_not_found():
    with patch.object(helpers, '_get_entity', return_value=None):
        summary = helpers._process_entity_guids(['g1'])
    assert summary['skipped_no_entity'] == 1


def test_process_entity_guids_skips_when_attributes_name_missing():
    document = {'entity': {'guid': 'g1', 'attributes': {}}}
    with patch.object(helpers, '_get_entity', return_value=document):
        summary = helpers._process_entity_guids(['g1'])
    assert summary['skipped_no_entity'] == 1


def test_process_entity_guids_skips_when_already_in_sync():
    document = {
        'entity': {
            'guid': 'g1',
            'attributes': {'name': 'patients'},
            'classifications': [{'typeName': 'Sensitivity.Public'}],
        }
    }
    dt = MagicMock()
    dt.metadata.return_value.configuration = {'data-sensitivity': ' Public '}
    with (
        patch.object(helpers, '_get_entity', return_value=document),
        patch.object(helpers, '_open_delta_table', return_value=dt),
    ):
        summary = helpers._process_entity_guids(['g1'])
    dt.alter.set_table_properties.assert_not_called()
    assert summary['skipped_already_in_sync'] == 1


def test_process_entity_guids_counts_errors_and_continues():
    document = {
        'entity': {
            'guid': 'g1',
            'attributes': {'name': 'patients'},
            'classifications': [{'typeName': 'Sensitivity.Public'}],
        }
    }
    with (
        patch.object(helpers, '_get_entity', side_effect=[RuntimeError('boom'), document]),
        patch.object(helpers, '_open_delta_table'),
    ):
        summary = helpers._process_entity_guids(['g1', 'g2'])
    assert summary['errors'] == 1
    assert summary['in_scope'] == 2

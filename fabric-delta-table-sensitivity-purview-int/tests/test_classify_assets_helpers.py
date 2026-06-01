"""Unit tests for shared_utils.classify_assets_helpers.

Targets each helper directly, rather than going through `classify_assets_impl`
(that path is already covered by `test_classify_assets.py`).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import responses
from deltalake.exceptions import TableNotFoundError

from shared_utils import classify_assets_helpers as helpers


# ---- _is_already_classified -------------------------------------------------


def _make_resp(status_code: int, json_payload: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    if json_payload is None:
        resp.json.side_effect = ValueError('no json')
    else:
        resp.json.return_value = json_payload
    return resp


def test_is_already_classified_returns_true_for_409():
    resp = _make_resp(409)
    assert helpers._is_already_classified(resp, 'Sensitivity.Public') is True


def test_is_already_classified_returns_true_for_400_with_matching_message():
    resp = _make_resp(
        400,
        {
            'errorMessage': (
                'Entity is already associated with classification Sensitivity.Public'
            )
        },
    )
    assert helpers._is_already_classified(resp, 'Sensitivity.Public') is True


def test_is_already_classified_returns_false_for_400_unrelated_message():
    resp = _make_resp(400, {'errorMessage': 'some other error'})
    assert helpers._is_already_classified(resp, 'Sensitivity.Public') is False


def test_is_already_classified_returns_false_for_400_with_invalid_json():
    resp = _make_resp(400)
    assert helpers._is_already_classified(resp, 'Sensitivity.Public') is False


def test_is_already_classified_returns_false_for_other_status():
    resp = _make_resp(500, {'errorMessage': 'boom'})
    assert helpers._is_already_classified(resp, 'Sensitivity.Public') is False


# ---- _classify --------------------------------------------------------------


@responses.activate
def test_classify_posts_classification_body(purview_url):
    responses.post(
        f'{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications',
        json={},
        status=200,
    )
    helpers._classify('g1', 'Sensitivity.Public')
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b'Sensitivity.Public' in body
    assert b'propagate' in body


@responses.activate
def test_classify_no_ops_on_409(purview_url, caplog):
    caplog.set_level('INFO')
    responses.post(
        f'{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications',
        json={},
        status=409,
    )
    helpers._classify('g1', 'Sensitivity.Public')
    assert 'already classified' in caplog.text


@responses.activate
def test_classify_raises_on_unrelated_error(purview_url):
    responses.post(
        f'{purview_url}/catalog/api/atlas/v2/entity/guid/g1/classifications',
        json={'errorMessage': 'permission denied'},
        status=403,
    )
    with pytest.raises(Exception):
        helpers._classify('g1', 'Sensitivity.Public')


# ---- _find_entity_guid ------------------------------------------------------


@responses.activate
def test_find_entity_guid_prefers_lakehouse_scoped_match(
    purview_url, lakehouse_id
):
    responses.post(
        f'{purview_url}/datamap/api/search/query?api-version=2023-09-01',
        json={
            'value': [
                {'name': 'patients', 'qualifiedName': f'other/{lakehouse_id[::-1]}', 'id': 'guid-wrong'},
                {'name': 'patients', 'qualifiedName': f'workspace/{lakehouse_id}/tables/patients', 'id': 'guid-correct'},
            ]
        },
    )
    assert helpers._find_entity_guid('patients') == 'guid-correct'


@responses.activate
def test_find_entity_guid_falls_back_to_legacy_url_on_404(
    purview_url, lakehouse_id
):
    responses.post(
        f'{purview_url}/datamap/api/search/query?api-version=2023-09-01',
        json={}, status=404,
    )
    responses.post(
        f'{purview_url}/catalog/api/search/query?api-version=2022-08-01-preview',
        json={
            'value': [
                {'name': 'patients', 'qualifiedName': f'workspace/{lakehouse_id}/tables/patients', 'guid': 'guid-legacy'},
            ]
        },
    )
    assert helpers._find_entity_guid('patients') == 'guid-legacy'


@responses.activate
def test_find_entity_guid_returns_none_when_no_match(purview_url):
    responses.post(
        f'{purview_url}/datamap/api/search/query?api-version=2023-09-01',
        json={'value': [{'name': 'other_table', 'qualifiedName': 'x', 'id': 'g'}]},
    )
    assert helpers._find_entity_guid('patients') is None


# ---- _read_sensitivity ------------------------------------------------------


def test_read_sensitivity_returns_value_from_delta_metadata():
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data-sensitivity': 'Confidential'}
    with patch.object(helpers, 'DeltaTable', return_value=fake_dt):
        assert helpers._read_sensitivity('patients') == 'Confidential'


def test_read_sensitivity_supports_underscore_key():
    fake_dt = MagicMock()
    fake_dt.metadata.return_value.configuration = {'data_sensitivity': 'Public'}
    with patch.object(helpers, 'DeltaTable', return_value=fake_dt):
        assert helpers._read_sensitivity('patients') == 'Public'


def test_read_sensitivity_returns_none_when_table_not_found(caplog):
    caplog.set_level('WARNING')
    with patch.object(helpers, 'DeltaTable', side_effect=TableNotFoundError('nope')):
        assert helpers._read_sensitivity('patients') is None
    assert 'Table not found' in caplog.text


def test_read_sensitivity_returns_none_on_unexpected_error(caplog):
    caplog.set_level('ERROR')
    with patch.object(helpers, 'DeltaTable', side_effect=RuntimeError('boom')):
        assert helpers._read_sensitivity('patients') is None
    assert 'Failed to read Delta log' in caplog.text


# ---- _list_lakehouse_tables -------------------------------------------------


@responses.activate
def test_list_lakehouse_tables_filters_directories_and_strips_prefix(
    workspace_id, lakehouse_id
):
    responses.get(
        f'https://onelake.dfs.fabric.microsoft.com/{workspace_id}',
        json={
            'paths': [
                {'name': f'{lakehouse_id}/Tables/patients', 'isDirectory': 'true'},
                {'name': f'{lakehouse_id}/Tables/visits', 'isDirectory': 'true'},
                {'name': f'{lakehouse_id}/Tables/patients/_delta_log', 'isDirectory': 'true'},
                {'name': f'{lakehouse_id}/Tables/readme.txt', 'isDirectory': 'false'},
                {'name': f'{lakehouse_id}/other/foo', 'isDirectory': 'true'},
            ]
        },
    )
    tables = helpers._list_lakehouse_tables()
    assert sorted(tables) == ['patients', 'visits']


# ---- _process_tables --------------------------------------------------------


def test_process_tables_classifies_when_sensitivity_and_entity_resolve():
    with (
        patch.object(helpers, '_read_sensitivity', return_value='Confidential') as read,
        patch.object(helpers, '_find_entity_guid', return_value='g1') as find,
        patch.object(helpers, '_classify') as classify,
    ):
        summary = helpers._process_tables(['patients'])
    read.assert_called_once_with('patients')
    find.assert_called_once_with('patients')
    classify.assert_called_once_with('g1', 'Sensitivity.Confidential')
    assert summary == {
        'total': 1,
        'classified': 1,
        'skipped_no_property': 0,
        'skipped_no_entity': 0,
        'errors': 0,
    }


def test_process_tables_skips_when_no_sensitivity_property():
    with (
        patch.object(helpers, '_read_sensitivity', return_value=None),
        patch.object(helpers, '_find_entity_guid') as find,
        patch.object(helpers, '_classify') as classify,
    ):
        summary = helpers._process_tables(['patients'])
    find.assert_not_called()
    classify.assert_not_called()
    assert summary['skipped_no_property'] == 1


def test_process_tables_skips_when_sensitivity_unknown():
    with (
        patch.object(helpers, '_read_sensitivity', return_value='nonsense'),
        patch.object(helpers, '_find_entity_guid') as find,
        patch.object(helpers, '_classify') as classify,
    ):
        summary = helpers._process_tables(['patients'])
    find.assert_not_called()
    classify.assert_not_called()
    assert summary['skipped_no_property'] == 1


def test_process_tables_skips_when_no_entity_found():
    with (
        patch.object(helpers, '_read_sensitivity', return_value='Public'),
        patch.object(helpers, '_find_entity_guid', return_value=None),
        patch.object(helpers, '_classify') as classify,
    ):
        summary = helpers._process_tables(['patients'])
    classify.assert_not_called()
    assert summary['skipped_no_entity'] == 1


def test_process_tables_counts_errors_and_continues():
    sensitivities = iter(['Public', 'Confidential'])
    with (
        patch.object(helpers, '_read_sensitivity', side_effect=lambda t: next(sensitivities)),
        patch.object(helpers, '_find_entity_guid', return_value='g'),
        patch.object(helpers, '_classify', side_effect=[RuntimeError('boom'), None]),
    ):
        summary = helpers._process_tables(['t1', 't2'])
    assert summary['total'] == 2
    assert summary['errors'] == 1
    assert summary['classified'] == 1


# Ensure SimpleNamespace import is exercised (sanity for tooling)
_ = SimpleNamespace

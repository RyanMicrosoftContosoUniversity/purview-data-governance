"""Unit tests for shared_utils.purview_classification_utils.

Targets the pure helpers (`bearer`, `atlas_headers`, `storage_options`,
`parse_event_documents`, `build_session`) and the module-level config that's
derived from environment variables in conftest.py.
"""

from __future__ import annotations

import json

from shared_utils import purview_classification_utils as pcu


# ---- Config -----------------------------------------------------------------


def test_module_config_derived_from_env():
    assert pcu.WORKSPACE_ID == '00000000-0000-0000-0000-00000000ws01'
    assert pcu.LAKEHOUSE_ID == '00000000-0000-0000-0000-00000000lh01'
    assert pcu.LAKEHOUSE_NAME == 'sensitivity_metadata_lh'
    assert pcu.PURVIEW_ACCOUNT == 'test-purview'
    assert pcu.NAMESPACE == 'Sensitivity'
    assert pcu.PURVIEW_ENDPOINT == 'https://test-purview.purview.azure.com'
    assert pcu.ATLAS_BASE == 'https://test-purview.purview.azure.com/catalog/api/atlas/v2'
    assert pcu.ONELAKE_DFS == 'onelake.dfs.fabric.microsoft.com'


def test_level_map_is_lowercased():
    assert pcu.LEVEL_MAP['public'] == 'Public'
    assert pcu.LEVEL_MAP['highly confidential'] == 'HighlyConfidential'


# ---- Auth helpers -----------------------------------------------------------


def test_bearer_returns_fake_token_from_conftest_patch():
    assert pcu.bearer('https://purview.azure.net') == 'fake-token'


def test_atlas_headers_includes_bearer_and_content_type():
    headers = pcu.atlas_headers()
    assert headers['Authorization'] == 'Bearer fake-token'
    assert headers['Content-Type'] == 'application/json'


def test_storage_options_sets_fabric_endpoint_flag():
    opts = pcu.storage_options()
    assert opts['bearer_token'] == 'fake-token'
    assert opts['use_fabric_endpoint'] == 'true'


# ---- HTTP session -----------------------------------------------------------


def test_build_session_mounts_adapters_with_retry():
    session = pcu.build_session()
    https_adapter = session.get_adapter('https://example.com')
    http_adapter = session.get_adapter('http://example.com')
    assert https_adapter is not None and http_adapter is not None
    # Retry totals must match the configured back-off policy.
    retry = https_adapter.max_retries
    assert retry.total == 5
    assert retry.connect == 5
    assert retry.read == 3
    assert 429 in retry.status_forcelist
    assert 503 in retry.status_forcelist


# ---- Event-hub batch parser -------------------------------------------------


def test_parse_event_documents_single_object(make_eh_event):
    events = [make_eh_event({'foo': 1})]
    assert pcu.parse_event_documents(events) == [{'foo': 1}]


def test_parse_event_documents_array_payload(make_eh_event):
    events = [make_eh_event([{'a': 1}, {'b': 2}])]
    assert pcu.parse_event_documents(events) == [{'a': 1}, {'b': 2}]


def test_parse_event_documents_records_envelope(make_eh_event):
    events = [make_eh_event({'records': [{'a': 1}, {'b': 2}, 'not-a-dict']})]
    assert pcu.parse_event_documents(events) == [{'a': 1}, {'b': 2}]


def test_parse_event_documents_ndjson(make_eh_event):
    body = '\n'.join([json.dumps({'a': 1}), json.dumps({'b': 2}), ''])
    events = [make_eh_event(body)]
    assert pcu.parse_event_documents(events) == [{'a': 1}, {'b': 2}]


def test_parse_event_documents_skips_invalid_lines_in_ndjson(make_eh_event, caplog):
    caplog.set_level('WARNING')
    body = '{"a": 1}\nnot-json\n{"b": 2}'
    events = [make_eh_event(body)]
    parsed = pcu.parse_event_documents(events)
    assert parsed == [{'a': 1}, {'b': 2}]
    assert 'Skipping non-JSON event body line' in caplog.text


def test_parse_event_documents_skips_event_with_unreadable_body():
    class BadEvent:
        def get_body(self):
            raise RuntimeError('boom')

    assert pcu.parse_event_documents([BadEvent()]) == []


def test_parse_event_documents_empty_batch():
    assert pcu.parse_event_documents([]) == []

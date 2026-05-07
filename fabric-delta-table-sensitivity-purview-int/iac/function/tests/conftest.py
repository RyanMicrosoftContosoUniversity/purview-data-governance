"""Test bootstrap.

Two things must happen *before* `classify_assets.handler` is imported by any test:
  1. Environment variables it reads at module load are set.
  2. `DefaultAzureCredential` is patched so no real Azure auth is attempted.

We do both at the module level here. pytest imports conftest.py before
collecting tests, so any `from classify_assets.handler import ...` inside a
test file will see the patched world.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Make the parent (function/) importable as a package root so tests can do
# `from classify_assets.handler import ...` regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 1. Env vars consumed at import time by classify_assets/handler.py
os.environ.setdefault("SOURCE_WORKSPACE_ID", "00000000-0000-0000-0000-00000000ws01")
os.environ.setdefault("SOURCE_LAKEHOUSE_ID", "00000000-0000-0000-0000-00000000lh01")
os.environ.setdefault("SOURCE_LAKEHOUSE_NAME", "sensitivity_metadata_lh")
os.environ.setdefault("PURVIEW_ACCOUNT", "test-purview")
os.environ.setdefault("CLASSIFICATION_NAMESPACE", "Sensitivity")
os.environ.setdefault(
    "SENSITIVITY_LEVEL_MAP_JSON",
    json.dumps(
        {
            "public": "Public",
            "general": "General",
            "confidential": "Confidential",
            "highly confidential": "HighlyConfidential",
        }
    ),
)

# 2. Patch DefaultAzureCredential so module load doesn't try to authenticate.
_FAKE_TOKEN = SimpleNamespace(token="fake-token", expires_on=9999999999)


class _FakeCredential:
    def get_token(self, *_args, **_kwargs):  # noqa: D401
        return _FAKE_TOKEN


_credential_patcher = patch(
    "azure.identity.DefaultAzureCredential", return_value=_FakeCredential()
)
_credential_patcher.start()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    _credential_patcher.stop()


# ---- Shared fixtures --------------------------------------------------------


@pytest.fixture
def purview_url():
    """Base Purview URL the module will hit (must match PURVIEW_ACCOUNT)."""
    return "https://test-purview.purview.azure.com"


@pytest.fixture
def workspace_id():
    return os.environ["SOURCE_WORKSPACE_ID"]


@pytest.fixture
def lakehouse_id():
    return os.environ["SOURCE_LAKEHOUSE_ID"]


def _make_eh_event(payload: dict | list | str) -> MagicMock:
    """Build a fake `func.EventHubEvent` whose `.get_body()` returns the given
    payload encoded as UTF-8 bytes (or the literal string if already a str).
    """
    import azure.functions as func

    body = payload if isinstance(payload, str) else json.dumps(payload)
    ev = MagicMock(spec=func.EventHubEvent)
    ev.get_body.return_value = body.encode("utf-8")
    return ev


@pytest.fixture
def make_eh_event():
    """Factory fixture for building fake EventHubEvent instances."""
    return _make_eh_event


@pytest.fixture
def fake_eh_events():
    """A one-element batch mimicking a successful Purview ScanStatusLogEvent
    streamed via diagnostic settings into Event Hub.
    """
    return [
        _make_eh_event(
            {
                "operationName": "ScanStatusLogEvent",
                "properties": {
                    "resultType": "Succeeded",
                    "scanName": "MyScan",
                    "dataSource": "fabric",
                },
            }
        )
    ]


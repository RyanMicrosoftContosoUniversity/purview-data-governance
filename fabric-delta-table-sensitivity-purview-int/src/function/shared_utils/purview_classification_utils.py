"""Shared utilities for the classify_assets and sync_classification handlers.

Both Event-Hub-triggered functions need the same building blocks:

* The same environment configuration (workspace / lakehouse / Purview account,
  sensitivity level map, Purview endpoint resolution).
* A single `requests.Session` with retry/back-off tuned for the Purview Unified
  endpoint's flaky TLS handshakes.
* A managed-identity `DefaultAzureCredential` and small wrappers to mint
  AAD tokens for Purview (`https://purview.azure.net`) and OneLake
  (`https://storage.azure.com`).
* A tolerant Event-Hub batch parser that handles single-doc, list-of-docs and
  `records`-wrapped diagnostic-log payloads.

Keeping these here ensures the two handlers stay byte-for-byte consistent on
auth, HTTP retry policy, and event parsing — bugs fixed once apply to both.

Notes for test authors:
* Tests do NOT patch any symbol in this module directly; they continue to
  patch `classify_assets.handler.*` and `sync_classification.handler.*`. The
  handlers re-use these helpers by import.
* `DefaultAzureCredential()` is instantiated at import time, so tests must
  ensure their `azure.identity.DefaultAzureCredential` patch is active before
  importing any handler (see tests/conftest.py).
"""

from __future__ import annotations

import json
import logging
import os
from typing import List

import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


### CONFIGURATION FROM FUNCTION APP SETTINGS / ENVIRONMENT VARIABLES ##########

WORKSPACE_ID = os.environ['SOURCE_WORKSPACE_ID']
LAKEHOUSE_ID = os.environ['SOURCE_LAKEHOUSE_ID']
LAKEHOUSE_NAME = os.environ['SOURCE_LAKEHOUSE_NAME']
PURVIEW_ACCOUNT = os.environ['PURVIEW_ACCOUNT']
NAMESPACE = os.environ.get('CLASSIFICATION_NAMESPACE', 'Sensitivity')

_RAW_LEVEL_MAP = json.loads(os.environ['SENSITIVITY_LEVEL_MAP_JSON'])
LEVEL_MAP = {k.strip().lower(): v for k, v in _RAW_LEVEL_MAP.items()}

PURVIEW_ENDPOINT = (
    os.environ.get('PURVIEW_ENDPOINT', '').rstrip('/')
    or f'https://{PURVIEW_ACCOUNT}.purview.azure.com'
)
ATLAS_BASE = f'{PURVIEW_ENDPOINT}/catalog/api/atlas/v2'
ONELAKE_DFS = 'onelake.dfs.fabric.microsoft.com'


### AUTH + HTTP SINGLETONS ####################################################

_credential = DefaultAzureCredential()


def build_session() -> requests.Session:
    """Session with retries for transient TLS / 5xx errors.

    The new Purview Unified endpoint is flaky on initial TLS handshakes, so
    we retry connect + read errors and the usual transient 5xx / 429 statuses.
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


http = build_session()


def bearer(resource: str) -> str:
    """Acquire an AAD access token for the given resource scope."""
    scope = resource.rstrip('/') + '/.default'
    return _credential.get_token(scope).token


def atlas_headers() -> dict:
    """Authorization + content-type headers for Purview Atlas API calls."""
    return {
        'Authorization': f'Bearer {bearer("https://purview.azure.net")}',
        'Content-Type': 'application/json',
    }


def storage_options() -> dict[str, str]:
    """Storage options passed to `DeltaTable(...)` for OneLake-backed tables."""
    return {
        'bearer_token': bearer('https://storage.azure.com'),
        'use_fabric_endpoint': 'true',
    }


### EVENT-HUB BATCH PARSER ####################################################


def parse_event_documents(events: List[func.EventHubEvent]) -> list[dict]:
    """Flatten an Event-Hub batch into a list of JSON dict payloads.

    Tolerates three shapes that Purview / diagnostic settings can emit:
      * A single JSON object body.
      * A JSON array of objects.
      * A `{"records": [...]}` envelope (diagnostic-log batches).
    Also tolerates newline-delimited JSON bodies. Non-JSON lines are logged
    and skipped rather than raising — a malformed event must not poison the
    whole batch.
    """
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

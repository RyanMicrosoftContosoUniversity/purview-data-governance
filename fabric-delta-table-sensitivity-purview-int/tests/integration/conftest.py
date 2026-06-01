"""Integration-test fixtures.

These tests hit REAL Azure resources (Purview, Event Hub, Function App,
OneLake) and require:
  1. RUN_INTEGRATION_TESTS=1 in the environment (gates the credential-mock
     in the parent tests/conftest.py).
  2. A signed-in identity (Azure CLI locally, or service-connection SP in CI)
     with these Azure RBAC + Purview roles:
       - Data Source Administrator on Purview collection {PURVIEW_COLLECTION_ID}
       - Contributor on the Fabric workspace (for OneLake fixture writes)
  3. Real environment variables (see _required_env() below).

Failing fast with a clear message when any of those are missing is the
explicit goal of this conftest.
"""
from __future__ import annotations

import logging
import os
import uuid

import pytest

logger = logging.getLogger(__name__)


# ---- Hard requirements ----------------------------------------------------


_REQUIRED_ENV_VARS = (
    # Purview
    "PURVIEW_ACCOUNT",
    "PURVIEW_RESOURCE_GROUP",
    "PURVIEW_DATA_SOURCE_NAME",
    "PURVIEW_SCAN_NAME",
    "PURVIEW_COLLECTION_ID",
    # Fabric source under scan
    "SOURCE_WORKSPACE_ID",
    "SOURCE_LAKEHOUSE_ID",
    "SOURCE_LAKEHOUSE_NAME",
    # Subscription (used to construct ARM resource IDs)
    "AZURE_SUBSCRIPTION_ID",
)


def _required_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.fail(
            f"Integration tests require env var {name}. Set it before running:\n"
            f"  PowerShell:  $env:{name} = '...'\n"
            f"  Bash:        export {name}=...\n"
            f"See tests/integration/README.md for the full setup checklist."
        )
    return val


# ---- Skip the whole suite if not opted in --------------------------------


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Auto-mark all tests in tests/integration/ with @pytest.mark.integration
    and skip them unless RUN_INTEGRATION_TESTS=1."""
    if os.environ.get("RUN_INTEGRATION_TESTS") == "1":
        for item in items:
            item.add_marker(pytest.mark.integration)
        return
    skip = pytest.mark.skip(
        reason="Integration tests skipped; set RUN_INTEGRATION_TESTS=1 to enable."
    )
    for item in items:
        item.add_marker(skip)


# ---- Config fixtures (read once per session) ------------------------------


@pytest.fixture(scope="session")
def integration_config() -> dict:
    """All Azure/Purview/Fabric coordinates needed by the test."""
    return {
        "subscription_id": _required_env("AZURE_SUBSCRIPTION_ID"),
        "purview_account": _required_env("PURVIEW_ACCOUNT"),
        "purview_rg": _required_env("PURVIEW_RESOURCE_GROUP"),
        "data_source_name": _required_env("PURVIEW_DATA_SOURCE_NAME"),
        "scan_name": _required_env("PURVIEW_SCAN_NAME"),
        "collection_id": _required_env("PURVIEW_COLLECTION_ID"),
        "workspace_id": _required_env("SOURCE_WORKSPACE_ID"),
        "lakehouse_id": _required_env("SOURCE_LAKEHOUSE_ID"),
        "lakehouse_name": _required_env("SOURCE_LAKEHOUSE_NAME"),
        # Fixture-table name written + scanned + asserted on.
        # Underscore-only name is valid for Delta + Fabric.
        "fixture_table_name": os.environ.get(
            "INTEGRATION_FIXTURE_TABLE", "integration_test_fixture"
        ),
        "fixture_sensitivity": "public",
        # Generated per-session GUID for the scan run.
        "scan_run_id": str(uuid.uuid4()),
        # Tunable timeouts (seconds).
        "scan_timeout_s": int(os.environ.get("SCAN_TIMEOUT_S", "900")),
        "classification_timeout_s": int(
            os.environ.get("CLASSIFICATION_TIMEOUT_S", "600")
        ),
        "poll_interval_s": int(os.environ.get("POLL_INTERVAL_S", "15")),
    }


@pytest.fixture(scope="session")
def az_credential():
    """Real DefaultAzureCredential. The parent conftest skips its mock-patch
    when RUN_INTEGRATION_TESTS=1, so we get the genuine article here."""
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@pytest.fixture(scope="session")
def purview_endpoints(integration_config) -> dict:
    """Resolve Purview scanning + catalog endpoints from the account."""
    import subprocess

    acct = integration_config["purview_account"]
    rg = integration_config["purview_rg"]
    out = subprocess.check_output(
        [
            "az",
            "purview",
            "account",
            "show",
            "--name",
            acct,
            "--resource-group",
            rg,
            "--query",
            "endpoints",
            "-o",
            "json",
        ],
        text=True,
    )
    import json as _json

    eps = _json.loads(out)
    # `catalog` ends with /catalog on Unified; strip to get the data-plane root.
    catalog_root = eps["catalog"].removesuffix("/catalog")
    return {
        "catalog_root": catalog_root,
        "scan_root": eps["scan"],
    }

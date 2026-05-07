#!/usr/bin/env python3
"""
get-data-map-metrics.py

Collects Data Map capacity unit metrics, autoscale history, and account properties
for the Purview account.

Queries Azure Resource Manager and Azure Monitor APIs to retrieve:
  - Purview account properties (SKU, Data Map size)
  - Capacity Unit (CU) metrics over the last 30 days
  - Autoscale history (periods where CU usage exceeded baseline)

Outputs a human-readable summary to stdout and saves JSON to the output directory.

Requirements:
  - Azure CLI (az) logged in with Reader access on the resource group
  - Python 3.9+, requests (pip install requests)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────────────

PURVIEW_ACCOUNT = os.environ.get("PURVIEW_ACCOUNT", "governancePurviewRH")
RESOURCE_GROUP = os.environ.get("RESOURCE_GROUP", "governance-rg")
SUBSCRIPTION_ID = os.environ.get("SUBSCRIPTION_ID", "")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "output"))

ARM_BASE = "https://management.azure.com"

# ── Auth Helper ──────────────────────────────────────────────────────────────


def get_token(resource: str) -> str:
    """Obtain an access token via Azure CLI."""
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", resource],
            capture_output=True,
            text=True,
            check=True,
            shell=True,
        )
        return json.loads(result.stdout)["accessToken"]
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: Failed to get token for {resource}: {exc}")
        sys.exit(1)


def get_subscription_id() -> str:
    """Resolve the current subscription ID via Azure CLI."""
    try:
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True,
            check=True,
            shell=True,
        )
        acct = json.loads(result.stdout)
        print(f"Using subscription: {acct['name']} ({acct['id']})")
        return acct["id"]
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: Failed to get subscription info: {exc}")
        sys.exit(1)


def api_get(url: str, token: str, params: dict | None = None):
    """Make an authenticated GET request and return the JSON response."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"  WARNING: API call failed: {url}\n  {exc}")
        return None


# ── Data Collection ──────────────────────────────────────────────────────────


def collect_account_properties(token: str, resource_id: str) -> dict | None:
    """Retrieve Purview account properties from ARM."""
    print("\n═══ Purview Account Properties ═══")

    url = f"{ARM_BASE}{resource_id}?api-version=2021-12-01"
    data = api_get(url, token)

    if not data:
        print("  WARNING: Could not retrieve account properties.")
        return None

    summary = {
        "accountName": data.get("name"),
        "location": data.get("location"),
        "sku": data.get("sku", {}).get("name"),
        "skuCapacity": data.get("sku", {}).get("capacity"),
        "provisioningState": data.get("properties", {}).get("provisioningState"),
        "publicNetworkAccess": data.get("properties", {}).get("publicNetworkAccess"),
        "managedResourceGroupName": data.get("properties", {}).get("managedResourceGroupName"),
        "createdAt": data.get("properties", {}).get("createdAt"),
        "endpoints": data.get("properties", {}).get("endpoints"),
    }

    print(f"  Account Name    : {summary['accountName']}")
    print(f"  Location        : {summary['location']}")
    print(f"  SKU             : {summary['sku']} (capacity: {summary['skuCapacity']})")
    print(f"  Provisioning    : {summary['provisioningState']}")
    print(f"  Created At      : {summary['createdAt']}")

    return summary


def collect_capacity_metrics(token: str, resource_id: str) -> dict:
    """Collect Data Map CU and storage metrics from Azure Monitor."""
    print("\n═══ Data Map Capacity Metrics (Last 30 Days) ═══")

    now = datetime.now(timezone.utc)
    end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    metrics_to_collect = ["DataMapCapacityUnits", "DataMapStorageSize"]
    metrics_results: dict[str, list] = {}

    for metric_name in metrics_to_collect:
        url = (
            f"{ARM_BASE}{resource_id}/providers/Microsoft.Insights/metrics"
            f"?api-version=2023-10-01"
            f"&metricnames={metric_name}"
            f"&timespan={start_time}/{end_time}"
            f"&interval=P1D"
            f"&aggregation=Average,Maximum"
        )
        data = api_get(url, token)
        if data and data.get("value"):
            metrics_results[metric_name] = data["value"]
        else:
            print(f"  WARNING: No metric data returned for {metric_name}.")
            metrics_results[metric_name] = []

    # ── Parse CU metrics ────────────────────────────────────────────────

    cu_timeseries = []
    autoscale_events = []
    max_cu = 0
    avg_cu_sum = 0

    cu_metric = metrics_results.get("DataMapCapacityUnits", [])
    if cu_metric:
        timeseries = cu_metric[0].get("timeseries", [])
        if timeseries:
            for point in timeseries[0].get("data", []):
                entry = {
                    "timestamp": point.get("timeStamp"),
                    "average": point.get("average"),
                    "maximum": point.get("maximum"),
                }
                cu_timeseries.append(entry)

                pt_max = point.get("maximum") or 0
                pt_avg = point.get("average") or 0

                if pt_max > 1:
                    autoscale_events.append(entry)
                if pt_max > max_cu:
                    max_cu = pt_max
                avg_cu_sum += pt_avg

    avg_cu = round(avg_cu_sum / len(cu_timeseries), 2) if cu_timeseries else 0

    print(f"  Average CU (30d): {avg_cu}")
    print(f"  Max CU (30d)    : {max_cu}")
    print(f"  Baseline        : 1 CU (10 GB / 25 ops/sec)")

    if max_cu > 1:
        print("  ⚠ Data Map has scaled beyond 1 CU baseline!")
        print("  Autoscale events (CU > 1):")
        for evt in autoscale_events:
            print(f"    {evt['timestamp']}  —  max={evt['maximum']}, avg={evt['average']}")
    else:
        print("  ✓ Data Map is within the 1 CU baseline.")

    # ── Parse storage size ──────────────────────────────────────────────

    storage_size_gb = 0
    storage_metric = metrics_results.get("DataMapStorageSize", [])
    if storage_metric:
        timeseries = storage_metric[0].get("timeseries", [])
        if timeseries:
            data_points = timeseries[0].get("data", [])
            if data_points:
                latest = data_points[-1]
                if latest.get("average"):
                    # Value is in bytes; convert to GB
                    storage_size_gb = round(latest["average"] / (1024 ** 3), 2)

    print(f"\n  Data Map Storage : {storage_size_gb} GB")
    if storage_size_gb > 10:
        print("  ⚠ Storage exceeds the 10 GB baseline for 1 CU!")
    else:
        print("  ✓ Storage is within the 10 GB baseline.")

    return {
        "periodDays": 30,
        "averageCU": avg_cu,
        "maxCU": max_cu,
        "baselineCU": 1,
        "aboveBaseline": max_cu > 1,
        "storageSizeGB": storage_size_gb,
        "storageBaselineGB": 10,
        "cuTimeseries": cu_timeseries,
        "autoscaleEvents": autoscale_events,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    subscription_id = SUBSCRIPTION_ID or get_subscription_id()
    token = get_token("https://management.azure.com")

    resource_id = (
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.Purview/accounts/{PURVIEW_ACCOUNT}"
    )

    account_props = collect_account_properties(token, resource_id)
    data_map_metrics = collect_capacity_metrics(token, resource_id)

    output = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": PURVIEW_ACCOUNT,
        "resourceGroup": RESOURCE_GROUP,
        "subscriptionId": subscription_id,
        "accountProperties": account_props,
        "dataMapMetrics": data_map_metrics,
    }

    json_path = os.path.join(OUTPUT_DIR, "data-map-metrics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ JSON saved to {json_path}")


if __name__ == "__main__":
    main()

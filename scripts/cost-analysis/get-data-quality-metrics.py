#!/usr/bin/env python3
"""
get-data-quality-metrics.py

Collects data quality metrics from the Purview Data Governance API:
  - DQ rule counts (by type/complexity)
  - DQ profile run history with DGPU consumption
  - Health management scores and asset coverage

Outputs a human-readable summary to stdout and saves JSON to the output directory.

Requirements:
  - Azure CLI (az) logged in
  - Python 3.9+, requests (pip install requests)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────────────

PURVIEW_ACCOUNT = os.environ.get("PURVIEW_ACCOUNT", "governancePurviewRH")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "output"))

GOVERNANCE_BASE = f"https://{PURVIEW_ACCOUNT}.purview.azure.com/datagovernance"

# DGPU pricing by SKU (approximate hourly rates)
DGPU_RATES = {
    "Basic": 0.105,
    "Standard": 0.21,
    "Advanced": 0.63,
}

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


# ── Data Collection Functions ────────────────────────────────────────────────


def collect_dq_rules(token: str) -> dict:
    """Get data quality rules from the governance API."""
    print("\n═══ Data Quality Rules ═══")

    # NOTE: Data Quality rules API is not yet available in the Unified Catalog REST API
    # (2025-09-15-preview). The endpoint /catalog/dataquality/rules returns 404.
    # When Microsoft publishes this endpoint, update the URL below.
    url = f"{GOVERNANCE_BASE}/catalog/dataquality/rules?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {
        "totalRules": 0,
        "byType": {},
        "bySku": {},
        "rules": [],
    }

    if not data:
        print("  Could not retrieve DQ rules (API may not be available).")
        return result

    rules = data.get("value", [])
    result["totalRules"] = len(rules)

    for rule in rules:
        props = rule.get("properties", {})
        rule_type = props.get("ruleType", "Unknown")
        sku = props.get("sku", "Basic")

        result["byType"][rule_type] = result["byType"].get(rule_type, 0) + 1
        result["bySku"][sku] = result["bySku"].get(sku, 0) + 1

        result["rules"].append({
            "name": rule.get("name", ""),
            "ruleType": rule_type,
            "sku": sku,
            "status": props.get("status", ""),
            "createdAt": props.get("createdAt", ""),
        })

    print(f"  Total DQ rules: {result['totalRules']}")

    if result["byType"]:
        print("\n  Rules by type:")
        for rtype, count in result["byType"].items():
            print(f"    {rtype}: {count}")

    if result["bySku"]:
        print("\n  Rules by SKU:")
        for sku, count in result["bySku"].items():
            rate = DGPU_RATES.get(sku, 0)
            print(f"    {sku}: {count} (DGPU rate: ${rate}/hr)")

    return result


def collect_dq_profile_runs(token: str) -> dict:
    """Get data quality profile run history."""
    print("\n═══ Data Quality Profile Runs ═══")

    # NOTE: Data Quality profile runs API is not yet available in the Unified Catalog REST API
    # (2025-09-15-preview). The endpoint /catalog/dataquality/profileruns returns 404.
    url = f"{GOVERNANCE_BASE}/catalog/dataquality/profileruns?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {
        "totalRuns": 0,
        "totalDgpuConsumed": 0.0,
        "estimatedDgpuCost": 0.0,
        "runs": [],
    }

    if not data:
        print("  Could not retrieve DQ profile runs (API may not be available).")
        return result

    runs = data.get("value", [])
    result["totalRuns"] = len(runs)

    for run in runs:
        props = run.get("properties", {})
        dgpu = props.get("processingUnitsConsumed", 0)
        sku = props.get("sku", "Basic")
        rate = DGPU_RATES.get(sku, DGPU_RATES["Basic"])

        run_entry = {
            "runId": run.get("name", ""),
            "status": props.get("status", ""),
            "sku": sku,
            "startTime": props.get("startTime", ""),
            "endTime": props.get("endTime", ""),
            "dgpuConsumed": dgpu,
            "estimatedCost": round(dgpu * rate, 4),
            "assetsProcessed": props.get("assetsProcessed", 0),
        }
        result["runs"].append(run_entry)
        result["totalDgpuConsumed"] += dgpu
        result["estimatedDgpuCost"] += run_entry["estimatedCost"]

    result["totalDgpuConsumed"] = round(result["totalDgpuConsumed"], 2)
    result["estimatedDgpuCost"] = round(result["estimatedDgpuCost"], 2)

    print(f"  Total profile runs   : {result['totalRuns']}")
    print(f"  Total DGPU consumed  : {result['totalDgpuConsumed']}")
    print(f"  Estimated DGPU cost  : ${result['estimatedDgpuCost']}")

    if result["runs"]:
        print("\n  Run ID                          Status     SKU       DGPU    Cost     Assets")
        print("  ──────                          ──────     ───       ────    ────     ──────")
        for r in sorted(result["runs"], key=lambda x: x.get("startTime", ""), reverse=True)[:10]:
            print(
                f"  {r['runId'][:32]:<32}  {r['status']:<8}  {r['sku']:<8}  "
                f"{r['dgpuConsumed']:<6}  ${r['estimatedCost']:<6}  {r['assetsProcessed']}"
            )
        if len(result["runs"]) > 10:
            print(f"  ... and {len(result['runs']) - 10} more (see JSON output)")

    return result


def collect_health_scores(token: str) -> dict:
    """Get data health management coverage."""
    print("\n═══ Data Health Management ═══")

    # NOTE: Data Health summary API is not yet available in the Unified Catalog REST API
    # (2025-09-15-preview). The endpoint /catalog/datahealth/summary returns 404.
    url = f"{GOVERNANCE_BASE}/catalog/datahealth/summary?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {
        "assetsWithHealthEnabled": 0,
        "averageHealthScore": 0.0,
        "dimensions": {},
    }

    if not data:
        print("  Could not retrieve health data (API may not be available).")
        return result

    props = data.get("properties", data)
    result["assetsWithHealthEnabled"] = props.get("totalAssets", 0)
    result["averageHealthScore"] = props.get("averageScore", 0.0)

    for dim in props.get("dimensions", []):
        dim_name = dim.get("name", "Unknown")
        result["dimensions"][dim_name] = {
            "score": dim.get("score", 0),
            "assetCount": dim.get("assetCount", 0),
        }

    print(f"  Assets with health enabled: {result['assetsWithHealthEnabled']}")
    print(f"  Average health score      : {result['averageHealthScore']}")

    if result["dimensions"]:
        print("\n  Dimension          Score  Assets")
        print("  ─────────          ─────  ──────")
        for name, dim in result["dimensions"].items():
            print(f"  {name:<18} {dim['score']:<5}  {dim['assetCount']}")

    return result


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    token = get_token("https://purview.azure.net")

    dq_rules = collect_dq_rules(token)
    dq_runs = collect_dq_profile_runs(token)
    health = collect_health_scores(token)

    output = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": PURVIEW_ACCOUNT,
        "dataQualityRules": dq_rules,
        "dataQualityProfileRuns": dq_runs,
        "dataHealth": health,
        "dgpuPricing": DGPU_RATES,
    }

    json_path = os.path.join(OUTPUT_DIR, "data-quality-metrics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ JSON saved to {json_path}")


if __name__ == "__main__":
    main()

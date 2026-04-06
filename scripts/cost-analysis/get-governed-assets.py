#!/usr/bin/env python3
"""
get-governed-assets.py

Collects governed-asset data from the Purview Data Map (Atlas) and Data Governance APIs:
  - Total asset counts broken down by source type
  - Classification status (classified vs. unclassified)
  - Data products and their asset counts
  - Glossary terms and assignments
  - Lineage relationship counts
  - Access policies

Outputs a human-readable summary to stdout and saves JSON to the output directory.

Requirements:
  - Azure CLI (az) logged in
  - Python 3.9+, requests (pip install requests)
"""

import json
import os
import subprocess
import sys
from collections import defaultdict
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

ATLAS_BASE = f"https://{PURVIEW_ACCOUNT}.purview.azure.com/datamap/api"
GOVERNANCE_BASE = f"https://{PURVIEW_ACCOUNT}.purview.azure.com/datagovernance"

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


def api_post(url: str, token: str, body: dict):
    """Make an authenticated POST request and return the JSON response."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"  WARNING: API call failed: {url}\n  {exc}")
        return None


# ── Data Collection Functions ────────────────────────────────────────────────


def collect_asset_counts(token: str) -> dict:
    """Get total asset count broken down by source type using search aggregation."""
    print("\n═══ Asset Counts by Source Type ═══")

    url = f"{ATLAS_BASE}/search/query?api-version=2023-09-01"
    body = {
        "keywords": "*",
        "limit": 1,
        "facets": [
            {"facet": "objectType", "count": 100},
            {"facet": "sourceType", "count": 100},
            {"facet": "classification", "count": 100},
        ],
    }

    data = api_post(url, token, body)
    result = {
        "totalCount": 0,
        "bySourceType": {},
        "byObjectType": {},
        "classifiedCount": 0,
        "unclassifiedCount": 0,
        "classificationBreakdown": {},
    }

    if not data:
        print("  Could not retrieve asset counts.")
        return result

    result["totalCount"] = data.get("@search.count", 0)
    print(f"  Total assets: {result['totalCount']}")

    # Parse facets
    for facet_result in data.get("@search.facets", {}).get("sourceType", []):
        source_type = facet_result.get("value", "Unknown")
        count = facet_result.get("count", 0)
        result["bySourceType"][source_type] = count

    for facet_result in data.get("@search.facets", {}).get("objectType", []):
        obj_type = facet_result.get("value", "Unknown")
        count = facet_result.get("count", 0)
        result["byObjectType"][obj_type] = count

    for facet_result in data.get("@search.facets", {}).get("classification", []):
        cls_name = facet_result.get("value", "Unknown")
        count = facet_result.get("count", 0)
        result["classificationBreakdown"][cls_name] = count
        result["classifiedCount"] += count

    result["unclassifiedCount"] = max(0, result["totalCount"] - result["classifiedCount"])

    # Print table
    print("\n  Source Type                Count")
    print("  ───────────                ─────")
    for st, count in sorted(result["bySourceType"].items(), key=lambda x: -x[1]):
        print(f"  {st:<26} {count}")

    print(f"\n  Classified assets  : {result['classifiedCount']}")
    print(f"  Unclassified assets: {result['unclassifiedCount']}")

    return result


def collect_glossary_terms(token: str) -> dict:
    """Get glossary terms and count assignments."""
    print("\n═══ Glossary Terms ═══")

    url = f"{GOVERNANCE_BASE}/catalog/terms?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {
        "totalTerms": 0,
        "termsWithAssignments": 0,
        "totalAssignments": 0,
        "terms": [],
    }

    if not data:
        print("  Could not retrieve glossary terms.")
        return result

    terms_list = data if isinstance(data, list) else data.get("value", [])
    result["totalTerms"] = len(terms_list)

    for term in terms_list:
        assigned_count = len(term.get("assignedEntities", []))
        result["terms"].append({
            "name": term.get("name", ""),
            "guid": term.get("guid", ""),
            "assignedEntityCount": assigned_count,
        })
        if assigned_count > 0:
            result["termsWithAssignments"] += 1
            result["totalAssignments"] += assigned_count

    print(f"  Total glossary terms     : {result['totalTerms']}")
    print(f"  Terms with assignments   : {result['termsWithAssignments']}")
    print(f"  Total entity assignments : {result['totalAssignments']}")

    return result


def collect_lineage_stats(token: str) -> dict:
    """Estimate lineage volume by querying for process entities."""
    print("\n═══ Lineage Data Volume ═══")

    url = f"{ATLAS_BASE}/search/query?api-version=2023-09-01"
    body = {
        "keywords": "*",
        "limit": 1,
        "filter": {
            "objectType": "Process",
        },
    }
    data = api_post(url, token, body)

    result = {"processEntityCount": 0}

    if data:
        result["processEntityCount"] = data.get("@search.count", 0)

    print(f"  Process entities (lineage sources): {result['processEntityCount']}")
    print("  (Each process entity represents one or more lineage relationships)")

    return result


def collect_data_products(token: str) -> dict:
    """Get data products from the Data Governance API."""
    print("\n═══ Data Products ═══")

    url = f"{GOVERNANCE_BASE}/catalog/dataproducts?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {"totalCount": 0, "products": [], "totalAssets": 0}

    if not data:
        print("  Could not retrieve data products (API may not be available).")
        return result

    products = data.get("value", [])
    result["totalCount"] = len(products)

    for dp in products:
        # New API returns fields at top level, not nested under "properties"
        asset_count = dp.get("assetCount", dp.get("properties", {}).get("assetCount", 0))
        result["products"].append({
            "name": dp.get("name", ""),
            "id": dp.get("id", ""),
            "assetCount": asset_count,
            "status": dp.get("status", dp.get("properties", {}).get("status", "")),
        })
        result["totalAssets"] += asset_count

    print(f"  Total data products: {result['totalCount']}")
    print(f"  Total assets in products: {result['totalAssets']}")

    if result["products"]:
        print("\n  Data Product            Assets  Status")
        print("  ────────────            ──────  ──────")
        for p in sorted(result["products"], key=lambda x: -x["assetCount"]):
            print(f"  {p['name']:<24} {p['assetCount']:<6}  {p['status']}")

    return result


def collect_access_policies(token: str) -> dict:
    """Get access policies from the Data Governance API."""
    print("\n═══ Access Policies ═══")

    url = f"{GOVERNANCE_BASE}/catalog/policies?api-version=2025-09-15-preview"
    data = api_get(url, token)

    result = {"totalCount": 0, "byType": {}, "policies": []}

    if not data:
        print("  Could not retrieve access policies (API may not be available).")
        return result

    policies = data.get("values", data.get("value", []))
    result["totalCount"] = len(policies)

    for policy in policies:
        policy_type = policy.get("policyType", policy.get("properties", {}).get("policyType", "Unknown"))
        result["byType"][policy_type] = result["byType"].get(policy_type, 0) + 1
        result["policies"].append({
            "name": policy.get("name", ""),
            "policyType": policy_type,
            "status": policy.get("status", policy.get("properties", {}).get("status", "")),
        })

    print(f"  Total access policies: {result['totalCount']}")
    for ptype, count in result["byType"].items():
        print(f"    {ptype}: {count}")

    return result


def estimate_governed_assets(asset_counts: dict, data_products: dict,
                             glossary: dict) -> dict:
    """Estimate governed-asset count from collected data."""
    print("\n═══ Governed Asset Estimate ═══")

    # Governed assets = assets linked to data products + assets with glossary terms
    # (with de-duplication approximation)
    dp_assets = data_products.get("totalAssets", 0)
    glossary_assets = glossary.get("totalAssignments", 0)
    # Conservative estimate: assume some overlap
    estimated = dp_assets + glossary_assets
    if dp_assets > 0 and glossary_assets > 0:
        overlap_estimate = min(dp_assets, glossary_assets) // 2
        estimated = dp_assets + glossary_assets - overlap_estimate

    result = {
        "assetsInDataProducts": dp_assets,
        "assetsWithGlossaryTerms": glossary_assets,
        "estimatedGovernedAssets": estimated,
        "costPerAssetPerDay": 0.0165,
        "estimatedDailyCost": round(estimated * 0.0165, 2),
        "estimatedMonthlyCost": round(estimated * 0.0165 * 30, 2),
    }

    print(f"  Assets in data products    : {dp_assets}")
    print(f"  Assets with glossary terms : {glossary_assets}")
    print(f"  Estimated governed assets  : {estimated}")
    print(f"  Estimated daily cost       : ${result['estimatedDailyCost']}")
    print(f"  Estimated monthly cost     : ${result['estimatedMonthlyCost']}")

    return result


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    purview_token = get_token("https://purview.azure.net")

    asset_counts = collect_asset_counts(purview_token)
    glossary = collect_glossary_terms(purview_token)
    lineage = collect_lineage_stats(purview_token)
    data_products = collect_data_products(purview_token)
    access_policies = collect_access_policies(purview_token)
    governed_estimate = estimate_governed_assets(asset_counts, data_products, glossary)

    output = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": PURVIEW_ACCOUNT,
        "assetCounts": asset_counts,
        "glossaryTerms": glossary,
        "lineage": lineage,
        "dataProducts": data_products,
        "accessPolicies": access_policies,
        "governedAssetEstimate": governed_estimate,
    }

    json_path = os.path.join(OUTPUT_DIR, "governed-assets.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ JSON saved to {json_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
get-cost-management-data.py

Retrieves actual cost data from Azure Cost Management for the Purview resource.

Queries the Azure Cost Management API to retrieve:
  - Actual costs for the Purview account over the last 30 days
  - Cost breakdown by meter category and meter name
  - Daily cost trend

Outputs a human-readable summary to stdout and saves JSON to the output directory.

Requirements:
  - Azure CLI (az) logged in with Cost Management Reader access
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


def collect_cost_by_meter(
    token: str, subscription_id: str, resource_id: str,
    start_date: str, end_date: str,
) -> tuple[list[dict], float]:
    """Query Azure Cost Management for cost breakdown by meter."""
    print("\n═══ Azure Cost Management — Purview Costs (Last 30 Days) ═══")

    url = (
        f"{ARM_BASE}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )

    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": start_date, "to": end_date},
        "dataset": {
            "granularity": "None",
            "aggregation": {
                "totalCost": {"name": "Cost", "function": "Sum"},
            },
            "grouping": [
                {"type": "Dimension", "name": "MeterCategory"},
                {"type": "Dimension", "name": "Meter"},
            ],
            "filter": {
                "dimensions": {
                    "name": "ResourceId",
                    "operator": "In",
                    "values": [resource_id],
                },
            },
        },
    }

    data = api_post(url, token, body)

    cost_by_meter: list[dict] = []
    total_cost = 0.0

    if data and data.get("properties", {}).get("rows"):
        for row in data["properties"]["rows"]:
            # Columns: Cost, MeterCategory, Meter, Currency
            cost = round(row[0], 2)
            meter_category = row[1]
            meter_name = row[2]
            currency = row[3] if len(row) > 3 else "USD"

            cost_by_meter.append({
                "meterCategory": meter_category,
                "meterName": meter_name,
                "cost": cost,
                "currency": currency,
            })
            total_cost += cost

    total_cost = round(total_cost, 2)
    print(f"  Total cost (30d): ${total_cost}")
    print()

    if cost_by_meter:
        print(f"  {'Meter Category':<26}  {'Meter Name':<28}  Cost")
        print(f"  {'──────────────':<26}  {'──────────':<28}  ────")
        for m in sorted(cost_by_meter, key=lambda x: -x["cost"]):
            print(f"  {m['meterCategory']:<26}  {m['meterName']:<28}  ${m['cost']}")
    else:
        print("  No cost data returned. This may be due to permissions or the billing period.")

    return cost_by_meter, total_cost


def collect_daily_costs(
    token: str, subscription_id: str, resource_id: str,
    start_date: str, end_date: str,
) -> tuple[list[dict], dict]:
    """Query Azure Cost Management for daily cost trend."""
    print("\n═══ Daily Cost Trend (Last 30 Days) ═══")

    url = (
        f"{ARM_BASE}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )

    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": start_date, "to": end_date},
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {"name": "Cost", "function": "Sum"},
            },
            "filter": {
                "dimensions": {
                    "name": "ResourceId",
                    "operator": "In",
                    "values": [resource_id],
                },
            },
        },
    }

    data = api_post(url, token, body)

    daily_costs: list[dict] = []
    if data and data.get("properties", {}).get("rows"):
        for row in data["properties"]["rows"]:
            cost = round(row[0], 2)
            date_val = row[1]
            currency = row[2] if len(row) > 2 else "USD"
            daily_costs.append({
                "date": date_val,
                "cost": cost,
                "currency": currency,
            })

    summary = {"averageDailyCost": 0, "maxDailyCost": 0, "projectedMonthlyCost": 0}

    if daily_costs:
        costs = [d["cost"] for d in daily_costs]
        avg_daily = round(sum(costs) / len(costs), 2)
        max_daily = round(max(costs), 2)
        projected = round(avg_daily * 30, 2)

        summary = {
            "averageDailyCost": avg_daily,
            "maxDailyCost": max_daily,
            "projectedMonthlyCost": projected,
        }

        print(f"  Average daily cost   : ${avg_daily}")
        print(f"  Max daily cost       : ${max_daily}")
        print(f"  Projected monthly    : ${projected}")
        print()

        # Print last 10 days
        print(f"  {'Date':<12}  Cost")
        print(f"  {'────':<12}  ────")
        for d in daily_costs[-10:]:
            print(f"  {str(d['date']):<12}  ${d['cost']}")
    else:
        print("  No daily cost data returned.")

    return daily_costs, summary


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    subscription_id = SUBSCRIPTION_ID or get_subscription_id()
    token = get_token("https://management.azure.com")

    now = datetime.now(timezone.utc)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    resource_id = (
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.Purview/accounts/{PURVIEW_ACCOUNT}"
    )

    cost_by_meter, total_cost = collect_cost_by_meter(
        token, subscription_id, resource_id, start_date, end_date
    )
    daily_costs, summary = collect_daily_costs(
        token, subscription_id, resource_id, start_date, end_date
    )

    output = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": PURVIEW_ACCOUNT,
        "resourceGroup": RESOURCE_GROUP,
        "subscriptionId": subscription_id,
        "period": {"startDate": start_date, "endDate": end_date},
        "costByMeter": cost_by_meter,
        "totalCost30Days": total_cost,
        "dailyCosts": daily_costs,
        "summary": summary,
    }

    json_path = os.path.join(OUTPUT_DIR, "cost-management-data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ JSON saved to {json_path}")


if __name__ == "__main__":
    main()

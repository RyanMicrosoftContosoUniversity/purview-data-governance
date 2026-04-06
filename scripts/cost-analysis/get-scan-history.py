#!/usr/bin/env python3
"""
get-scan-history.py

Collects scan history, registered data sources, and classification rules
from the Purview Scanning API.

Queries the Purview Scanning REST API to retrieve:
  - All registered data sources with type and connection info
  - Recent scan runs with duration, status, and asset counts
  - Scan rulesets and classification rules (custom + built-in)

Outputs a human-readable summary to stdout and saves JSON to the output directory.

Requirements:
  - Azure CLI (az) logged in with Purview Data Source Administrator access
  - Python 3.9+, requests (pip install requests)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from operator import itemgetter

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────────────

PURVIEW_ACCOUNT = os.environ.get("PURVIEW_ACCOUNT", "governancePurviewRH")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "output"))

SCAN_BASE = f"https://{PURVIEW_ACCOUNT}.purview.azure.com/scan"

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


def collect_data_sources(token: str) -> list[dict]:
    """List all registered data sources."""
    print("\n═══ Registered Data Sources ═══")

    data = api_get(
        f"{SCAN_BASE}/datasources?api-version=2022-07-01-preview", token
    )

    sources = []
    if data and data.get("value"):
        for src in data["value"]:
            sources.append({
                "name": src.get("name"),
                "kind": src.get("kind"),
                "createdAt": src.get("properties", {}).get("createdAt"),
                "lastModifiedAt": src.get("properties", {}).get("lastModifiedAt"),
            })

    print(f"  Total registered sources: {len(sources)}")
    print()
    print(f"  {'Name':<30}  {'Kind':<20}  Created At")
    print(f"  {'────':<30}  {'────':<20}  ──────────")
    for s in sources:
        print(f"  {s['name'] or '':<30}  {s['kind'] or '':<20}  {s['createdAt'] or ''}")

    return sources


def collect_scan_runs(token: str, sources: list[dict]) -> list[dict]:
    """Collect recent scan runs across all data sources."""
    print("\n═══ Recent Scan Runs ═══")

    all_runs: list[dict] = []

    for src in sources:
        src_name = src["name"]
        scans_data = api_get(
            f"{SCAN_BASE}/datasources/{src_name}/scans?api-version=2022-07-01-preview",
            token,
        )
        if not scans_data or not scans_data.get("value"):
            continue

        for scan in scans_data["value"]:
            scan_name = scan.get("name")
            runs_data = api_get(
                f"{SCAN_BASE}/datasources/{src_name}/scans/{scan_name}"
                f"/runs?api-version=2022-07-01-preview",
                token,
            )
            if not runs_data or not runs_data.get("value"):
                continue

            for run in runs_data["value"]:
                start_time = run.get("startTime")
                end_time = run.get("endTime")
                duration = None

                if start_time and end_time:
                    try:
                        st = datetime.fromisoformat(
                            start_time.replace("Z", "+00:00")
                        )
                        et = datetime.fromisoformat(
                            end_time.replace("Z", "+00:00")
                        )
                        duration = str(et - st)
                    except (ValueError, TypeError):
                        duration = "N/A"

                scan_type = (
                    scan.get("properties", {}).get("scanType") or "Unknown"
                )

                all_runs.append({
                    "dataSource": src_name,
                    "scanName": scan_name,
                    "runId": run.get("id"),
                    "status": run.get("status"),
                    "scanType": scan_type,
                    "startTime": start_time,
                    "endTime": end_time,
                    "duration": duration,
                    "assetsDiscovered": run.get("assetsDiscovered"),
                    "assetsClassified": run.get("assetsClassified"),
                    "scanRulesetName": scan.get("properties", {}).get(
                        "scanRulesetName"
                    ),
                })

    # Sort by start time descending
    all_runs.sort(key=lambda r: r.get("startTime") or "", reverse=True)

    print(f"  Total scan runs found: {len(all_runs)}")
    print()

    if all_runs:
        print(
            f"  {'Source':<22}  {'Scan':<16}  {'Status':<10}  "
            f"{'Type':<10}  {'Duration':<20}  Assets"
        )
        print(
            f"  {'──────':<22}  {'────':<16}  {'──────':<10}  "
            f"{'────':<10}  {'────────':<20}  ──────"
        )
        for r in all_runs[:20]:
            print(
                f"  {(r['dataSource'] or ''):<22}  "
                f"{(r['scanName'] or ''):<16}  "
                f"{(r['status'] or ''):<10}  "
                f"{(r['scanType'] or ''):<10}  "
                f"{(r['duration'] or ''):<20}  "
                f"{r['assetsDiscovered'] or ''}"
            )
        if len(all_runs) > 20:
            print(f"  ... and {len(all_runs) - 20} more (see JSON output)")

    # Top 5 longest scans
    print("\n═══ Top 5 Longest Scans ═══")
    valid_runs = [r for r in all_runs if r.get("duration") and r["duration"] != "N/A"]
    ranked = sorted(valid_runs, key=lambda r: r["duration"], reverse=True)[:5]
    for r in ranked:
        print(
            f"  {r['dataSource']} / {r['scanName']} — "
            f"{r['duration']} (assets: {r['assetsDiscovered']})"
        )

    return all_runs


def collect_classification_rules(token: str) -> dict:
    """Collect system and custom scan rulesets and classification rules."""
    print("\n═══ Classification Rules ═══")

    # System scan rulesets
    system_data = api_get(
        f"{SCAN_BASE}/systemScanRulesets?api-version=2022-07-01-preview", token
    )
    system_rulesets = []
    if system_data and system_data.get("value"):
        for rs in system_data["value"]:
            rule_names = rs.get("properties", {}).get("classificationRuleNames", [])
            system_rulesets.append({
                "name": rs.get("name"),
                "kind": rs.get("kind"),
                "ruleCount": len(rule_names) if rule_names else 0,
            })

    # Custom scan rulesets
    custom_rs_data = api_get(
        f"{SCAN_BASE}/scanrulesets?api-version=2022-07-01-preview", token
    )
    custom_rulesets = []
    if custom_rs_data and custom_rs_data.get("value"):
        for rs in custom_rs_data["value"]:
            rule_names = rs.get("properties", {}).get("classificationRuleNames", [])
            custom_rulesets.append({
                "name": rs.get("name"),
                "kind": rs.get("kind"),
                "ruleCount": len(rule_names) if rule_names else 0,
            })

    # Custom classification rules
    class_data = api_get(
        f"{SCAN_BASE}/classificationrules?api-version=2022-07-01-preview", token
    )
    custom_class_rules = []
    if class_data and class_data.get("value"):
        for rule in class_data["value"]:
            custom_class_rules.append({
                "name": rule.get("name"),
                "kind": rule.get("kind"),
                "ruleStatus": rule.get("properties", {}).get("ruleStatus"),
                "createdAt": rule.get("properties", {}).get("createdAt"),
            })

    total_builtin = sum(rs["ruleCount"] for rs in system_rulesets)
    total_custom = len(custom_class_rules)

    print(f"  System scan rulesets : {len(system_rulesets)}")
    print(f"  Custom scan rulesets : {len(custom_rulesets)}")
    print(f"  Built-in class. rules: {total_builtin} (across all system rulesets)")
    print(f"  Custom class. rules  : {total_custom}")

    if custom_class_rules:
        print("\n  Custom Classification Rules:")
        for cr in custom_class_rules:
            print(f"    - {cr['name']} (status: {cr['ruleStatus']})")

    return {
        "systemRulesetCount": len(system_rulesets),
        "customRulesetCount": len(custom_rulesets),
        "totalBuiltInRules": total_builtin,
        "totalCustomRules": total_custom,
        "systemRulesets": system_rulesets,
        "customRulesets": custom_rulesets,
        "customClassificationRules": custom_class_rules,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    token = get_token("https://purview.azure.net")

    sources = collect_data_sources(token)
    scan_runs = collect_scan_runs(token, sources)
    classification_rules = collect_classification_rules(token)

    output = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": PURVIEW_ACCOUNT,
        "dataSources": {
            "totalCount": len(sources),
            "sources": sources,
        },
        "scanRuns": {
            "totalCount": len(scan_runs),
            "runs": scan_runs,
        },
        "classificationRules": classification_rules,
    }

    json_path = os.path.join(OUTPUT_DIR, "scan-history.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ JSON saved to {json_path}")


if __name__ == "__main__":
    main()

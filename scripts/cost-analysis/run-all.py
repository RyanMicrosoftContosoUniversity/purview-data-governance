#!/usr/bin/env python3
"""
run-all.py

Master script — runs all Purview cost analysis collection scripts and produces
a consolidated JSON report.

Order of execution:
  1. get-data-map-metrics.py     — Data Map CU metrics and autoscale history
  2. get-scan-history.py         — Registered sources, scan runs, classification rules
  3. get-governed-assets.py      — Asset counts, data products, glossary, lineage, policies
  4. get-data-quality-metrics.py — DQ rules, profile runs, DGPU consumption
  5. get-cost-management-data.py — Azure Cost Management billing data
  6. generate-cost-report.py     — Consolidated cost projection and recommendations

Requirements:
  - Azure CLI (az) logged in
  - Python 3.9+ with 'requests' package

All outputs are saved to scripts/cost-analysis/output/
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

# ── Configuration ────────────────────────────────────────────────────────────

PURVIEW_ACCOUNT = os.environ.get("PURVIEW_ACCOUNT", "governancePurviewRH")
RESOURCE_GROUP = os.environ.get("RESOURCE_GROUP", "governance-rg")
SUBSCRIPTION_ID = os.environ.get("SUBSCRIPTION_ID", "")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

# Steps to execute in order — each is a (name, script_filename) tuple
STEPS = [
    ("Data Map Metrics", "get-data-map-metrics.py"),
    ("Scan History & Classification Rules", "get-scan-history.py"),
    ("Governed Assets", "get-governed-assets.py"),
    ("Data Quality Metrics", "get-data-quality-metrics.py"),
    ("Cost Management Data", "get-cost-management-data.py"),
    ("Generate Consolidated Report", "generate-cost-report.py"),
]


# ── Runner ───────────────────────────────────────────────────────────────────


def run_step(name: str, script: str, env: dict) -> dict:
    """Run a single collection script and return status info."""
    print()
    print("─" * 58)
    print(f"  Step: {name}")
    print("─" * 58)

    script_path = os.path.join(SCRIPT_DIR, script)
    if not os.path.exists(script_path):
        print(f"  ERROR: Script not found: {script_path}")
        return {"success": False, "duration": "00:00", "error": "Script not found"}

    start = time.monotonic()
    success = True
    error_msg = None

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            timeout=300,
        )
        if result.returncode != 0:
            success = False
            error_msg = f"Exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        success = False
        error_msg = "Timed out after 300 seconds"
    except Exception as exc:
        success = False
        error_msg = str(exc)

    elapsed = time.monotonic() - start
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    duration = f"{mins:02d}:{secs:02d}"

    if success:
        print(f"  ✓ {name} completed in {duration}")
    else:
        print(f"  ✗ {name} failed ({duration}): {error_msg}")

    return {"success": success, "duration": duration, "error": error_msg}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("═" * 58)
    print("  Purview Cost Analysis — Full Collection Run")
    print("═" * 58)
    print(f"  Account       : {PURVIEW_ACCOUNT}")
    print(f"  Resource Group: {RESOURCE_GROUP}")
    print(f"  Output Dir    : {OUTPUT_DIR}")
    print(f"  Timestamp     : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Build environment for child processes
    env = os.environ.copy()
    env["PURVIEW_ACCOUNT"] = PURVIEW_ACCOUNT
    env["RESOURCE_GROUP"] = RESOURCE_GROUP
    env["OUTPUT_DIR"] = OUTPUT_DIR
    if SUBSCRIPTION_ID:
        env["SUBSCRIPTION_ID"] = SUBSCRIPTION_ID

    results: dict[str, dict] = {}
    overall_success = True

    for name, script in STEPS:
        result = run_step(name, script, env)
        results[name] = result
        if not result["success"]:
            overall_success = False

    # ── Summary ──────────────────────────────────────────────────────────

    print()
    print("═" * 58)
    print("  Run Summary")
    print("═" * 58)
    print()
    print(f"  {'Step':<38}  {'Status':<8}  Duration")
    print(f"  {'────':<38}  {'──────':<8}  ────────")

    for name, info in results.items():
        status = "✓ Pass" if info["success"] else "✗ Fail"
        print(f"  {name:<38}  {status:<8}  {info['duration']}")

    print()
    if overall_success:
        print("  ✓ All steps completed successfully.")
    else:
        print("  ⚠ Some steps failed. Review the output above.")

    # List output files
    print()
    print("  Output files:")
    if os.path.isdir(OUTPUT_DIR):
        for fname in sorted(os.listdir(OUTPUT_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(OUTPUT_DIR, fname)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                print(f"    {fname} ({size_kb} KB)")

    print(f"\n  Consolidated report: {OUTPUT_DIR}/consolidated-report.json")


if __name__ == "__main__":
    main()

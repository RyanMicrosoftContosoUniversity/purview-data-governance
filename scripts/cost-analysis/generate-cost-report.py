#!/usr/bin/env python3
"""
generate-cost-report.py

Reads JSON outputs from all collection scripts and produces:
  - Monthly cost estimate (Data Map CUs + governed assets + DGPU)
  - Top 5 cost drivers ranked by estimated monthly spend
  - Optimization recommendations with estimated savings

Outputs a human-readable report to stdout and saves JSON to the output directory.

Requirements:
  - Python 3.9+
  - Run after all other collection scripts have completed
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "output"))

# Pricing constants (pay-as-you-go, approximate)
PRICING = {
    "dataMapCU_per_month": 300.00,       # ~$0.411/CU-hour × 730 hours
    "governedAsset_per_day": 0.0165,
    "dgpu_basic_per_hour": 0.105,
    "dgpu_standard_per_hour": 0.21,
    "dgpu_advanced_per_hour": 0.63,
}

# ── Helpers ──────────────────────────────────────────────────────────────────


def load_json(filename: str) -> dict | None:
    """Load a JSON file from the output directory."""
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        print(f"  WARNING: {filename} not found at {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_currency(amount: float) -> str:
    """Format a number as a currency string."""
    return f"${amount:,.2f}"


# ── Cost Estimation ─────────────────────────────────────────────────────────


def estimate_data_map_cost(data_map: dict | None) -> dict:
    """Estimate monthly Data Map CU cost."""
    if not data_map:
        return {"description": "Data Map CUs", "monthlyCost": 0, "details": "No data available"}

    metrics = data_map.get("dataMapMetrics", {})
    avg_cu = metrics.get("averageCU", 0)
    max_cu = metrics.get("maxCU", 0)

    # Baseline of 1 CU is included; only charge for additional CUs
    additional_cus = max(0, avg_cu - 1)
    monthly_cost = round(additional_cus * PRICING["dataMapCU_per_month"], 2)

    return {
        "description": "Data Map Capacity Units (above baseline)",
        "averageCU": avg_cu,
        "maxCU": max_cu,
        "additionalCUs": round(additional_cus, 2),
        "monthlyCost": monthly_cost,
        "details": (
            f"Average {avg_cu} CU, max {max_cu} CU. "
            f"Baseline is 1 CU (included). "
            f"Additional CUs: {additional_cus:.2f} × ${PRICING['dataMapCU_per_month']}/mo = "
            f"{format_currency(monthly_cost)}/mo"
        ),
    }


def estimate_governed_asset_cost(governed: dict | None) -> dict:
    """Estimate monthly governed-asset cost."""
    if not governed:
        return {"description": "Governed Assets", "monthlyCost": 0, "details": "No data available"}

    estimate = governed.get("governedAssetEstimate", {})
    governed_count = estimate.get("estimatedGovernedAssets", 0)
    daily_cost = governed_count * PRICING["governedAsset_per_day"]
    monthly_cost = round(daily_cost * 30, 2)

    return {
        "description": "Governed Assets (data products + glossary)",
        "governedAssetCount": governed_count,
        "costPerAssetPerDay": PRICING["governedAsset_per_day"],
        "dailyCost": round(daily_cost, 2),
        "monthlyCost": monthly_cost,
        "details": (
            f"{governed_count} governed assets × "
            f"${PRICING['governedAsset_per_day']}/asset/day × 30 days = "
            f"{format_currency(monthly_cost)}/mo"
        ),
    }


def estimate_dgpu_cost(dq_metrics: dict | None) -> dict:
    """Estimate monthly DGPU cost from data quality runs."""
    if not dq_metrics:
        return {"description": "DGPU (Data Quality)", "monthlyCost": 0, "details": "No data available"}

    runs = dq_metrics.get("dataQualityProfileRuns", {})
    total_cost = runs.get("estimatedDgpuCost", 0)

    # Extrapolate to monthly if data covers less than 30 days
    # (simple assumption: use the total as a monthly estimate)
    monthly_cost = round(total_cost, 2)

    return {
        "description": "DGPU — Data Quality Processing Units",
        "totalDgpuConsumed": runs.get("totalDgpuConsumed", 0),
        "totalRuns": runs.get("totalRuns", 0),
        "monthlyCost": monthly_cost,
        "details": (
            f"{runs.get('totalRuns', 0)} profile runs, "
            f"{runs.get('totalDgpuConsumed', 0)} DGPU consumed = "
            f"{format_currency(monthly_cost)}/mo"
        ),
    }


def estimate_scan_cost(scan_data: dict | None) -> dict:
    """Estimate scan-related cost impact (scans drive CU throughput)."""
    if not scan_data:
        return {"description": "Scan Operations", "monthlyCost": 0, "details": "No data available"}

    scan_runs = scan_data.get("scanRuns", {})
    total_runs = scan_runs.get("totalCount", 0)
    sources = scan_data.get("dataSources", {}).get("totalCount", 0)

    # Scans are an indirect cost driver (they consume CU throughput)
    # This is informational rather than a direct line item
    return {
        "description": "Scan Operations (indirect — drives CU throughput)",
        "totalScanRuns": total_runs,
        "registeredSources": sources,
        "monthlyCost": 0,  # Indirect; captured in CU cost
        "details": (
            f"{total_runs} scan runs across {sources} sources. "
            f"Scans consume CU throughput — cost is captured under Data Map CUs."
        ),
    }


def estimate_classification_cost(scan_data: dict | None) -> dict:
    """Estimate classification overhead."""
    if not scan_data:
        return {"description": "Classification Rules", "monthlyCost": 0, "details": "No data available"}

    rules = scan_data.get("classificationRules", {})
    custom = rules.get("totalCustomRules", 0)
    builtin = rules.get("totalBuiltInRules", 0)
    total = custom + builtin

    return {
        "description": "Classification Rules (indirect — increases scan time)",
        "customRules": custom,
        "builtInRules": builtin,
        "totalRules": total,
        "monthlyCost": 0,  # Indirect
        "details": (
            f"{total} classification rules ({custom} custom, {builtin} built-in). "
            f"More rules = longer scans = more CU consumption."
        ),
    }


def generate_optimization_recommendations(
    data_map: dict | None,
    scan_data: dict | None,
    governed: dict | None,
    dq_metrics: dict | None,
) -> list:
    """Generate optimization recommendations based on collected data."""
    recommendations = []

    # Check scan frequency
    if scan_data:
        scan_runs = scan_data.get("scanRuns", {}).get("runs", [])
        if len(scan_runs) > 30:
            recommendations.append({
                "priority": "High",
                "category": "Scan Optimization",
                "recommendation": "Reduce scan frequency",
                "detail": (
                    f"Found {len(scan_runs)} scan runs in the collection period. "
                    "Consider switching high-frequency scans from daily to weekly "
                    "or weekly to monthly for stable data sources."
                ),
                "estimatedSavings": "10-30% reduction in CU throughput consumption",
            })

        # Check for full scans that could be incremental
        full_scans = [r for r in scan_runs if r.get("scanType", "").lower() == "full"]
        if full_scans:
            recommendations.append({
                "priority": "Medium",
                "category": "Scan Optimization",
                "recommendation": "Convert full scans to incremental where supported",
                "detail": (
                    f"Found {len(full_scans)} full scan runs. "
                    "Incremental scans process only changed data and "
                    "consume significantly less CU throughput."
                ),
                "estimatedSavings": "20-50% reduction per scan",
            })

    # Check classification rules
    if scan_data:
        rules = scan_data.get("classificationRules", {})
        custom = rules.get("totalCustomRules", 0)
        if custom > 10:
            recommendations.append({
                "priority": "Medium",
                "category": "Classification Optimization",
                "recommendation": "Consolidate custom classification rules",
                "detail": (
                    f"Found {custom} custom classification rules. "
                    "Review for overlapping patterns and consolidate "
                    "to reduce per-scan compute time."
                ),
                "estimatedSavings": "5-15% reduction in scan duration",
            })

    # Check governed assets
    if governed:
        estimate = governed.get("governedAssetEstimate", {})
        governed_count = estimate.get("estimatedGovernedAssets", 0)
        if governed_count > 100:
            monthly = governed_count * PRICING["governedAsset_per_day"] * 30
            savings_10pct = round(monthly * 0.10, 2)
            recommendations.append({
                "priority": "High",
                "category": "Governed Asset Optimization",
                "recommendation": "Review and de-govern low-value assets",
                "detail": (
                    f"{governed_count} governed assets cost "
                    f"{format_currency(monthly)}/mo. "
                    "Review assets linked to data products and glossary terms. "
                    "De-governing 10% of low-value assets saves "
                    f"{format_currency(savings_10pct)}/mo."
                ),
                "estimatedSavings": f"{format_currency(savings_10pct)}/mo (10% reduction)",
            })

    # Check DQ runs
    if dq_metrics:
        dq_runs = dq_metrics.get("dataQualityProfileRuns", {})
        if dq_runs.get("totalRuns", 0) > 0:
            dgpu_cost = dq_runs.get("estimatedDgpuCost", 0)
            if dgpu_cost > 50:
                recommendations.append({
                    "priority": "Medium",
                    "category": "Data Quality Optimization",
                    "recommendation": "Optimize DQ rule SKU selection",
                    "detail": (
                        f"DGPU cost: {format_currency(dgpu_cost)}. "
                        "Review if Advanced-tier rules can be downgraded "
                        "to Standard or Basic where full capabilities aren't needed."
                    ),
                    "estimatedSavings": "Up to 50% per rule (Basic vs. Advanced)",
                })

    # Check Data Map CUs
    if data_map:
        metrics = data_map.get("dataMapMetrics", {})
        if metrics.get("aboveBaseline", False):
            max_cu = metrics.get("maxCU", 0)
            recommendations.append({
                "priority": "High",
                "category": "Data Map Optimization",
                "recommendation": "Investigate Data Map autoscale triggers",
                "detail": (
                    f"Data Map scaled to {max_cu} CUs. "
                    "Review scan schedules and lineage extraction "
                    "to identify operation spikes. Staggering scans "
                    "may reduce peak throughput needs."
                ),
                "estimatedSavings": "Reduce peak CU from autoscale",
            })

    # General recommendations
    recommendations.append({
        "priority": "Low",
        "category": "General",
        "recommendation": "Remove stale data sources",
        "detail": (
            "Periodically review registered data sources. "
            "Remove sources that are no longer active to reduce "
            "metadata volume and scan overhead."
        ),
        "estimatedSavings": "Varies — reduces metadata storage",
    })

    return recommendations


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("═══════════════════════════════════════════════════════════")
    print("  Purview Cost Analysis — Consolidated Report")
    print("═══════════════════════════════════════════════════════════")

    # Load all JSON outputs
    data_map = load_json("data-map-metrics.json")
    scan_data = load_json("scan-history.json")
    governed = load_json("governed-assets.json")
    dq_metrics = load_json("data-quality-metrics.json")
    cost_mgmt = load_json("cost-management-data.json")

    # ── Cost estimates ───────────────────────────────────────────────────

    print("\n═══ Monthly Cost Estimates ═══")

    dm_cost = estimate_data_map_cost(data_map)
    ga_cost = estimate_governed_asset_cost(governed)
    dgpu_cost = estimate_dgpu_cost(dq_metrics)
    scan_cost = estimate_scan_cost(scan_data)
    class_cost = estimate_classification_cost(scan_data)

    all_costs = [dm_cost, ga_cost, dgpu_cost, scan_cost, class_cost]

    total_estimated_monthly = sum(c["monthlyCost"] for c in all_costs)

    for c in all_costs:
        indicator = format_currency(c["monthlyCost"]) if c["monthlyCost"] > 0 else "(indirect)"
        print(f"\n  {c['description']}")
        print(f"    {c['details']}")
        print(f"    Monthly cost: {indicator}")

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL ESTIMATED MONTHLY COST: {format_currency(total_estimated_monthly)}")

    # Compare with actual cost
    if cost_mgmt:
        actual_projected = cost_mgmt.get("summary", {}).get("projectedMonthlyCost", 0)
        actual_30d = cost_mgmt.get("totalCost30Days", 0)
        print(f"  Actual billed cost (30d)    : {format_currency(actual_30d)}")
        print(f"  Actual projected monthly    : {format_currency(actual_projected)}")

    # ── Top 5 cost drivers ───────────────────────────────────────────────

    print("\n═══ Top 5 Cost Drivers ═══")

    cost_drivers = []

    # Direct costs
    for c in all_costs:
        if c["monthlyCost"] > 0:
            cost_drivers.append({
                "driver": c["description"],
                "monthlyCost": c["monthlyCost"],
            })

    # Add actual meter data if available
    if cost_mgmt and cost_mgmt.get("costByMeter"):
        for meter in cost_mgmt["costByMeter"]:
            cost_drivers.append({
                "driver": f"{meter['meterCategory']} — {meter['meterName']}",
                "monthlyCost": round(meter["cost"], 2),
            })

    # Sort and take top 5
    cost_drivers = sorted(cost_drivers, key=lambda x: -x["monthlyCost"])[:5]

    print(f"\n  {'Rank':<6} {'Driver':<50} {'Monthly Cost':>12}")
    print(f"  {'────':<6} {'──────':<50} {'────────────':>12}")
    for i, driver in enumerate(cost_drivers, 1):
        print(f"  {i:<6} {driver['driver']:<50} {format_currency(driver['monthlyCost']):>12}")

    if not cost_drivers:
        print("  No cost drivers found. Run the collection scripts first.")

    # ── Optimization recommendations ─────────────────────────────────────

    print("\n═══ Optimization Recommendations ═══")

    recommendations = generate_optimization_recommendations(
        data_map, scan_data, governed, dq_metrics
    )

    for i, rec in enumerate(recommendations, 1):
        print(f"\n  {i}. [{rec['priority']}] {rec['recommendation']}")
        print(f"     Category: {rec['category']}")
        print(f"     {rec['detail']}")
        print(f"     Estimated savings: {rec['estimatedSavings']}")

    # ── Build consolidated output ────────────────────────────────────────

    output = {
        "reportGeneratedAt": datetime.now(timezone.utc).isoformat(),
        "purviewAccount": os.environ.get("PURVIEW_ACCOUNT", "governancePurviewRH"),
        "pricing": PRICING,
        "costEstimates": {
            "dataMapCUs": dm_cost,
            "governedAssets": ga_cost,
            "dgpu": dgpu_cost,
            "scanOperations": scan_cost,
            "classificationRules": class_cost,
            "totalEstimatedMonthlyCost": total_estimated_monthly,
        },
        "topCostDrivers": cost_drivers,
        "optimizationRecommendations": recommendations,
        "sourceData": {
            "dataMapMetrics": data_map,
            "scanHistory": scan_data,
            "governedAssets": governed,
            "dataQualityMetrics": dq_metrics,
            "costManagement": cost_mgmt,
        },
    }

    json_path = os.path.join(OUTPUT_DIR, "consolidated-report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ Consolidated report saved to {json_path}")


if __name__ == "__main__":
    main()

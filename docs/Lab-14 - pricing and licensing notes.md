# Lab‑14: Pricing and licensing – Speaker notes

## Purpose and goals

- Understand **Microsoft Purview pricing principles** and the components that drive cost【362572060908785†L21-L45】.
- Learn how to estimate costs for the unified catalog and data management workloads; choose the right compute tier for your needs.【362572060908785†L99-L120】

## Pricing principles【362572060908785†L21-L45】

Purview pricing is built around four principles:

1. **Fair market value** – Costs align with the value delivered by the service; customers pay only for what they use.
2. **Consumption‑based** – Billing is based on consumption of compute resources (Data Governance Processing Units, or DGPUs) and storage; there are no per‑user fees.
3. **Customer control** – Customers can choose compute tiers and scale up or down; no fixed commitment.
4. **Transparency** – Pricing and usage metrics are visible; customers can forecast and manage costs.

## Billing meters

- **Unified Catalog** – charged per **asset ingested** into the data map and stored in the catalog; includes metadata storage and search features【362572060908785†L21-L45】.
- **Data Management** – charged based on **compute consumption** measured in **Data Governance Processing Units (DGPUs)**; covers scanning, classification, data quality and health management.【362572060908785†L21-L45】

## Data management compute tiers【362572060908785†L99-L120】

- Purview offers several **compute tiers**, each providing a specific number of DGPUs per hour.  Examples:
  - **Tier 1**: 1 DGPU – for small or infrequent workloads.
  - **Tier 2**: 4 DGPUs – medium workloads or more frequent scanning.
  - **Tier 3**: 16 DGPUs – large enterprises or heavy scanning and data quality analysis.
  - Additional tiers provide more DGPUs to support large volumes of scanning and classification.【362572060908785†L99-L120】
- You can **change tiers** at any time; scaling up increases throughput (scans run faster), while scaling down saves costs.
- Purview automatically scales down compute when idle to reduce charges.

## Cost estimation examples【362572060908785†L99-L120】

- Example: scanning a **1 TB storage account** once weekly with Tier 1 compute.  The scanning job may take several hours; cost is proportional to DGPU hours consumed.
- Example: running **daily data quality scans** on multiple databases might require Tier 2 or Tier 3 to complete within schedule; compute costs will be higher.
- Data management costs also include **health actions and reports**; heavier use of DQ and health management increases DGPU consumption.

## Licensing considerations

- Purview is **pay‑as‑you‑go**; there is no license subscription.  Only compute and storage consumption are billed.
- The same Purview account can govern multiple data sources and domains; costs scale with usage rather than number of domains.
- If you stop scanning and the service remains idle, compute charges drop to near zero, but unified catalog storage fees remain for assets stored.
- For budgeting, monitor usage in **Azure Cost Management** and set **spending alerts**.

## Lab tasks and walkthrough

- Review the pricing calculator on Azure and experiment with different **compute tiers** and scanning frequencies.
- Estimate the monthly cost for your organisation’s known data sources and scanning cadence; compare tiers.
- Configure **alerts** in Azure Cost Management to notify administrators when spending approaches budget thresholds.
- Discuss strategies to **optimise costs**, such as reducing scanning frequency for static data and curating assets to avoid scanning irrelevant items.

## Tips for facilitators

- emphasise that cost is driven largely by scanning and data quality workloads; proper planning can avoid surprises.
- Encourage participants to monitor consumption and adjust compute tiers proactively.
- Remind teams that curating assets and pruning unused sources can reduce both unified catalog and scanning costs.

## References

1. Pricing principles and cost components【362572060908785†L21-L45】.
2. Data management compute tiers and examples【362572060908785†L99-L120】.

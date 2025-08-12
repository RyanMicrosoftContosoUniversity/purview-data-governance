# Lab‑11: Health management reports – Speaker notes

## Purpose and goals

- Explore **built‑in health reports** in Purview, which provide aggregated metrics and insights about your data estate.
- Learn how to interpret the Data Governance and Data Quality reports to identify areas for improvement【300196264775587†L36-L115】.

## Available reports【300196264775587†L36-L115】

Purview currently offers eight reports (some are preview features):

1. **Data Governance report** – summarises scanning, classification, curation and term coverage across domains.
2. **Data Estate report (preview)** – high‑level view of registered sources and assets; includes a heatmap of asset types.
3. **Data Usage report (preview)** – shows how often assets are accessed and by whom (requires diagnostic settings).
4. **Data Estate Coverage report (preview)** – highlights sources that are registered but not scanned or curated.
5. **Data Quality report (preview)** – summarises data quality scores and rule pass/fail counts for scanned datasets.
6. **Data Quality Health report** – provides detailed metrics and visualisations on data quality tests.【300196264775587†L36-L115】
7. **Data Map Stats report** – lists counts of assets, terms, classifications and policies; useful for tracking growth.
8. **Data Map Growth report (preview)** – charts asset counts over time to monitor adoption.

## Data Governance report【300196264775587†L130-L167】

- Presents an overview of **scanning coverage**, **classification coverage**, **term coverage** and **curation**.  Each metric is compared against thresholds.
- Use the **domain filter** to view metrics for a specific domain.  This helps domain leads identify areas needing attention.
- The report includes top performing domains and underperforming domains; use this to prioritise improvement efforts.
- Example: the classification coverage section shows the percentage of assets with at least one classification versus the target threshold【300196264775587†L130-L167】.

## Data Quality Health report【300196264775587†L170-L218】

- Focuses on the results of DQ scans.  Provides:
  - **Dataset coverage** – number of datasets scanned vs total datasets.
  - **DQ test coverage** – proportion of datasets with at least one rule applied.
  - **Score distribution** – percentage of datasets scoring high, medium or low quality.
  - **Top failing rules** – list of rules with highest failure rates; helps prioritise remediation.
  - **Trend charts** – show how quality scores evolve over time.
- Use these insights to focus on problematic datasets and adjust rules or upstream processes.【300196264775587†L170-L218】

## Other reports

- The **Data Estate report** (preview) shows registered sources by type and region; use it to ensure all critical systems are represented.
- The **Data Usage report** (preview) highlights adoption; identify high‑value assets based on view counts.
- **Data Map Stats** and **Data Map Growth** help track the scale and adoption of Purview over time.

## Lab tasks and walkthrough

- Navigate to **Reports** under Health Management; explore each report and discuss its purpose.
- Using the Data Governance report, select your domain and **identify metrics** that are below target (e.g., low curation coverage).
- Examine the **Data Quality Health report**; identify a dataset with a low score and discuss why it might be failing tests.
- Use the **Date filters** or **trend charts** to observe changes in scores or coverage over time; correlate them with actions taken in previous labs.
- Discuss how these reports can be shared with stakeholders to communicate progress and justify resource allocation.

## Tips for facilitators

- emphasise that reports are updated after scans and actions; delays may occur between improvement efforts and reflected metrics.
- Encourage participants to export or screenshot report sections for presentations or steering committee updates.
- Remind participants that preview reports may change; check the documentation for the latest features.

## References

1. Overview of built‑in reports【300196264775587†L36-L115】.
2. Data Governance report metrics【300196264775587†L130-L167】.
3. Data Quality Health report metrics and visuals【300196264775587†L170-L218】.

# Lab‑09: Data quality management – Speaker notes

## Purpose and goals

- Establish a **data quality (DQ) framework** within Purview to assess, monitor and improve the quality of data sets across the organisation.
- Learn how to configure DQ scanning, define quality rules and interpret results to drive remediation.【43512880369851†L15-L29】【43512880369851†L73-L100】

## Why data quality matters

- High‑quality data is essential for reliable analytics, regulatory compliance and business decision‑making.  Poor data quality leads to mistrust and inefficient processes【43512880369851†L15-L29】.
- In a multi‑cloud world, consistent data quality measurement is challenging.  Purview addresses this by providing **unified DQ scanning** that can be applied to data in Azure, AWS or on‑premises environments【43512880369851†L15-L29】.

## Pre‑requisites for DQ scanning【43512880369851†L73-L100】

- Registered data source and scan rule set (see Lab 03); DQ scanning builds on existing scans.
- Appropriate **integration runtime** configured (Azure IR for cloud, self‑hosted IR for on‑premises).
- Permissions: you need the **Data Source Administrator** role to set up DQ scanning.
- For Onelake integration, you may need to create a **shortcut** from the external storage to Onelake.【43512880369851†L176-L211】

## Configuring scan connections and profiles【43512880369851†L73-L100】

- In Purview, create a **data quality scan** for a source; choose whether to run it **ad‑hoc** or on a **schedule** (daily/weekly).
- Define the **scan scope**: specific tables, folders or entire schemas.
- Enable **profiling** to generate column statistics such as null counts, distinct values, pattern distribution.  Profiling helps identify data issues before rule definition.
- Use sampling when profiling large datasets to reduce scan time.

## Defining data quality rules【43512880369851†L214-L254】

- There are three rule types:
  1. **Dataset rules**: apply to entire datasets (e.g., row count > 0).  Useful for completeness checks.
  2. **Table rules**: apply to specific tables (e.g., table contains column `CustomerID`).  Use for schema validation.
  3. **Column rules**: apply to individual columns (e.g., values are not null, within range, match regex).  These are the most granular and common.
- Rules can be created manually or imported from templates.  Define a **threshold** (percentage of acceptable rows) and set a severity (Informational, Warning, Error).
- You can group multiple rules into **rule sets** and apply them across multiple datasets for consistency.

## Scheduling and monitoring【43512880369851†L176-L211】【43512880369851†L214-L254】

- Schedule data quality scans to run at appropriate intervals; align with data refresh frequency.
- After scans run, review results in the **Data quality dashboard**.  Look for metrics such as **score** (percentage of rules passed) and **failed records**.
- When a rule fails, drill down to see which rows or columns caused the failure; export sample data if needed.
- Track trends over time to see whether data quality is improving or deteriorating.

## Improving data quality

- Use Purview’s **actions** (see Lab 10) to assign remediation tasks when quality issues are found.
- Adjust rule thresholds or definitions as data changes; unrealistic thresholds may generate false positives.
- Share data quality metrics with data owners and stakeholders to promote accountability.
- Consider implementing upstream data cleansing (e.g., in ETL pipelines) to prevent recurring issues.

## Lab tasks and walkthrough

- Select a source previously registered and scanned; create a **data quality scan** for one of its tables.
- Run the scan with **profiling** enabled; examine the profile results (null ratios, patterns, etc.).
- Define **one dataset rule**, **one table rule** and **two column rules**; apply them to the dataset.
- Schedule the scan to run daily for a week and review the resulting DQ metrics.  Discuss any issues found.
- Experiment with changing thresholds and observe how the scores change.  Identify root causes for failed records.

## Tips for facilitators

- emphasise that DQ scanning is optional but highly valuable; start with critical datasets and expand coverage gradually.
- Remind participants to base rules on business logic, not just technical constraints.
- Suggest using a **naming convention** for rules and rule sets to make them reusable across datasets.

## References

1. Importance of data quality and multi‑cloud management【43512880369851†L15-L29】.
2. Pre‑requisites and configuring data quality scans【43512880369851†L73-L100】.
3. Types of data quality rules and their usage【43512880369851†L214-L254】.

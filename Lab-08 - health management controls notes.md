# Lab‑08: Health management controls – Speaker notes

## Purpose and goals

- Learn how Purview provides **health management** for the data estate, enabling proactive monitoring and actionable insights.
- Understand the **eight pillars of data estate health** and the role of **controls**, **actions** and **reports**.
- Practise reviewing health controls and updating thresholds and notifications【184492788950348†L72-L93】.

## Data estate health pillars【184492788950348†L72-L93】

Purview assesses health across eight pillars:

1. **Scanning coverage** – percentage of registered sources scanned regularly; low coverage indicates blind spots.
2. **Curation** – proportion of assets with curated descriptions, contacts and classifications.
3. **Classification coverage** – how many assets have been classified with sensitive information types.
4. **Term coverage** – adoption of glossary terms across assets.
5. **Data quality** – quality scores resulting from data profiling and rule evaluation.
6. **Access policy coverage** – existence of policies controlling access to assets.
7. **Data sharing** – use of data products and sharing mechanisms.
8. **Usage metrics** – how often assets are viewed or queried.

![Health status gauge]({{file:file-VX4dJhF1eWCxnogFqyCNT9}})

Each pillar has one or more **controls** that track specific metrics (e.g., “Sources scanned in last 30 days”).  Controls have thresholds and status (Good, Warning, Poor).

## Health controls and configuration【184492788950348†L72-L93】

- **Controls** evaluate the health pillars; each control has a **threshold** (e.g., 80% coverage) and a **target date**.
- Purview calculates the **status** of each control (e.g., on target, at risk) and surfaces them in dashboards.
- Administrators can **edit thresholds** to reflect organisational goals; for example, raising the target for curation coverage.
- Controls can be grouped by domains or collections; this allows domain leads to monitor their own data health.

## Lab tasks and walkthrough

- Navigate to **Health management > Controls** in the Purview portal.
- Review the list of controls across the eight pillars; note which are on track and which need attention.
- For a control that is in **warning** state (e.g., low classification coverage), **adjust the threshold** or **assign an action** to a responsible owner.
- Create a **custom control** if there is a unique metric your organisation wants to track (e.g., number of certified assets).
- Explore the **dashboard**: examine the dials and color coding; discuss what constitutes a healthy data estate.
- Optionally, set up **email alerts** for controls that fall below thresholds.

## Tips for facilitators

- Emphasise that health monitoring is continuous; review controls regularly to identify trends.
- Highlight that thresholds should be **realistic** and reflect current maturity; gradually raise them as governance matures.
- Encourage domains to own their controls; a federated approach ensures accountability and focused improvement.

## References

1. Eight pillars of data estate health and their descriptions【184492788950348†L72-L93】.

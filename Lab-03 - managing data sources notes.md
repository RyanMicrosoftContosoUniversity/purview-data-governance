# Lab‑03: Managing Data Sources – Speaker notes

## Purpose and goals

- Learn how to **register data sources** in Purview and plan a scanning strategy.
- Understand **scan rule sets**, classifications and custom classifications to maximise metadata capture.
- Set up **integration runtimes** appropriate for your environment (Azure, virtual network managed, self‑hosted or AWS)【653045028596927†L331-L376】.

## Registering data sources

- **Registration** creates a logical representation of a data store (e.g., an Azure SQL database, ADLS Gen2 account, Power BI workspace) in the data map【653045028596927†L16-L40】.
- Without registration, Purview cannot scan or enforce policies; registration is the first step for any source.
- During registration you specify the collection, friendly name and authentication method; for Azure resources you can browse your subscription.
- Tips:
  - Use a consistent naming convention to reflect environment and purpose (e.g., `Sales_Prod_ADLS`).
  - Organise sources into the correct collection to ensure appropriate role assignments.

## Scanning and scan rule sets

- **Scanning** pulls technical metadata, schema information and sample data profiles into the data map.
- You must create a **scan rule set** specifying what to scan (e.g., specific databases, schemas, file types) and how often【653045028596927†L140-L173】.
- Consider the **frequency** (daily, weekly, on‑demand) based on how often the source changes; too frequent scanning can increase costs.
- **Incremental scanning** updates only changed objects; this reduces time and compute compared with full scans.
- Review the default rule sets for each source type; customise them if necessary to include or exclude certain objects.

## Classification and custom classifications

- Purview includes built‑in **classifications** that detect sensitive data types such as personal identifiers, financial data and health records.
- During scanning you can **apply system classifications** by enabling classification in the scan settings.
- You can also create **custom classifications** for patterns unique to your organisation (e.g., employee ID format, contract numbers).  Use regular expressions or custom rules to define them【653045028596927†L331-L376】.
- After scanning, review classification results and adjust scan rules if the classification coverage is not satisfactory【653045028596927†L16-L40】.

## Integration runtimes (IR)

- Scans require an **integration runtime (IR)** to connect to sources.  There are four types【653045028596927†L331-L376】:
  - **Azure IR**: fully managed; used for scanning Azure resources via public endpoints.
  - **Managed virtual network IR**: automatically deploys inside a Purview‑managed VNet; used to scan Azure resources within a private network.
  - **Self‑hosted IR**: installed on‑premises; used for scanning on‑premise databases, file systems or networks with no inbound connectivity.
  - **AWS (cloud)**: used for scanning Amazon S3 via cross‑cloud bridging.
- Choose the IR type based on network configuration and security requirements; ensure necessary firewall rules are in place.

## Lab tasks and walkthrough

- **Register a sample source** (e.g., ADLS Gen2 account or SQL database) under the appropriate collection; practise naming conventions.
- Create a **scan rule set**: select the scope (databases, file paths), enable classification and define recurrence (e.g., weekly).
- **Configure an integration runtime**: choose Azure IR for Azure resources; if scanning on‑premises, install a self‑hosted IR and link it to Purview.
- Run a **test scan**; review the scan results in the data catalog, including classifications and lineage.
- Modify the scan rule set to include incremental scanning; observe changes in the next scan cycle.
- Define at least one **custom classification** (e.g., pattern for employee IDs) and verify that it applies during scanning.

## Tips for facilitators

- Emphasise that scanning can be resource‑intensive; schedule scans during off‑peak hours.
- Encourage participants to track scanning status and failures via the Purview portal; scanning logs can reveal misconfigurations.
- Remind teams to update scan rule sets when new schemas or file types are introduced.

## References

1. The importance of registering sources and the registration process【653045028596927†L16-L40】.
2. Scan rule sets, scanning frequency and considerations【653045028596927†L140-L173】.
3. Types of integration runtimes and pro tips【653045028596927†L331-L376】.

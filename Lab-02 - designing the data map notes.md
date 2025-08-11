# Lab‑02: Designing the Data Map – Speaker notes

## Purpose and goals

- Design an intuitive **logical structure** for Purview using **platform domains** and **collections**.
- Understand how **sensitivity labels** enhance classification and protection of data across the Data Map【614453694275890†L136-L229】.
- Plan for **lineage capture** through built‑in connectors to services like Azure Data Factory and Synapse【614453694275890†L45-L124】.

## Platform domains

- A **domain** is a top‑level grouping that reflects the business structure; it can represent a business unit, product line or functional area【614453694275890†L45-L124】.
- Each Purview account is pre‑populated with a **default domain** for unclassified assets.  You can create up to four additional custom domains【614453694275890†L45-L124】.
- Domains should align to how people think about the data; ensure each domain has clear ownership and accountability.
- When designing domains, avoid overlapping responsibilities; maintain autonomy for each team while enabling enterprise standards.

## Collections hierarchy

- **Collections** are hierarchical containers within domains that organise assets and resources【614453694275890†L45-L124】.
- Use collections to align datasets to teams, projects or environments (e.g., `Finance/Reporting/PowerBI`).
- RBAC roles (e.g., data reader, curator, policy author) are assigned at the collection level to delegate responsibilities.
- Collections can be nested; access inherits downwards.  Design the hierarchy carefully to minimise redundant assignments.

![Domain and collections hierarchy]({{file:file-VHPTbf6UaChDJgesvpa21Y}})

## Sensitivity labels

- Sensitivity labels are used to **classify and protect data** both in the Data Map and beyond (e.g., Microsoft 365)【614453694275890†L136-L229】.
- Labels can apply encryption, watermarking or metadata to assets; they help meet compliance obligations by marking confidential or regulated information.
- When Purview scans a source, it can apply **information‑type classifications** (e.g., `US Social Security Number`) and associate a sensitivity label accordingly【614453694275890†L136-L229】.
- Design a **label taxonomy** that matches your compliance policies; avoid having too many similar labels which can cause confusion.
- Remember that only a subset of assets may need sensitivity labels; focus on high‑risk data first.

## Lineage connectors

- Lineage captures **how data moves** between sources, transformations and destinations.  It supports traceability, impact analysis and data‑quality monitoring.
- Purview automatically captures lineage through built‑in connectors for **Azure Data Factory**, **Azure Synapse Analytics**, **SQL Server Integration Services** and other services【614453694275890†L45-L124】.
- You can also publish lineage programmatically using Purview REST APIs; this is useful for custom ETL pipelines or third‑party tools.
- Encourage teams to enable lineage wherever possible; it helps answer “where did this data come from?” and “who will be impacted by a change?”.

## Lab tasks and walkthrough

- **Review the organisation structure**: decide on domain names and the number of domains needed.
- Create the domain structure in Purview: use the UI to add new domains and rename or repurpose the default domain.
- Within each domain, **define collections** reflecting teams or data sets; assign appropriate RBAC roles at each collection level.
- **Configure sensitivity labels**: import existing labels from Microsoft Purview Information Protection or create new ones; associate them with information‑type classifications.
- Set up **lineage capture**: enable built‑in connectors in Data Factory and other ETL services; test by running sample pipelines and viewing lineage graphs.
- Document design decisions; maintain a dictionary of domains, collections and labels for future reference.

## Tips for facilitators

- Use the diagram above to illustrate how domains and collections form a tree; emphasise that good design reduces administrative overhead.
- Remind participants that labels and classifications drive both compliance and access controls; they are not just metadata.
- Encourage a **minimum‑viable structure** first; complexity can always be added later.

## References

1. Designing domains and collections【614453694275890†L45-L124】.
2. Sensitivity labels, features and integration【614453694275890†L136-L229】.

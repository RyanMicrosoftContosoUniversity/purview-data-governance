# Lab‑01: Introduction and overview – Speaker notes

## Purpose and goals

- **Kick off the masterclass** by clarifying the current data‑governance maturity of the organisation.  Ask whether there is a data steward, an existing data catalog, or any compliance obligations in place【636819359404975†L25-L126】.
- Set expectations for the **governance journey** by highlighting the importance of building a data map and a unified catalog; these will serve as the foundation for all later labs【636819359404975†L25-L126】.
- Explain why **Azure Purview** was chosen: it provides a federated data map (for metadata storage) and a unified data catalog (for search and discovery) – together they support compliance, curation and collaboration【636819359404975†L25-L126】.

## Key discussion questions for participants

- Do we know who our **data owners/stewards** are?  Without ownership, assets remain ungoverned【636819359404975†L25-L126】.
- Is there a **data catalog** today?  If yes, what are its limitations?  If no, what pain points exist when finding data【636819359404975†L25-L126】?
- What **compliance obligations** (GDPR, HIPAA, etc.) apply?  Are there regulatory audits or classification mandates【636819359404975†L25-L126】?
- How are **business domains** organised?  Understanding domain structure will influence the data map design【636819359404975†L25-L126】.

## Executive overview: Purview architecture

- Purview consists of two core components: the **Data Map** and the **Unified Catalog**【636819359404975†L25-L126】.
  - The **Data Map** is the metadata store; it indexes technical metadata from scanned sources and stores relationships between assets, terms and policies.
  - The **Unified Catalog** provides a familiar search and browsing experience on top of the data map, enabling data consumers to discover and request access to assets【636819359404975†L25-L126】.
- Scanning is used to populate the data map; classification engines automatically label sensitive data and assign system‑generated lineage.
- The unified catalog surfaces curated descriptions, terms, quality scores, access policies and usage metrics.

![Data Map vs Unified Catalog]({{file:file-FP3oCzbTGsETDCPcBMvXo1}})

## Concept of federated governance

- Purview supports a **federated governance model**.  Central governance teams define standards and policies, while domain teams curate assets and implement them.
- A federated model scales to diverse business units: each domain manages its own collections and data products, but shares definitions and policies across the enterprise【636819359404975†L25-L126】.
- During this lab, emphasise the importance of **ownership**: success depends on data owners actively curating assets and maintaining quality.

## Lab tasks and walkthrough

- **Discuss the maturity questions** listed above with participants; record answers to identify gaps and set priorities.
- Show a high‑level **architecture diagram** of Purview, highlighting ingestion, scanning, classification and curation paths.
- **Demonstrate the unified catalog**: search for a sample asset, view its classification, lineage and contacts.
- Explain how scanning from on‑premises or multi‑cloud sources populates the data map; mention connectors for SQL Server, Azure SQL, storage accounts and SaaS sources.
- Outline the labs that follow: participants will design domains, register data sources, curate assets, create data products, manage OKRs, monitor health and implement policies.
- Encourage questions and emphasise that the success of the program depends on continued engagement from domain stewards.

## Tips for facilitators

- Keep the session interactive – ask participants to share examples of data‑governance challenges they face.
- Use the diagram above to reinforce the difference between the **metadata store (Data Map)** and the **consumer interface (Unified Catalog)**.
- Set the tone for a **federated approach**, clarifying that central teams provide the platform and guidance while domains manage their own assets.

## References

1. Purview introduction and governance maturity questions【636819359404975†L25-L126】.

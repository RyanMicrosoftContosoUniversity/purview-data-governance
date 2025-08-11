# Lab‑06: Data products and access – Speaker notes

## Purpose and goals

- Introduce **data products** as a way to package curated assets with business context, ensuring clarity of purpose and accountability【928666488517323†L17-L37】.
- Explain how data products differ from individual assets and how they support consumption via Purview’s unified catalog.
- Define **access policies** and understand how Purview’s access management controls secure data products【928666488517323†L40-L45】.

## Data products concept

- A **data product** is a collection of assets, metadata, and policies curated to serve a specific business need (e.g., `Customer360`, `Daily Sales Report`).  It provides context, quality, lineage and terms【928666488517323†L17-L37】.
- Components of a data product【928666488517323†L17-L37】:
  - **Product description**: high‑level overview of purpose and scope.
  - **Associated assets**: datasets, reports, dashboards or models that support the product.
  - **Glossary terms**: business terms linked to the product to clarify meaning.
  - **Objectives and key results (OKRs)**: metrics that track the value delivered (see Lab 07).
  - **Access policy**: defines who can access the data and under what conditions【928666488517323†L40-L45】.
- Unlike individual assets, a data product is designed for **reuse and sharing**; it has clear ownership and is treated as a product with a lifecycle.
- Data products map to business domains; they support a federated model by allowing domains to publish consumable packages.

## Designing data products

- Identify a **business use case** that requires multiple assets (e.g., cross‑selling analysis, regulatory reporting).
- Gather the relevant assets from the catalog; ensure they are curated (descriptions, ownership, classifications).
- Define a **product scope**: what questions should the product answer?  Who is the target consumer?
- Add a **product description** and link to **glossary terms**; this helps consumers understand context.
- Establish **quality indicators** or **certification status** to signal trustworthiness.

## Access policies【928666488517323†L40-L45】

- Purview uses **access policies** to control who can view or query assets within a data product; these policies are enforced at the data source via Microsoft Purview access control.
- Policies can be **read**, **purview read**, or **create** operations; they are defined on collections or individual assets.
- Data product owners should review existing policies and create new ones when necessary to align with business requirements.
- Access policies complement RBAC assignments; RBAC controls what a user can do within Purview, while access policies control access to the underlying data.

## Lab tasks and walkthrough

- **Identify a candidate product**: choose an analytics or reporting use case that spans multiple curated assets.
- In Purview, create a **new data product**; provide a descriptive name and business description.
- **Associate assets**: select datasets, reports or tables from the catalog.  Ensure they belong to the same domain and are properly curated.
- Link **glossary terms** and set an **owner** (product manager) and **steward** (data engineer).
- Add an **access policy**: grant appropriate roles (e.g., reader) to consumer groups; verify that the policy is correctly scoped to the collections or assets involved.
- Discuss how OKRs (Lab 07) can be linked to data products to track success.

## Tips for facilitators

- Emphasise that data products should be **maintained over time**: update assets, descriptions and policies as requirements evolve.
- Encourage alignment between data products and business domains; avoid creating overlapping products.
- Remind participants to check that access policies meet security and compliance requirements.

## References

1. Definition and components of data products【928666488517323†L17-L37】.
2. The need for access policies and securing data products【928666488517323†L40-L45】.

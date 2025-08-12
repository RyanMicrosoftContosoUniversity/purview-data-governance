# Lab‑05: Curating data assets – Speaker notes

## Purpose and goals

- Introduce **federated governance** and the importance of **data curation** for high‑quality data products【836156919177758†L16-L35】.
- Learn how to enrich assets with business context (descriptions, terms, contacts) and differentiate between curated and non‑curated assets.
- Practice browsing, editing and managing data assets in the Purview catalog.

## Federated governance and curation

- Purview encourages a **federated governance model** where central teams provide the platform and policies, while domain teams curate their own data【836156919177758†L16-L35】.
- **Data curation** means enriching raw technical metadata with business context, quality indicators and relationships.  Curated assets are more discoverable and trustworthy.
- Reasons to curate data include:
  - Improving searchability through meaningful names and descriptions.
  - Defining ownership and accountability (contacts, stewards).
  - Associating data assets with glossary terms and data products.
  - Documenting lineage and quality indicators.

## Federated curation process

- **Discover assets** using search or browse; identify candidates for curation.
- **Review the metadata**: check classifications, sensitivity labels and existing terms.
- **Add a description** that explains the purpose of the asset, its data sources and usage.  Aim for clarity and brevity.
- **Assign a data owner/steward** to set accountability; choose someone who knows the asset well.
- **Link to glossary terms**: select appropriate business terms from the enterprise glossary; add synonyms if necessary.
- **Review and adjust classifications**: verify that sensitive data is correctly labelled; apply custom classifications if missing.
- Optionally, **associate the asset with a data product** to contextualise it within a product offering (see Lab 06).

## Curated vs non‑curated assets【836156919177758†L16-L35】

| Aspect                | Non‑curated asset          | Curated asset            |
|-----------------------|-----------------------------|---------------------------|
| Description           | May be blank or technical  | Clear business purpose    |
| Ownership             | Not assigned               | Owner and steward listed  |
| Glossary terms        | None                       | Linked to domain terms    |
| Classification        | Default only               | Reviewed and adjusted     |
| Discoverability       | Low                        | High – easier to search   |

## Lab tasks and walkthrough【836156919177758†L60-L76】

- **Browse the catalog**: search for a table or file from a previously scanned source.
- Identify an asset with minimal metadata and designate it as a **candidate for curation**.
- Edit the asset and add a meaningful **name and description**.  Answer questions such as:  What business process does this support?  How often is it refreshed?  What is the source system【836156919177758†L60-L76】?
- Assign **contacts** (owner and steward).  Discuss how responsibilities differ between these roles.
- **Link glossary terms** relevant to the asset (e.g., `Customer`, `Sales`).  Add synonyms where necessary.
- Review existing **classifications**; adjust or add custom ones if classification is missing or incorrect.
- Mark the asset as **certified** or **promotion status** if your organisation uses these features.
- Save the changes and demonstrate how the asset appears in search results; note the improved visibility.

## Tips for facilitators

- Remind participants that curation is an ongoing effort; allocate time for teams to review and update their assets regularly.
- Encourage the creation of guidelines for naming, descriptions and ownership so that curated assets follow consistent patterns.
- Point out that curation is necessary for delivering reliable data products; uncurated assets may not meet quality standards.

## References

1. Definition and reasons for federated curation【836156919177758†L16-L35】.
2. Questions to ask when editing assets and curation tasks【836156919177758†L60-L76】.

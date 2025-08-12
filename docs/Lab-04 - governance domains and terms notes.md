# Lab‑04: Governance domains and terms – Speaker notes

## Purpose and goals

- Define and implement **governance domains** that mirror business responsibilities and support a federated operating model【530152535503717†L15-L52】.
- Introduce **domain terms** and **glossary terms**; these provide consistent business definitions across data products【530152535503717†L165-L185】.
- Map domains and terms into the Purview data map to improve search, curation and policy enforcement.

## Governance domains

- A **governance domain** is a cross‑functional grouping of data assets, policies, roles and responsibilities【530152535503717†L15-L52】.
- Domains align with business areas (e.g., `Sales`, `Finance`, `HR`) and may map to platform domains defined in Lab 02.
- Domains should be hierarchical: high‑level domains can contain sub‑domains or collections; this mirrors organisational structure.
- Key facts about domains【530152535503717†L15-L52】:
  - They are the organising units for *data products*, *data owners*, *stewards* and *policies*.
  - Domain leads are accountable for curation and compliance within their domain.
  - Domains promote autonomy while ensuring adherence to enterprise standards.

## Domain terms and enterprise glossary

- **Domain terms** are business concepts specific to a domain (e.g., `Customer`, `Order`).  They provide canonical definitions and synonyms【530152535503717†L165-L185】.
- Terms are stored in the **enterprise glossary** and can be hierarchical; this supports a consistent vocabulary across the organisation.
- Each term may include:
  - **Definition**: a concise description accessible to all stakeholders.
  - **Steward**: the person responsible for maintaining the term.
  - **Synonyms**: alternative names used by different teams.
  - **Related terms**: relationships to other concepts (e.g., `Order` relates to `Invoice`).
- Domain terms can be linked to assets and data products to provide context; they improve search and help data consumers understand meaning【530152535503717†L165-L185】.
- The glossary also contains **policy terms** and **taxonomy terms** that support classification and access policies.

## Mapping to the data map

- Domains and collections are mapped into Purview to support **policy scoping** and **metadata inheritance**.
- Assign domain terms to assets and data products; this fosters consistent definitions and facilitates cross‑domain discovery.
- Use the enterprise glossary view in the Purview portal to manage terms, synonyms and relationships.

## Lab tasks and walkthrough

- **Review existing business domain structure**: identify major functional areas and sub‑domains.
- Create corresponding **governance domains** in Purview; map them to collections where appropriate.
- Build an **enterprise glossary**: add key business terms, assign definitions, synonyms and stewards.
- Link domain terms to data assets: choose a few assets from previous labs and associate them with terms to demonstrate improved search.
- Discuss how domain terms can drive *policy scoping* (e.g., access policies for a term `Confidential Customer Info`).

## Tips for facilitators

- Emphasise the importance of naming conventions and synonyms.  Consistent terms reduce ambiguity and facilitate cross‑team collaboration.
- Encourage domains to maintain their portions of the glossary; stewards should regularly review definitions.
- Remind participants that domains and terms are living artefacts – update them as the business evolves.

## References

1. Definition and key facts of governance domains【530152535503717†L15-L52】.
2. Characteristics and policies of governance domain terms【530152535503717†L165-L185】.

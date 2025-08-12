# Lab‑12: Business continuity and disaster recovery – Speaker notes

## Purpose and goals

- Understand the **business continuity and disaster recovery (BCDR)** capabilities and responsibilities for Microsoft Purview.
- Learn the shared responsibility model, service level agreements and how to implement resilience strategies【785151931933367†L13-L52】.

## Service level agreement and responsibilities【785151931933367†L13-L52】

- Microsoft Purview guarantees a **99.9% uptime SLA**; Microsoft is responsible for the availability of the managed service.【785151931933367†L13-L52】
- Customers are responsible for:
  - **Data backups and restores** of custom metadata (e.g., attachments, manual lineage) if required.
  - **Configuring resilience** in downstream analytics systems that rely on Purview.
  - Managing **identity and access** (e.g., Azure AD, RBAC).

## Backup and restore considerations【785151931933367†L74-L89】

- Purview automatically backs up system metadata; you cannot directly restore at an account level.  However, you can export and re‑import **glossary terms**, **classifications** and **policies** via the REST API.
- Maintain a **snapshot** of critical metadata such as glossary terms and custom classifications; schedule periodic exports using API automation.
- For disaster recovery, create an automation script to **recreate the Purview account** with the same collections, policies and glossary terms.

## BCDR strategies【785151931933367†L13-L52】【785151931933367†L74-L89】

- Adopt a **shared responsibility model**: Microsoft ensures platform availability; customers manage data resilience and security.
- **Deploy Purview in multiple regions** only if compliance mandates cross‑region redundancy; replication is not currently automatic.
- Use **resource locks** to protect the Purview account from accidental deletion.  Configure alerts for deletion attempts.【785151931933367†L74-L89】
- Ensure **break‑glass procedures** are in place for identity management: maintain at least two global administrators and track Azure AD role assignments.
- Document the steps to **recreate classifications, terms and collections** if a region fails; keep the scripts tested and up to date.

## Lab tasks and walkthrough

- Review the SLA and discuss what is covered by Microsoft versus the customer.
- Create a **resource lock** on your Purview account: use the Azure portal to set a read‑only lock and test deletion behaviour.【785151931933367†L74-L89】
- Design a **backup strategy**: write a small script using the Purview REST API to export glossary terms and classifications.
- Document the **recovery plan**: outline the steps to recreate the Purview account, import exported metadata and restore policies.
- Discuss how to integrate Purview BCDR planning with the broader organisational disaster recovery plan.

## Tips for facilitators

- emphasise that although Purview is a managed service, customers must plan for metadata resilience; there is no built‑in point‑in‑time restoration.
- Encourage participants to involve security and infrastructure teams when defining BCDR processes.
- Remind teams to test backup and recovery procedures regularly; theoretical plans may fail in real‑world scenarios.

## References

1. Business continuity responsibilities and SLA【785151931933367†L13-L52】.
2. Steps for resilience and break‑glass strategies【785151931933367†L74-L89】.

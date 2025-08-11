# Lab‑13: Custom API functionality – Speaker notes

## Purpose and goals

- Introduce the **Microsoft Purview REST APIs and SDKs** to extend Purview’s functionality and integrate with external systems【233883290170681†L14-L34】.
- Demonstrate scenarios for consuming Purview events via **Event Hub** and performing custom actions.
- Discuss considerations and best practices for using preview APIs and building custom solutions【233883290170681†L54-L62】.

## Purview APIs overview【233883290170681†L14-L34】

- Purview provides a set of **REST APIs** for managing data catalog objects, scanning, classification, policies and lineage.  These APIs allow programmatic access to create, read, update and delete metadata.
- **Data Map APIs** enable ingestion and retrieval of metadata objects such as assets, glossary terms, classifications and lineage; they use Azure Active Directory authentication.
- **Policy APIs** allow you to create and manage access policies programmatically.
- **Scanning APIs** can trigger scans, monitor status and fetch results; useful for automation scenarios.
- The **Event Hub integration** emits events when certain actions occur (e.g., new asset, classification applied).  An **Azure Function** can subscribe to these events and trigger custom workflows (e.g., send notifications).

## Caution about preview features【233883290170681†L54-L62】

- Some Purview APIs are in **public preview** and may change without notice; use them judiciously in production.
- Always refer to the latest API documentation; ensure your code handles version changes gracefully.
- Avoid building core business processes solely on preview APIs; consider them for non‑critical experiments.

## Scenarios for custom integrations

- **Webhook notifications**: subscribe to Event Hub events; when new assets are registered, automatically create Jira tickets for curation.
- **Custom lineage ingestion**: publish lineage from bespoke ETL pipelines to the Purview Data Map via the REST API.
- **Metadata synchronisation**: integrate Purview with a master data management (MDM) system to keep terms and classifications aligned.
- **Bulk operations**: script the creation of thousands of glossary terms or update classifications across multiple assets.

## Lab tasks and walkthrough

- Review the Purview **API documentation** (via Microsoft Learn) and identify endpoints for assets, glossaries or policies.
- Write a simple **script** (e.g., in PowerShell or Python) to call the Data Map API and retrieve assets from a specific collection.
- Configure an **Event Hub** and **Azure Function** to capture events when new assets are registered; log the event details or send an email.
- Discuss security: ensure the application has appropriate **service principal credentials** and uses **least privilege**.
- Evaluate whether your organisation needs a custom integration; not all scenarios require custom coding.

## Tips for facilitators

- emphasise **design decisions**: before writing code, determine whether built‑in Purview functionality suffices【233883290170681†L54-L62】.
- Encourage participants to start with small proofs of concept; avoid heavy reliance on preview features for critical processes.
- Remind participants to register applications in Azure AD and manage secrets securely.

## References

1. Overview of Purview APIs and event integration【233883290170681†L14-L34】.
2. Considerations when implementing custom integrations【233883290170681†L54-L62】.

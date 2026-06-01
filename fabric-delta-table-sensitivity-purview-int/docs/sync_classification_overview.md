# Sync Purview Classification → Fabric Delta TBLPROPERTY — Overview

This is the **reverse** of [`classify_assets_overview.md`](classify_assets_overview.md).
Where `classify_assets` reads `data-sensitivity` from Fabric Delta tables and
pushes a matching classification to Purview, `sync_classification` does the
opposite: when a Data Governance user **edits a `Sensitivity.*` classification
on a Data Asset in Purview**, the change is propagated back onto the
corresponding Fabric Delta table's `TBLPROPERTIES['data-sensitivity']`.

The forward flow is untouched — both functions live side-by-side in the same
Function App (`func-fabricsens-rh`) and share its identity, networking and
configuration.

## Why this exists

The forward flow established Fabric as the *source of truth* for sensitivity
labels at deploy time. In day-to-day governance, however, the Purview Unified
Catalog is where stewards actually live — and when they correct or refine a
classification there, that correction needs to land back on the Delta table so
that:

- The next Purview scan + forward flow doesn't undo the change.
- Downstream consumers reading TBLPROPERTIES directly (Spark jobs, lineage
  scripts, table-DDL audits) see the same classification the catalog shows.

## Trigger: Bring-Your-Own Atlas Notification Event Hub

Microsoft Purview implements Apache Atlas's two notification topics:

| Atlas topic | Purview "Kafka configuration" type | Direction |
|---|---|---|
| `ATLAS_HOOK` | Hook configuration | External producers → push metadata into Purview |
| `ATLAS_ENTITIES` | **Notification configuration** | **Purview → emits entity & classification change events out** |

Purview supports either a **managed** Event Hubs namespace (provisioned in
Microsoft's subscription) or **bring-your-own** (BYO) — a namespace in the
customer's subscription. The managed option is no longer available on
`governancePurviewRH` (managed EH was disabled and cannot be re-enabled, per
Azure error code 2008), and Microsoft's own docs now recommend BYO regardless
("To keep the Event Hub's supported TLS version updated, we recommend using BYO
Event Hub" —
[Configure Event Hubs for Kafka](https://learn.microsoft.com/en-us/purview/configure-event-hubs-for-kafka)).

This solution therefore reuses the existing `ehns-fabricsens-rh` namespace
(also used by the forward flow for `purview-scan-status` diagnostic logs):

```
ehns-fabricsens-rh (Standard, public-network-enabled)
├── purview-scan-status        ← diagnostic logs       (forward flow)
└── atlas-notifications        ← Atlas ENTITY_NOTIFICATION_V2 (this flow)
```

Wiring is done declaratively in Terraform via
`Microsoft.Purview/accounts/kafkaConfigurations@2021-12-01`
(`azapi_resource.purview_atlas_notification_config`), with
`eventHubType = "Notification"` and `credentials.type = "SystemAssigned"`.
Purview's system-assigned managed identity authenticates to the namespace; it
needs **Contributor** at namespace scope so it can configure the hub on its
end (granted via `azurerm_role_assignment.purview_eh_contributor`).

The Function MI's existing `Azure Event Hubs Data Receiver` assignment is
namespace-scoped (`azurerm_role_assignment.func_eh_receiver`), so it
automatically covers the new hub — no extra RBAC on the function side.

## The numbered flow

The diagram below maps 1-to-1 onto `sync_classification_impl` in
`iac/function/sync_classification/handler.py`.

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. User edits Sensitivity.* classification on a Data Asset in Purview UI   │
│ 2. Purview catalog (Atlas backend) writes the change                       │
│ 3. Purview emits ENTITY_NOTIFICATION_V2 to                                 │
│    ehns-fabricsens-rh / atlas-notifications                                │
│ 4. Function `sync_classification` fires (EH trigger, cardinality=many)     │
│ 5. Filter: keep only events whose entity.attributes.qualifiedName contains │
│    BOTH SOURCE_WORKSPACE_ID and SOURCE_LAKEHOUSE_ID, AND whose             │
│    operationType is in {ENTITY_CREATE, ENTITY_UPDATE, CLASSIFICATION_ADD,  │
│    CLASSIFICATION_UPDATE, CLASSIFICATION_DELETE}                           │
│ 6. De-duplicate by entity GUID within the batch                            │
│ 7. Re-GET each entity from Purview Atlas (source of truth — event          │
│    payload may be out-of-order)                                            │
│ 8. Resolve the desired data-sensitivity value                              │
│      - 1 Sensitivity.* classification → use it                             │
│      - >1 → log warning, pick highest severity                             │
│        (HighlyConfidential > Confidential > General > Public)              │
│      - 0 → use DELETED_SENSITIVITY_VALUE (default "None")                  │
│ 9. Open the Delta table, read current TBLPROPERTY                          │
│      - Equal to target → no-op, increment skipped_already_in_sync          │
│        (this is the loop-avoidance guard against the forward flow)         │
│      - Different → call DeltaTable.alter.set_table_properties(...)         │
│        Retry once on CommitFailedError (Delta optimistic concurrency).     │
│ 10. Log RESYNC_SUMMARY with counters                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

## Loop avoidance

Both functions watch state that the other writes, so each side needs an
idempotency guard to prevent infinite ping-pong:

| Side | Guard |
|---|---|
| Forward (`classify_assets`) | The Atlas classify call is idempotent on `typeName` — a re-application of the same `Sensitivity.*` to an already-classified entity returns 400 "already associated" and is treated as a no-op. Additionally, an unknown sensitivity value (including the literal `"None"` written by this flow on classification delete) falls into `LEVEL_MAP.get(...)` → `None` → `skipped_no_property`, so the forward flow never tries to POST `Sensitivity.None`. Regression-tested in `tests/test_classify_assets.py`. |
| Reverse (`sync_classification`) | Before writing, the function reads `dt.metadata().configuration['data-sensitivity']` and compares (case- and whitespace-insensitively) against the target. If equal, the deltalake write is skipped entirely. |

The result is that a sequence like (forward applies `Sensitivity.General`)
→ (reverse fires on `CLASSIFICATION_ADD`) settles in one round-trip: the
TBLPROPERTY already equals `"general"`, so the reverse flow no-ops.

## Multiple classifications on one entity

Purview allows multiple classifications per entity. A user could attach both
`Sensitivity.General` and `Sensitivity.Confidential`. The flow handles this
via a **last-write-wins with highest-severity tiebreaker**:

- Severity order is configurable via app setting
  `SENSITIVITY_SEVERITY_ORDER_JSON`
  (default `["HighlyConfidential","Confidential","General","Public"]`,
  highest first).
- When more than one `Sensitivity.*` classification is present, a warning is
  logged listing all of them, and the highest-severity one wins.

## Classification removal

When all `Sensitivity.*` classifications are removed from an entity in
Purview, the function writes the literal string from app setting
`DELETED_SENSITIVITY_VALUE` (default `"None"`) into the TBLPROPERTY. The next
forward scan will see this value, fail to map it to any known sensitivity
level, and skip — preserving the user's intent that the table currently has
*no* sensitivity classification.

## Components

### Azure (new resources)

- **`atlas-notifications` Event Hub** (`azurerm_eventhub.atlas_notifications`)
  — 4 partitions (matches Atlas's default for `ATLAS_ENTITIES`), 1-day
  retention. Lives inside the existing `ehns-fabricsens-rh` namespace.
- **Purview MI → Contributor on `ehns-fabricsens-rh`**
  (`azurerm_role_assignment.purview_eh_contributor`) — required by the
  Purview docs so Purview can configure the hub on its side.
- **Purview Notification Kafka configuration**
  (`azapi_resource.purview_atlas_notification_config`) — the actual wiring
  that tells Purview "send ATLAS_ENTITIES events here". Only one Notification
  configuration is allowed per Purview account.

### Function (new code)

- **`sync_classification/handler.py`** — all business logic. Reuses the same
  `DefaultAzureCredential` + retrying `requests.Session` patterns as
  `classify_assets/handler.py`.
- **`function_app.py`** — adds a second `@app.event_hub_message_trigger`
  decorator on the same `FunctionApp`. The connection name `PurviewEvents` is
  reused from the forward flow (same namespace, same auth), only the
  `event_hub_name='atlas-notifications'` differs.

### App settings (new)

| Name | Default | Purpose |
|---|---|---|
| `ATLAS_NOTIFICATION_EVENT_HUB` | `atlas-notifications` | Name of the BYO Notification hub (kept in sync with Terraform). |
| `SENSITIVITY_SEVERITY_ORDER_JSON` | `["HighlyConfidential","Confidential","General","Public"]` | Tiebreaker order when multiple `Sensitivity.*` classifications are present. |
| `DELETED_SENSITIVITY_VALUE` | `"None"` | TBLPROPERTY value written when all `Sensitivity.*` classifications are removed in Purview. |

### App settings (reused — no change)

`SOURCE_WORKSPACE_ID`, `SOURCE_LAKEHOUSE_ID`, `SOURCE_LAKEHOUSE_NAME`,
`PURVIEW_ACCOUNT`, `PURVIEW_ENDPOINT`, `CLASSIFICATION_NAMESPACE`,
`SENSITIVITY_LEVEL_MAP_JSON`, `PurviewEvents__fullyQualifiedNamespace`,
`PurviewEvents__credential`.

## How a single end-to-end cycle plays out

1. In Purview UI: open the `appointments` Lakehouse Table asset → Classifications
   → change `Sensitivity.General` → `Sensitivity.Confidential` → Save.
2. Purview catalog writes the change; an `ENTITY_NOTIFICATION_V2` event with
   `operationType: CLASSIFICATION_UPDATE` lands on `atlas-notifications`.
3. The function's EH listener picks it up. Filter passes (qualifiedName
   contains the configured workspace + lakehouse IDs; op type is in-scope).
4. Re-GET entity from Purview Atlas — confirms exactly one `Sensitivity.*`
   classification: `Sensitivity.Confidential`.
5. Inverse-map lookup: `Confidential` → `"confidential"`.
6. Open the Delta table, read current `data-sensitivity` = `"general"`.
   Not equal → proceed.
7. `dt.alter.set_table_properties({"data-sensitivity": "confidential"})`.
8. `RESYNC_SUMMARY {"total": 1, "in_scope": 1, "updated": 1, ...}` lands in
   App Insights.
9. Next `DESCRIBE EXTENDED appointments` in Fabric shows
   `data-sensitivity=confidential` under Table Properties.

## Notes & operational gotchas

- **Cardinality of `ATLAS_ENTITIES`**: this topic carries **every** entity
  change in the Purview account, not just Sensitivity ones. The
  qualifiedName + operationType filter must run cheaply and *before* any
  Purview/OneLake call — and it does (one-liner string check + set membership).
- **Only one Notification configuration is allowed per Purview account.** If a
  second flow ever needs to listen to Atlas notifications, it must share this
  hub (using a different consumer group) rather than creating a second
  Notification configuration.
- **Function deploy**: same `null_resource.function_deploy` path as today.
  No changes to deployment or CI/CD.
- **Network hardening (future)**: today `ehns-fabricsens-rh` is on the public
  network. To restrict it, set `defaultAction = Deny` on the namespace and
  enable "Allow trusted Microsoft services" — Purview is on the trusted-services
  list. The function-side EH trigger is already MI-based, so no SAS keys are
  in play.

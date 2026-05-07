# fabric-delta-table-sensitivity-purview-int

End-to-end Terraform deployment that:

1. Provisions a **Fabric lakehouse** (`sensitivity_metadata_lh`) and a **notebook** (`create_sensitivity_tables`) in the existing `sensitivity-metadata-ws` workspace, then runs the notebook once to seed 4 fake-healthcare Delta tables (`patients`, `claims`, `appointments`, `providers`), each tagged with a `data-sensitivity` TBLPROPERTY.
2. Registers 4 custom **classification typedefs** in an existing **Microsoft Purview** account (`governancePurviewRH`).
3. Deploys an **Azure Function** (Flex Consumption, Python 3.11) that, on a 15-minute timer, reads the `data-sensitivity` TBLPROPERTY off each Delta table, finds the corresponding Purview asset, and applies the matching classification.

The whole thing is one Terraform root module — no submodules, no workspaces.

---

## Architecture

```
                        ┌──────────────────────────────────────────────────┐
                        │              Fabric workspace                    │
                        │           sensitivity-metadata-ws                │
                        │                                                  │
       ┌────────────────┼─►  fabric_lakehouse.this                         │
       │                │     (sensitivity_metadata_lh)                    │
       │                │      └─ Tables/  ◄─── populated by notebook ──┐  │
       │                │           ├─ patients                          │  │
       │                │           ├─ claims                            │  │
       │                │           ├─ appointments                      │  │
       │                │           └─ providers                         │  │
       │                │                                                │  │
       │                │     fabric_notebook.this  ──────────────────────┘  │
       │                │     (create_sensitivity_tables.ipynb)            │
       │                │       ▲                                          │
       │                │       │ on-demand POST /jobs/instances           │
       │                │       │   (null_resource.run_notebook_once)      │
       │                └───────┼──────────────────────────────────────────┘
       │                        │
       │                        │
       │   ┌────────────────────┴────────────────────────┐
       │   │   azurerm_function_app_flex_consumption.func│
       │   │   (func-fabricsens-rh, Python 3.11, FC1)    │
       │   │                                             │
       │   │   classify_assets/__init__.py               │  reads OneLake Delta logs
       │   │     timerTrigger: "0 */15 * * * *"  ────────┼──► abfss://{ws}@onelake…/{lh}/Tables/<t>
       │   │     • DefaultAzureCredential (System MI)   │
       │   │     • DeltaTable(...)→ data-sensitivity     │
       │   │     • Purview Atlas API: search + classify │
       │   └──────────────────┬──────────────────────────┘
       │                      │
       │     supporting infra │
       │      ─ azurerm_service_plan.func          (FC1)
       │      ─ azurerm_storage_account.func       (deployment package + state)
       │      ─ azurerm_storage_container.deployments
       │      ─ azurerm_storage_blob.function_zip  (function.zip from data.archive_file)
       │      ─ azurerm_log_analytics_workspace.func
       │      ─ azurerm_application_insights.func
       │      ─ azurerm_role_assignment.func_storage   (MI → "Storage Blob Data Owner" on its own SA)
       │      ─ fabric_workspace_role_assignment.func_workspace_viewer
       │                                          (MI → "Viewer" on the Fabric workspace)
       │                      │
       │                      ▼
       │     ┌─────────────────────────────────────────────────────────────┐
       │     │      Microsoft Purview account: governancePurviewRH         │
       └────►│                                                             │
             │   restapi_object.classification[*]   (4 typedefs)           │
             │       ─ Sensitivity.Public            #15803D  (green)      │
             │       ─ Sensitivity.General           #0369A1  (blue)       │
             │       ─ Sensitivity.Confidential      #D97706  (amber)      │
             │       ─ Sensitivity.HighlyConfidential #B91C1C (red)        │
             │                                                             │
             │   Function MI must have "Data Curator" on the collection    │
             │   that contains the Fabric source (granted MANUALLY)        │
             └─────────────────────────────────────────────────────────────┘
```

---

## What gets deployed (resource-by-resource)

### Phase 1 — Fabric (file: `main.tf`)

| Resource | Purpose |
|---|---|
| `fabric_lakehouse.this` | The lakehouse `sensitivity_metadata_lh`. Holds the 4 Delta tables. |
| `fabric_notebook.this` | Notebook `create_sensitivity_tables` (uploaded from `notebook/create_sensitivity_tables.ipynb`). Tokens (`workspace_id`, `lakehouse_id`, `lakehouse_name`) are substituted into the notebook content at upload time. |
| `null_resource.run_notebook_once` | Invokes `POST /v1/workspaces/{ws}/items/{notebook}/jobs/instances?jobType=RunNotebook` via `pwsh` + `az` to populate the lakehouse on first apply. **Has `lifecycle.ignore_changes = [triggers]`** so notebook edits never auto-rerun the populate (defense-in-depth against data loss). To force a rerun: `terraform taint null_resource.run_notebook_once && terraform apply`. |

**The notebook itself is also idempotent.** Each table write is guarded by `if spark.catalog.tableExists(name): continue` and uses `mode('errorifexists')`, so even if the populate is re-fired it cannot overwrite existing data.

### Phase 2 — Function infra (file: `phase2_function.tf`)

| Resource | Purpose |
|---|---|
| `azurerm_storage_account.func` (`stfabricsensrh`) | Holds the function deployment zip + Flex Consumption runtime state. Public network access (Function MI auth, no PE). |
| `azurerm_storage_container.deployments` | Container for the deployment package blob. |
| `azurerm_log_analytics_workspace.func` (`law-func-fabricsens-rh`) | LA workspace for App Insights data. 30-day retention. |
| `azurerm_application_insights.func` (`appi-func-fabricsens-rh`) | Workspace-based App Insights for the function. |
| `azurerm_service_plan.func` (`asp-func-fabricsens-rh`) | Linux **FC1** (Flex Consumption) plan. |
| `data.archive_file.function_zip` | Builds `function.zip` from `function/` (excludes `__pycache__`, `.python_packages`, `local.settings.json`). Output SHA256 is folded into the blob name so a code change forces a redeploy. |
| `azurerm_storage_blob.function_zip` | The deployment package (`function-<sha256>.zip`) in the deployments container. |
| `azurerm_function_app_flex_consumption.func` (`func-fabricsens-rh`) | Python 3.11, max 40 instances × 2 GB. System-assigned MI. Pulls package via `WEBSITE_RUN_FROM_PACKAGE` using its MI (`storage_authentication_type = "SystemAssignedIdentity"`). |
| `azurerm_role_assignment.func_storage` | Function MI → **Storage Blob Data Owner** on its own storage account (Flex Consumption needs MI to fetch the package). |
| `fabric_workspace_role_assignment.func_workspace_viewer` | Function MI → **Viewer** on the Fabric workspace (lets the function read OneLake Delta logs via `https://storage.azure.com` token). |

**Function app settings** wired by Terraform:

| Setting | Source / Value |
|---|---|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection string |
| `SOURCE_WORKSPACE_ID` | `var.workspace_id` (`a9574816-…`) |
| `SOURCE_LAKEHOUSE_ID` | `fabric_lakehouse.this.id` |
| `SOURCE_LAKEHOUSE_NAME` | `var.lakehouse_name` (`sensitivity_metadata_lh`) |
| `PURVIEW_ACCOUNT` | `var.purview_account_name` (`governancePurviewRH`) |
| `CLASSIFICATION_NAMESPACE` | `Sensitivity` |
| `SENSITIVITY_LEVEL_MAP_JSON` | JSON map from TBLPROPERTY value → typedef suffix |
| `WEBSITE_RUN_FROM_PACKAGE` | URL of the zip blob |

### Phase 2 — Purview classifications (file: `phase2_classifications.tf`)

| Resource | Purpose |
|---|---|
| `restapi_object.classification["public"]` | POST `/catalog/api/atlas/v2/types/typedefs` creating `Sensitivity.Public` (green) |
| `restapi_object.classification["general"]` | `Sensitivity.General` (blue) |
| `restapi_object.classification["confidential"]` | `Sensitivity.Confidential` (amber) |
| `restapi_object.classification["highly confidential"]` | `Sensitivity.HighlyConfidential` (red) |

Each typedef is its own Terraform resource so drift can be detected per-typedef.

### Function code (file: `function/classify_assets/__init__.py`)

Timer-triggered (`0 */15 * * * *` — every 15 min). Per run:

1. **List tables** — `GET https://onelake.dfs.fabric.microsoft.com/{ws}?directory={lh}/Tables&recursive=false&resource=filesystem` (System MI bearer token for `https://storage.azure.com`).
2. **Read sensitivity** — for each table, open `abfss://{ws}@onelake.dfs.fabric.microsoft.com/{lh}/Tables/{t}` with `deltalake`'s `DeltaTable`, pull `metadata().configuration['data-sensitivity']`.
3. **Map to typedef** — `level (lowercased) → typedef suffix → "Sensitivity.<Suffix>"`.
4. **Find Atlas entity** — `POST /datamap/api/search/query?api-version=2023-09-01` filtered to `objectType=Tables`, `assetType=Fabric Lakehouse`, keyword=table name; falls back to the older `catalog/api/search/query` if 404. Picks the first hit whose `qualifiedName` contains the lakehouse ID.
5. **Apply classification** — `POST /catalog/api/atlas/v2/entity/guid/{guid}/classifications`; on 409, switches to `PUT` (idempotent update).
6. **Logs** a `CLASSIFY_SUMMARY {…}` line to App Insights with counts (`total`, `classified`, `skipped_no_property`, `skipped_no_entity`, `errors`).

### Providers (files: `providers.tf`, `phase2_providers.tf`, `versions.tf`)

| Provider | Source / version | Auth |
|---|---|---|
| `microsoft/fabric` | `~> 1.9` | `use_cli = true` (Azure CLI session) |
| `hashicorp/azurerm` | `~> 4.16` | `use_cli` (default) — also reads `var.subscription_id` |
| `Azure/azapi` | `~> 2.1` | `use_cli = true` |
| `Mastercard/restapi` | `~> 2.0` | Bearer token from `data.external.purview_token` (calls `az account get-access-token --resource https://purview.azure.net`) |
| `hashicorp/null` / `archive` / `external` | utility | – |

Backend: `azurerm`, state in `terraformsaeheus2/tf-state-container/fabric-delta-table-sensitivity-purview-int.tfstate` (RG `terraform-rg`).

---

## Variables (defaults shown — override in `terraform.tfvars` if needed)

| Variable | Default | Notes |
|---|---|---|
| `subscription_id` | `910ebf13-1058-405d-b6cf-eda03e5288d1` | All Azure-side resources land here. |
| `workspace_id` | `a9574816-83cc-4629-b086-356e14c495c7` | Existing Fabric workspace `sensitivity-metadata-ws`. |
| `lakehouse_name` | `sensitivity_metadata_lh` | Lakehouse display name. |
| `notebook_display_name` | `create_sensitivity_tables` | Notebook display name. |
| `phase2_resource_group` | `governance-rg` | Holds Purview + Function. |
| `phase2_location` | `westus` | Region for Function/Storage/AI. |
| `purview_account_name` | `governancePurviewRH` | Existing Purview account. |
| `purview_collection_id` | `bhhlid` | Where the Function MI must be granted Data Curator (manual step). |
| `function_app_name` | `func-fabricsens-rh` | Globally unique. |
| `function_storage_account_name` | `stfabricsensrh` | Globally unique. |
| `classification_namespace` | `Sensitivity` | Typedef name prefix. |
| `sensitivity_levels` | `{"highly confidential":"HighlyConfidential", "confidential":"Confidential", "general":"General", "public":"Public"}` | TBLPROPERTY → typedef-suffix map. |

---

## Outputs

`lakehouse_id`, `lakehouse_properties`, `notebook_id`, `notebook_run_trigger_id`, `function_app_name`, `function_app_principal_id`, `function_app_url`, `purview_account_id`, `purview_atlas_endpoint`, `classification_typedef_names`.

---

## Prerequisites

- **Azure CLI** logged in to the target subscription (`az login`); the user/SP must have:
  - Contributor or equivalent on `governance-rg` (for Storage / Function / App Insights / LAW / role assignments).
  - Permission to create role assignments on the storage account (Owner / RBAC Admin).
  - Workspace Admin (or Member with item-create rights) on `sensitivity-metadata-ws`, plus the Fabric tenant settings that allow service principals / users to use the Fabric APIs.
  - Data plane access on the Purview account (`Data Source Administrator` or higher).
- **Fabric capacity** backing the workspace must be **running** (the provider cannot resume a paused capacity — provisioning will 503 with `CapacityNotActive` if it's paused). This module's workspace is on capacity `uswest3capacity` (resource group `fabric-rg`).
- **Terraform** ≥ 1.8.
- **PowerShell 7+** (`pwsh`) on PATH — used by:
  - `data.external.purview_token` (mints a Purview data-plane token).
  - `null_resource.run_notebook_once` (calls Fabric REST to fire the notebook).

---

## Deployment

```powershell
cd fabric-delta-table-sensitivity-purview-int/iac

terraform init

# Recommend serializing — Purview's public Atlas endpoint is EOF-prone under
# concurrent load.
terraform plan -parallelism=1 -out tfplan
terraform apply -parallelism=1 tfplan
```

### Manual post-deploy step (one-time)

The Function's managed identity needs **Data Curator** on the Purview collection that contains the Fabric source. There is no clean Terraform resource for this (the `metadataRoles` REST surface is inconsistent across Purview versions), so grant it manually:

> Purview portal → Data Map → Collections → *(collection containing the Fabric lakehouse source)* → Role assignments → Data curators → Add → select `func-fabricsens-rh`.

Without this, classification POSTs from the Function will return 403.

### Verifying the deployment

```powershell
terraform output

# Lakehouse + notebook
az resource show --ids /subscriptions/.../providers/Microsoft.Web/sites/func-fabricsens-rh -o table

# Tables (in a Spark notebook in the workspace):
#   DESCRIBE EXTENDED sensitivity_metadata_lh.patients;
# → "Table Properties" row should include data-sensitivity=Highly Confidential

# Typedefs:
$t = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
"Sensitivity.Public","Sensitivity.General","Sensitivity.Confidential","Sensitivity.HighlyConfidential" |
  ForEach-Object {
    Invoke-RestMethod -Uri "https://governancePurviewRH.purview.azure.com/catalog/api/atlas/v2/types/typedef/name/$_" `
      -Headers @{Authorization="Bearer $t"} | Select-Object name, category
  }

# Function logs (App Insights / LAW):
#   traces | where message startswith "CLASSIFY_SUMMARY"
```

---

## Operational notes & gotchas

- **Use `-parallelism=1`** for plan and apply. Purview's public Atlas endpoint is intermittently flaky (returns `EOF` / `SSL handshake` failures under concurrent calls). With concurrency, multiple typedefs hit the API simultaneously and most fail; the failures sometimes complete *server-side* anyway, leaving state out of sync. Even with parallelism=1 you may need to retry a typedef create a few times — the saved provider responses are flaky enough that 1-3 retries per typedef is normal.
- **Don't move Purview behind a private endpoint** unless you also wire the Function VNet + DNS for it. The restapi/atlas calls in this module assume the public endpoint.
- **Notebook populate is locked.** `null_resource.run_notebook_once` has `lifecycle.ignore_changes = [triggers]`, so editing the notebook content does *not* auto-rerun it. To intentionally re-populate: `terraform taint null_resource.run_notebook_once && terraform apply`. The notebook is also idempotent (`tableExists` + `errorifexists`), so even an unintended rerun won't clobber existing data.
- **Lakehouse "deleted outside Terraform" warning** can be a false positive caused by a paused Fabric capacity — when the capacity is paused, Fabric API calls return `CapacityNotActive` which the provider sometimes treats as 404. Resume the capacity, then `terraform import fabric_lakehouse.this <workspace_id>/<lakehouse_id>` to put it back in state.
- **Function code redeploy.** Edit anything under `function/`, run `terraform apply`. The blob name is `function-<sha256>.zip`, so a content change creates a new blob and updates `WEBSITE_RUN_FROM_PACKAGE`; the function picks it up on its next instance start.
- **Drift on typedef refresh.** `terraform plan` may sometimes show the 4 typedefs as "to add" even after a successful apply — this is the restapi provider misinterpreting an EOF on the refresh-read as "resource missing". The typedefs *are* in state (`terraform state list` to confirm) and *do* exist server-side. If a re-apply is unavoidable, delete the affected typedefs server-side first (`DELETE /catalog/api/atlas/v2/types/typedef/name/<name>`) so the recreate doesn't 409.
- **Provider deviation.** The `microsoft/fabric` provider (1.9.x) has no on-demand notebook-job-instance resource; only `fabric_item_job_scheduler` (recurring schedules). The "run once on apply" requirement is therefore implemented with `null_resource` + `local-exec` calling the Fabric REST API.

---

## File map

| File | Contents |
|---|---|
| `main.tf` | Phase 1: lakehouse, notebook, on-demand runner. |
| `variables.tf` | Phase 1 variables. |
| `outputs.tf` | Phase 1 outputs. |
| `providers.tf` | Fabric provider. |
| `versions.tf` | Required versions + `azurerm` backend config. |
| `phase2_function.tf` | Phase 2: Storage, LAW, App Insights, Service Plan, archive_file, blob, Function App, role assignments. |
| `phase2_classifications.tf` | Phase 2: 4 Purview classification typedefs (`restapi_object`). |
| `phase2_providers.tf` | Phase 2: `azurerm`, `azapi`, Purview-token data source, `restapi` provider. |
| `phase2_variables.tf` | Phase 2 variables. |
| `phase2_outputs.tf` | Phase 2 outputs. |
| `notebook/create_sensitivity_tables.ipynb` | Notebook source — generates 4 fake-healthcare Delta tables and tags each with `data-sensitivity`. Idempotent. |
| `function/classify_assets/__init__.py` | Timer-triggered classify-assets function. |
| `function/classify_assets/function.json` | Timer binding (every 15 min). |
| `function/host.json` | Functions host config. |
| `function/requirements.txt` | `azure-functions`, `azure-identity`, `deltalake`, `requests`. |
| `terraform.tfvars.example` | Sample `tfvars` (all variables have working defaults — override only as needed). |

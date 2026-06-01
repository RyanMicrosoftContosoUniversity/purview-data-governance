# CI/CD pipeline — Purview sensitivity functions

Covers both `classify_assets` (Fabric → Purview) and `sync_classification`
(Purview → Fabric) — they live in the same Function App and are deployed
together.

Azure DevOps pipeline definition: [`fabric-purview-functions-pipeline.yml`](../.cicd/fabric-purview-functions-pipeline.yml).

## What it does

| Stage | Trigger | Purpose |
|-------|---------|---------|
| **Validate** | PR + main | Ruff format check (`classify_assets/`, `sync_classification/`, `shared_utils/`, `function_app.py`) + pytest unit tests |
| **ValidateIaC** | PR + main | `terraform fmt -check -recursive` + `terraform init -backend=false` + `terraform validate` on `iac/` (no Azure credentials needed; runs in parallel with Validate) |
| **Package** | PR + main | Install prod deps into `.python_packages/lib/site-packages`, zip the function |
| **Deploy** | main only | `az functionapp deployment source config-zip` to `func-fabricsens-rh` (Flex Consumption) |
| **Verify** | main only | `az functionapp function list` to confirm both `classify_assets` and `sync_classification` are indexed |
| **IntegrationTestE2E** | manual opt-in only (`runIntegrationTests=true`) | Triggers a real Purview scan against the Fabric data source + waits for the function to attach a `Sensitivity.Public` classification to a fixture table. Default OFF. ~5-10 min. See [`tests/integration/README.md`](../tests/integration/README.md). |

Triggered only by changes under `fabric-delta-table-sensitivity-purview-int/src/function/**` so unrelated repo edits don't fire it.

## One-time ADO setup

1. **Create the pipeline** in Azure DevOps (`Contoso-University` org), pointing at this YAML file.
2. **Create a service connection** named `sc-purview-data-governance-dev` with contributor on subscription `910ebf13-1058-405d-b6cf-eda03e5288d1` (or scoped to `governance-rg`).
3. **Create a variable group** named `purview-data-governance-dev` containing:

   | Name | Value | Required for |
   |------|-------|--------------|
   | `AZURE_SUBSCRIPTION_ID` | `910ebf13-1058-405d-b6cf-eda03e5288d1` | All stages |
   | `RESOURCE_GROUP_NAME` | `governance-rg` | Deploy + Verify |
   | `FUNCTION_APP_NAME` | `func-fabricsens-rh` | Deploy + Verify |
   | `PURVIEW_ACCOUNT` | `governancePurviewRH` | IntegrationTestE2E only |
   | `PURVIEW_RESOURCE_GROUP` | `governance-rg` | IntegrationTestE2E only |
   | `PURVIEW_DATA_SOURCE_NAME` | `Fabric` | IntegrationTestE2E only |
   | `PURVIEW_SCAN_NAME` | `integration-test-scan` | IntegrationTestE2E only |
   | `PURVIEW_COLLECTION_ID` | `bhhlid` | IntegrationTestE2E only |
   | `SOURCE_WORKSPACE_ID` | `a9574816-83cc-4629-b086-356e14c495c7` | IntegrationTestE2E only |
   | `SOURCE_LAKEHOUSE_ID` | (Fabric lakehouse GUID — see Fabric portal → workspace → lakehouse → Settings → SQL endpoint or copy from URL) | IntegrationTestE2E only |
   | `SOURCE_LAKEHOUSE_NAME` | `sensitivity_metadata_lh` | IntegrationTestE2E only |

   The `PURVIEW_*` / `SOURCE_*` variables are only consumed when
   `runIntegrationTests=true`. You can omit them initially and add them
   later when you're ready to enable E2E tests.

4. **Create an environment** named `purview-data-governance-dev` (add approvals here if you want them).

## What it does NOT do

- Does **not** run `terraform apply` or `terraform plan`. Infra changes in `iac/` still go through `terraform plan/apply` locally — the pipeline only catches *static* IaC errors (format, syntax, references) via `terraform validate`. Running `plan`/`apply` would require an Azure service connection with broad permissions and is deferred to a separate infra-only pipeline if/when needed.
- Does **not** create or rotate app settings — those are owned by Terraform (`iac/function_app.tf`).
- Does **not** run E2E integration tests by default. They cost 5-10 min per run + trigger real Purview scans. Toggle with the `runIntegrationTests` queue-time parameter when you want them.

## E2E integration tests

The `IntegrationTestE2E` stage covers the wiring that unit tests cannot:
Purview → diag setting → Event Hub → Function MI auth → Atlas classification.

**Prerequisites** (one-time grants on the service connection's SP):

- **Data Source Administrator** on Purview collection `bhhlid` (grant via Purview portal → Data Map → Domains → click collection → Role assignments)
- **Contributor** on Fabric workspace `sensitivity-metadata-ws` (grant via Fabric portal → workspace → Manage access)

See [`tests/integration/README.md`](../tests/integration/README.md) for the full setup checklist, troubleshooting, and how to run the same test locally.

## Local equivalent

```powershell
cd fabric-delta-table-sensitivity-purview-int
pip install -r src/function/requirements-dev.txt
python -m pytest tests/ -x --tb=short

# E2E integration tests — see tests/integration/README.md for the full env setup
$env:RUN_INTEGRATION_TESTS = "1"  # ...plus PURVIEW_*, SOURCE_*, AZURE_SUBSCRIPTION_ID
python -m pytest tests/integration/ -v -s --tb=short

# then deploy via terraform apply (which runs az functionapp deployment source config-zip)
```

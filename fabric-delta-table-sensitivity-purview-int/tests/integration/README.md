# Integration tests — Purview scan → Function → classification (E2E)

These tests trigger a **real Purview scan** against the Fabric data source and
assert that the function pipeline attaches a `Sensitivity.*` classification to
the scanned table. They cover the wiring that unit tests cannot:

- Purview → diag setting → Event Hub delivery
- Function App MI auth to Event Hub (scale controller + listener)
- `app_settings` drift between Terraform and the live app
- Atlas API call against the real Purview account
- OneLake read access from the function MI

**Cost:** ~5-10 minutes per run (the scan + ingestion is the long pole).
**Default in CI:** off. Toggle the `runIntegrationTests` pipeline parameter
to enable. See [docs/CICD.md](../../docs/CICD.md).

---

## One-time setup (Azure / Purview side)

1. **Fabric data source registered in Purview** — name: `Fabric`.
   (Already in place per repo convention.)

2. **Scan configured in Purview** — name: `integration-test-scan`, scoped to
   workspace `sensitivity-metadata-ws`. (Already in place.)

3. **Role grants** (the SP behind `sc-purview-data-governance-dev`, or your
   user when running locally):

   | Role | Scope | How to grant |
   |------|-------|--------------|
   | **Data Source Administrator** | Purview collection `bhhlid` | Purview portal → Data Map → Domains → click collection → Role assignments → Data source administrators → Add |
   | **Contributor** | Fabric workspace `sensitivity-metadata-ws` | Fabric portal → workspace → Manage access → Add → role: Contributor |

   These are *separate* from the Function MI's grants. The test identity
   writes the fixture table itself and triggers the scan itself.

4. **Function App deployed and healthy** — verified by the `Verify` stage
   that runs before integration tests.

---

## Run locally

```powershell
cd C:\Users\rharrington\repos\purview-data-governance\fabric-delta-table-sensitivity-purview-int

# Ensure you're signed in to the right tenant/subscription
az login --tenant 35acf02c-4b87-4ae6-9221-ff5cafd430b4
az account set --subscription 910ebf13-1058-405d-b6cf-eda03e5288d1

# Install dev deps
pip install -r src/function/requirements-dev.txt

# Configure the integration env
$env:RUN_INTEGRATION_TESTS = "1"
$env:AZURE_SUBSCRIPTION_ID = "910ebf13-1058-405d-b6cf-eda03e5288d1"
$env:PURVIEW_ACCOUNT = "governancePurviewRH"
$env:PURVIEW_RESOURCE_GROUP = "governance-rg"
$env:PURVIEW_DATA_SOURCE_NAME = "Fabric"
$env:PURVIEW_SCAN_NAME = "integration-test-scan"
$env:PURVIEW_COLLECTION_ID = "bhhlid"
$env:SOURCE_WORKSPACE_ID = "a9574816-83cc-4629-b086-356e14c495c7"
$env:SOURCE_LAKEHOUSE_NAME = "sensitivity_metadata_lh"

# Run
python -m pytest tests/integration/ -v -s --tb=short
```

Tunable timeouts (defaults shown):

| Var | Default | Purpose |
|---|---|---|
| `SCAN_TIMEOUT_S` | 900 | How long to wait for the scan run to reach a terminal status |
| `CLASSIFICATION_TIMEOUT_S` | 600 | How long to wait for the function to attach the classification after the scan succeeds |
| `POLL_INTERVAL_S` | 15 | Poll cadence for both waits |
| `INTEGRATION_FIXTURE_TABLE` | `integration_test_fixture` | Name of the test table created in the lakehouse |

---

## What the test does, step by step

1. **Ensure** Delta table `integration_test_fixture` exists in the lakehouse
   with TBLPROPERTY `data-sensitivity='public'`. Idempotent: creates if missing,
   rewrites the property if wrong.
2. **Pre-clean** any stale `Sensitivity.*` classification on the fixture
   table's entity so we can prove the *current* scan ran.
3. **POST** to the Purview scanning API: `POST /scan/datasources/Fabric/scans/integration-test-scan:run?runId={new-guid}`
4. **Poll** `runs/{runId}` until status is `Succeeded` or `PartialSucceeded` (≤ 15 min).
5. **Poll** Atlas: `GET /datamap/api/atlas/v2/entity/guid/{guid}` for the
   fixture table's entity, looking for `Sensitivity.Public` in its
   `classifications` (≤ 10 min). This covers the diag-setting + EH delivery
   + function execution + Atlas POST round trip.
6. **Assert** `Sensitivity.Public` is present.
7. **Best-effort cleanup** — remove the `Sensitivity.Public` classification
   so the next run starts clean. Cleanup failures don't fail the test.

The fixture table is **left in place** between runs (it's empty, costs
nothing, and reusing it shaves ~60s off subsequent runs).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403` on `POST scan:run` | Test identity lacks Data Source Administrator | Grant role per setup step 3 |
| `Scan run did not complete within 900s` (status `Queued`) | Purview scan service backlog | Re-run, or raise `SCAN_TIMEOUT_S` |
| Scan finishes `Succeeded` but assertion fails on classification | EH→function pipeline broken — check App Insights for `classify_assets` traces around the scan completion time | If no invocation, check `PurviewEvents__credential=managedidentity` is still set; if invocation but error, check whichever exception was logged |
| `Cannot find Atlas entity` even after scan succeeded | Scan didn't actually index `Tables/` (often a permissions or scope issue) | Check Purview UI → scan run → ingestion stats; ensure scan scope includes the test lakehouse |
| Fixture table create fails with `403` | Test identity lacks Contributor on Fabric workspace | Grant role per setup step 3 |

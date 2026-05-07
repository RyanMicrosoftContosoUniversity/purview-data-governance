# CI/CD pipeline — `classify_assets` function

Azure DevOps pipeline definition: [`azure-pipelines.yml`](./azure-pipelines.yml).

## What it does

| Stage | Trigger | Purpose |
|-------|---------|---------|
| **Validate** | PR + main | Ruff format check + 28 pytest unit tests |
| **Package** | PR + main | Install prod deps into `.python_packages/lib/site-packages`, zip the function |
| **Deploy** | main only | `az functionapp deployment source config-zip` to `func-fabricsens-rh` (Flex Consumption) |
| **Verify** | main only | `az functionapp function list` to confirm `classify_assets` is indexed |

Triggered only by changes under `fabric-delta-table-sensitivity-purview-int/iac/function/**` so unrelated repo edits don't fire it.

## One-time ADO setup

1. **Create the pipeline** in Azure DevOps (`Contoso-University` org), pointing at this YAML file.
2. **Create a service connection** named `sc-purview-data-governance-dev` with contributor on subscription `910ebf13-1058-405d-b6cf-eda03e5288d1` (or scoped to `governance-rg`).
3. **Create a variable group** named `purview-data-governance-dev` containing:

   | Name | Value |
   |------|-------|
   | `AZURE_SUBSCRIPTION_ID` | `910ebf13-1058-405d-b6cf-eda03e5288d1` |
   | `RESOURCE_GROUP_NAME` | `governance-rg` |
   | `FUNCTION_APP_NAME` | `func-fabricsens-rh` |

4. **Create an environment** named `purview-data-governance-dev` (add approvals here if you want them).

## What it does NOT do

- Does **not** run `terraform apply`. Infra changes in `iac/` still go through `terraform plan/apply` locally. The pipeline only updates function code.
- Does **not** create or rotate app settings — those are owned by Terraform (`iac/phase2_function.tf`).

## Local equivalent

```powershell
cd fabric-delta-table-sensitivity-purview-int/iac/function
pip install -r requirements-dev.txt
python -m pytest tests/ -x --tb=short
# then deploy via terraform apply (which runs az functionapp deployment source config-zip)
```

# CI/CD Pipeline Setup Guide

## Overview

The `fabric-purview-purview-access-provisioning/src/function-pipeline.yml` pipeline has 5 stages that run in order:

```
┌──────────┐    ┌────────────────┐    ┌─────────────────┐    ┌───────────┐    ┌──────────┐
│ Validate │───▶│ Infrastructure │───▶│ App Registration│    │ purview-access-provisioning/src/function │───▶│ Workflow │
│ (always) │    │ (Bicep)        │    │ (manual only)   │    │ (deploy)  │    │ (Purview)│
└──────────┘    └───────┬────────┘    └─────────────────┘    └───────────┘    └──────────┘
                        │                                          ▲
                        └──────────────────────────────────────────┘
```

- **Validate** — Always runs. Lints Bicep, compiles Python, parses JSON.
- **Infrastructure** — Deploys Azure resources via Bicep (skipped on PRs).
- **App Registration** — Creates the SPN. **Off by default** — run once per environment.
- **purview-access-provisioning/src/function** — Builds and deploys the Python Azure purview-access-provisioning/src/function.
- **Workflow** — Deploys the Purview workflow definition.

## Prerequisites

### 1. Azure DevOps Service Connection

Create an Azure Resource Manager service connection for each environment:

| Name | Type | Scope |
|------|------|-------|
| `sc-purview-fabric-dev` | Azure Resource Manager | Subscription or Resource Group |
| `sc-purview-fabric-staging` | Azure Resource Manager | Subscription or Resource Group |
| `sc-purview-fabric-prod` | Azure Resource Manager | Subscription or Resource Group |

The service principal behind the connection needs:
- **Contributor** on the resource group (for Bicep deployments)
- **Key Vault Administrator** (for secret management)
- **User Access Administrator** (for RBAC role assignments in Bicep)

### 2. Variable Groups

Create a variable group for each environment in Azure DevOps → Pipelines → Library:

**Group name:** `purview-fabric-access-{env}` (e.g., `purview-fabric-access-dev`)

| Variable | Example Value | Secret? | Description |
|----------|---------------|---------|-------------|
| `AZURE_SUBSCRIPTION_ID` | `aaaabbbb-...` | No | Azure subscription ID |
| `RESOURCE_GROUP_NAME` | `rg-purview-fabric-access-dev` | No | Target resource group |
| `LOCATION` | `eastus2` | No | Azure region |
| `PURVIEW_ACCOUNT_NAME` | `my-purview-account` | No | Purview account name |
| `FABRIC_WORKSPACE_ID` | `ccccdddd-...` | No | Fabric workspace GUID |
| `PURVIEW_COLLECTION_ID` | `my-collection` | No | Purview collection for workflow binding |
| `APPROVER_EMAIL` | `admin@contoso.com` | No | Workflow approver email |
| `KEY_VAULT_NAME` | `pvfab-dev-kv-abc123` | No | Key Vault name (set after first infra deploy) |

### 3. Environments

Create environments in Azure DevOps → Pipelines → Environments:

- `purview-fabric-dev`
- `purview-fabric-staging`
- `purview-fabric-prod`

Add approval gates on `staging` and `prod` environments for manual sign-off before deployment.

## Running the Pipeline

### First-Time Setup (New Environment)

1. **Run with all stages enabled:**
   - `deployInfra` = ✅
   - `runAppRegistration` = ✅
   - `deployFunctions` = ✅
   - `deployWorkflow` = ✅

2. **After the pipeline completes**, perform the manual steps printed by the App Registration stage:
   - Grant admin consent in Azure portal
   - Add SPN to Fabric tenant settings security group
   - Assign Purview Workflow Admin role

3. **Update the variable group** with `KEY_VAULT_NAME` from the infra deployment outputs.

### Subsequent Deployments

- Code changes to `purview-access-provisioning/src/function/` or `purview-access-provisioning/src/workflows/` auto-trigger the pipeline.
- Infrastructure and App Registration are **skipped** by default (toggle on if needed).
- PR builds only run the **Validate** stage.

### Manual Run with Parameters

Queue the pipeline manually to select which stages to run:

```
Pipeline Parameters:
  environment:          dev | staging | prod
  deployInfra:          true | false
  deployFunctions:      true | false
  deployWorkflow:       true | false
  runAppRegistration:   true | false (default: false)
```

## Pipeline Triggers

| Event | Stages Run |
|-------|-----------|
| PR to `main` | Validate only |
| Push to `main` (purview-access-provisioning/iac/ changed) | Validate → Infra → purview-access-provisioning/src/function → Workflow |
| Push to `main` (purview-access-provisioning/src/function/ changed) | Validate → Infra → purview-access-provisioning/src/function → Workflow |
| Push to `main` (purview-access-provisioning/src/workflows/ changed) | Validate → Infra → purview-access-provisioning/src/function → Workflow |
| Manual queue | User-selected stages |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Service connection not found" | Create the service connection matching `sc-purview-fabric-{env}` |
| "Variable group not found" | Create the variable group `purview-fabric-access-{env}` in Library |
| Bicep what-if fails | Ensure the resource group exists and service connection has Contributor |
| Function deploy 403 | Service connection needs Contributor on the Function App |
| Workflow deploy 401 | The `az login` session in the pipeline must have Purview API access |
| Output variables empty | Ensure Infrastructure stage ran; purview-access-provisioning/src/function stage reads outputs from it |

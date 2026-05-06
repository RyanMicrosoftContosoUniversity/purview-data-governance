# Runbook: Purview Self-Service Access Workflow for Fabric

> **Purpose:** Bridge the gap between Microsoft Purview self-service access requests and Microsoft Fabric workspace access provisioning via a custom integration.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  User Journey                                                           │
│                                                                         │
│  1. User discovers dataset in Purview Unified Catalog                   │
│  2. Clicks "Request Access" (selects role: Viewer by default)           │
│  3. Purview workflow fires ──────────────────────────────┐              │
│                                                          ▼              │
│  ┌──────────────────────┐    ┌────────────────────────────────────┐     │
│  │  Purview Workflow     │───▶│  ServiceNow Stub (HTTP trigger)    │     │
│  │  (access-request)     │    │  Creates ticket, returns ticket ID │     │
│  └──────────┬───────────┘    └────────────────────────────────────┘     │
│             │                                                           │
│             ▼                                                           │
│  ┌──────────────────────┐    ┌────────────────────────────────────┐     │
│  │  Admin Approval Task  │    │  ServiceNow Stub (Timer trigger)   │     │
│  │  (Purview portal)     │    │  Auto-approves after 2 min         │     │
│  └──────────┬───────────┘    └──────────────┬─────────────────────┘     │
│             │ approved                       │                          │
│             ▼                                ▼                          │
│  ┌─────────────────────────────────────────────────────┐               │
│  │  Azure Storage Queue: purview-access-requests        │               │
│  │  (JSON message with user, workspace, role)           │               │
│  └──────────────────────────┬──────────────────────────┘               │
│                             ▼                                           │
│  ┌─────────────────────────────────────────────────────┐               │
│  │  Fabric Provisioner (Queue-triggered Azure Function) │               │
│  │  1. Validate requested role                          │               │
│  │  2. POST /v1/workspaces/{id}/roleAssignments         │               │
│  │  3. Callback to Purview workflow (approve/reject)     │               │
│  └─────────────────────────────────────────────────────┘               │
│                             │                                           │
│                             ▼                                           │
│  ┌─────────────────────────────────────────────────────┐               │
│  │  Purview Workflow updated → User notified             │               │
│  │  "Access granted: Viewer on workspace XYZ"            │               │
│  └─────────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

| Component | Type | Purpose |
|-----------|------|---------|
| `infra/` | Bicep IaC | Function App, Storage Account + Queue, Key Vault, App Insights |
| `scripts/setup-app-registration.ps1` | PowerShell | Create Entra ID SPN with Fabric + Purview API permissions |
| `functions/shared/` | Python modules | Auth (MSAL), Fabric client, Purview client, Pydantic models |
| `functions/servicenow_stub/` | Azure Functions | Simulates ServiceNow ticket creation and approval |
| `functions/fabric_provisioner/` | Azure Function | Queue trigger → Fabric API → Purview callback |
| `workflows/` | JSON + Python | Purview workflow definition + deployment script |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Azure subscription | With permissions to create resource groups, Function Apps, Storage, Key Vault |
| Azure CLI | v2.50+ with `bicep` extension installed |
| Python | 3.11+ (for Azure Functions and deploy scripts) |
| Azure Functions Core Tools | v4.x (`npm i -g azure-functions-core-tools@4`) |
| Microsoft Purview account | With Workflow Admin permissions |
| Microsoft Fabric workspace | Target workspace for access provisioning |
| Entra ID permissions | Ability to create App Registrations and grant admin consent |

---

## Deployment Steps

### Step 1 — Deploy Azure Infrastructure

```powershell
# Create a resource group
az group create --name rg-purview-fabric-access-dev --location eastus2

# Deploy Bicep templates
cd infra
.\deploy.ps1 `
    -ResourceGroupName "rg-purview-fabric-access-dev" `
    -Location "eastus2" `
    -EnvironmentName "dev"
```

Record the outputs:
- `functionAppName` — needed for Function deployment
- `functionAppHostname` — needed for workflow configuration
- `keyVaultName` — needed for app registration script
- `storageAccountName` — needed for local development

### Step 2 — Create App Registration

```powershell
cd scripts
.\setup-app-registration.ps1 `
    -KeyVaultName "<keyVaultName from Step 1>" `
    -FabricWorkspaceId "<your-fabric-workspace-guid>"
```

**Manual follow-up steps** (printed by the script):

1. **Grant admin consent** for the Fabric API permission in the Azure portal:
   - Azure portal → App Registrations → `purview-fabric-access-provisioner` → API Permissions → Grant admin consent

2. **Add SPN to Fabric tenant settings**:
   - Fabric Admin portal → Tenant settings → "Service principals can use Fabric APIs" → add the security group containing the SPN

3. **Assign Purview Workflow Admin role**:
   - Purview portal → Data Map → Collections → select collection → Role assignments → Workflow Admin → add the SPN

### Step 3 — Configure Local Development (Optional)

```powershell
cd functions
cp local.settings.json.example local.settings.json
# Edit local.settings.json with actual values from Steps 1 and 2
```

### Step 4 — Deploy Azure Functions

```powershell
cd functions

# Install dependencies
pip install -r requirements.txt

# Deploy to Azure
func azure functionapp publish <functionAppName from Step 1> --python
```

### Step 5 — Deploy Purview Workflow

```powershell
cd scripts

# Login to Azure (if not already)
az login

# Deploy the workflow
python deploy-workflow.py `
    --purview-account "<your-purview-account-name>" `
    --workflow-file "../workflows/access-request-workflow.json" `
    --servicenow-url "https://<functionAppHostname from Step 1>" `
    --approver-email "admin@contoso.com" `
    --collection-id "<your-purview-collection-id>"
```

### Step 6 — Verify Deployment

| Check | How |
|-------|-----|
| Function App running | Azure portal → Function App → Functions → verify 4 functions listed |
| Queue exists | Azure portal → Storage Account → Queues → `purview-access-requests` |
| Key Vault secret | Azure portal → Key Vault → Secrets → `spn-client-secret` |
| Workflow active | Purview portal → Management → Workflows → verify workflow is enabled |
| App Insights | Azure portal → Application Insights → Live Metrics |

---

## Testing the End-to-End Flow

### Quick Test (ServiceNow Stub Only)

1. **Create a stub ticket** (simulates Purview calling ServiceNow):
   ```bash
   curl -X POST "https://<functionAppHostname>/api/servicenow/ticket" \
     -H "Content-Type: application/json" \
     -d '{
       "request_id": "test-001",
       "workflow_run_id": "test-wfrun-001",
       "task_id": "test-task-001",
       "requestor_email": "testuser@contoso.com",
       "requestor_object_id": "<user-entra-object-id>",
       "target_workspace_id": "<fabric-workspace-id>",
       "requested_role": "Viewer"
     }'
   ```

2. **Wait 2 minutes** for the timer trigger to auto-approve, or force-approve:
   ```bash
   curl -X POST "https://<functionAppHostname>/api/servicenow/approval-callback" \
     -H "Content-Type: application/json" \
     -d '{ "ticket_id": "<STUB-id from step 1>" }'
   ```

3. **Check the queue** — a message should appear in `purview-access-requests`.

4. **Check the Fabric workspace** — the user should now have Viewer access.

5. **Check Application Insights** — verify logs show successful provisioning.

### Full End-to-End Test

1. Navigate to Purview Unified Catalog → find a dataset in the target workspace.
2. Click **Request Access** → select desired role.
3. Observe the workflow run in Purview → Management → Workflows.
4. Approve the admin approval task when it appears.
5. Verify Fabric workspace access was granted.
6. Verify the workflow status updates to "Completed."

---

## Replacing the ServiceNow Stub

When you have a real ServiceNow environment:

1. **Update the Purview workflow HTTP step** to point to your ServiceNow instance:
   - Replace `{{SERVICENOW_URL}}/api/servicenow/ticket` with your actual ServiceNow REST API endpoint (e.g., `https://yourcompany.service-now.com/api/now/table/sc_request`)

2. **Configure ServiceNow to callback** on approval:
   - Create a ServiceNow Business Rule or Flow that fires when the ticket is approved
   - The callback should POST to your `approval-callback` function endpoint (or directly enqueue to the Storage Queue)

3. **Update authentication**:
   - Store ServiceNow credentials in Key Vault
   - Update the Purview workflow HTTP step to include ServiceNow auth headers

4. **Remove the stub functions** (optional):
   - Delete `functions/servicenow_stub/` once real integration is confirmed working

---

## Queue Message Schema

Messages on the `purview-access-requests` queue use this JSON schema:

```json
{
  "request_id": "unique-uuid",
  "workflow_run_id": "purview-workflow-run-id",
  "task_id": "purview-task-id",
  "requestor_object_id": "entra-user-object-id",
  "requestor_email": "user@contoso.com",
  "target_workspace_id": "fabric-workspace-guid",
  "requested_role": "Viewer",
  "servicenow_ticket_id": "STUB-abc123",
  "approved_at": "2026-04-06T19:00:00Z"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `request_id` | Yes | Unique identifier for idempotency |
| `workflow_run_id` | Yes | Purview workflow run to update on completion |
| `task_id` | Yes | Purview task to approve/reject |
| `requestor_object_id` | Yes | Entra ID object ID — used for Fabric role assignment |
| `requestor_email` | Yes | For logging and notification |
| `target_workspace_id` | Yes | Fabric workspace to grant access to |
| `requested_role` | Yes | One of: `Admin`, `Contributor`, `Member`, `Viewer` (default: `Viewer`) |
| `servicenow_ticket_id` | No | Reference to the ServiceNow ticket |
| `approved_at` | No | ISO 8601 timestamp of approval |

---

## Troubleshooting

### Function App Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Function App not starting | Missing app settings | Verify all settings from `local.settings.json.example` are in the Function App configuration |
| Queue trigger not firing | Wrong connection string | Check `STORAGE_QUEUE_CONNECTION` in app settings matches the Storage Account |
| Key Vault access denied | Missing RBAC | Verify the Function App's managed identity has `Key Vault Secrets User` role |

### Fabric API Errors

| HTTP Code | Meaning | Fix |
|-----------|---------|-----|
| 201 | Success — role assigned | N/A |
| 400 | Bad request (invalid role or principal) | Check the `requested_role` is valid and `requestor_object_id` exists in Entra ID |
| 401 | Authentication failed | Check SPN client secret hasn't expired; verify admin consent was granted |
| 403 | Insufficient permissions | SPN needs Admin role on the workspace; check Fabric tenant settings |
| 404 | Workspace not found | Verify `target_workspace_id` is correct |
| 409 | User already has this role | Treated as success — logged and Purview task approved |

### Purview Workflow API Errors

| Issue | Fix |
|-------|-----|
| 401 Unauthorized | SPN needs `Workflow Admin` role in Purview |
| Workflow not triggering | Verify workflow is bound to the correct collection and is enabled |
| Task already completed | Idempotency — the callback may have run twice; safe to ignore |

### ServiceNow Stub Issues

| Issue | Fix |
|-------|-----|
| Tickets not auto-approving | Check the timer trigger is running (Application Insights → Live Metrics) |
| Table Storage errors | Verify `AzureWebJobsStorage` connection string is correct |
| Queue messages not appearing | Check the ticket was stored in Table Storage with status "pending" |

---

## Security Considerations

- **SPN credentials** are stored in Azure Key Vault, accessed via Function App managed identity — never in code or app settings.
- **Admin consent** is required for the Fabric API permission — this is a one-time manual step.
- **Default role is Viewer** — elevated roles (Contributor, Member, Admin) require explicit admin approval in the workflow.
- **Queue messages** contain Entra ID object IDs, not passwords or tokens.
- **The Purview Workflow API** is in public preview (`2023-10-01-preview`) — evaluate for production use per Microsoft's preview terms.

---

## Related Resources

| Resource | Link |
|----------|------|
| Purview Workflow API | https://learn.microsoft.com/en-us/rest/api/purview/workflowdataplane/workflow |
| Fabric Add Workspace Role Assignment | https://learn.microsoft.com/en-us/rest/api/fabric/core/workspaces/add-workspace-role-assignment |
| Purview ServiceNow Integration | https://learn.microsoft.com/en-us/purview/legacy/how-to-use-servicenow-workflows |
| Purview HTTP Connector (preview) | https://techcommunity.microsoft.com/blog/microsoft-security-blog/now-in-public-preview-microsoft-purview-workflows-http-connector/3655281 |
| Purview Self-Service Access Concepts | https://learn.microsoft.com/en-us/purview/legacy/concept-self-service-data-access-policy |

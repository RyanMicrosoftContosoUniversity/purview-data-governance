# Purview Self-Service Fabric Access Request Workflow

Automated workflow deployed to Microsoft Purview that orchestrates self-service access requests for Fabric workspace resources. When a user requests access through the Purview Unified Catalog, this workflow creates a ServiceNow ticket (stubbed), routes the request for approval, and triggers automated Fabric role provisioning.

## Workflow Steps

```
User requests access via Purview Unified Catalog
  │
  ▼
┌─────────────────────────────────────────────┐
│ 1. Notify data steward of new request       │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 2. Create ServiceNow ticket (HTTP → stub)   │
│    POST {{SERVICENOW_URL}}/api/servicenow/ticket │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 3. Approval task assigned to data steward   │
│    (shows requestor, role, workspace, SNOW) │
└──────────────────┬──────────────────────────┘
                   ▼
            ┌──────┴──────┐
            │  Approved?  │
            └──┬───────┬──┘
         Yes   │       │   No
               ▼       ▼
┌──────────────────┐ ┌──────────────────────┐
│ Approve ticket + │ │ Reject ticket +      │
│ enqueue provision│ │ notify requestor     │
└────────┬─────────┘ └──────────────────────┘
         ▼
┌─────────────────────────────────────────────┐
│ 5. Wait for provisioner callback            │
│    (Fabric provisioner calls Purview API)   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 6. Final notification — access granted      │
└─────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|---|---|
| **Purview account** | Microsoft Purview with Unified Catalog and Workflow feature enabled |
| **Purview role** | Workflow Admin role on the target collection |
| **ServiceNow stub** | Deployed Azure Function App (see `../scripts/` for the stub) |
| **Azure CLI** | Logged in with `az login` (or Managed Identity for CI/CD) |
| **Python 3.9+** | With `requests` and `azure-identity` packages |
| **Collection ID** | The Purview collection to bind this workflow to |

## Configuration

Before deploying, you need three values to substitute into the workflow template:

### 1. ServiceNow Stub URL (`{{SERVICENOW_URL}}`)

The base URL of the deployed ServiceNow stub Function App:

```
https://<your-funcapp-name>.azurewebsites.net
```

The workflow calls these endpoints:
- `POST /api/servicenow/ticket` — create ticket
- `POST /api/servicenow/ticket/approve` — update ticket on approval
- `POST /api/servicenow/ticket/reject` — update ticket on rejection

### 2. Approver Email (`{{APPROVER_EMAIL}}`)

The email address of the data steward or admin who reviews access requests. This can be:
- An individual user: `admin@contoso.com`
- A mail-enabled security group: `fabric-data-stewards@contoso.com`

### 3. Collection ID (`{{COLLECTION_ID}}`)

The Purview collection that this workflow is bound to. Requests for assets in this collection (or child collections) will trigger the workflow. Find this in:
- Purview portal → Data Map → Collections → select collection → copy the ID from the URL
- Or via the Purview Collections API

## Deployment

### Using the deploy script

```bash
python purview-access-provisioning/scripts/deploy-workflow.py \
    --purview-account my-purview-account \
    --workflow-file purview-access-provisioning/src/workflows/access-request-workflow.json \
    --servicenow-url https://my-funcapp.azurewebsites.net \
    --approver-email fabric-stewards@contoso.com \
    --collection-id "abc123-def456"
```

### What the script does

1. Authenticates to Purview via `DefaultAzureCredential` (uses `az login` session)
2. Reads `access-request-workflow.json` and substitutes `{{SERVICENOW_URL}}`, `{{APPROVER_EMAIL}}`, and `{{COLLECTION_ID}}`
3. Generates a deterministic workflow ID (UUID v5 from the account + workflow name)
4. PUTs the workflow definition to the Purview Workflow API (`2023-10-01-preview`)
5. Prints the workflow ID and status

### Manual deployment (Purview portal)

1. Open the Purview portal → Management → Workflows
2. Create a new workflow and paste the contents of `access-request-workflow.json`
3. Replace all `{{...}}` placeholders with actual values
4. Bind the workflow to the desired collection
5. Enable the workflow

## Testing

### 1. Trigger a test request

In the Purview Unified Catalog, find an asset in the bound collection and click **Request Access**. Fill in a role and justification.

### 2. Verify the ServiceNow ticket

Check the Function App logs or the stub's Table Storage for the created ticket:

```bash
az functionapp logs show --name <funcapp-name> --resource-group <rg>
```

### 3. Complete the approval

In Purview → My Approvals, find the pending task and approve or reject it.

### 4. Verify provisioning

After approval, check that:
- The ServiceNow ticket status updated to `approved`
- A message was enqueued to the Storage Queue (via the stub's timer trigger)
- The Fabric provisioner picked up the message and assigned the role

### 5. Check the callback

The provisioner Azure Function calls back to the Purview Workflow API to complete step 5 (external callback), which triggers the final notification.

## Replacing the ServiceNow Stub with Real ServiceNow

When you're ready to connect to a real ServiceNow instance:

### 1. Update the HTTP connector URLs

Replace the `{{SERVICENOW_URL}}/api/servicenow/ticket*` endpoints with your ServiceNow instance REST API:

| Stub endpoint | ServiceNow equivalent |
|---|---|
| `POST /api/servicenow/ticket` | `POST https://<instance>.service-now.com/api/now/table/sc_request` |
| `POST /api/servicenow/ticket/approve` | `PATCH https://<instance>.service-now.com/api/now/table/sc_request/{sys_id}` |
| `POST /api/servicenow/ticket/reject` | `PATCH https://<instance>.service-now.com/api/now/table/sc_request/{sys_id}` |

### 2. Add ServiceNow authentication

Add Basic Auth or OAuth headers to the HTTP connector steps:

```json
"headers": {
    "Content-Type": "application/json",
    "Authorization": "Basic <base64-encoded-credentials>"
}
```

Or use a Purview-managed connection for ServiceNow if available.

### 3. Map the request body fields

ServiceNow uses different field names. Map the stub fields to ServiceNow table columns (e.g., `short_description`, `assignment_group`, `caller_id`, `u_custom_fields`).

### 4. Update the provisioning trigger

With a real ServiceNow instance, you may want to:
- Use a ServiceNow Business Rule to enqueue provisioning (instead of the stub's timer)
- Or keep the Storage Queue pattern but have ServiceNow write directly to it

## File Reference

| File | Purpose |
|---|---|
| `purview-access-provisioning/src/workflows/access-request-workflow.json` | Purview workflow definition (JSON template) |
| `purview-access-provisioning/scripts/deploy-workflow.py` | Deployment script for Purview Workflow API |

resource "fabric_lakehouse" "this" {
  display_name = var.lakehouse_name
  description  = "Sensitivity-metadata lakehouse holding Delta tables tagged with data-sensitivity TBLPROPERTIES."
  workspace_id = var.workspace_id
}

resource "fabric_notebook" "this" {
  display_name              = var.notebook_display_name
  description               = "Creates fake healthcare Delta tables and tags each with a data-sensitivity TBLPROPERTY."
  workspace_id              = var.workspace_id
  format                    = "ipynb"
  definition_update_enabled = true

  definition = {
    "notebook-content.ipynb" = {
      source = "${path.module}/notebook/create_sensitivity_tables.ipynb"
      tokens = {
        workspace_id   = var.workspace_id
        lakehouse_id   = fabric_lakehouse.this.id
        lakehouse_name = var.lakehouse_name
      }
    }
  }

  depends_on = [fabric_lakehouse.this]
}

# The microsoft/fabric provider (v1.9.x) does not expose a dedicated on-demand
# job-instance resource. fabric_item_job_scheduler only manages recurring
# schedules. To fulfil the "run once on apply" requirement we call the Fabric
# REST API ourselves via a null_resource + local-exec, using the same Azure CLI
# session the provider relies on.
#
# Triggers ensure the run repeats whenever the notebook/lakehouse changes.
resource "null_resource" "run_notebook_once" {
  # Triggers intentionally exclude source_content_sha256 so that editing the
  # notebook .ipynb does NOT auto-rerun the populate step (which would
  # overwrite any data changes made post-deploy). The notebook itself is also
  # idempotent (skips writes when tables already exist), but this is the
  # belt-and-braces guard. To force a rerun, run:
  #   terraform taint null_resource.run_notebook_once
  triggers = {
    notebook_id  = fabric_notebook.this.id
    lakehouse_id = fabric_lakehouse.this.id
  }

  lifecycle {
    ignore_changes = [triggers]
  }

  provisioner "local-exec" {
    interpreter = ["pwsh", "-NoProfile", "-NonInteractive", "-Command"]
    command     = <<-EOT
      $ErrorActionPreference = 'Stop'
      Write-Host 'Acquiring Fabric access token via Azure CLI...'
      $token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
      if (-not $token) { throw 'Failed to get Fabric access token via az CLI. Run "az login" first.' }
      $headers = @{ Authorization = "Bearer $token" }
      $uri = "https://api.fabric.microsoft.com/v1/workspaces/${var.workspace_id}/items/${fabric_notebook.this.id}/jobs/instances?jobType=RunNotebook"
      Write-Host "Triggering on-demand notebook run: $uri"
      Invoke-WebRequest -Method Post -Uri $uri -Headers $headers -UseBasicParsing | Out-Null
      Write-Host 'Notebook run requested.'
    EOT
  }

  depends_on = [
    fabric_lakehouse.this,
    fabric_notebook.this,
  ]
}

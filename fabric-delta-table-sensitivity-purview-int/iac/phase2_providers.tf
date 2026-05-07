provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azapi" {
  use_cli = true
}

# Acquire a short-lived Purview data-plane token via Azure CLI for the
# restapi provider to call the Atlas API.
data "external" "purview_token" {
  program = [
    "pwsh", "-NoProfile", "-NonInteractive", "-Command",
    "az account get-access-token --resource https://purview.azure.net --query '{token:accessToken}' -o json"
  ]
}

# Resolve the Purview catalog endpoint dynamically — newer "Purview Unified"
# accounts only serve TLS on https://<guid>-api.purview-service.microsoft.com,
# not the legacy https://<account>.purview.azure.com hostname.
data "external" "purview_catalog_endpoint" {
  program = [
    "pwsh", "-NoProfile", "-NonInteractive", "-Command",
    "$ep = az purview account show --name ${var.purview_account_name} --resource-group ${var.phase2_resource_group} --query endpoints.catalog -o tsv; @{ uri = ($ep -replace '/catalog$', '') } | ConvertTo-Json -Compress"
  ]
}

provider "restapi" {
  uri                  = data.external.purview_catalog_endpoint.result.uri
  write_returns_object = true
  debug                = false

  headers = {
    Authorization = "Bearer ${data.external.purview_token.result.token}"
    Content-Type  = "application/json"
  }
}

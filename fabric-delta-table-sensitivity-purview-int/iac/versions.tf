terraform {
  required_version = ">= 1.8.0, < 2.0.0"

  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "~> 1.9"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.16"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.1"
    }
    restapi = {
      source  = "Mastercard/restapi"
      version = "~> 2.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }

  backend "azurerm" {
    resource_group_name  = "terraform-rg"
    storage_account_name = "terraformsaeheus2"
    container_name       = "tf-state-container"
    key                  = "fabric-delta-table-sensitivity-purview-int.tfstate"
  }
}

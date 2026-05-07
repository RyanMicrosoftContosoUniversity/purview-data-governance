variable "subscription_id" {
  description = "Azure subscription ID hosting the Purview account and the Phase 2 Function resources."
  type        = string
  default     = "910ebf13-1058-405d-b6cf-eda03e5288d1"
}

variable "phase2_resource_group" {
  description = "Resource group hosting the Purview account and the Phase 2 Function resources."
  type        = string
  default     = "governance-rg"
}

variable "phase2_location" {
  description = "Azure region for Phase 2 resources (Function, Storage, App Insights)."
  type        = string
  default     = "westus"
}

variable "purview_account_name" {
  description = "Microsoft Purview account name (data-plane host = <name>.purview.azure.com)."
  type        = string
  default     = "governancePurviewRH"
}

variable "purview_collection_id" {
  description = "Purview collection ID (the short alphanumeric collection 'name' field) where the Fabric lakehouse assets live and where the Function MI gets Data Curator."
  type        = string
  default     = "bhhlid"
}

variable "function_app_name" {
  description = "Function app name (must be globally unique within azurewebsites.net)."
  type        = string
  default     = "func-fabricsens-rh"
}

variable "function_storage_account_name" {
  description = "Storage account backing the Function app (must be globally unique, 3-24 lowercase alphanumeric)."
  type        = string
  default     = "stfabricsensrh"
}

variable "classification_namespace" {
  description = "Namespace prefix for the 4 custom classification typedefs."
  type        = string
  default     = "Sensitivity"
}

# Map of TBLPROPERTY value (lowercased) -> classification suffix (typedef name = "{namespace}.{suffix}")
variable "sensitivity_levels" {
  description = "Mapping from TBLPROPERTY data-sensitivity value to classification typedef suffix."
  type        = map(string)
  default = {
    "highly confidential" = "HighlyConfidential"
    "confidential"        = "Confidential"
    "general"             = "General"
    "public"              = "Public"
  }
}

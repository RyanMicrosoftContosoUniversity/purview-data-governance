# =============================================================================
# Input variables
# =============================================================================
# Defaults are populated for the dev/RH environment; override per env via
# `-var` / `terraform.tfvars` (gitignored). A planned follow-up will move
# these defaults out to config/*.yml files consumed by `yamldecode`.

# --- Fabric (workspace, lakehouse, notebook) -------------------------------

variable "workspace_id" {
  description = "The existing Fabric workspace ID where the lakehouse and notebook will be created."
  type        = string
  default     = "a9574816-83cc-4629-b086-356e14c495c7"
}

variable "lakehouse_name" {
  description = "Display name of the Fabric lakehouse to create."
  type        = string
  default     = "sensitivity_metadata_lh"
}

variable "notebook_display_name" {
  description = "Display name of the Fabric notebook to create."
  type        = string
  default     = "create_sensitivity_tables"
}

# --- Azure subscription / resource group / region --------------------------

variable "subscription_id" {
  description = "Azure subscription ID hosting the Purview account and the Function resources."
  type        = string
  default     = "910ebf13-1058-405d-b6cf-eda03e5288d1"
}

variable "phase2_resource_group" {
  description = "Resource group hosting the Purview account and the Function resources."
  type        = string
  default     = "governance-rg"
}

variable "phase2_location" {
  description = "Azure region for the Function, Storage, App Insights, and Event Hub."
  type        = string
  default     = "westus"
}

# --- Purview ---------------------------------------------------------------

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

# --- Function app ----------------------------------------------------------

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

# --- Classification model --------------------------------------------------

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

variable "sensitivity_severity_order" {
  description = "Ordered list (highest severity first) used as a tiebreaker when multiple Sensitivity.* classifications are attached to one entity."
  type        = list(string)
  default     = ["HighlyConfidential", "Confidential", "General", "Public"]
}

variable "deleted_sensitivity_value" {
  description = "TBLPROPERTY value written to a Delta table when its Sensitivity.* classification is removed from Purview."
  type        = string
  default     = "None"
}

# --- Event Hub -------------------------------------------------------------

variable "atlas_notification_eventhub_name" {
  description = "Name of the Event Hub (inside ehns-fabricsens-rh) that receives Purview Atlas Notification messages."
  type        = string
  default     = "atlas-notifications"
}

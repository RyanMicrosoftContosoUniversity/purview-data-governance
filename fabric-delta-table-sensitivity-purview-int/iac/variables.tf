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

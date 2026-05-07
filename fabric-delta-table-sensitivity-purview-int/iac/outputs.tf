output "lakehouse_id" {
  description = "The ID of the created Fabric lakehouse."
  value       = fabric_lakehouse.this.id
}

output "lakehouse_properties" {
  description = "Read-only properties exposed by the lakehouse resource (includes SQL endpoint info when available)."
  value       = fabric_lakehouse.this.properties
}

output "notebook_id" {
  description = "The ID of the created Fabric notebook."
  value       = fabric_notebook.this.id
}

output "notebook_run_trigger_id" {
  description = "ID of the null_resource that triggered the on-demand notebook run."
  value       = null_resource.run_notebook_once.id
}

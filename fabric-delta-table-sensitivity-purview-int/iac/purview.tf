# =============================================================================
# Purview: account lookup, classification typedefs, Atlas notification wiring
# =============================================================================
# The Purview account itself is NOT managed by this module (it predates the
# project). We look it up by name and reference it via a constructed ARM ID.

# Existing Purview account ARM ID (constructed; account is not managed here).
locals {
  purview_account_id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.phase2_resource_group}/providers/Microsoft.Purview/accounts/${var.purview_account_name}"
}

# azapi lookup of the Purview account (used to read its system-assigned MI
# principal_id when granting it Contributor on the Atlas-notification EH).
data "azapi_resource" "purview_account" {
  type      = "Microsoft.Purview/accounts@2021-12-01"
  name      = var.purview_account_name
  parent_id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.phase2_resource_group}"
}

# --- Custom classification typedefs ----------------------------------------
locals {
  classification_defs = {
    for level, suffix in var.sensitivity_levels :
    level => {
      typedef_name = "${var.classification_namespace}.${suffix}"
      description  = "Data sensitivity = ${level}. Sourced from Delta TBLPROPERTY 'data-sensitivity' on the source table."
      color = lookup({
        "highly confidential" = "#B91C1C", # red
        "confidential"        = "#D97706", # amber
        "general"             = "#0369A1", # blue
        "public"              = "#15803D", # green
      }, level, "#525252")
    }
  }
}

# One restapi_object per classification typedef. Atlas typedefs API expects an
# array wrapped under "classificationDefs" on POST; we POST one at a time so
# each Terraform resource maps 1:1 to a typedef and can be drift-checked.
resource "restapi_object" "classification" {
  for_each = local.classification_defs

  # Use PUT for create so the call is idempotent against pre-existing typedefs
  # (Atlas /types/typedefs is upsert-safe under PUT). POST returns 409 if the
  # typedef already exists, which would block apply on re-runs after manual
  # creation or partial state loss.
  path          = "/catalog/api/atlas/v2/types/typedefs"
  read_path     = "/catalog/api/atlas/v2/types/typedef/name/${each.value.typedef_name}"
  destroy_path  = "/catalog/api/atlas/v2/types/typedef/name/${each.value.typedef_name}"
  create_method = "PUT"
  update_method = "PUT"
  id_attribute  = "classificationDefs/0/name"
  read_search   = { search_key = "name", search_value = each.value.typedef_name, results_key = "classificationDefs" }

  data = jsonencode({
    classificationDefs = [
      {
        category      = "CLASSIFICATION"
        name          = each.value.typedef_name
        description   = each.value.description
        typeVersion   = "1.0"
        attributeDefs = []
        superTypes    = []
        entityTypes   = []
        options = {
          color = each.value.color
        }
      }
    ]
    entityDefs           = []
    enumDefs             = []
    relationshipDefs     = []
    structDefs           = []
    businessMetadataDefs = []
  })
}

# --- Purview kafkaConfigurations (BYO Event Hub for Atlas notifications) ----
# Purview's kafkaConfigurations resource isn't modeled in azurerm, so use
# azapi. Requires `purview_eh_contributor` RBAC to be in place first
# (Purview MI must be Contributor on the EH namespace) — enforced via
# depends_on so plan/apply ordering is correct.
resource "azapi_resource" "purview_atlas_notification_config" {
  type      = "Microsoft.Purview/accounts/kafkaConfigurations@2021-12-01"
  name      = "atlas-notification-config"
  parent_id = local.purview_account_id

  body = {
    properties = {
      eventHubResourceId  = azurerm_eventhub.atlas_notifications.id
      eventHubType        = "Notification"
      eventStreamingState = "Enabled"
      eventStreamingType  = "Azure"
      consumerGroup       = "$Default"
      credentials = {
        type = "SystemAssigned"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.purview_eh_contributor,
  ]
}

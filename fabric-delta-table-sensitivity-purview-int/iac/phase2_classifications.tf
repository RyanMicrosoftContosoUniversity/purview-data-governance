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

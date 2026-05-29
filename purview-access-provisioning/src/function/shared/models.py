"""Pydantic models for the Purview-to-Fabric access workflow."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FabricRole(str, Enum):
    """Fabric workspace roles that can be assigned."""

    ADMIN = "Admin"
    CONTRIBUTOR = "Contributor"
    MEMBER = "Member"
    VIEWER = "Viewer"


class AccessRequestMessage(BaseModel):
    """Message schema for the purview-access-requests queue."""

    request_id: str = Field(..., description="Unique request identifier")
    workflow_run_id: str = Field(..., description="Purview workflow run ID")
    task_id: str = Field(..., description="Purview approval task ID")
    requestor_object_id: str = Field(
        ..., description="Entra ID object ID of the requesting user"
    )
    requestor_email: str = Field(..., description="Email of the requesting user")
    target_workspace_id: str = Field(
        ..., description="Fabric workspace GUID to grant access to"
    )
    requested_role: FabricRole = Field(
        default=FabricRole.VIEWER, description="Fabric workspace role to assign"
    )
    servicenow_ticket_id: Optional[str] = Field(
        None, description="ServiceNow ticket ID (or stub ID)"
    )
    approved_at: Optional[str] = Field(
        None, description="ISO 8601 timestamp of approval"
    )


class ProvisioningResult(BaseModel):
    """Result of a Fabric access provisioning operation."""

    success: bool
    request_id: str
    workspace_id: str
    role_assigned: Optional[str] = None
    error_message: Optional[str] = None
    fabric_response_code: Optional[int] = None

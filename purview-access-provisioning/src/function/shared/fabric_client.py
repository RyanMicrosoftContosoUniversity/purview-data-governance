"""Fabric REST API client for workspace role assignment operations."""

import logging
from typing import Optional

import requests

from .models import ProvisioningResult

logger = logging.getLogger(__name__)

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"


class FabricApiError(Exception):
    """Raised when a Fabric API call fails unexpectedly."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class FabricClient:
    """Client for Fabric workspace role-assignment operations.

    Args:
        access_token: Bearer token for the Fabric REST API.
    """

    def __init__(self, access_token: str):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def add_workspace_role_assignment(
        self,
        workspace_id: str,
        principal_id: str,
        principal_type: str,
        role: str,
    ) -> ProvisioningResult:
        """Add a role assignment to a Fabric workspace.

        Args:
            workspace_id: GUID of the target workspace.
            principal_id: Entra ID object ID of the user or group.
            principal_type: 'User', 'Group', or 'ServicePrincipal'.
            role: Fabric role name (Admin, Contributor, Member, Viewer).

        Returns:
            ProvisioningResult indicating success or failure.
        """
        url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/roleAssignments"
        payload = {
            "principal": {
                "id": principal_id,
                "type": principal_type,
            },
            "role": role,
        }

        logger.info(
            "Adding role assignment: workspace=%s principal=%s role=%s",
            workspace_id,
            principal_id,
            role,
        )

        try:
            response = self._session.post(url, json=payload)
        except requests.RequestException as exc:
            logger.error("Network error calling Fabric API: %s", exc)
            return ProvisioningResult(
                success=False,
                request_id="",
                workspace_id=workspace_id,
                error_message=f"Network error: {exc}",
            )

        if response.status_code == 201:
            logger.info("Role assignment created successfully.")
            return ProvisioningResult(
                success=True,
                request_id="",
                workspace_id=workspace_id,
                role_assigned=role,
                fabric_response_code=201,
            )

        if response.status_code == 409:
            # Principal already has a role in this workspace — treat as success
            logger.warning(
                "Role assignment already exists (409). Treating as success."
            )
            return ProvisioningResult(
                success=True,
                request_id="",
                workspace_id=workspace_id,
                role_assigned=role,
                error_message="Role assignment already exists",
                fabric_response_code=409,
            )

        # 400 / 401 / 403 / 404 and other errors
        error_body = response.text
        logger.error(
            "Fabric API error: status=%d body=%s", response.status_code, error_body
        )
        return ProvisioningResult(
            success=False,
            request_id="",
            workspace_id=workspace_id,
            error_message=f"Fabric API returned {response.status_code}: {error_body}",
            fabric_response_code=response.status_code,
        )

    def get_workspace_role_assignments(self, workspace_id: str) -> list:
        """Retrieve existing role assignments for a workspace.

        Args:
            workspace_id: GUID of the target workspace.

        Returns:
            List of role-assignment dicts from the Fabric API.

        Raises:
            FabricApiError: If the API call fails.
        """
        url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/roleAssignments"
        logger.info("Fetching role assignments for workspace %s", workspace_id)

        response = self._session.get(url)

        if response.status_code == 200:
            data = response.json()
            return data.get("value", [])

        raise FabricApiError(
            f"Failed to get role assignments: {response.status_code} {response.text}",
            status_code=response.status_code,
        )

"""Purview Workflow API client for task approval and run management."""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_VERSION = "2023-10-01-preview"


class PurviewApiError(Exception):
    """Raised when a Purview Workflow API call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class PurviewWorkflowClient:
    """Client for Purview Workflow task and run operations.

    Args:
        account_name: Purview account name (used to build the base URL).
        access_token: Bearer token for the Purview REST API.
    """

    def __init__(self, account_name: str, access_token: str):
        self._base_url = f"https://{account_name}.purview.azure.com/workflow"
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        """Build a full URL with the API version query parameter."""
        separator = "&" if "?" in path else "?"
        return f"{self._base_url}{path}{separator}api-version={API_VERSION}"

    def approve_task(self, task_id: str, comment: Optional[str] = None) -> dict:
        """Approve a Purview workflow approval task.

        Args:
            task_id: The workflow task ID to approve.
            comment: Optional comment to include with the approval.

        Returns:
            Parsed JSON response from the API.

        Raises:
            PurviewApiError: If the API call fails.
        """
        url = self._url(f"/workflowtasks/{task_id}/approve-approval-task")
        payload = {"comment": comment or "Approved via automated workflow"}

        logger.info("Approving Purview task: %s", task_id)
        response = self._session.post(url, json=payload)

        if response.status_code in (200, 202):
            logger.info("Task %s approved successfully.", task_id)
            return response.json() if response.content else {}

        raise PurviewApiError(
            f"Failed to approve task {task_id}: {response.status_code} {response.text}",
            status_code=response.status_code,
        )

    def reject_task(self, task_id: str, comment: Optional[str] = None) -> dict:
        """Reject a Purview workflow approval task.

        Args:
            task_id: The workflow task ID to reject.
            comment: Optional comment to include with the rejection.

        Returns:
            Parsed JSON response from the API.

        Raises:
            PurviewApiError: If the API call fails.
        """
        url = self._url(f"/workflowtasks/{task_id}/reject-approval-task")
        payload = {"comment": comment or "Rejected via automated workflow"}

        logger.info("Rejecting Purview task: %s", task_id)
        response = self._session.post(url, json=payload)

        if response.status_code in (200, 202):
            logger.info("Task %s rejected.", task_id)
            return response.json() if response.content else {}

        raise PurviewApiError(
            f"Failed to reject task {task_id}: {response.status_code} {response.text}",
            status_code=response.status_code,
        )

    def get_workflow_run(self, run_id: str) -> dict:
        """Retrieve details of a Purview workflow run.

        Args:
            run_id: The workflow run ID.

        Returns:
            Parsed JSON response with workflow run details.

        Raises:
            PurviewApiError: If the API call fails.
        """
        url = self._url(f"/workflowruns/{run_id}")

        logger.info("Fetching workflow run: %s", run_id)
        response = self._session.get(url)

        if response.status_code == 200:
            return response.json()

        raise PurviewApiError(
            f"Failed to get workflow run {run_id}: {response.status_code} {response.text}",
            status_code=response.status_code,
        )

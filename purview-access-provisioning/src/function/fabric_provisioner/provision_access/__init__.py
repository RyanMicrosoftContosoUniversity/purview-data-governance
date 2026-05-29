"""Azure Function: Queue-triggered Fabric workspace access provisioner.

Reads approved access requests from the purview-access-requests queue,
provisions workspace role assignments via the Fabric REST API, and
calls back to Purview to complete the workflow task.
"""

import azure.functions as func
import json
import logging
import base64
import time
import traceback
import os
import sys

# Add the shared modules directory to the path so sibling-package imports work
# in the Azure Functions v1 Python model.
_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
if os.path.isdir(_shared_path) and _shared_path not in sys.path:
    sys.path.insert(0, _shared_path)

from models import AccessRequestMessage, ProvisioningResult, FabricRole
from auth import get_fabric_token, get_purview_token, get_spn_credentials_from_keyvault
from fabric_client import FabricClient
from purview_client import PurviewWorkflowClient

logger = logging.getLogger(__name__)

# Fabric API response codes that indicate a permanent (non-retryable) failure.
_PERMANENT_FAILURE_CODES = {400, 403, 404}

# Environment variable for Purview account name used by the workflow client.
_PURVIEW_ACCOUNT_ENV = "PURVIEW_ACCOUNT_NAME"


class PermanentProvisioningError(Exception):
    """Raised when provisioning fails in a way that retries will not fix."""


def _parse_queue_message(msg: func.QueueMessage) -> AccessRequestMessage:
    """Deserialize the queue message into an AccessRequestMessage.

    Azure Storage Queue base64-encodes message bodies, so we try
    base64 decoding first and fall back to the raw string.
    """
    raw = msg.get_body()
    try:
        decoded = base64.b64decode(raw)
    except Exception:
        decoded = raw

    payload = json.loads(decoded)
    return AccessRequestMessage(**payload)


def _validate_role(role: FabricRole | str) -> FabricRole:
    """Validate that the requested role is a recognised Fabric workspace role.

    The model may already deserialize the value into a FabricRole enum; if it
    arrives as a plain string we attempt the conversion here.
    """
    if isinstance(role, FabricRole):
        return role
    try:
        return FabricRole(role)
    except ValueError:
        valid = ", ".join(r.value for r in FabricRole)
        raise PermanentProvisioningError(
            f"Invalid role '{role}'. Must be one of: {valid}"
        )


def _get_purview_account_name() -> str:
    """Read the Purview account name from environment configuration."""
    name = os.environ.get(_PURVIEW_ACCOUNT_ENV, "")
    if not name:
        raise RuntimeError(
            f"Missing required environment variable: {_PURVIEW_ACCOUNT_ENV}"
        )
    return name


def main(msg: func.QueueMessage) -> None:
    start_time = time.time()
    request: AccessRequestMessage | None = None

    try:
        # ── 1. Parse the queue message ──────────────────────────────────
        request = _parse_queue_message(msg)
        logger.info(
            "Processing access request | request_id=%s requestor=%s "
            "workspace=%s role=%s",
            request.request_id,
            request.requestor_email,
            request.target_workspace_id,
            request.requested_role,
        )

        # ── 2. Validate the requested role ──────────────────────────────
        role = _validate_role(request.requested_role)

        # ── 3. Acquire Fabric API token ─────────────────────────────────
        credentials = get_spn_credentials_from_keyvault()
        fabric_token = get_fabric_token(credentials)
        fabric_client = FabricClient(fabric_token)

        # ── 4. Idempotency check ────────────────────────────────────────
        existing_assignments = fabric_client.get_workspace_role_assignments(
            request.target_workspace_id
        )
        already_assigned = any(
            a.get("principal", {}).get("id") == request.requestor_object_id
            and a.get("role", "").lower() == role.value.lower()
            for a in existing_assignments
        )

        if already_assigned:
            logger.info(
                "User %s already has %s role on workspace %s — skipping assignment",
                request.requestor_email,
                role.value,
                request.target_workspace_id,
            )
            result = ProvisioningResult(
                success=True,
                request_id=request.request_id,
                workspace_id=request.target_workspace_id,
                role_assigned=role.value,
                fabric_response_code=200,
            )
        else:
            # ── 5. Provision the workspace role assignment ──────────────
            result = fabric_client.add_workspace_role_assignment(
                workspace_id=request.target_workspace_id,
                principal_id=request.requestor_object_id,
                principal_type="User",
                role=role.value,
            )
            logger.info(
                "Fabric API response | status=%s role_assigned=%s error=%s",
                result.fabric_response_code,
                result.role_assigned,
                result.error_message,
            )

        # ── 6. Handle the result ────────────────────────────────────────
        if result.success or result.fabric_response_code == 409:
            _handle_success(request, role)
        elif result.fabric_response_code in _PERMANENT_FAILURE_CODES:
            raise PermanentProvisioningError(
                f"Fabric API returned {result.fabric_response_code}: "
                f"{result.error_message}"
            )
        else:
            # Transient failure — raise so the queue retries the message.
            raise RuntimeError(
                f"Fabric API returned {result.fabric_response_code}: "
                f"{result.error_message}"
            )

    except PermanentProvisioningError as exc:
        _handle_permanent_failure(request, exc)

    except Exception as exc:
        logger.error(
            "Unhandled error provisioning access | error=%s\n%s",
            exc,
            traceback.format_exc(),
        )
        # Attempt to reject the Purview task so the requester is notified,
        # but only if we've exhausted retries (dequeue count check).
        if msg.dequeue_count >= 3 and request is not None:
            _handle_permanent_failure(request, exc)
        else:
            # Re-raise to let the Functions runtime put the message back on
            # the queue for retry (up to maxDequeueCount in host.json).
            raise

    finally:
        elapsed = time.time() - start_time
        logger.info("Function execution completed in %.2f s", elapsed)


# ── Callback helpers ────────────────────────────────────────────────────────


def _handle_success(
    request: AccessRequestMessage,
    role: FabricRole,
) -> None:
    """Approve the Purview workflow task after successful provisioning."""
    comment = (
        f"Access granted: {role.value} role on workspace "
        f"{request.target_workspace_id} for {request.requestor_email}"
    )
    logger.info("Provisioning succeeded — approving Purview task | comment=%s", comment)

    try:
        credentials = get_spn_credentials_from_keyvault()
        purview_token = get_purview_token(credentials)
        purview_client = PurviewWorkflowClient(
            account_name=_get_purview_account_name(),
            access_token=purview_token,
        )
        purview_client.approve_task(task_id=request.task_id, comment=comment)
        logger.info("Purview task approved successfully")
    except Exception as purview_exc:
        # Fabric access was granted — don't fail the function just because
        # the Purview callback had an issue.
        logger.warning(
            "Purview approve callback failed (access was still granted) | error=%s\n%s",
            purview_exc,
            traceback.format_exc(),
        )


def _handle_permanent_failure(
    request: AccessRequestMessage | None,
    exc: Exception,
) -> None:
    """Reject the Purview workflow task after a non-retryable failure."""
    error_message = str(exc)
    logger.error("Permanent provisioning failure | error=%s", error_message)

    if request is None:
        logger.error("Cannot callback to Purview — request was not parsed")
        return

    comment = f"Failed to provision access: {error_message}"

    try:
        credentials = get_spn_credentials_from_keyvault()
        purview_token = get_purview_token(credentials)
        purview_client = PurviewWorkflowClient(
            account_name=_get_purview_account_name(),
            access_token=purview_token,
        )
        purview_client.reject_task(task_id=request.task_id, comment=comment)
        logger.info("Purview task rejected successfully")
    except Exception as purview_exc:
        logger.warning(
            "Purview reject callback failed | error=%s\n%s",
            purview_exc,
            traceback.format_exc(),
        )

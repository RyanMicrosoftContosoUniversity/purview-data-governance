"""HTTP trigger: creates a stub ServiceNow ticket and stores it in Table Storage."""

import json
import logging
import uuid
from datetime import datetime, timezone

import azure.functions as func

from ..table_helper import upsert_ticket

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "request_id",
    "workflow_run_id",
    "task_id",
    "requestor_email",
    "requestor_object_id",
    "target_workspace_id",
    "requested_role",
]

VALID_ROLES = {"Viewer", "Contributor", "Member", "Admin"}


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Create a stub ServiceNow ticket from a Purview access-request payload.

    Generates a ``STUB-<short-uuid>`` ticket ID, persists the ticket in
    Azure Table Storage with status ``pending``, and returns the ticket
    metadata as JSON.
    """
    logger.info("create_ticket: received request  method=%s  url=%s", req.method, req.url)

    # --- Parse body -----------------------------------------------------------
    try:
        body: dict = req.get_json()
    except ValueError:
        logger.warning("create_ticket: invalid JSON body")
        return func.HttpResponse(
            json.dumps({"error": "Request body must be valid JSON."}),
            status_code=400,
            mimetype="application/json",
        )

    # --- Validate required fields --------------------------------------------
    missing = [f for f in REQUIRED_FIELDS if not body.get(f)]
    if missing:
        logger.warning("create_ticket: missing fields %s", missing)
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {missing}"}),
            status_code=400,
            mimetype="application/json",
        )

    requested_role: str = body["requested_role"]
    if requested_role not in VALID_ROLES:
        logger.warning("create_ticket: invalid role '%s'", requested_role)
        return func.HttpResponse(
            json.dumps({"error": f"Invalid requested_role '{requested_role}'. Must be one of {sorted(VALID_ROLES)}."}),
            status_code=400,
            mimetype="application/json",
        )

    # --- Generate ticket ------------------------------------------------------
    short_id = uuid.uuid4().hex[:8]
    ticket_id = f"STUB-{short_id}"
    now = datetime.now(timezone.utc).isoformat()

    entity = {
        "PartitionKey": "tickets",
        "RowKey": ticket_id,
        "request_id": body["request_id"],
        "workflow_run_id": body["workflow_run_id"],
        "task_id": body["task_id"],
        "requestor_email": body["requestor_email"],
        "requestor_object_id": body["requestor_object_id"],
        "target_workspace_id": body["target_workspace_id"],
        "requested_role": requested_role,
        "callback_url": body.get("callback_url", ""),
        "status": "pending",
        "created_at": now,
    }

    try:
        upsert_ticket(entity)
    except Exception as exc:
        logger.exception("create_ticket: failed to persist ticket %s", ticket_id)
        return func.HttpResponse(
            json.dumps({"error": f"Internal storage error: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    response_body = {
        "ticket_id": ticket_id,
        "status": "pending",
        "message": "ServiceNow ticket created (STUB). Auto-approval will occur on next timer run.",
        "created_at": now,
    }

    logger.info("create_ticket: created ticket %s for request %s", ticket_id, body["request_id"])
    return func.HttpResponse(
        json.dumps(response_body),
        status_code=201,
        mimetype="application/json",
    )

"""HTTP trigger: force-approve a specific stub ticket and enqueue the access-request message."""

import base64
import json
import logging
import os
from datetime import datetime, timezone

import azure.functions as func
from azure.storage.queue import QueueClient

from ..table_helper import get_ticket, upsert_ticket

logger = logging.getLogger(__name__)

QUEUE_NAME = "purview-access-requests"


def _get_queue_client() -> QueueClient:
    """Return a QueueClient for the access-request queue, creating it if needed."""
    conn_str = os.environ["AzureWebJobsStorage"]
    client = QueueClient.from_connection_string(conn_str, QUEUE_NAME)
    client.create_queue()
    return client


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Force-approve a single stub ticket by ``ticket_id``.

    Looks up the ticket in Table Storage, marks it approved, and enqueues
    an ``AccessRequestMessage`` to the ``purview-access-requests`` queue.
    """
    logger.info("approval_callback: received request  method=%s  url=%s", req.method, req.url)

    # --- Parse body -----------------------------------------------------------
    try:
        body: dict = req.get_json()
    except ValueError:
        logger.warning("approval_callback: invalid JSON body")
        return func.HttpResponse(
            json.dumps({"error": "Request body must be valid JSON."}),
            status_code=400,
            mimetype="application/json",
        )

    ticket_id: str | None = body.get("ticket_id")
    if not ticket_id:
        logger.warning("approval_callback: missing ticket_id")
        return func.HttpResponse(
            json.dumps({"error": "Missing required field: ticket_id"}),
            status_code=400,
            mimetype="application/json",
        )

    # --- Look up ticket -------------------------------------------------------
    ticket = get_ticket(ticket_id)
    if ticket is None:
        logger.warning("approval_callback: ticket %s not found", ticket_id)
        return func.HttpResponse(
            json.dumps({"error": f"Ticket '{ticket_id}' not found."}),
            status_code=404,
            mimetype="application/json",
        )

    if ticket.get("status") == "approved":
        logger.info("approval_callback: ticket %s already approved", ticket_id)
        return func.HttpResponse(
            json.dumps({"ticket_id": ticket_id, "status": "approved", "message": "Ticket was already approved."}),
            status_code=200,
            mimetype="application/json",
        )

    # --- Approve and enqueue --------------------------------------------------
    now = datetime.now(timezone.utc).isoformat()
    try:
        ticket["status"] = "approved"
        ticket["approved_at"] = now
        upsert_ticket(ticket)

        queue_message = json.dumps({
            "request_id": ticket["request_id"],
            "workflow_run_id": ticket["workflow_run_id"],
            "task_id": ticket["task_id"],
            "requestor_object_id": ticket["requestor_object_id"],
            "requestor_email": ticket["requestor_email"],
            "target_workspace_id": ticket["target_workspace_id"],
            "requested_role": ticket["requested_role"],
            "servicenow_ticket_id": ticket_id,
            "approved_at": now,
        })
        encoded = base64.b64encode(queue_message.encode("utf-8")).decode("utf-8")

        queue_client = _get_queue_client()
        queue_client.send_message(encoded)

        logger.info("approval_callback: approved ticket %s and enqueued message", ticket_id)
    except Exception as exc:
        logger.exception("approval_callback: failed to approve ticket %s", ticket_id)
        return func.HttpResponse(
            json.dumps({"error": f"Internal error approving ticket: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps({
            "ticket_id": ticket_id,
            "status": "approved",
            "message": "Ticket approved and access-request message enqueued.",
            "approved_at": now,
        }),
        status_code=200,
        mimetype="application/json",
    )

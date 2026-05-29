"""Timer trigger: auto-approves pending stub tickets and enqueues access-request messages."""

import base64
import json
import logging
import os
from datetime import datetime, timezone

import azure.functions as func
from azure.storage.queue import QueueClient

from ..table_helper import query_pending_tickets, upsert_ticket

logger = logging.getLogger(__name__)

QUEUE_NAME = "purview-access-requests"


def _get_queue_client() -> QueueClient:
    """Return a QueueClient for the access-request queue, creating it if needed."""
    conn_str = os.environ["AzureWebJobsStorage"]
    client = QueueClient.from_connection_string(conn_str, QUEUE_NAME)
    client.create_queue()  # no-op if exists
    return client


def _build_queue_message(ticket: dict) -> str:
    """Build an AccessRequestMessage JSON string from a ticket entity."""
    now = datetime.now(timezone.utc).isoformat()
    message = {
        "request_id": ticket["request_id"],
        "workflow_run_id": ticket["workflow_run_id"],
        "task_id": ticket["task_id"],
        "requestor_object_id": ticket["requestor_object_id"],
        "requestor_email": ticket["requestor_email"],
        "target_workspace_id": ticket["target_workspace_id"],
        "requested_role": ticket["requested_role"],
        "servicenow_ticket_id": ticket["RowKey"],
        "approved_at": now,
    }
    return json.dumps(message)


def main(timer: func.TimerRequest) -> None:
    """Approve all pending stub tickets and enqueue access-request messages.

    Runs on a 2-minute timer schedule.  For each pending ticket the function:
    1. Marks the ticket as ``approved`` in Table Storage.
    2. Builds an ``AccessRequestMessage`` JSON payload.
    3. Base64-encodes and enqueues the message to the
       ``purview-access-requests`` Storage Queue.
    """
    logger.info("approve_tickets: timer fired  past_due=%s", timer.past_due)

    pending = query_pending_tickets()
    if not pending:
        logger.info("approve_tickets: no pending tickets found")
        return

    logger.info("approve_tickets: found %d pending ticket(s)", len(pending))
    queue_client = _get_queue_client()
    approved_count = 0

    for ticket in pending:
        ticket_id: str = ticket["RowKey"]
        try:
            # Mark approved in table storage
            ticket["status"] = "approved"
            ticket["approved_at"] = datetime.now(timezone.utc).isoformat()
            upsert_ticket(ticket)

            # Enqueue base64-encoded message
            raw_message = _build_queue_message(ticket)
            encoded = base64.b64encode(raw_message.encode("utf-8")).decode("utf-8")
            queue_client.send_message(encoded)

            approved_count += 1
            logger.info(
                "approve_tickets: approved ticket %s  request_id=%s",
                ticket_id,
                ticket.get("request_id"),
            )
        except Exception:
            logger.exception("approve_tickets: failed to approve ticket %s", ticket_id)

    logger.info("approve_tickets: completed  approved=%d/%d", approved_count, len(pending))

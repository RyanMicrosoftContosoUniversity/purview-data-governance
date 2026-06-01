"""Helper for Azure Table Storage operations on the servicenowstubtickets table."""

import logging
import os
from typing import Any, Optional

from azure.data.tables import TableClient, TableServiceClient

logger = logging.getLogger(__name__)

TABLE_NAME = "servicenowstubtickets"
PARTITION_KEY = "tickets"


def _get_table_client() -> TableClient:
    """Return a TableClient, creating the table if it doesn't exist."""
    conn_str = os.environ["AzureWebJobsStorage"]
    service = TableServiceClient.from_connection_string(conn_str)
    service.create_table_if_not_exists(TABLE_NAME)
    return service.get_table_client(TABLE_NAME)


def upsert_ticket(entity: dict[str, Any]) -> None:
    """Insert or update a ticket entity in Table Storage."""
    entity.setdefault("PartitionKey", PARTITION_KEY)
    client = _get_table_client()
    client.upsert_entity(entity)
    logger.info("Upserted ticket %s in table storage", entity.get("RowKey"))


def get_ticket(ticket_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a single ticket by its ID (RowKey)."""
    client = _get_table_client()
    try:
        return client.get_entity(partition_key=PARTITION_KEY, row_key=ticket_id)
    except Exception:
        logger.warning("Ticket %s not found in table storage", ticket_id)
        return None


def query_pending_tickets() -> list[dict[str, Any]]:
    """Return all tickets with status 'pending'."""
    client = _get_table_client()
    query = f"PartitionKey eq '{PARTITION_KEY}' and status eq 'pending'"
    return list(client.query_entities(query))

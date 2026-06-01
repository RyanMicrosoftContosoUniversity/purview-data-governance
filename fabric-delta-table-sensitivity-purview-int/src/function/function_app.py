"""Azure Functions v2 entry point.

Registers the `classify_assets` and `sync_classification` Event Hub triggers.
All business logic lives in the respective handler modules; this file is a thin
decorator layer so the host can discover the functions via worker indexing.
"""

from __future__ import annotations
from typing import List
import azure.functions as func
from classify_assets.handler import classify_assets_impl
from sync_classification.handler import sync_classification_impl


app = func.FunctionApp()


@app.function_name(name='classify_assets')
@app.event_hub_message_trigger(
    arg_name='events',
    event_hub_name='purview-scan-status',
    connection='PurviewEvents',
    cardinality='many',
    consumer_group='$Default',
)
def classify_assets(events: List[func.EventHubEvent]) -> None:
    classify_assets_impl(events)


@app.function_name(name='sync_classification')
@app.event_hub_message_trigger(
    arg_name='events',
    event_hub_name='atlas-notifications',  # Must match Terraform atlas_notification_eventhub_name.
    connection='PurviewEvents',
    cardinality='many',
    consumer_group='$Default',
)
def sync_classification(events: List[func.EventHubEvent]) -> None:
    sync_classification_impl(events)

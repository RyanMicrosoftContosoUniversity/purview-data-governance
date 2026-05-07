"""Azure Functions v2 entry point.

Registers the `classify_assets` Event Hub trigger. All business logic lives in
`classify_assets/handler.py`; this file is a thin decorator layer so the host
can discover the function via worker indexing.
"""

from __future__ import annotations
from typing import List
import azure.functions as func
from classify_assets.handler import classify_assets_impl


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

# create resource group
az group create --name fabric-monitoring-rg --location eastus

# create event hub namespace
az eventhubs namespace create  \
    --resource-group fabric-monitoring-rg \
    --name fabric-telemetry-ehns \
    --location eastus \
    --sku Standard \
    -- capacity 2

# create event hub
az eventhubs eventhub create \
    --resource-group fabric-monitoring-rg \
    --namespace-name fabric-telemetry-ehns \
    --name fabric-telemetry-eh \
    --cleanup-policy Delete \
    --retention-time-in-hours 1 \
    --partition-count 4


PENTEST_STATES = {
    "Scheduled": "scheduled",
    "Provisioning": "provisioning",
    "Ready": "ready",
    "Running": "running",
    "Complete": "complete",
    "Post-Processing": "post-processing",
    "Done": "done",
    "Cancelling": "cancelling",
    "Canceled": "canceled",
    "Paused": "paused",
    "Error": "error"
}

# Date field mappings
DATE_FIELDS = {
    "Launch Date": "launched_at",
    "Completion Date": "completed_at",
    "Schedule Date": "scheduled_at",
    "Cancellation Date": "canceled_at"
}

# Sorting field mappings
ORDER_BY_FIELDS = {
    "Operation Name": "name",
    "Status": "state",
    "Client": "client_name",
    "Launch Date": "launched_at",
    "Completion Date": "completed_at",
    "Impact Count": "impacts_count",
    "Attack Path Count": "attack_paths_count"
}

# Sort direction mappings
SORT_DIRECTIONS = {
    "Ascending": "ASC",
    "Descending": "DESC"
}

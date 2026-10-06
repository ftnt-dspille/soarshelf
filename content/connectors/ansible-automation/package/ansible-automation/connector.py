"""FortiSOAR connector adapter. Thin: maps operation names to functions in
operations.py. All real logic lives in the pydantic-typed, Django-free modules."""

from connectors.core.connector import Connector, get_logger

from .constants import LOGGER_NAME
from .operations import (
    cancel_run,
    check_health,
    get_run_artifacts,
    get_run_status,
    install_collection,
    list_collections,
    list_modules,
    run_module,
    run_playbook,
    run_role,
    validate_playbook,
)

logger = get_logger(LOGGER_NAME)

OPERATIONS = {
    "run_playbook": run_playbook,
    "run_module": run_module,
    "run_role": run_role,
    "get_run_status": get_run_status,
    "get_run_artifacts": get_run_artifacts,
    "cancel_run": cancel_run,
    "validate_playbook": validate_playbook,
    "list_collections": list_collections,
    "install_collection": install_collection,
    "list_modules": list_modules,
}


class AnsibleAutomation(Connector):
    def execute(self, config, operation, params, **kwargs):
        action = OPERATIONS.get(operation)
        if action is None:
            raise ValueError(f"Unsupported operation: {operation}")
        return action(config, dict(params or {}))

    def check_health(self, config):
        return check_health(config)

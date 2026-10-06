from connectors.core.connector import Connector, ConnectorError, get_logger

from .operations import check_health, operations

logger = get_logger("code-runner")


class CodeRunner(Connector):
    def execute(self, config, operation, params, **kwargs):
        logger.info(f"In execute() Operation:[{operation}]")
        op = operations.get(operation, None)
        if not op:
            logger.error(f"Unsupported operation [{operation}]")
            raise ConnectorError(f"Unsupported operation: {operation}")
        return op(config, params)

    def check_health(self, config):
        return check_health(config)

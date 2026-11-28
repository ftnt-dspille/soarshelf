from connectors.core.connector import Connector, get_logger

from .operations import operations, check_health_ex

logger = get_logger('microsoft-office-365-feed-v2')


class MicrosoftOffice365Feed(Connector):
    def execute(self, config, operation, params, **kwargs):
        action = operations.get(operation)
        if action is None:
            raise ValueError('Unknown operation: {0}'.format(operation))
        logger.info('Executing action {0}'.format(operation))
        return action(config, params or {}, **kwargs)

    def check_health(self, config, **kwargs):
        return check_health_ex(config)

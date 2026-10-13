from connectors.core.connector import Connector, get_logger

from .operations import operations, _check_health

logger = get_logger('hashicorp-vault-kv')


class VaultKV(Connector):
    def execute(self, config, operation, params, **kwargs):
        action = operations.get(operation)
        if action is None:
            raise ValueError('Unknown operation: {0}'.format(operation))
        logger.info('Executing action {0}'.format(operation))
        return action(config, params)

    def check_health(self, config):
        return _check_health(config)

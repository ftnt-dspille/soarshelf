"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""
from connectors.core.connector import Connector, ConnectorError, get_logger

from .operations import check_health, operations

logger = get_logger('jirav2')


class JiraV2(Connector):
    def execute(self, config, operation, params, **kwargs):
        action = operations.get(operation)
        if action is None:
            raise ConnectorError('Unsupported operation: %s' % operation)
        try:
            return action(config, params or {})
        except ConnectorError:
            raise
        except Exception as err:
            logger.exception('Operation %s failed', operation)
            raise ConnectorError('%s failed: %s' % (operation, err))

    def check_health(self, config):
        try:
            return check_health(config)
        except ConnectorError:
            raise
        except Exception as err:
            logger.exception('Health check failed')
            raise ConnectorError('Health check failed: %s' % err)

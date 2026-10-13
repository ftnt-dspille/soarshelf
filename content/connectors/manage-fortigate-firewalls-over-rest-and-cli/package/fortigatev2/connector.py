""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """
from connectors.core.connector import Connector, ConnectorError, get_logger

from .operation import check_health, fortigate_operations

logger = get_logger('fortigatev2')


class FortiGate(Connector):
    def execute(self, config, operation, params, **kwargs):
        try:
            logger.info('In execute() Operation:[{}]'.format(operation))
            action = fortigate_operations.get(operation)
            if action is None:
                raise ConnectorError('Unsupported operation: {}'.format(operation))
            return action(config, params)
        except Exception as e:
            logger.error('Error in Operation:[{0}] \n{1}'.format(operation, str(e)))
            raise ConnectorError(e)

    def check_health(self, config):
        try:
            return check_health(config)
        except Exception as e:
            raise ConnectorError(e)

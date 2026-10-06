""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import Connector, get_logger, ConnectorError
from .operations import check_health, aws_operations

logger = get_logger('aws')

class AWS(Connector):
    def execute(self, config, operation, params, **kwargs):
        try:
            logger.info('In execute() Operation:[{}]'.format(operation))
            operation = aws_operations.get(operation, None)
            if not operation:
                logger.info('Unsupported operation [{}]'.format(operation))
                raise ConnectorError('Unsupported operation')
            result = operation(config, params)
            return result
        except Exception as err:
            logger.exception(err)
            if 'UnauthorizedOperation' in str(err):
                raise ConnectorError('An error occurred (UnauthorizedOperation) when calling the {0} operation: '
                                     'You are not authorized to perform this operation'.format(operation))
            raise ConnectorError(err)

    def check_health(self, config):
        return check_health(config)

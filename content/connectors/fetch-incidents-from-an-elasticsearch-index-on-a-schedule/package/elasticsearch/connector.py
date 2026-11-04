""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import Connector
from connectors.core.connector import get_logger, ConnectorError
from .operations import operations, check_health

logger = get_logger('elasticsearch_cs')


class Elasticsearch_cs(Connector):
    def execute(self, config, operation, params, **kwargs):
        try:
            action = operations.get(operation)
            if (isinstance(params, list) and len(params) == 0):
                result = action(config)
            else:
                result = action(config, params)
            return result
        except Exception as Err:
            logger.error('Exception occurred: {}'.format(Err))
            raise ConnectorError(Err)

    def check_health(self, config):
        return check_health(config)

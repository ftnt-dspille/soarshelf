"""
Copyright start
MIT License
Copyright (c) 2025   Fortinet Inc
Copyright end
"""

from connectors.core.connector import Connector
from connectors.core.connector import get_logger, ConnectorError
from .operations import check_health, operations
from integrations.crudhub import make_request
from django.conf import settings
from .constants import MACRO_LIST


logger = get_logger('group-ib-threat-intelligence-attribution-feed')


class GroupIB(Connector):
    def execute(self, config, operation, params, **kwargs):
        try:
            # Handle incoming parameters structure variability to prevent 400 API exceptions
            if isinstance(params, list) or not params:
                params = {}
                
            operation_func = operations.get(operation)
            if not operation_func:
                raise ConnectorError(f"Unsupported operational action: {operation}")
                
            return operation_func(config, params)
        except Exception as Err:
            raise ConnectorError(Err)

    def check_health(self, config):
        return check_health(config)

    def del_micro(self, config):
        if not settings.LW_AGENT:
            for macro in MACRO_LIST:
                try:
                    resp = make_request(f'/api/wf/api/dynamic-variable/?name={macro}', 'GET')
                    if resp['hydra:member']:
                        logger.info("resetting global variable '%s'" % macro)
                        macro_id = resp['hydra:member'][0]['id']
                        resp = make_request(f'/api/wf/api/dynamic-variable/{macro_id}/?format=json', 'DELETE')
                except Exception as e:
                    logger.error(e)

    def on_deactivate(self, config):
        self.del_micro(config)

    def on_activate(self, config):
        self.del_micro(config)

    def on_add_config(self, config, active):
        self.del_micro(config)

    def on_delete_config(self, config):
        self.del_micro(config)
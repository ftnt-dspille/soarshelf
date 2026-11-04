"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""

from connectors.core.connector import Connector, get_logger, ConnectorError
from .operations import operations, _check_health, API_VERSION, AUTH_BEHALF_OF_USER
from connectors.core.utils import update_connnector_config
logger = get_logger('microsoft-graph')


class MicrosoftGraph(Connector):

    def execute(self, config, operation, params, **kwargs):
        try:
            config['connector_info'] = {"connector_name": self._info_json.get('name'),
                                        "connector_version": self._info_json.get('version')}
            config['api_version'] = API_VERSION
            action = operations.get(operation)
            return action(config, params)
        except Exception as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(e))

    def check_health(self, config):
        config['connector_info'] = {"connector_name": self._info_json.get('name'),
                                    "connector_version": self._info_json.get('version')}
        return _check_health(config)

    def on_update_config(self, old_config, new_config, active):
        connector_info = {"connector_name": self._info_json.get('name'),
                          "connector_version": self._info_json.get('version')}

        if new_config.get('auth_type', '') == AUTH_BEHALF_OF_USER:
            old_auth_code = old_config.get('code')
            new_auth_code = new_config.get('code')
            if old_auth_code != new_auth_code:
                new_config.pop('accessToken', '')
            else:
                new_config['accessToken'] = old_config.get('accessToken')
                new_config['expiresOn'] = old_config.get('expiresOn')
            update_connnector_config(connector_info['connector_name'], connector_info['connector_version'], new_config,
                                 new_config['config_id'])

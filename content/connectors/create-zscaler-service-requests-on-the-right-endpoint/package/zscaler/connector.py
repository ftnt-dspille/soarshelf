""" Copyright start
  Copyright (C) 2008 - 2026 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import Connector, get_logger, ConnectorError
from .operations import ZscalerConnector

logger = get_logger("zscaler")


class Zscaler(Connector):
    def execute(self, config, operation, params, **kwargs):
        logger.info('In execute() Operation:[{}]'.format(operation))
        try:
            zs = ZscalerConnector(config)
            operations = {
                'get_whitelist_urls': zs.get_whitelist_urls,
                'get_blacklist_urls': zs.get_blacklist_urls,
                'update_whitelist_urls': zs.update_whitelist_urls,
                'block_url': zs.block_url,
                'unblock_url': zs.unblock_url,
                'get_sandbox_report_quota': zs.get_sandbox_report_quota,
                'get_sandbox_report_md5_hash': zs.get_sandbox_report_md5_hash,
                'get_url_categories': zs.get_url_categories,
                'add_new_category': zs.add_new_category,
                'get_lightweight_url_categories': zs.get_lightweight_url_categories,
                'get_url_categories_quota': zs.get_url_categories_quota,
                'get_url_category_info': zs.get_url_category_info,
                'update_url_category': zs.update_url_category,
                'delete_url_category': zs.delete_url_category,
                'url_lookup': zs.url_lookup,
                'get_exempted_urls': zs.get_exempted_urls,
                'update_exempted_urls': zs.update_exempted_urls
            }
            connector_info = {"connector_name": self._info_json.get('name'),
                              "connector_version": self._info_json.get('version')}
            operation = operations.get(operation)
            return operation(config, params, connector_info)
        except Exception as err:
            logger.exception('{0}'.format(str(err)))
            raise ConnectorError('{0}'.format(err))

    def check_health(self, config):
        zs = ZscalerConnector(config)
        connector_info = {"connector_name": self._info_json.get('name'),
                          "connector_version": self._info_json.get('version')}
        return zs.check_health(config, connector_info)

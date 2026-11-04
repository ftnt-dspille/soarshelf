""" Copyright start
  Copyright (C) 2008 - 2026 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from .zscaler_api_auth import *
import json, requests, time
from connectors.core.connector import get_logger, ConnectorError
from urllib.parse import urlparse

logger = get_logger("zscaler")

error_msgs = {
    400: 'Bad/Invalid Request',
    401: 'Unauthorized: Invalid credentials or token provided failed to authorize',
    403: 'Access Denied',
    404: 'Not Found',
    500: 'Internal Server Error',
    503: 'Service Unavailable',
    'time_out': 'The request timed out while trying to connect to the remote server',
    'ssl_error': 'SSL certificate validation failed'
}


class ZscalerConnector(object):
    def __init__(self, config):
        self.server_url = config.get('server_url').strip('/')
        if not self.server_url.startswith('https://'):
            self.server_url = 'https://' + self.server_url
        self.username = config.get('username')
        self.password = config.get('password')
        self.api_key = config.get('api_key')
        self.verify_ssl = config.get('verify_ssl', False)
        self.log = logger
        self.JSESSIONID = None
        self.headers = {'content-type': "application/json"}

    def obfuscate_api_key(self):
        seed = self.api_key
        now = str(int(time.time() * 1000))
        n = now[-6:]
        r = str(int(n) >> 1).zfill(6)
        key = ""
        for i in range(0, len(n), 1):
            key += seed[int(n[i])]
        for j in range(0, len(r), 1):
            key += seed[int(r[j]) + 2]
        return now, key

    def make_rest_call(self, config, connector_info, endpoint, default_headers=None, payload=None, params=None,
                       method='GET'):
        authentication_type = config.get('authentication_type')
        if authentication_type == 'OAuth Authentication':
            zscaler_obj = ZscalerAuth(config)
            token = zscaler_obj.validate_token(config, connector_info)
            self.headers['Authorization'] = token
        else:
            if default_headers:
                self.headers = default_headers
            else:
                self.JSESSIONID if self.JSESSIONID else self.start_session(config, connector_info)
                if self.JSESSIONID:
                    self.headers.update({'cookie': self.JSESSIONID})
        try:
            service_endpoint = '{0}'.format(self.server_url) + '{0}'.format(endpoint)
            self.log.debug("Service endpoint: {0}".format(service_endpoint))
            self.log.debug("API Request Payload: {0}".format(payload))
            response = requests.request(method, service_endpoint, headers=self.headers, params=params, data=payload,
                                        verify=self.verify_ssl)
            self.log.debug("API Response Status Code: {0}".format(response.status_code))
            self.log.debug("API Response: {0}".format(response.text))
            if response.ok:
                if default_headers and method.lower() == "post":
                    if not self.JSESSIONID:
                        self.JSESSIONID = response.headers['Set-Cookie']
                content_type = response.headers.get('Content-Type')
                resp_data = response.content

                if resp_data:
                    if 'application/json' in content_type:
                        return response.json()
                    else:
                        return response.text
            else:
                if error_msgs[response.status_code]:
                    raise ConnectorError('{0}: {1}'.format(error_msgs.get(response.status_code), response.text))
        except requests.exceptions.SSLError as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(error_msgs['ssl_error']))
        except requests.exceptions.ConnectionError as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(error_msgs['time_out']))
        except Exception as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(e))

    def check_health(self, config, connector_info):
        try:
            authentication_type = config.get('authentication_type')
            if authentication_type == 'OAuth Authentication':
                check(config, connector_info)
            else:
                zscaler_obj = ZscalerConnector(config)
                zscaler_obj.test_connectivity(config, connector_info)
        except Exception as error:
            logger.exception('An exception occurred {}'.format(str(error)))
            raise ConnectorError(error)

    def start_session(self, config, connector_info):
        timestamp, obfuscate_key = self.obfuscate_api_key()
        payload = {"username": self.username, "password": self.password, "apiKey": obfuscate_key,
                   "timestamp": timestamp}
        json_data = json.dumps(payload)
        self.make_rest_call(config, connector_info, "/api/v1/authenticatedSession", default_headers=self.headers,
                            payload=json_data,
                            method='POST')
        if self.JSESSIONID:
            self.log.info('Session created successfully')
        else:
            self.log.error('Error in start session')

    def stop_session(self, config, connector_info):
        if self.JSESSIONID:
            self.headers.update({'cookie': self.JSESSIONID})
        response = self.make_rest_call(config, connector_info, '/api/v1/authenticatedSession',
                                       default_headers=self.headers, method='DELETE')
        if response:
            self.JSESSIONID = None
            self.log.info('Successfully stop Zscaler session')

    def build_payload(self, params):
        result = {k: v for k, v in params.items() if v is not None and v != ''}
        return result

    def get_whitelist_urls(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, "/api/v1/security")
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_blacklist_urls(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, "/api/v1/security/advanced")
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def block_url(self, config, params, connector_info):
        urls = params.get('urls')
        if urls and isinstance(urls, str):
            urls = urls.split(',')
        data = {
            'blacklistUrls': urls
        }
        resp = self.make_rest_call(config, connector_info, "/api/v1/security/advanced/blacklistUrls?action=ADD_TO_LIST",
                                   payload=json.dumps(data), method='POST')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        if not resp:
            return {'status': 'success', 'result': 'URLs successfully Blocked'}
        else:
            return resp

    def unblock_url(self, config, params, connector_info):
        list_urls = params.get('urls')
        if list_urls and isinstance(list_urls, str):
            list_urls = list_urls.split(',')
        data = {
            'blacklistUrls': list_urls
        }
        resp = self.make_rest_call(config, connector_info,
                                   '/api/v1/security/advanced/blacklistUrls?action=REMOVE_FROM_LIST',
                                   payload=json.dumps(data), method='POST')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        if not resp:
            return {'status': 'success', 'result': 'URLs successfully Unblocked'}
        else:
            return resp

    def update_whitelist_urls(self, config, params, connector_info):
        action_type = {'Add in List': 'ADD_IN_LIST', 'Remove from List': 'REMOVE_FROM_LIST'}
        list_urls = params.get('urls')
        if list_urls and isinstance(list_urls, str):
            list_urls = list_urls.split(',')
        action = action_type[params.get('action')]
        response = self.get_whitelist_urls(config, params, connector_info)
        whitelist = response.get('whitelistUrls')
        if action == 'ADD_IN_LIST':
            filter_urls = list(set(whitelist) | set(list_urls))
        else:
            filter_urls = list(set(whitelist) - set(list_urls))
        payload = {'whitelistUrls': filter_urls}
        response = self.make_rest_call(config, connector_info, '/api/v1/security', payload=json.dumps(payload),
                                       method='PUT')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_sandbox_report_quota(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, '/api/v1/sandbox/report/quota')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_sandbox_report_md5_hash(self, config, params, connector_info):
        report_type = {"Full": "full", "Summary": "summary"}
        details = report_type[params.get('details')]

        endpoint = "/api/v1/sandbox/report/{md5Hash}".format(md5Hash=params.get('md5Hash'))
        if params.get('details'):
            endpoint += "?details={details}".format(details=details)

        response = self.make_rest_call(config, connector_info, endpoint)
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_url_categories(self, config, params, connector_info):
        result = self.build_payload(params)
        if result:
            response = self.make_rest_call(config, connector_info, '/api/v1/urlCategories', params=result)
        else:
            response = self.make_rest_call(config, connector_info, '/api/v1/urlCategories')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def add_new_category(self, config, params, connector_info):
        list_urls = params.get('urls').split(',') if isinstance(params.get('urls'), str) else params.get('urls')
        other_fields = params.get('other_fields')
        other_fields.update({'urls': list_urls})
        response = self.make_rest_call(config, connector_info, '/api/v1/urlCategories',
                                       payload=json.dumps(other_fields), method='POST')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_lightweight_url_categories(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, '/api/v1/urlCategories/lite')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_url_categories_quota(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, '/api/v1/urlCategories/urlQuota')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_url_category_info(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info,
                                       '/api/v1/urlCategories/{categoryId}'.format(categoryId=params.get('categoryId')))
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_category_by_id(self, category_id, config, connector_info):
        categories = self.make_rest_call(config, connector_info, '/api/v1/urlCategories')
        for category in categories:
            if category['id'] == category_id:
                return category
        return None

    def validate_urls(self, list_urls):
        """Updating URLs on for specific Category, A url starting with https or http. For Zscaler the REST API does not
        support updating URLs, For this reason removing https and http from urls."""
        urls = []
        for url in list_urls:
            parse_object = urlparse(url)
            if parse_object.scheme:
                urls.append(parse_object.netloc + parse_object.path)
            else:
                urls.append(parse_object.path)
        urls = list(set(urls))
        return urls

    def update_url_category(self, config, params, connector_info):
        action_type = {'Add to List': 'ADD_TO_LIST', 'Remove from List': 'REMOVE_FROM_LIST'}
        list_urls = params.get('urls').split(',') if isinstance(params.get('urls'), str) else params.get('urls')
        other_fields = params.pop('other_fields', '')
        action = params.pop('action', '')
        category_id = params.pop('categoryId', '')
        payload = self.build_payload(params)
        if other_fields:
            payload.update(other_fields)
        action = action_type.get(action)
        list_urls = list(filter(lambda x: x.strip() != '', list_urls))
        urls = self.validate_urls(list_urls)
        payload.update({'urls': urls})
        endpoint = '/api/v1/urlCategories/{categoryId}?action={action}'.format(categoryId=category_id, action=action)
        response = self.make_rest_call(config, connector_info, endpoint, payload=json.dumps(payload), method='PUT')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def delete_url_category(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info,
                                       '/api/v1/urlCategories/{categoryId}'.format(categoryId=params.get('categoryId')),
                                       method='DELETE')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def url_lookup(self, config, params, connector_info):
        list_urls = params.get('urls').split(',') if isinstance(params.get('urls'), str) else params.get('urls')
        urls = json.dumps(list_urls)
        response = self.make_rest_call(config, connector_info, '/api/v1/urlLookup', payload=urls, method='POST')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def get_exempted_urls(self, config, params, connector_info):
        response = self.make_rest_call(config, connector_info, '/api/v1/authSettings/exemptedUrls')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def update_exempted_urls(self, config, params, connector_info):
        action_type = {'Add to List': 'ADD_TO_LIST', 'Remove from List': 'REMOVE_FROM_LIST'}

        action = action_type[params.get('action')]

        response = self.make_rest_call(config, connector_info,
                                       '/api/v1/urlCategories/{categoryId}?action={action}'.format(
                                           categoryId=params.get('categoryId'),
                                           action=action),
                                       method='POST')
        if config.get('authentication_type') == 'Basic Authentication':
            self.stop_session(config, connector_info)
        return response

    def test_connectivity(self, config, connector_info):
        try:
            self.start_session(config, connector_info)
            if self.JSESSIONID:
                self.log.info('connector available')
                if config.get('authentication_type') == 'Basic Authentication':
                    self.stop_session(config, connector_info)
                return True
        except Exception as err:
            logger.exception("{0}".format(err))
            raise ConnectorError("{0}".format(err))

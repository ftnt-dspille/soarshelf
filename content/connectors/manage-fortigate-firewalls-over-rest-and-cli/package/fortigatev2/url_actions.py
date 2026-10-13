""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """


from connectors.core.connector import ConnectorError, get_logger

from .constants import *
from .utils import *
from .utils import _api_request, _get_list_from_str_or_list, _path, _validate_vdom

logger = get_logger('fortigatev2')


def block_url(config, params):
    try:
        result = {'already_blocked': [], 'newly_blocked': [], 'not_block': []}
        current_urls = []
        profile_name = config.get('url_block_policy')
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
        url_filter_details = get_web_filter(config, params)
        list_urls = url_filter_details.get("results")[0].get("entries") if url_filter_details.get("results") else []
        url_names = [i.get('url') for i in list_urls]
        urls = _get_list_from_str_or_list(params, "url")
        for url in urls:
            if url in url_names:
                result['already_blocked'].append(url)
                continue
            payload = {
                "status": "enable",
                "exempt": "av web-content activex-java-cookie dlp fortiguard range-block all",
                "web-proxy-profile": "",
                "action": "block",
                "type": "simple",
                "url": url,
                "referrer-host": "",
            }
            current_urls.append(url)
            list_urls.append(payload)
        if not current_urls:
            return result
        url_profile_id = url_filter_details.get('mkey')
        if url_profile_id is None:
            response = _create_url_filter_table(config, profile_name, list_urls, vdom_list)
        else:
            url_filter_payload = {
                "id": url_profile_id,
                "name": profile_name,
                "entries": list_urls
            }
            response = _api_request(config, URL_FILTER + '/' + str(url_profile_id),
                                    method="put", body=url_filter_payload, parameters={'vdom': vdom_list})
        if response.get("status") == "success":
            result.update({'newly_blocked': current_urls})
        else:
            result.update({'not_block': current_urls})
        return result
    except Exception as Err:
        if '500' in str(Err):
            msg = {"ERROR": 500,
                   "Response": "Please input a valid URL. Examples: example.com, example.com/help, 192.168.1.1"}
            raise ConnectorError(msg)
        raise ConnectorError(Err)


def unblock_url(config, params):
    try:
        result = {'not_exist': [], 'newly_unblocked': [], 'not_unblock': []}
        user_urls = _get_list_from_str_or_list(params, "url")
        profile_name = config.get('url_block_policy')
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
        url_filter_details = get_web_filter(config, params)
        list_urls = url_filter_details.get("results")[0].get("entries") if url_filter_details.get("results") else []
        url_names = [i.get('url') for i in list_urls]
        result['not_exist'] = list(filter(lambda x: x not in url_names, user_urls))
        current_urls = list(filter(lambda x: x in url_names, user_urls))
        if not current_urls:
            return result
        for url in current_urls:
            list_urls = list(filter(lambda x: x['url'] != url, list_urls))
        url_profile_id = url_filter_details.get('mkey')
        url_filter_payload = {
            "id": url_profile_id,
            "name": profile_name,
            "entries": list_urls
        }
        response = _api_request(config, URL_FILTER + '/' + str(url_profile_id),
                                method="put", body=url_filter_payload, parameters={'vdom': vdom_list})
        if response.get("status") == "success":
            result.update({'newly_unblocked': current_urls})
        else:
            result.update({'not_unblock': current_urls})
        return result
    except Exception as Err:
        if '500' in str(Err):
            msg = {"ERROR": 500,
                   "Response": "Please input a valid URL. Examples: example.com, example.com/help, 192.168.1.1"}
            raise ConnectorError(msg)
        raise ConnectorError(Err)


def get_web_filter(config, params):
    profile_name = config.get('url_block_policy')
    vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
    web_param = dict()
    web_param.update({'key': 'name', 'pattern': profile_name, 'vdom': vdom_list})
    if profile_name:
        response = _api_request(config, GET_WEB_PROFILE, parameters=web_param)
        if not response.get('results'):
            logger.exception('{0}'.format(response))
            raise ConnectorError(
                "Web filter profile name '{url_block_policy_name}' not found in '{vdom}' VDOM. Provide valid web filter profile name in configuration.".format(
                    url_block_policy_name=profile_name, vdom=', '.join(vdom_list)))
        if not response.get('results')[0].get('web', {}):
            logger.error(WEB_PERMISSION)
            raise ConnectorError(WEB_PERMISSION)
        url_table_id = response.get('results')[0].get('web', {}).get('urlfilter-table')
        if not url_table_id:
            # Profile has no URL filter table attached yet (urlfilter-table 0): nothing is blocked.
            # block_url creates and attaches one on first use.
            return {'results': [{'entries': []}], 'mkey': None}
        response = _api_request(config, URL_FILTER + '/' + str(url_table_id), parameters={'vdom': vdom_list})
        return response
    else:
        raise ConnectorError("Web filter profile name not defined in configuration parameter.")


def _create_url_filter_table(config, profile_name, entries, vdom_list):
    response = _api_request(config, URL_FILTER, method='post', body={'name': profile_name, 'entries': entries},
                            parameters={'vdom': vdom_list})
    url_table_id = response.get('mkey')
    _api_request(config, GET_WEB_PROFILE + '/' + _path(profile_name), method='put',
                 body={'web': {'urlfilter-table': url_table_id}}, parameters={'vdom': vdom_list})
    return response


def get_blocked_urls(config, params):
    profile_name = config.get('url_block_policy')
    if profile_name:
        response = get_web_filter(config, params)
        return list(filter(lambda url_obj: url_obj.get("action") == "block",
                           response.get("results", [])[0].get("entries"))) if response.get("results") else []
    else:
        raise ConnectorError("Web filter profile name not defined in configuration parameter.")

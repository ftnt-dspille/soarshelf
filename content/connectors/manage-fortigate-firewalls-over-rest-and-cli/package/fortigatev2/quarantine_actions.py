""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import re

from connectors.core.connector import ConnectorError, get_logger

from .utils import *
from .utils import _api_request, _get_list_from_str_or_list, _validate_vdom

logger = get_logger('fortigatev2')


def get_list_diff(list1, list2):
    return list(set(list1) - set(list2)) + list(set(list2) - set(list1))


def is_valid_mac_address(input_mac_addr):
    regex = ("^([0-9A-Fa-f]{2}[:-])" +
             "{5}([0-9A-Fa-f]{2})|" +
             "([0-9a-fA-F]{4}\\." +
             "[0-9a-fA-F]{4}\\." +
             "[0-9a-fA-F]{4})$")
    p = re.compile(regex)
    if (re.search(p, input_mac_addr)):
        return True
    else:
        return False


def get_quarantine_hosts(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        param = {"vdom": vdom_list}
        return _api_request(config, QUARANTINE_HOST_API, parameters=param, method="GET")
    except Exception as Err:
        raise ConnectorError(str(Err))


def get_current_new_list(config, params, Flag=False):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        param = {"vdom": vdom_list}
        resp = _api_request(config, QUARANTINE_HOST_API, parameters=param, method="GET")
        body = resp.get('results', {})
        current_list = []
        new_quaran_lst = []
        already_quaran_list =[]
        for item in body.get('targets', []):
            temp = item.get('macs')
            for addr in temp:
                current_list.append(addr.get('mac'))
        params['macs'] = _get_list_from_str_or_list(params, 'macs')
        for item in params['macs']:
            if item in current_list:
                already_quaran_list.append(item)
            else:
                new_quaran_lst.append(item)
        if Flag:
            return body, param, new_quaran_lst, already_quaran_list
        else:
            return new_quaran_lst, already_quaran_list
    except Exception as Err:
        raise ConnectorError(str(Err))


def quarantine_host(config, params):
    try:
        result = {'already_quarantine': [], 'newly_quarantine': [], 'not_quarantine': []}
        body, param, new_quaran_lst, already_quaran_list = get_current_new_list(config, params, Flag=True)
        for mac_addr in new_quaran_lst:
            if is_valid_mac_address(mac_addr):
                target_lst = {
                "entry": mac_addr,
                "description": 'Quarantined by FortiSOAR',
                "macs": [{'mac': mac_addr, "description": 'Quarantined by FortiSOAR'}]
                }
                body['targets'].append(target_lst)

            else:
                result['not_quarantine'].append(mac_addr)
        result['already_quarantine'] = already_quaran_list

        quarantine_resp = _api_request(config, QUARANTINE_HOST_API, parameters=param, method="PUT", body=body)
        if quarantine_resp.get('status') == 'success':
            result['newly_quarantine'] = get_list_diff(new_quaran_lst, result['not_quarantine'])
        else:
            result['not_quarantine'] += [mac for mac in new_quaran_lst if mac not in result['not_quarantine']]
        return result
    except Exception as Err:
        raise ConnectorError(str(Err))


def unquarantine_host(config, params):
    try:
        result = {'not_exist': [], 'newly_unquarantine': [], 'not_unquarantine': []}
        body, param, not_exist_mac_lst, quaran_mac_list = get_current_new_list(config, params, Flag=True)
        result['not_exist'] = not_exist_mac_lst
        target_lst = []
        res = body.get('targets', [])

        if len(res) > 0 and isinstance(res, list):
            for item in res:
                # for address in quaran_mac_list:
                macs = item.get('macs', [])
                for mac in macs:
                    if mac.get('mac') not in quaran_mac_list:
                        target_lst.append(item)
        body['targets'] = target_lst
        logger.info('target_list = {}'.format(target_lst))
        unquarantine_resp = _api_request(config, QUARANTINE_HOST_API, parameters=param, method="PUT", body=body)
        if unquarantine_resp.get('status') == 'success':
            result.update({'newly_unquarantine': quaran_mac_list })
        else:
            result.update({'not_unquarantine': quaran_mac_list})
        return result
    except Exception as Err:
        raise ConnectorError(str(Err))

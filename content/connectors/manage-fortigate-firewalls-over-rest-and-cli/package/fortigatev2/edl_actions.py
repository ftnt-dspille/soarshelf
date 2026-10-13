""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from .constants import LIST_EDL_ENTRIES_ENDPOINT, MODIFY_EDL_ENDPOINT
from .utils import *
from .utils import _api_request, _get_list_from_str_or_list, _validate_vdom

logger = get_logger('fortigatev2')


def get_entries_from_edl(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params)
        filter_param = {
            "mkey": params.get('mkey'),
            "status_only": params.get('status_only'),
            "counts_only": params.get('counts_only'),
            "include_notes": params.get('include_notes'),
            "entry": params.get('entry'),
            "vdom": ','.join(vdom_list)
        }
        filter_param = {key: value for key, value in filter_param.items() if value not in [None, "", False]}
        result = _api_request(config, url=LIST_EDL_ENTRIES_ENDPOINT, parameters=filter_param)
        response = result if isinstance(result, dict) else {'result': result}
        if isinstance(response, list):
            response = {'result': response}
        if 'vdom_not_exist' not in response:
            response.update({'vdom_not_exist': vdom_not_exists})
        return response
    except Exception as Err:
        raise ConnectorError(Err)


def modify_entries_in_edl(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params)
        req_params = {"vdom": ','.join(vdom_list)} if vdom_list else {}
        payload = {
            "commands": [
                {
                    "name": params.get('mkey'),
                    "command": params.get('action', '').lower(),
                    "entries": _get_list_from_str_or_list(params, 'entries')}
            ]}
        result = _api_request(config, url=MODIFY_EDL_ENDPOINT, parameters=req_params, body=payload, method='POST')
        response = result if isinstance(result, dict) else {'result': result}
        if 'vdom_not_exist' not in response:
            response.update({'vdom_not_exist': vdom_not_exists})

        if response.get('results') and response.get('results')[0].get('error'):
            raise ConnectorError(response.get('results')[0].get('error'))
        return response
    except ConnectorError:
        raise
    except Exception as Err:
        raise ConnectorError(f"Error modifying EDL entries: {Err}")

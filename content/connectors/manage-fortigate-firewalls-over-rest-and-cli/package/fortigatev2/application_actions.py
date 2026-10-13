""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import ConnectorError, get_logger

from .constants import *
from .utils import *
from .utils import _api_request, _get_list_from_str_or_list, _get_vdom, _path, _validate_vdom

logger = get_logger('fortigatev2')


def _get_app_block_profile(config, params):
    app_block_policy_name = config.get("app_block_policy")
    vdom = _get_vdom(config, params, check_multiple_vdom=True)
    app_param = {'vdom': vdom} if vdom else {}
    try:
        response = _api_request(config, BLOCK_APP.format(app_block_policy=_path(app_block_policy_name)), parameters=app_param)
        if response.get("status") == "success":
            return response
        else:
            logger.error("Application control profile name not defined in configuration parameter.")
            raise ConnectorError("Application control profile name not defined in configuration parameter.")
    except Exception as Err:
        logger.error("Application control profile name not found : {} ".format(str(Err)))
        raise ConnectorError(
            "Application control profile name '{app_block_policy_name}' not found in '{vdom}' VDOM. Provide valid application control profile name in configuration.".format(
                app_block_policy_name=app_block_policy_name, vdom=', '.join(vdom)))


def _get_app_id(config, params, app_name_list):
    result = []
    # Get application details for getting application id
    all_apps_details = get_list_of_applications(config, params)
    app_id_list = []
    for app in app_name_list:
        temp_id = list(filter(lambda app_details: app == app_details.get("name"),
                              all_apps_details.get("results")))
        if temp_id:
            app_id_list += temp_id
        else:
            result.append({"message": "Application not found in Fortinet FortiGate database", "status":
                "Failed", "name": app})
    return result, app_id_list


def get_list_of_applications(config, params):
    try:
        vdom = _get_vdom(config, params, check_multiple_vdom=True)
        app_param = {'vdom': vdom} if vdom  else {}
        return _api_request(config, GET_LIST_OF_APPLICATIONS, parameters=app_param)
    except Exception as Err:
        raise ConnectorError(Err)


def block_applications(config, params):

    app_block_policy_name = config.get("app_block_policy")
    vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
    app_param = {'vdom': vdom_list} if vdom_list else {}
    try:
        block_policy = {'rate-duration': 60, 'protocols': 'all', 'shaper': '', 'id': 1,
                        'session-ttl': 0, 'application': [], 'log-packet': 'disable',
                        'behavior': 'all', 'technology': 'all', 'sub-category': [],
                        'action': 'block', 'rate-count': 0, 'category': [], 'q_origin_key': 1,
                        'tags': [], 'risk': [], 'rate-track': 'none', 'shaper-reverse': '',
                        'log': 'enable', 'quarantine-expiry': '5m', 'vendor': 'all',
                        'quarantine-log': 'enable', 'rate-mode': 'continuous', 'per-ip-shaper': '',
                        'parameters': [], 'popularity': '1 2 3 4 5', 'quarantine': 'none'}
        if not app_block_policy_name:
            logger.error("Application control profile name is not defined in configuration parameter.")
            raise ConnectorError("Application control profile name is not defined in configuration parameter.")

        app_name_list = _get_list_from_str_or_list(params, 'app_list')
        result, app_id_list = _get_app_id(config, params, app_name_list)
        # Get default application block policy
        block_policy_details = _get_app_block_profile(config, params)
        logger.info('block_policy_details = {}'.format(block_policy_details))
        if 'entries' not in block_policy_details.get('results')[0]:
            logger.error(APP_PERMISSION)
            raise ConnectorError(APP_PERMISSION)
        entries = block_policy_details.get("results")[0].get("entries")
        # Apps must go into a rule whose action is block -- never into a pass/monitor rule.
        temp_policy = [entry for entry in entries if entry.get("action") == "block"][:1]
        if not temp_policy:
            temp_policy = [block_policy]
            # Creating new block policy and put it into 1st position and change all policy sequence incrementing by 1.
            for policy in entries:
                policy["q_origin_key"] = policy["q_origin_key"] + 1
                policy["id"] = policy["id"] + 1
            block_policy_details["results"][0]["entries"] = temp_policy + entries
        for app in app_id_list:
            block_found = list(filter(lambda app_id: app_id.get("id") == app.get("id"),
                                      temp_policy[0].get("application")))
            if block_found:
                result.append({"message": "Application already blocked", "name": app.get("name"),
                               "status": "Successful"})
            else:
                temp_policy[0]["application"] += [{"id": app.get("id"), "q_origin_key": app.get("id")}]
                result.append({"name": app.get("name"), "message": "Application blocked successfully",
                               "status": "Successful"})
        response = _api_request(config, BLOCK_APP.format(app_block_policy=_path(app_block_policy_name)),
                                parameters=app_param, method="put", body=block_policy_details.get("results")[0])
        if response.get("status") == "success":
            return result
        else:
            result = []
            for app in app_name_list:
                result.append({"name": app, "message": "Application block fail", "status": "Failed"})
            return result
    except Exception as Err:
        if '404' in str(Err):
            logger.exception(
                "{} resource Not Found. Unable to find the specified resource.".format(app_block_policy_name))
            raise ConnectorError(
                "{} resource Not Found. Unable to find the specified resource.".format(app_block_policy_name))
        raise ConnectorError(Err)


def unblock_applications(config, params):
    try:
        app_block_policy_name = config.get("app_block_policy")
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
        app_param = {'vdom': vdom_list} if vdom_list else {}
        if not app_block_policy_name:
            logger.error("Application control profile name is not defined in configuration parameter.")
            raise ConnectorError("Application control profile name is not defined in configuration parameter.")

        app_name_list = _get_list_from_str_or_list(params, 'app_list')
        result, app_id_list = _get_app_id(config, params, app_name_list)
        # Get default application block policy
        block_policy_details = _get_app_block_profile(config, params)
        if 'entries' not in block_policy_details.get('results')[0]:
            logger.error(APP_PERMISSION)
            raise ConnectorError(APP_PERMISSION)
        # Finding all block policy.
        block_policy_list = list(
            filter(lambda app: app.get("action") == "block",
                   block_policy_details.get("results")[0].get("entries")))
        if block_policy_list:
            for policy in block_policy_list:
                for app_id in app_id_list:
                    block_found = list(filter(lambda app: app.get("id") == app_id.get("id"),
                                              policy.get("application")))
                    if block_found:
                        policy.get("application").remove(block_found[0])
                        result.append({"name": str(app_id.get("name")), "message":
                            "Application unblock successfully", "status": "Successful"})
                    else:
                        app_name = [i['name'] for i in result]
                        if app_id.get("name") not in app_name:
                            result.append({"name": str(app_id.get("name")), "message":
                                "Application not found in block state", "status": "Successful"})
            response = _api_request(config, BLOCK_APP.format(app_block_policy=_path(app_block_policy_name)),
                                    parameters=app_param, method="put", body=block_policy_details.get("results")[0])
            if response.get("status") == "success":
                return result
        logger.exception("Application block policy not found")
        result = []
        for app in app_name_list:
            result.append({"name": app, "message": "Application unblock fail", "status": "Failed"})
        return result
    except Exception as Err:
        raise ConnectorError(Err)


def get_blocked_applications(config, params):
    app_block_policy_name = config.get("app_block_policy")
    vdom, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=True)
    app_param = {'vdom': vdom} if vdom else {}
    try:
        if not app_block_policy_name:
            logger.error("Application control profile name is not defined in configuration parameter.")
            raise ConnectorError("Application control profile name is not defined in configuration parameter.")

        all_apps_details = get_list_of_applications(config, params)
        # Get default application block policy
        block_policy_details = _api_request(config, BLOCK_APP.format(app_block_policy=_path(app_block_policy_name)), parameters=app_param)
        if 'entries' not in block_policy_details.get('results')[0]:
            logger.error(APP_PERMISSION)
            raise ConnectorError(APP_PERMISSION)
        # Finding all block policy.
        block_policy_list = list(
            filter(lambda app: app.get("action") == "block",
                   block_policy_details.get("results")[0].get("entries")))
        app_id_list = []
        for policy in block_policy_list:
            app_id_list += list(map(lambda app_id: app_id.get("id"), policy.get("application")))
        block_app_details = []
        for app in app_id_list:
            block_app_details += list(filter(lambda app_details: app_details.get("id") == app,
                                             all_apps_details.get("results")))
        return block_app_details
    except Exception as Err:
        if '404' in str(Err):
            logger.exception(
                "{0} resource not found in {1} VDOM. Unable to find the specified resource. Provide valid application control profile name in configuration.".format(
                    app_block_policy_name, ','.join(vdom)))
            raise ConnectorError(
                "{0} resource not found in {1} VDOM. Unable to find the specified resource. Provide valid application control profile name in configuration.".format(
                    app_block_policy_name, ','.join(vdom)))
        raise ConnectorError(Err)


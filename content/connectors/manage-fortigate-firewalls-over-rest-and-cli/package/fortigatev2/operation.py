""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import ConnectorError, get_logger

from .address_actions import *
from .address_grp_actions import *
from .application_actions import *
from .cli_based_action import *
from .edl_actions import get_entries_from_edl, modify_entries_in_edl
from .policy_actions import *
from .policy_actions import _get_policy
from .quarantine_actions import *
from .service_actions import *
from .service_group_actions import *
from .url_actions import *
from .user_actions import *
from .utils import _api_request, _get_list_from_str_or_list, _get_vdom, _path, _validate_vdom

logger = get_logger('fortigatev2')


def check_health(config):
    try:
        res = get_list_of_policies(config, {})
        vdom_not_exist = res.get('vdom_not_exist')
        if vdom_not_exist:
            error_message = VDOM_NOT_EXIST_ERROR.format(', '.join(res.get('vdom_not_exist')))
            logger.error(error_message)
            raise ConnectorError(error_message)
        if res.get('result'):
            if config.get('app_block_policy'):
                get_blocked_applications(config, {})
            if config.get('url_block_policy'):
                get_blocked_urls(config, {})
            return True
    except Exception as e:
        raise ConnectorError(str(e))


def _block_ip(config, params):
    result = {'already_blocked': [], 'newly_blocked': [], 'error_with_block': []}
    vdom, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
    result.update({'vdom_not_exist': vdom_not_exists})
    try:
        user_address_list = _get_list_from_str_or_list(params, 'ip_addresses', is_ip=True)
        result['already_blocked'], ip_address_list = check_ip_exists(config, user_address_list, vdom)
        if len(ip_address_list) == 0:
            logger.exception('IP address {} already blocked.'.format(user_address_list))
            return result
        time_to_live = params.get('time_to_live')
        if time_to_live == "Custom Time":
            duration = params.get('duration')
        else:
            duration = int(time_to_live_values.get(time_to_live))
        querystring = {}
        if vdom:
            querystring.update({'vdom': ','.join(vdom)})
        data = {"ip_addresses": ip_address_list, "expiry": duration, 'src': 'ips'}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = _api_request(config, BAN_IP_API, header=headers, body=data, method='POST', parameters=querystring)
        if isinstance(response, dict) and (response.get('result') or (response.get('status') == 'success')):
            result.update({'newly_blocked': ip_address_list})
        elif isinstance(response, list):
            for i in response:
                if i.get('status') == 'success':
                    result.update({'newly_blocked': ip_address_list})
                else:
                    result['error_with_block'].append({'name': i.get('vdom'), 'ip_addresses': ip_address_list})
                    logger.error('Check VDOM/User or API key permission to update quarantine IP.')
        else:
            logger.error('Check VDOM/User or API key permission to update quarantine IP.')
            result.update({'error_with_block': ip_address_list})
        return result
    except Exception as Err:
        raise ConnectorError(str(Err))


def block_ip(config, params):
    method = params.get("method")
    try:
        if "Quarantine Based" == method:
            return _block_ip(config, params)
        else:
            return policy_base_block_ip(config, params)
    except Exception as e:
        logger.exception('Failed to block IP address with error {}'.format(e))
        raise ConnectorError('Failed to block IP address with error {}'.format(e))


def delete_bulk_address(config, vdom, ip_list, type):
    querystring = {}
    referenced_ips = []
    if vdom:
        querystring.update({'vdom': ','.join(vdom)})
    if 'IPv4' in type:
        url = DELETE_ADDRESS
    else:
        url = DELETE_IPv6_ADDRESS
    try:
        for ip in ip_list:
            try:
                response = _api_request(config, url.format(ip_name=_path(ip)), parameters=querystring, method='DELETE')
                logger.debug('IP {} deleted successfully.. '.format(ip))
            except Exception as e:
                referenced_ips.append(ip)
                logger.debug('Not able to delete {} IP address entry.'.format(ip))
                logger.error('{}'.format(str(e)))
                continue
        return referenced_ips if len(referenced_ips) > 0 else True
    except Exception as err:
        logger.exception(err)


def update_address_grp(config, vdom, ip_group_name, ip_list, blocked_ips=None, unblock_ips=None, type='', is_new=False):
    status = False
    if ip_list:
        bulk_result = add_bulk_address(config, vdom, ip_list=ip_list, type=type)

    querystring = {}
    if vdom:
        querystring.update({'vdom': ','.join(vdom)})
    try:
        if is_new:
            data = list(map(lambda x: {'name': x}, ip_list))
            method = 'POST'
            endpoint = ADDRESS_GROUP_MEMBER_API if 'IPv4' in type else ADDRESS_GROUP_MEMBER_API_IPv6
        else:
            data = {'member': list(map(lambda x: {'name': x}, ip_list + (blocked_ips if blocked_ips else [])))}
            method = 'PUT'
            endpoint = ADDRESS_GROUP_API if 'IPv4' in type else ADDRESS_GROUP_API_IPv6
        response = _api_request(config, endpoint.format(ip_group_name=_path(ip_group_name)), parameters=querystring, body=data, method=method)
        if 'result' in response and not response.get('result', []):
            logger.error('Check VDOM/user or API key permission to update address group.')
            return False
        logger.debug('IP address: {} updated in group successfully.. '.format(ip_list))
        if unblock_ips:
            referenced_ips = delete_bulk_address(config, vdom, ip_list=unblock_ips, type=type)
        return True
    except Exception as err:
        logger.exception(err)
    return status


def policy_base_block_ip(config, params):
    result = {'already_blocked': [], 'newly_blocked': [], 'error_with_block': []}
    ip_group_name = params.get('ip_group_name')
    current_ip_list = []
    created_address_list = []
    ip_list, blocked_ips, vdom = extract_blocked_unblock_ips(config, params, ip_group_name)
    if isinstance(blocked_ips, bool):
        result['error_with_block'] += ip_list
        return result
    for ip in ip_list:
        if ip not in blocked_ips:
            current_ip_list.append(ip)
        else:
            result['already_blocked'].append(ip)
    if len(current_ip_list) == 0:
        return result
    if len(blocked_ips) == MAX_GROUP_SIZE:
        logger.exception('Max {} items are allowed for {} address group'.format(MAX_GROUP_SIZE, ip_group_name))
        raise ConnectorError('Maximum {} items exceeded for {} group.'.format(MAX_GROUP_SIZE, ip_group_name))
    remain_ips_len = MAX_GROUP_SIZE - len(blocked_ips)
    if ip_list == result.get('already_blocked'):
        logger.exception('{} already blocked'.format(', '.join(ip_list)))
        raise ConnectorError('{} already blocked'.format(', '.join(ip_list)))
    if update_address_grp(config, vdom, ip_group_name, current_ip_list[:remain_ips_len], blocked_ips=blocked_ips,
                          type=params.get('ip_type'), is_new=params.get("is_new")):
        created_address_list += current_ip_list
    else:
        result['error_with_block'] += current_ip_list
    result['error_with_block'] += current_ip_list[remain_ips_len:]
    result['newly_blocked'] = created_address_list
    return result


def check_ip_exists(config, ip_address_list, vdom, unblock=False):
    vdoms_param = {}
    user_ip_list = []
    blocked_ip_list = []
    blocked_ips = []
    tmp = []
    if vdom:
        vdoms_param = {'vdom': ','.join(vdom)}
    response = _api_request(config, LIST_BANNED_IPS_API, parameters=vdoms_param)
    result = [response] if isinstance(response, dict) else response
    for record in result:
        if 'results' not in record:
            # User don't have permission to read banned IPs
            logger.error('Check VDOM/user or API key permission. {}'.format(response))
            raise ConnectorError(
                'Check VDOM/user or API key permission. Response: {}'.format(response))
        blocked_ips += list(map(lambda ip: ip.get("ip_address"), record['results']))
        tmp += blocked_ips
    for ip in ip_address_list:
        if ip not in blocked_ips:
            user_ip_list.append(ip)
        else:
            if blocked_ips.count(ip) == len(result) and not unblock:
                blocked_ip_list.append(ip)
            elif unblock:
                blocked_ip_list.append(ip)
            else:
                user_ip_list.append(ip)
    return blocked_ip_list, user_ip_list


def extract_blocked_unblock_ips(config, params, ip_group_name):
    try:
        ip_list = _get_list_from_str_or_list(params, 'ip', is_ip=True)
        vdom, vdom_not_exists = _validate_vdom(config, params)

        policy_data = _get_policy(config, params, vdom)
        logger.info('policy data = {}'.format(policy_data))
        if len(policy_data[0].get('results')) <= 0:
            raise ConnectorError('Input policy name not found')
        if params.get('ip_type') == 'IPv6':
            dst_block_ipv6_obj = policy_data[0].get('results')[0].get("dstaddr6")
            src_block_ipv6_obj = policy_data[0].get('results')[0].get("srcaddr6")
            blocked_data = list(map(lambda ip: ip.get("name"), dst_block_ipv6_obj))
            blocked_data += list(map(lambda ip: ip.get("name"), src_block_ipv6_obj))
        else:
            dst_block_ips_obj = policy_data[0].get('results')[0].get("dstaddr")
            src_block_ips_obj = policy_data[0].get('results')[0].get("srcaddr")
            blocked_data = list(map(lambda ip: ip.get("name"), dst_block_ips_obj))
            blocked_data += list(map(lambda ip: ip.get("name"), src_block_ips_obj))

        if ip_group_name not in blocked_data:
            logger.exception('IP address group {} not exist in {} policy.'.format(
                ip_group_name, policy_data[0].get('results')[0].get('name')))
            raise ConnectorError('IP address group {} not exist in {} policy.'.format(
                ip_group_name, policy_data[0].get('results')[0].get('name')))
        ip_list = list(set(ip_list))
        blocked_ips = get_address_grp(config, ip_group_name, vdom, type=params.get('ip_type'))
        return ip_list, blocked_ips, vdom
    except Exception as Err:
        raise ConnectorError(Err)


def _unblock_ip(config, params):
    querystring = {}
    result = {'ip_not_exist': [], 'newly_unblocked': [], 'error_with_unblock': []}
    vdom, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
    result.update({'vdom_not_exist': vdom_not_exists})
    try:
        user_address_list = _get_list_from_str_or_list(params, 'ip_addresses', is_ip=True)
        ip_address_list, result['ip_not_exist'] = check_ip_exists(config, user_address_list, vdom, unblock=True)
        if len(ip_address_list) == 0:
            logger.exception('IP address {} not exists.'.format(user_address_list))
            return result
        if vdom:
            querystring.update({'vdom': ','.join(vdom)})
        data = {"ip_addresses": ip_address_list}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = _api_request(config, REMOVE_BAN_API, header=headers, parameters=querystring, body=data,
                                method='POST')
        if isinstance(response, dict) and (response.get('result') or response.get('status') == 'success'):
            result.update({'newly_unblocked': ip_address_list})
        elif isinstance(response, list):
            for i in response:
                if i.get('status') == 'success':
                    result.update({'newly_unblocked': ip_address_list})
                else:
                    result['error_with_unblock'].append(
                        {'name': i.get('vdom'), 'ip_addresses': ip_address_list})
        else:
            logger.error('Check VDOM/User or API key permission to update quarantine IP.')
            result.update({'error_with_unblock': ip_address_list})
        return result
    except Exception as Err:
        raise ConnectorError(str(Err))


def unblock_ip(config, params):
    method = params.get("method")
    if "Quarantine Based" == method:
        return _unblock_ip(config, params)
    else:
        return policy_base_unblock_ip(config, params)


def policy_base_unblock_ip(config, params):
    result = {'not_exist': [], 'newly_unblocked': [], 'error_with_unblock': []}
    ip_group_name = params.get('ip_group_name')
    current_unblock_ips = []
    ip_list, blocked_ips, vdom = extract_blocked_unblock_ips(config, params, ip_group_name)
    if isinstance(blocked_ips, bool):
        result['error_with_unblock'] += ip_list
        return result
    for ip in ip_list:
        if ip in blocked_ips:
            current_unblock_ips.append(ip)
        else:
            result['not_exist'].append(ip)
    if ip_list == result.get('not_exist'):
        logger.exception('{} not exists in {} group.'.format(', '.join(ip_list), ip_group_name))
        raise ConnectorError('{} not exists in {} group.'.format(', '.join(ip_list), ip_group_name))
    if len(current_unblock_ips) == 0:
        return result
    current_block_ips = list(set(blocked_ips) - set(current_unblock_ips))
    if update_address_grp(config, vdom, ip_group_name, current_block_ips, unblock_ips=current_unblock_ips,
                          type=params.get('ip_type')):
        result['newly_unblocked'] = current_unblock_ips
    else:
        result['error_with_unblock'] = current_unblock_ips
    return result


def _get_blocked_ip(config, params):
    try:
        vdoms_param = {}
        vdoms, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        if vdoms:
            vdoms_param.update({'vdom': ','.join(vdoms)})
        response = _api_request(config, LIST_BANNED_IPS_API, parameters=vdoms_param)
        if 'result' in response and not response.get('result', []):
            logger.error('Check VDOM/user or API key permission. {}'.format(response))
            raise ConnectorError(
                'Check VDOM/user or API key permission. Response: {}'.format(
                    response))
        response = {'result': [response]} if isinstance(response,
                                                        dict) and 'result' not in response else response

        if isinstance(response, list):
            response = {'result': response}
        if 'vdom_not_exist' not in response: response.update({'vdom_not_exist': vdom_not_exists})
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def get_blocked_ip(config, params):
    method = params.get("method")
    if "Quarantine Based" == method:
        return _get_blocked_ip(config, params)
    else:
        return policy_base_get_blocked_ips(config, params)


def policy_base_get_blocked_ips(config, params):
    result_data = {
        "addrgrp": [],
        "addrgrp_not_exist": []
    }
    ip_group_name = _get_list_from_str_or_list(params, 'ip_group_name')
    try:
        vdom = _get_vdom(config, params, check_multiple_vdom=True)
        policy_list = _get_policy(config, params, vdom)
        policy = policy_list.get('result')[0] if 'result' in policy_list else policy_list[0]
        if len(policy.get('results', [])) <= 0:
            raise ConnectorError('Input policy name not found.')
        result_data.update(
            {"policy_name": policy.get("results")[0].get("name"),
             "dstaddr": list(map(lambda ip: ip.get("name"), policy.get("results")[0].get("dstaddr"))),
             "srcaddr": list(map(lambda ip: ip.get("name"), policy.get("results")[0].get("srcaddr"))),
             "srcaddr6": list(map(lambda ip: ip.get("name"), policy.get("results")[0].get("srcaddr6"))),
             "dstaddr6": list(map(lambda ip: ip.get("name"), policy.get("results")[0].get("dstaddr6")))
             })
        ipv4_data = result_data.get('dstaddr') + result_data.get('srcaddr')
        ipv6_data = result_data.get('srcaddr6') + result_data.get('dstaddr6')
        for grp_name in ip_group_name:
            if grp_name not in ipv4_data + ipv6_data:
                result_data['addrgrp_not_exist'].append(grp_name)
                logger.debug('IP address group {} not exist in {} policy.'.format(grp_name,
                                                                                  policy.get('results')[0].get('name')))
                continue
            grp_type ='IPv4' if grp_name in ipv4_data else 'IPv6'
            blocked_ips = get_address_grp(config, grp_name, vdom, type=grp_type)
            result_data['addrgrp'].append(
                {"name": grp_name, "member": [] if isinstance(blocked_ips, bool) else blocked_ips})
        return result_data
    except Exception as Err:
        raise ConnectorError(Err)


fortigate_operations = {
    'create_policy': create_policy,
    'get_list_of_policies': get_list_of_policies,
    'update_policy': update_policy,
    'delete_policy': delete_policy,

    'get_blocked_ip': get_blocked_ip,
    'block_ip': block_ip,
    'unblock_ip': unblock_ip,
    'block_ip_new': block_ip,

    'get_list_of_applications': get_list_of_applications,
    'block_applications': block_applications,
    'unblock_applications': unblock_applications,
    'get_blocked_applications': get_blocked_applications,

    'block_url': block_url,
    'unblock_url': unblock_url,
    'get_blocked_urls': get_blocked_urls,

    'quarantine_host': quarantine_host,
    'unquarantine_host': unquarantine_host,
    'get_quarantine_hosts': get_quarantine_hosts,

    'create_address': create_address,
    'get_addresses': get_addresses,
    'update_address': update_address,
    'delete_address': delete_address,

    'create_address_group': create_address_group,
    'get_address_groups': get_address_groups,
    'update_address_group': update_address_group,
    'delete_address_group': delete_address_group,

    'create_service_group': create_service_group,
    'get_service_groups': get_service_groups,
    'update_service_group': update_service_group,
    'delete_service_group': delete_service_group,

    'create_firewall_service': create_firewall_service,
    'get_firewall_services': get_firewall_services,
    'update_firewall_service': update_firewall_service,
    'delete_firewall_service': delete_firewall_service,

    'get_country_names': get_country_names,

    'execute_command': execute_command,

    'create_user': create_user,
    'get_users': get_users,
    'update_user': update_user,
    'delete_user': delete_user,
    'get_user_list_login_details': get_user_list_login_details,

    'get_system_events': get_system_events,

    'get_entries_from_edl': get_entries_from_edl,
    'modify_entries_in_edl': modify_entries_in_edl

}

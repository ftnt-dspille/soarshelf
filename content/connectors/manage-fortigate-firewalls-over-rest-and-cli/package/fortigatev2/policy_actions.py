""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import ConnectorError, get_logger

from .utils import *
from .utils import _api_request, _get_list_from_str_or_list, _path, _validate_vdom

logger = get_logger('fortigatev2')


def create_policy(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        body = {
            'name': params.get('name'),
            'status': params.get('status').lower() if params.get('status') else None,
            'srcintf': generate_dict_from_list(params.get('srcintf')),
            'dstintf': generate_dict_from_list(params.get('dstintf')),
            'srcaddr': generate_dict_from_list(params.get('srcaddr')),
            'dstaddr': generate_dict_from_list(params.get('dstaddr')),
            'service': generate_dict_from_list(params.get('service')),
            'action': PARAM.get(params.get('action'), None),
            'inspection-mode': PARAM.get(params.get('inspection_mode'), None),
            'av-profile': {"q_origin_key": params.get('av_profile')} if params.get('av_profile') else None,
            'webfilter-profile': {"q_origin_key": params.get('webfilter_profile')} if params.get(
                'webfilter_profile') else None,
            'dnsfilter-profile': {"q_origin_key": params.get('dnsfilter_profile')} if params.get(
                'dnsfilter_profile') else None,
            'application-list': {"q_origin_key": params.get('application_list')} if params.get(
                'application_list') else None,
            'ips-sensor': {"q_origin_key": params.get('ips_sensor')} if params.get('ips_sensor') else None,
            'file-filter-profile': {"q_origin_key": params.get('file_filter_profile')} if params.get(
                'file_filter_profile') else None,
            'ssl-ssh-profile': {"q_origin_key": params.get('ssl_ssh_profile')} if params.get(
                'ssl_ssh_profile') else None,
            'logtraffic': PARAM.get(params.get('logtraffic')),
            'schedule': params.get('schedule'),
            'nat': 'enable' if params.get('nat') else None,
            'poolname': generate_dict_from_list(params.get('poolname')),
            'fixedport': params.get('fixedport').lower() if params.get('fixedport') else None,
            'profile-protocol-options': params.get('profile-protocol-options'),
            'comments': params.get('comment')

        }
        if params.get('ip_pool_config') == 'Use Outgoing Interface Address':
            body['ippool'] = 'disable'
        elif params.get('ip_pool_config') == 'Use Dynamic IP Pool':
            body['ippool'] = 'enable'
        if params.get('security_profile_name'):
            body.update({"utm-status": "enable"})
        param = {"vdom": vdom_list}
        if params.get('additional_args'):
            body.update(params.get('additional_args'))
        body_param = {k: v for k, v in body.items() if v is not None and v != '' and v != {} and v!=[]}
        response = _api_request(config, LIST_OF_POLICIES_API, parameters=param, body=body_param, method='POST',
                                header={'accept': 'application/json'})
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def update_policy(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        response = _api_request(config, LIST_OF_POLICIES_API + _path(params.get('policyid')), parameters={"vdom": vdom_list})
        curr_details = response.get('results', [])
        if len(curr_details) != 1:
            raise ConnectorError('Input Policy name not found')

        srcaddr_list = get_final_lst(params, curr_details, 'srcaddr', 'add_srcaddr', 'remove_srcaddr')
        dstaddr_list = get_final_lst(params, curr_details, 'dstaddr', 'add_dstaddr', 'remove_dstaddr')
        service_lst = get_final_lst(params, curr_details, 'service', 'add_service', 'remove_service')
        if not srcaddr_list:
            srcaddr_list = ['none']
        if not dstaddr_list:
            dstaddr_list = ['none']
        if not service_lst:
            service_lst = ['NONE']
        body = {
            'name': params.get('name'),
            'status': params.get('status').lower() if params.get('status') else None,
            'srcintf': generate_dict_from_list(params.get('srcintf')),
            'dstintf': generate_dict_from_list(params.get('dstintf')),
            'srcaddr': generate_dict_from_list(srcaddr_list),
            'dstaddr': generate_dict_from_list(dstaddr_list),
            'service': generate_dict_from_list(service_lst),
            'action': PARAM.get(params.get('action'), None),
            'inspection-mode': PARAM.get(params.get('inspection_mode'), None),
            'av-profile': {"q_origin_key": params.get('av_profile')} if params.get('av_profile') else None,
            'webfilter-profile': {"q_origin_key": params.get('webfilter_profile')} if params.get(
                'webfilter_profile') else None,
            'dnsfilter-profile': {"q_origin_key": params.get('dnsfilter_profile')} if params.get(
                'dnsfilter_profile') else None,
            'application-list': {"q_origin_key": params.get('application_list')} if params.get(
                'application_list') else None,
            'ips-sensor': {"q_origin_key": params.get('ips_sensor')} if params.get('ips_sensor') else None,
            'file-filter-profile': {"q_origin_key": params.get('file_filter_profile')} if params.get(
                'file_filter_profile') else None,
            'ssl-ssh-profile': {"q_origin_key": params.get('ssl_ssh_profile')} if params.get(
                'ssl_ssh_profile') else None,
            'logtraffic': PARAM.get(params.get('logtraffic')),
            'schedule': params.get('schedule'),
            'nat': 'enable' if params.get('nat') else None,
            'poolname': generate_dict_from_list(params.get('poolname')),
            'fixedport': params.get('fixedport').lower() if params.get('fixedport') else None,
            'profile-protocol-options': params.get('profile-protocol-options'),
            'comments': params.get('comment')
        }

        if params.get('ip_pool_config') == 'Use Outgoing Interface Address':
            body['ippool'] = 'disable'
        elif params.get('ip_pool_config') == 'Use Dynamic IP Pool':
            body['ippool'] = 'enable'

        param = {"vdom": vdom_list}

        if params.get('additional_args'):
            body.update(params.get('additional_args'))

        body_param = {k: v for k, v in body.items() if v is not None and v != '' and v != {} and v != []}
        if params.get('security_profile_names_to_disable'):
            for profile in params.get('security_profile_names_to_disable'):
                tmp = security_profiles.get(profile)
                body_param[tmp] = ""
        response = _api_request(config, LIST_OF_POLICIES_API + _path(params.get('policyid')), parameters=param,
                                body=body_param, method='PUT', header={'accept': 'application/json'})
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def delete_policy(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        response = _api_request(config, LIST_OF_POLICIES_API + _path(params.get('policyid')),
                                parameters={"vdom": vdom_list}, method='DELETE', header={'accept': 'application/json'})
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def _get_policy(config, params, vdoms, check_multiple_policy=True):
    try:
        policy_param = {'vdom': ','.join(vdoms)} if vdoms else {}
        result = []
        endpoint = LIST_OF_SECURITY_POLICIES_API if params.get('ngfw_mode') == 'Policy Based' else LIST_OF_POLICIES_API
        if check_multiple_policy:
            block_ip_policy = _get_list_from_str_or_list(params, "ip_block_policy")
            for policy in block_ip_policy:
                policy_param.update({'key': 'name', 'pattern': policy})
                response = _api_request(config, url=endpoint, parameters=policy_param,
                                        header={'accept': 'application/json'})
                try:
                    if response.get("results") and response.get("results")[0].get("action") != 'deny':
                        logger.exception('IP4 policy {0} action is not deny: {1}'.
                                         format(block_ip_policy, response))
                        raise ConnectorError('IPv4 policy {0} don\'t have action as \'deny\''.format(policy))
                    result.append(response)
                except Exception as e:
                    if 'deny' in str(e):
                        raise ConnectorError(e)
                    logger.error('Check VDOM/user/API key permission or IPv4 Policy not found.')
                    raise ConnectorError(
                        'Check VDOM/user/API key permission or IPv4 Policy not found. Policy response: {}'.format(
                            response))
        else:
            result = _api_request(config, url=endpoint, parameters=policy_param)
            response = {'result': [result]} if isinstance(result, dict) and 'result' not in result else result
            return response
        return result
    except Exception as Err:
        raise ConnectorError(Err)


def get_list_of_policies(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        if params.get('policyid'):
            endpoint = LIST_OF_SECURITY_POLICIES_API if params.get('ngfw_mode') == 'Policy Based' else LIST_OF_POLICIES_API
            response = _api_request(config, endpoint + _path(params.get('policyid')), parameters={"vdom": vdom_list})
        else:
            response = _get_policy(config, params, vdoms=vdom_list, check_multiple_policy=False)
        if 'result' in response and not response.get('result', []):
            logger.error('Check VDOM/user or API key permission to access policies. {0}'.format(response))
            raise ConnectorError(
                'Check VDOM/user or API key permission to access policies. Response: {0}'.format(
                    response))
        if isinstance(response, list):
            response = {'result': response}
        if 'vdom_not_exist' not in response:
            response.update({'vdom_not_exist': vdom_not_exists})
        return response
    except Exception as Err:
        raise ConnectorError(Err)

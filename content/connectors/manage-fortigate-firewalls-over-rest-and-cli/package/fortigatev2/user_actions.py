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


def send_activation_code(config, params, querystring):
    try:
        activation_code_data = {
                    "token": params.get('fortitoken'),
                    "user_name": params.get('name'),
                    "method": params.get('activation_method').lower()
                }
        if params.get('activation_method').lower() == 'sms' and not params.get('phone_number'):
            raise ConnectorError('Phone details required to send activation code details.')
        if params.get('activation_method').lower() == 'email' and not params.get('email-to'):
            raise ConnectorError('Email address is required to send activation code details.')
        if params.get('activation_method').lower() == 'sms':
            activation_code_data['sms_phone'] = str(params.get('country_code', '')) + str(params.get('phone_number', ''))
        else:
            activation_code_data['email'] = params.get('email-to')
        activation_api_res = _api_request(config, USER_ACTIVATION_API, parameters=querystring,
                                            body=activation_code_data, method='POST')
        if activation_api_res:
            logger.info('activation code send successfully, api response is {0}'.format(activation_api_res))
    except Exception as Err:
        logger.error('Input User created/updated successfully but failed to send activation code, error is = {0}'.
                     format(str(Err)))
        raise ConnectorError('Input User created/updated successfully but failed to send activation code, '
                             'error is = {0}'.format(str(Err)))


def update_user_group(config, params, querystring, flag=False):
    try:
        if flag:
            user_groups_list = _get_list_from_str_or_list(params, 'user_group_name_to_remove')
        else:
            user_groups_list = _get_list_from_str_or_list(params, 'user_group_name')
        for user_group_name in user_groups_list:
            user_group_res = _api_request(config, USER_GROUP.format(group_name=_path(user_group_name)), parameters=querystring,
                                          method='GET')
            if len(user_group_res.get('results')) == 1:
                put_body = user_group_res.get('results')[0]
                if flag:
                    for item in put_body.get('member'):
                        if item.get('name') == params.get('name'):
                            put_body['member'].remove(item)
                else:
                    if put_body.get('member') is None:
                        put_body['member'] = {'name': params.get('name')}
                    else:
                        put_body['member'].append({'name': params.get('name')})
                try:
                    # Add user to user group
                    add_user_group_res = _api_request(config, USER_GROUP.format(group_name=_path(user_group_name)),
                                                      parameters=querystring, body=put_body, method='PUT')
                    logger.info('user added successfully to user group, api response is {0}'.format(add_user_group_res))
                except Exception as err:
                    logger.error('Failed to add user {0} into user group {1}, api rersponse is {2}'.
                                 format(params.get('name'), user_group_name, str(err)))
                    raise ConnectorError(str(err))
            else:
                logger.error('Input user group name not valid or not found')
                raise ConnectorError('Input user group name not valid or not found')
    except Exception as Err:
        logger.error('Input User created/updated successfully but failed to add user to user group, error is = {}'
                     .format(str(Err)))
        raise ConnectorError('Input User created/updated successfully but failed to add user to user group, '
                             'error is = {0}'.format(str(Err)))


def _two_factor(params):
    # FortiOS values: disable | fortitoken | fortitoken-cloud | email | sms
    value = params.get('auth_type') or params.get('two-factor') or ''
    return value.lower().replace(' ', '-')


def _sms_phone(params):
    if not params.get('phone_number'):
        return None
    return str(params.get('country_code') or '') + str(params.get('phone_number'))


def create_user(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        querystring = {}
        create_user_params = {}
        if vdom_list:
            querystring.update({'vdom': ','.join(vdom_list)})
        create_user_params.update({
            'name': params.get('name'),
            'status': params.get('status').lower() if params.get('status') else '',
            'passwd': params.get('passwd'),
            'radius-server': params.get('radius-server'),
            'tacacs+-server': params.get('tacacs+-server'),
            'two-factor': _two_factor(params),
            'fortitoken': params.get('fortitoken'),
            'email-to': params.get('email-to')})

        create_user_params['type'] = PARAM.get(params.get('user_type', None))
        create_user_params['sms-phone'] = _sms_phone(params)
        data = {k: v for k, v in create_user_params.items() if v is not None and v != '' and v != {} and v != []}
        response = _api_request(config, USER_API, parameters=querystring, body=data, method='POST')

        # Add user to user group
        if params.get('user_group') == 'Enable':
            update_user_group(config, params, querystring)

        # Send activation code
        if params.get('send_activation_code') == 'Enable':
            send_activation_code(config, params, querystring)

        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def get_users(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        querystring = {}
        if vdom_list:
            querystring.update({'vdom': ','.join(vdom_list)})

        if params.get('name'):
            response = _api_request(config, USER_API + _path(params.get('name')), parameters=querystring, method='GET')
        else:
            querystring.update({'start': params.get('start'), 'count': params.get('count')})
            data = {k: v for k, v in querystring.items() if v is not None and v != '' and v != {} and v != []}
            response = _api_request(config, USER_API, parameters=data, method='GET')
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def update_user(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        querystring = {}
        if vdom_list:
            querystring.update({'vdom': ','.join(vdom_list)})

        name = params.get('name')
        if params.get('new_username'):
            params.update({'name': params.get('new_username')})
        # only FortiOS user/local attributes go in the body -- not the form's helper fields
        data = {
            'name': params.get('name'),
            'status': params.get('status').lower() if params.get('status') else None,
            'passwd': params.get('passwd'),
            'radius-server': params.get('radius-server'),
            'tacacs+-server': params.get('tacacs+-server'),
            'two-factor': _two_factor(params),
            'fortitoken': params.get('fortitoken'),
            'email-to': params.get('email-to')
        }
        data = {k: v for k, v in data.items() if v is not None and v != '' and v != {} and v != []}

        if params.get('sms') == 'Disable':
            data['sms-phone'] = ''
        elif params.get('sms') == 'Enable':
            data['sms-phone'] = _sms_phone(params)
        response = _api_request(config, USER_API + _path(name), parameters=querystring, method='PUT', body=data)

        # Add user to user groups
        if params.get('user_group_name'):
            update_user_group(config, params, querystring)

        # Remove user from user groups
        if params.get('user_group_name_to_remove'):
            update_user_group(config, params, querystring, flag=True)

        # Send activation code
        if params.get('send_activation_code') == 'Enable':
            send_activation_code(config, params, querystring)
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def delete_user(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        querystring = {}
        if vdom_list:
            querystring.update({'vdom': ','.join(vdom_list)})

        # delete User
        response = _api_request(config, USER_API + _path(params.get('name')), parameters=querystring, method='DELETE')
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def get_user_list_login_details(config, params):
    try:
        res = get_system_events(config, params={'filter': 'user=*{}, logdesc=*"Admin login successful"'.format(params.get('username'))})
        if len(res.get('results')) > 0:
            return res.get('results')[0]
        return {'message': 'Login details not found', 'response': res}
    except Exception as Err:
        raise ConnectorError(str(Err))

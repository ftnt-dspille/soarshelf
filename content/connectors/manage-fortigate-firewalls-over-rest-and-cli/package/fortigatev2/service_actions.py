""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import ConnectorError, get_logger

from .utils import *
from .utils import _api_request, _path, _validate_vdom

logger = get_logger('fortigatev2')

LEGACY_TCP_PROTOCOL = 'TCP/UDP/SCTP'
# Older info.json shipped 'All' as the protocol default, which is not a FortiOS value ('ALL').
UNSET_PROTOCOL_DEFAULT = 'All'


def _service_protocol(config, protocol, app_param, is_update=False):
    """FortiOS 7.4+ renamed the TCP/UDP/SCTP service protocol to TCP/UDP/UDP-Lite/SCTP.
    Map the UI value to whichever spelling this FortiGate's schema accepts."""
    if protocol == UNSET_PROTOCOL_DEFAULT:
        # untouched default: on update leave the service's protocol alone
        return None if is_update else 'ALL'
    if protocol != LEGACY_TCP_PROTOCOL:
        return protocol
    schema = _api_request(config, FIREWALL_SERVICE_API, parameters=dict(app_param, action='schema'))
    options = [o.get('name') for o in schema.get('results', {}).get('children', {}).get('protocol', {}).get('options', [])]
    return next((o for o in options if o.startswith('TCP/UDP')), protocol)


def _service_body(config, params, app_param, is_update=False):
    body = {
        'name': params.get('name'),
        'category': params.get('category'),
        'protocol': _service_protocol(config, params.get('protocol'), app_param, is_update),
        'iprange': params.get('iprange'),
        'fqdn': params.get('fqdn'),
        'tcp-portrange': params.get('tcp_portrange'),
        'udp-portrange': params.get('udp_portrange'),
        'sctp-portrange': params.get('sctp_portrange'),
        'comment': params.get('comment'),
        'visibility': params.get('visibility').lower() if params.get('visibility') else None,
        'protocol-number': params.get('protocol-number'),
        'icmptype': params.get('icmptype'),
        'icmpcode': params.get('icmpcode')
    }
    return {k: v for k, v in body.items() if v is not None and v != '' and v != {} and v != []}


def _set_protocol_fields(config, name, body, app_param):
    """FortiOS ignores icmptype/icmpcode/protocol-number sent in the same request that
    sets protocol ICMP/IP, so apply them with a follow-up PUT."""
    fields = {k: body[k] for k in ('icmptype', 'icmpcode', 'protocol-number') if k in body}
    if fields and body.get('protocol') in ('ICMP', 'ICMP6', 'IP'):
        _api_request(config, FIREWALL_SERVICE_API + _path(name), parameters=app_param, method='PUT',
                     body=fields)


def create_firewall_service(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        app_param = {'vdom': vdom_list} if vdom_list  else {}
        body_param = _service_body(config, params, app_param)
        response = _api_request(config, FIREWALL_SERVICE_API, parameters=app_param, method='POST', body=body_param)
        _set_protocol_fields(config, body_param['name'], body_param, app_param)
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def get_firewall_services(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)

        app_param = {'vdom': vdom_list} if vdom_list else {}
        if params.get('name'):
            return _api_request(config, FIREWALL_SERVICE_API + _path(params.get('name')), parameters=app_param)
        else:
            return _api_request(config, FIREWALL_SERVICE_API, parameters=app_param)
    except Exception as Err:
        raise ConnectorError(str(Err))


def update_firewall_service(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        app_param = {'vdom': vdom_list} if vdom_list else {}
        body_param = _service_body(config, params, app_param, is_update=True)
        if params.get('new_name'):
            body_param.update({'name': params.get('new_name')})
        response = _api_request(config, FIREWALL_SERVICE_API + _path(params.get('name')), parameters=app_param, method='PUT',
                                body=body_param)
        _set_protocol_fields(config, body_param['name'], body_param, app_param)
        return response
    except Exception as Err:
        raise ConnectorError(str(Err))


def delete_firewall_service(config, params):
    try:
        vdom_list, vdom_not_exists = _validate_vdom(config, params, check_multiple_vdom=False)
        app_param = {'vdom': vdom_list} if vdom_list else {}
        return _api_request(config, FIREWALL_SERVICE_API + _path(params.get('name')), parameters=app_param, method='DELETE')
    except Exception as Err:
        raise ConnectorError(str(Err))

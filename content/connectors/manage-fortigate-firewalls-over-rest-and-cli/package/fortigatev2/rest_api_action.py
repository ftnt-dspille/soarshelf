""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import json
from urllib.parse import unquote, urlparse

from connectors.core.connector import ConnectorError, get_logger

from .utils import _api_request, _get_vdom

logger = get_logger('fortigatev2')

METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')


def safe_endpoint(endpoint):
    """A path on the configured FortiGate, or an error.

    A full URL, a `//host` start, a `..` segment (also percent-encoded, up to three
    layers) or a backslash is refused, so the API key can never be sent to another host.
    """
    endpoint = str(endpoint or '').strip()
    if not endpoint:
        raise ConnectorError('Endpoint is required')
    path = endpoint.split('?')[0]
    for _ in range(3):
        path = unquote(path)
    parsed = urlparse(endpoint)
    if parsed.scheme or parsed.netloc or endpoint.startswith('//') or '..' in path.split('/') or '\\' in path:
        raise ConnectorError('Endpoint must be a path on the configured server, '
                             'for example /api/v2/monitor/system/status - not a full URL')
    return endpoint if endpoint.startswith('/') else '/' + endpoint


def json_object(value, name):
    """A JSON object from a dict or a JSON string; blank means none."""
    if value is None or value == '' or value == {}:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ConnectorError('{0} must be valid JSON'.format(name))
    if not isinstance(value, dict):
        raise ConnectorError('{0} must be a JSON object'.format(name))
    return value


def execute_api_request(config, params):
    """Call any FortiOS REST API endpoint with the configured API key (REST only; see Execute Command for the CLI)."""
    method = str(params.get('method') or 'GET').upper()
    if method not in METHODS:
        raise ConnectorError('Method must be GET, POST, PUT, PATCH or DELETE')
    path = safe_endpoint(params.get('endpoint'))
    query = json_object(params.get('query_params'), 'Query Parameters') or {}
    body = json_object(params.get('request_body'), 'Request Body')
    if 'vdom' not in query:
        vdom = _get_vdom(config, {})
        if vdom:
            query['vdom'] = ','.join(vdom)
    response = _api_request(config, path, body=body if method in ('POST', 'PUT', 'PATCH') else None,
                            parameters=query, method=method,
                            header={'Content-Type': 'application/json'} if body else None)
    # _api_request turns a 403 into a {'vdom_not_exist', 'result'} summary built for the VDOM checks
    if isinstance(response, dict) and set(response) == {'vdom_not_exist', 'result'} and response['vdom_not_exist']:
        raise ConnectorError('FortiGate refused the request (HTTP 403): {0}'.format(
            json.dumps(response['vdom_not_exist'])[:500]))
    return response

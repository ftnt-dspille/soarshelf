""" AWS Extended -- overlay module.

Adds a generic boto3 passthrough operation and repairs the platform's
numeric-string coercion for security-group rule operations.

This file is our own code. It is layered onto a vendor connector at build
time by ``build.py`` and imports the vendor's client helpers by relative
import; it does not modify any vendor function body.
"""

import json
from functools import wraps

from connectors.core.connector import get_logger, ConnectorError

from .utils import _get_aws_client, _get_aws_resource, _change_date_format

logger = get_logger('aws-extended')

# boto3 client methods that only read. Used to enforce read_only mode.
_READ_PREFIXES = ('describe_', 'get_', 'list_', 'search_', 'lookup_', 'batch_get_')


def _normalize_ip_permissions(ip_permissions):
    """Coerce each rule's ``IpProtocol`` back to a string.

    FortiSOAR's parameter layer retypes numeric-looking strings to int before
    the connector sees them, so an ``ip_permissions`` entry of
    ``{"IpProtocol": "-1"}`` -- the form the vendor's own placeholder text
    documents -- reaches boto3 as int ``-1`` and is rejected by parameter
    validation. Every numeric protocol is affected, including ``-1``
    ("all protocols"), which is what a quarantine security group must revoke
    to be egress-locked.

    Protocol numbers are legal AWS input as strings, so stringify rather than
    reject.
    """
    if isinstance(ip_permissions, str):
        try:
            ip_permissions = json.loads(ip_permissions)
        except ValueError:
            return ip_permissions
    if not isinstance(ip_permissions, list):
        return ip_permissions
    for rule in ip_permissions:
        if isinstance(rule, dict) and 'IpProtocol' in rule:
            rule['IpProtocol'] = str(rule['IpProtocol'])
    return ip_permissions


def wrap_ip_permissions(func):
    """Normalize ``ip_permissions`` before handing params to a vendor op."""

    @wraps(func)
    def _wrapped(config, params):
        if isinstance(params, dict) and 'ip_permissions' in params:
            params = dict(params)
            params['ip_permissions'] = _normalize_ip_permissions(params.get('ip_permissions'))
        return func(config, params)

    return _wrapped


def _load_payload(payload):
    """Accept the payload as a JSON string or an already-decoded mapping.

    Passing it as a *string* is what preserves types: the platform cannot
    retype values it never parsed, so ``"-1"`` stays a string and an ARN that
    happens to be all digits stays an ARN.
    """
    if payload in (None, ''):
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except ValueError as err:
            raise ConnectorError(f'Payload is not valid JSON: {err}')
        if not isinstance(decoded, dict):
            raise ConnectorError(
                f'Payload must be a JSON object of boto3 keyword arguments, got {type(decoded).__name__}'
            )
        return decoded
    raise ConnectorError(f'Unsupported payload type: {type(payload).__name__}')


def _jsonable(obj):
    """Round-trip through the vendor's date handler so the result is JSON-safe."""
    return json.loads(json.dumps(obj, default=_change_date_format))


def generic_action(config, params):
    """Call any boto3 client method on any AWS service.

    The vendor connector exposes 32 curated EC2/IAM operations. Anything else
    -- listing every instance, describing subnets, deactivating an access key,
    reading CloudTrail -- has no operation at all. This is the escape hatch:
    name the service, name the API action, hand it the keyword arguments.
    """
    service = (params.get('service') or '').strip()
    api_action = (params.get('api_action') or '').strip()
    if not service:
        raise ConnectorError('Service is required, e.g. ec2, iam, s3, cloudtrail')
    if not api_action:
        raise ConnectorError('API Action is required, e.g. describe_instances')
    if api_action.startswith('_'):
        raise ConnectorError(f'Refusing to call private attribute {api_action!r}')

    read_only = params.get('read_only')
    if read_only and not api_action.startswith(_READ_PREFIXES):
        raise ConnectorError(
            f'{api_action!r} is not a read operation and Read Only Mode is enabled. '
            'Disable Read Only Mode to allow it.'
        )

    kwargs = _load_payload(params.get('payload'))
    aws_client = _get_aws_client(config, params, service)

    method = getattr(aws_client, api_action, None)
    if not callable(method):
        raise ConnectorError(
            f'{service!r} has no API action {api_action!r}. '
            'Use the boto3 client method name, e.g. describe_instances, not DescribeInstances.'
        )

    if params.get('paginate'):
        return _paginate(aws_client, service, api_action, kwargs)

    logger.info('generic_action %s.%s', service, api_action)
    return _jsonable(method(**kwargs))


def _paginate(aws_client, service, api_action, kwargs):
    """Walk every page and merge the results.

    Without this, ``describe_instances`` on a real account silently returns
    only the first page -- the kind of truncation that reads as "clean" when
    it is actually partial.
    """
    if not aws_client.can_paginate(api_action):
        raise ConnectorError(
            f'{service}.{api_action} does not support pagination; disable Paginate Results.'
        )
    paginator = aws_client.get_paginator(api_action)
    merged = {}
    pages = 0
    for page in paginator.paginate(**kwargs):
        pages += 1
        page.pop('ResponseMetadata', None)
        page.pop('NextToken', None)
        for key, value in page.items():
            if isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            else:
                merged.setdefault(key, value)
    logger.info('generic_action %s.%s paginated over %s page(s)', service, api_action, pages)
    merged['PageCount'] = pages
    return _jsonable(merged)


def generic_resource_action(config, params):
    """Call a method on a boto3 *resource* object rather than a client.

    A few AWS operations are only reachable this way -- the vendor's own
    revoke_egress/revoke_ingress go through ``ec2.SecurityGroup(...)``. Supply
    the resource class and its identifier, then the method.
    """
    service = (params.get('service') or '').strip()
    resource_class = (params.get('resource_class') or '').strip()
    resource_id = (params.get('resource_id') or '').strip()
    api_action = (params.get('api_action') or '').strip()
    if not (service and resource_class and resource_id and api_action):
        raise ConnectorError('Service, Resource Class, Resource ID and API Action are all required')
    if api_action.startswith('_') or resource_class.startswith('_'):
        raise ConnectorError('Refusing to access a private attribute')

    kwargs = _load_payload(params.get('payload'))
    aws_resource = _get_aws_resource(config, params, service)

    factory = getattr(aws_resource, resource_class, None)
    if not callable(factory):
        raise ConnectorError(f'{service!r} has no resource class {resource_class!r}')
    obj = factory(resource_id)

    method = getattr(obj, api_action, None)
    if not callable(method):
        raise ConnectorError(f'{resource_class!r} has no method {api_action!r}')

    logger.info('generic_resource_action %s.%s(%s).%s', service, resource_class, resource_id, api_action)
    return _jsonable(method(**kwargs))

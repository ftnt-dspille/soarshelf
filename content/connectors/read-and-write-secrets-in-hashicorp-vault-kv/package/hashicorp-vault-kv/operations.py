"""Operation handlers for the HashiCorp Vault KV connector."""

from __future__ import annotations

import json

from .connections import ConnectorError, VaultClient, json_object

operations = {}


def _client(config):
    return VaultClient(
        server=config['server'],
        token=config['token'],
        mount=config.get('mount') or 'secret',
        verify_ssl=config.get('verify_ssl', True),
        timeout=config.get('timeout') or 30,
    )


def get_health(config, params):
    return _client(config).health()


operations['get_health'] = get_health


def read_secret(config, params):
    if not params.get('path'):
        raise ValueError('path is required')
    version = params.get('version')
    version = int(version) if version not in (None, '', 'null') else None
    return _client(config).read_secret(params['path'], version)


operations['read_secret'] = read_secret


def write_secret(config, params):
    if not params.get('path') or not params.get('secret_data'):
        raise ValueError('path and secret_data are required')
    return _client(config).write_secret(params['path'], params['secret_data'],
                                        create_only=_bool_param(params.get('create_only')))


operations['write_secret'] = write_secret


def list_secrets(config, params):
    return {'keys': _client(config).list_secrets(params.get('path') or '')}


operations['list_secrets'] = list_secrets


def _list_param(value, name):
    """A list from a list, a JSON array string or comma-separated text; blank means None."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith('['):
            try:
                value = json.loads(text)
            except ValueError:
                raise ConnectorError('{0} must be a JSON array or comma-separated text'.format(name))
        else:
            value = [part.strip() for part in text.split(',')]
    if not isinstance(value, list):
        raise ConnectorError('{0} must be a list'.format(name))
    return [str(v) for v in value if str(v).strip()]


def _bool_param(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('true', '1', 'yes')


def _int_param(params, name, default, low, high, title):
    value = params.get(name)
    if value in (None, '', 'null'):
        return default
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ConnectorError('{0} must be a whole number'.format(title))
    if not low <= value <= high:
        raise ConnectorError('{0} must be between {1} and {2}'.format(title, low, high))
    return value


def patch_secret(config, params):
    if not params.get('path') or not params.get('secret_data'):
        raise ValueError('path and secret_data are required')
    return _client(config).patch_secret(
        params['path'], params['secret_data'],
        retries=_int_param(params, 'retries', 3, 0, 10, 'Retries'))


operations['patch_secret'] = patch_secret


def read_metadata(config, params):
    if not params.get('path'):
        raise ValueError('path is required')
    return _client(config).read_metadata(params['path'],
                                         missing_ok=_bool_param(params.get('missing_ok')))


operations['read_metadata'] = read_metadata


def patch_metadata(config, params):
    if not params.get('path'):
        raise ValueError('path is required')
    return _client(config).patch_metadata(
        params['path'], json_object(params.get('custom_metadata'), 'Custom Metadata'))


operations['patch_metadata'] = patch_metadata


def find_secrets_by_metadata(config, params):
    if not params.get('metadata_key'):
        raise ValueError('metadata_key is required')
    return _client(config).find_by_metadata(
        params.get('path') or '', params['metadata_key'],
        values=_list_param(params.get('values'), 'Values'),
        max_paths=_int_param(params, 'max_paths', 1000, 1, 10000, 'Max Secrets'))


operations['find_secrets_by_metadata'] = find_secrets_by_metadata


def delete_secret(config, params):
    if not params.get('path'):
        raise ValueError('path is required')
    return _client(config).delete_secret(params['path'])


operations['delete_secret'] = delete_secret


def execute_api_request(config, params):
    """Call any Vault HTTP API endpoint with the configured token.

    `endpoint` is a path on the server (`/v1/sys/health`; `/v1` is added when
    missing). Methods: GET, POST, PUT, PATCH, DELETE and LIST.
    """
    method = (params.get('method') or 'GET').upper()
    if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'LIST'):
        raise ConnectorError('Method must be GET, POST, PUT, PATCH, DELETE or LIST')
    return _client(config).raw(method, params.get('endpoint'),
                               json_object(params.get('query_params'), 'Query Parameters'),
                               json_object(params.get('request_body'), 'Request Body'))


operations['execute_api_request'] = execute_api_request


def _check_health(config):
    return _client(config).health()

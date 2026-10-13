"""Operation handlers for the HashiCorp Vault KV connector."""

from __future__ import annotations

from .connections import VaultClient

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
    return _client(config).write_secret(params['path'], params['secret_data'])


operations['write_secret'] = write_secret


def list_secrets(config, params):
    return {'keys': _client(config).list_secrets(params.get('path') or '')}


operations['list_secrets'] = list_secrets


def delete_secret(config, params):
    if not params.get('path'):
        raise ValueError('path is required')
    return _client(config).delete_secret(params['path'])


operations['delete_secret'] = delete_secret


def _check_health(config):
    return _client(config).health()

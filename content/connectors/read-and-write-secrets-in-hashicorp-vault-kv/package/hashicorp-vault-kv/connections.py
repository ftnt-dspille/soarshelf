"""Typed HashiCorp Vault KV v2 client used by the connector operations.

Wire format for the KV version 2 engine:

- read:    GET  /v1/{mount}/data/{path}[?version=N]
- write:   POST /v1/{mount}/data/{path}            body {"data": {...}}
- list:    GET  /v1/{mount}/metadata/{path}?list=true
- delete:  DELETE /v1/{mount}/data/{path}           (latest version, soft)
- auth:    X-Vault-Token header; token validity via /v1/auth/token/lookup-self

Writes create a new version; they replace, not merge, the secret data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import unquote, urlparse

import requests

from connectors.core.connector import ConnectorError, get_logger

logger = get_logger('hashicorp-vault-kv')


def normalize_server(server: str) -> str:
    server = (server or '').strip().rstrip('/')
    if not server:
        raise ConnectorError('Server URL is required')
    if not (server.startswith('http://') or server.startswith('https://')):
        server = 'https://' + server
    return server


def safe_endpoint(endpoint: Any) -> str:
    """A path on the configured server, or an error.

    A full URL, a `..` segment (also percent-encoded, up to three layers) or a
    backslash is refused, so the Vault token can never be sent to another host.
    """
    endpoint = str(endpoint or '').strip()
    if not endpoint:
        raise ConnectorError('Endpoint is required')
    path = endpoint.split('?')[0]
    for _ in range(3):
        path = unquote(path)
    if urlparse(endpoint).scheme or urlparse(endpoint).netloc or '..' in path.split('/') or '\\' in path:
        raise ConnectorError('Endpoint must be a path on the configured server, '
                             'for example /v1/sys/health - not a full URL')
    return endpoint if endpoint.startswith('/') else '/' + endpoint


def json_object(value: Any, name: str) -> Optional[dict]:
    """A JSON object from a dict or a JSON string; blank means none."""
    if value in (None, '', {}):
        return None
    if isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except ValueError:
            raise ConnectorError('{0} must be valid JSON'.format(name))
    if not isinstance(value, dict):
        raise ConnectorError('{0} must be a JSON object'.format(name))
    return value


def parse_secret_data(secret_data: Any) -> dict:
    """Accept a JSON object, a JSON string, or key=val pairs from botcontext."""
    if isinstance(secret_data, dict):
        return secret_data
    if isinstance(secret_data, str):
        text = secret_data.strip()
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
        pairs = {}
        for chunk in text.split(','):
            if '=' in chunk:
                key, value = chunk.split('=', 1)
                pairs[key.strip()] = value.strip()
            elif chunk.strip():
                raise ConnectorError(
                    'Secret Data must be a JSON object, got {0!r}'.format(text[:120]))
        if pairs:
            return pairs
    raise ConnectorError(
        'Secret Data must be a JSON object of secret fields')


@dataclass
class Secret:
    path: str
    version: int
    data: dict
    metadata: dict

    def to_dict(self) -> dict:
        return {'data': self.data, 'version': self.version,
                'metadata': self.metadata, 'path': self.path}


class VaultClient:
    """Token-authenticated KV v2 client."""

    def __init__(self, server: str, token: str, mount: str = 'secret',
                 verify_ssl: bool = True, timeout: int = 30):
        self.server = normalize_server(server)
        if not token:
            raise ConnectorError('Token is required')
        self.token = token
        self.mount = (mount or 'secret').strip('/')
        self.verify_ssl = bool(verify_ssl)
        self.timeout = int(timeout or 30)
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self.session.headers['X-Vault-Token'] = self.token

    def _url(self, path: str) -> str:
        return '{0}/v1/{1}/{2}'.format(self.server, self.mount, path.lstrip('/'))

    def _call(self, method: str, url: str, params: Any = None,
              json_body: Any = None, ok_missing: bool = False,
              follow_redirects: bool = True) -> Any:
        try:
            resp = self.session.request(method, url, params=params,
                                        json=json_body, timeout=self.timeout,
                                        allow_redirects=follow_redirects)
        except requests.RequestException as err:
            raise ConnectorError('Vault request failed: {0}'.format(err))
        if not follow_redirects and 300 <= resp.status_code < 400:
            # The X-Vault-Token header must not follow a redirect to another host.
            raise ConnectorError('Vault answered with a redirect (HTTP {0}); not following it '
                                 'so the token stays on the configured server'.format(resp.status_code))
        if resp.status_code == 404 and ok_missing:
            return None
        if resp.status_code == 403:
            raise ConnectorError('Vault rejected the token (HTTP 403): {0}'.format(
                resp.text[:200]))
        if resp.status_code >= 400:
            raise ConnectorError('Vault {0} {1} failed (HTTP {2}): {3}'.format(
                method, url.replace(self.server, ''), resp.status_code,
                resp.text[:200]))
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {'raw': resp.text}

    def raw(self, method: str, endpoint: str, params: Any = None, body: Any = None) -> Any:
        """Any Vault API call, with this client's token. `/v1` is added when the path lacks it."""
        path = safe_endpoint(endpoint)
        if not (path == '/v1' or path.startswith('/v1/')):
            path = '/v1' + path
        return self._call(method, self.server + path, params=params, json_body=body,
                          follow_redirects=False)

    # - operations -----------------------------------------------------------

    def read_secret(self, path: str, version: Optional[int] = None) -> dict:
        params = {'version': str(version)} if version else None
        data = self._call('GET', self._url('data/' + path), params=params)
        envelope = data.get('data') or {}
        secret_data = envelope.get('data', {})
        metadata = envelope.get('metadata', {})
        if not secret_data and not metadata:
            secret_data = data.get('data', {})
        version_number = metadata.get('version') or 0
        return Secret(path=path, version=int(version_number),
                      data=secret_data, metadata=metadata).to_dict()

    def read_secret_latest(self, path: str) -> dict:
        return self.read_secret(path)

    def write_secret(self, path: str, secret_data: dict) -> dict:
        body = {'data': parse_secret_data(secret_data)}
        data = self._call('POST', self._url('data/' + path), json_body=body)
        new_version = (data.get('data') or {}).get('version')
        if new_version is None:
            new_version = (data.get('version') or 0)
        logger.info('Wrote {0} (new version {1})'.format(path, new_version))
        return {'path': path, 'version': int(new_version or 0)}

    def list_secrets(self, path: str = '') -> list:
        url = self._url('metadata/' + path) if path else self._url('metadata')
        data = self._call('GET', url, params={'list': 'true'})
        keys = ((data.get('data') or {}).get('keys')) or []
        return list(keys)

    def delete_secret(self, path: str) -> dict:
        self._call('DELETE', self._url('data/' + path))
        return {'path': path, 'deleted': True}

    def health(self) -> dict:
        data = self._call('GET', self.server + '/v1/auth/token/lookup-self')
        info = data.get('data') or {}
        return {'valid': True,
                'policies': info.get('policies', []),
                'display_name': info.get('display_name')}

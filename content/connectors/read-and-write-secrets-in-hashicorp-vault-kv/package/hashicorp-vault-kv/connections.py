"""Typed HashiCorp Vault KV v2 client used by the connector operations.

Wire format for the KV version 2 engine:

- read:    GET  /v1/{mount}/data/{path}[?version=N]
- write:   POST /v1/{mount}/data/{path}            body {"data": {...}}
- list:    GET  /v1/{mount}/metadata/{path}?list=true
- delete:  DELETE /v1/{mount}/data/{path}           (latest version, soft)
- patch:   PATCH /v1/{mount}/data/{path}            merge-patch {"data": {...}}
- metadata: GET / PATCH /v1/{mount}/metadata/{path}  custom_metadata lives here
- auth:    X-Vault-Token header; token validity via /v1/auth/token/lookup-self

Writes create a new version; they replace, not merge, the secret data. A
patch also creates a new version but merges, so only the named fields change.
Vault cannot search secrets by value or by metadata: finding the secret that
carries a tag means listing the paths and reading each one's metadata, which
find_by_metadata does without ever reading a secret value.
"""

from __future__ import annotations

import json
import time
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


def safe_secret_path(path: Any) -> str:
    """A path inside the mount, or an error.

    Secret paths reach the connector from playbook input (an API body, a folder
    to search), so a `.` or `..` segment (also percent-encoded, up to three
    layers), a backslash, `?` or `#` is refused: none can be used to reach
    another part of the Vault API with the configured token.
    """
    text = str(path or '').strip().lstrip('/')
    decoded = text
    for _ in range(3):
        decoded = unquote(decoded)
    if any(seg in ('.', '..') for seg in decoded.split('/')) or any(c in decoded for c in '\\?#'):
        raise ConnectorError('Secret path {0!r} is not allowed: no ".", ".." segments, '
                             'backslashes, "?" or "#"'.format(text))
    # 'data/' + '/apps/x' must not become data//apps/x
    joined = '/'.join(seg for seg in text.split('/') if seg)
    return joined + '/' if text.endswith('/') and joined else joined


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
        return '{0}/v1/{1}/{2}'.format(self.server, self.mount, safe_secret_path(path))

    def _call(self, method: str, url: str, params: Any = None,
              json_body: Any = None, ok_missing: bool = False,
              follow_redirects: bool = True, merge_patch: bool = False) -> Any:
        kwargs: dict = {'json': json_body}
        if merge_patch:
            # Vault only accepts PATCH as a JSON merge patch.
            kwargs = {'data': json.dumps(json_body),
                      'headers': {'Content-Type': 'application/merge-patch+json'}}
        try:
            resp = self.session.request(method, url, params=params,
                                        timeout=self.timeout,
                                        allow_redirects=follow_redirects, **kwargs)
        except requests.RequestException as err:
            raise ConnectorError('Vault request failed: {0}'.format(err))
        if not follow_redirects and 300 <= resp.status_code < 400:
            # The X-Vault-Token header must not follow a redirect to another host.
            raise ConnectorError('Vault answered with a redirect (HTTP {0}); not following it '
                                 'so the token stays on the configured server'.format(resp.status_code))
        if resp.status_code == 404 and ok_missing:
            return None
        if resp.status_code == 403:
            raise ConnectorError('Vault refused {0} {1} (HTTP 403): the token is invalid, or its '
                                 'policy does not allow this on that path: {2}'.format(
                                     method, url.replace(self.server, ''), resp.text[:200]))
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

    def write_secret(self, path: str, secret_data: dict, create_only: bool = False) -> dict:
        body: dict = {'data': parse_secret_data(secret_data)}
        if create_only:
            # Check-and-set 0: Vault refuses the write if any version exists, atomically.
            body['options'] = {'cas': 0}
        try:
            data = self._call('POST', self._url('data/' + path), json_body=body)
        except ConnectorError as err:
            if create_only and 'check-and-set' in str(err):
                raise ConnectorError('A secret already exists at {0}; Create Only never '
                                     'overwrites one'.format(path))
            raise
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

    def patch_secret(self, path: str, secret_data: Any, retries: int = 3,
                     delay: float = 2.0) -> dict:
        """Change only the given fields of an existing secret (a new version).

        Retried on a network error or a 5xx, since a caller that has just
        rotated a credential has nowhere else to put it. A 4xx is not retried:
        403 is the policy, 404 means there is no secret to patch.
        """
        body = {'data': parse_secret_data(secret_data)}
        attempts = max(1, int(retries or 0) + 1)
        for attempt in range(1, attempts + 1):
            try:
                data = self._call('PATCH', self._url('data/' + path), json_body=body,
                                  ok_missing=True, merge_patch=True)
                break
            except ConnectorError as err:
                transient = 'Vault request failed' in str(err) or '(HTTP 5' in str(err)
                if not transient or attempt == attempts:
                    raise
                logger.warning('Patch of {0} failed (attempt {1}/{2}): {3}'.format(
                    path, attempt, attempts, err))
                time.sleep(float(delay))
        if data is None:
            raise ConnectorError('No secret at {0}: a patch only changes an existing '
                                 'secret (use Write Secret to create one)'.format(path))
        version = (data.get('data') or {}).get('version')
        logger.info('Patched {0} (new version {1}, attempt {2})'.format(path, version, attempt))
        return {'path': path, 'version': int(version or 0), 'attempts': attempt,
                'fields': sorted(body['data'])}

    def read_metadata(self, path: str, missing_ok: bool = False) -> dict:
        """A secret's metadata (custom_metadata, versions) - never its value.

        With missing_ok, a path with no secret answers exists=False instead of failing.
        """
        data = self._call('GET', self._url('metadata/' + path), ok_missing=missing_ok)
        if data is None:
            return {'path': path, 'exists': False, 'custom_metadata': {}, 'current_version': 0,
                    'current_deleted': False, 'created_time': None, 'updated_time': None}
        md = data.get('data') or {}
        current = int(md.get('current_version') or 0)
        cur = (md.get('versions') or {}).get(str(current)) or {}
        return {'path': path, 'exists': True,
                'custom_metadata': md.get('custom_metadata') or {},
                'current_version': current,
                'current_deleted': bool(cur.get('deletion_time') or cur.get('destroyed')),
                'created_time': md.get('created_time'),
                'updated_time': md.get('updated_time')}

    def patch_metadata(self, path: str, custom_metadata: dict) -> dict:
        """Merge keys into a secret's custom_metadata; a null value removes a key."""
        if not isinstance(custom_metadata, dict) or not custom_metadata:
            raise ConnectorError('Custom Metadata must be a non-empty JSON object')
        values = {str(k): (None if v is None else str(v)) for k, v in custom_metadata.items()}
        self._call('PATCH', self._url('metadata/' + path),
                   json_body={'custom_metadata': values}, merge_patch=True)
        return self.read_metadata(path)

    def walk(self, prefix: str = '', max_paths: int = 1000) -> list:
        """Every secret path under prefix, recursing into folders (LIST is one level)."""
        prefix = (prefix or '').strip('/')
        found, folders = [], [prefix]
        while folders:
            folder = folders.pop()
            url = self._url('metadata/' + folder) if folder else self._url('metadata')
            data = self._call('GET', url, params={'list': 'true'}, ok_missing=True)
            for key in ((data or {}).get('data') or {}).get('keys') or []:
                full = '{0}/{1}'.format(folder, key) if folder else key
                if key.endswith('/'):
                    folders.append(full.rstrip('/'))
                else:
                    found.append(full)
                    if len(found) > max_paths:
                        raise ConnectorError('More than {0} secrets under {1!r}; narrow the '
                                             'path or raise Max Secrets'.format(max_paths, prefix))
        return sorted(found)

    def find_by_metadata(self, prefix: str, metadata_key: str, values: Optional[list] = None,
                         max_paths: int = 1000) -> dict:
        """Which secrets under prefix carry custom_metadata[metadata_key], and its value.

        Reads metadata only. A secret whose current version is deleted is not a
        match (nothing reads it any more). With values, each one is sorted into
        matches (exactly one secret), unmatched (none) and conflicts (several).
        """
        if not metadata_key:
            raise ConnectorError('Metadata Key is required')
        tagged, untagged, deleted = [], [], []
        paths = self.walk(prefix, max_paths)
        for path in paths:
            md = self.read_metadata(path)
            value = md['custom_metadata'].get(metadata_key)
            if not value:
                untagged.append(path)
            elif md['current_deleted']:
                deleted.append(path)
            else:
                tagged.append({'path': path, 'value': value,
                               'custom_metadata': md['custom_metadata']})
        by_value: dict = {}
        for item in tagged:
            by_value.setdefault(item['value'], []).append(item['path'])
        result = {'prefix': prefix, 'metadata_key': metadata_key, 'scanned': len(paths),
                  'tagged': tagged, 'by_value': by_value,
                  'untagged': untagged, 'deleted': deleted}
        if values is not None:
            wanted = list(dict.fromkeys(str(v) for v in values if v))
            result['matches'] = [{'value': v, 'path': by_value[v][0]}
                                 for v in wanted if len(by_value.get(v, [])) == 1]
            result['unmatched'] = [v for v in wanted if v not in by_value]
            result['conflicts'] = [{'value': v, 'paths': by_value[v]}
                                   for v in wanted if len(by_value.get(v, [])) > 1]
        return result

    def delete_secret(self, path: str) -> dict:
        self._call('DELETE', self._url('data/' + path))
        return {'path': path, 'deleted': True}

    def health(self) -> dict:
        data = self._call('GET', self.server + '/v1/auth/token/lookup-self')
        info = data.get('data') or {}
        return {'valid': True,
                'policies': info.get('policies', []),
                'display_name': info.get('display_name')}

"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end

HTTP client for Jira Cloud (REST v3 and the Jira Service Management API).

Everything that talks to Atlassian goes through JiraClient.request(), so
authentication, URL resolution, retries and error reporting live in one place.
"""
import json
import time
from urllib.parse import urlparse

import requests
from connectors.core.connector import ConnectorError, get_logger

logger = get_logger('jirav2')

GATEWAY_HOST = 'api.atlassian.com'
GATEWAY_PREFIX = 'https://api.atlassian.com/ex/jira/'
DEFAULT_TIMEOUT = 30
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 30

# tenant_info answers never change for a site, so look each one up once per
# worker process.
_CLOUD_IDS = {}


def _sleep(seconds):
    time.sleep(seconds)


def normalize_server(server):
    server = (server or '').strip()
    if not server:
        raise ConnectorError('Server URL is required.')
    if not server.startswith(('http://', 'https://')):
        server = 'https://' + server
    return server.rstrip('/')


def error_details(response):
    """Pull a human-readable message out of a Jira or JSM error body."""
    try:
        body = response.json()
    except ValueError:
        text = (response.text or '').strip()
        return text[:500]
    if not isinstance(body, dict):
        return str(body)[:500]
    parts = []
    for key in ('errorMessages',):
        parts.extend(str(m) for m in body.get(key) or [])
    errors = body.get('errors')
    if isinstance(errors, dict):
        parts.extend('%s: %s' % (field, msg) for field, msg in errors.items())
    for key in ('errorMessage', 'message', 'i18nErrorMessage'):
        value = body.get(key)
        if isinstance(value, dict):
            value = value.get('i18nKey') or value.get('message')
        if value:
            parts.append(str(value))
    if parts:
        return '; '.join(dict.fromkeys(parts))
    return json.dumps(body)[:500]


def _hint(status, details):
    lowered = details.lower()
    if status == 401:
        if 'scope' in lowered:
            return ('The token is missing a scope this call needs. See the "Permissions" '
                    'section of the README for the scopes per operation.')
        return ('Check the username (the Atlassian account email, not the token name) and '
                'the API token. A scoped token needs the "Scoped API Token" option.')
    if status == 403:
        return ('The account is authenticated but lacks the Jira project or global '
                'permission for this call (or the token lacks a scope).')
    if status == 404:
        return ('Not found, or not visible to this account: Jira answers 404 when the '
                'account lacks Browse permission. Check the key/id and the Server URL.')
    return ''


class JiraClient(object):
    def __init__(self, config):
        config = config or {}
        self.server = normalize_server(config.get('server_url'))
        self.auth_type = config.get('auth_type') or 'Basic (Email + API Token)'
        self.username = config.get('username') or ''
        self.token = config.get('token') or ''
        self.scoped = bool(config.get('scoped'))
        self.cloud_id = (config.get('cloud_id') or '').strip()
        self.verify = config.get('verify_ssl', True)
        self.timeout = self._timeout(config.get('timeout'))
        self._base = None

    @staticmethod
    def _timeout(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT
        return value if value > 0 else DEFAULT_TIMEOUT

    # -- URL ---------------------------------------------------------------

    @property
    def base_url(self):
        if self._base is None:
            self._base = self._resolve_base()
        return self._base

    def _resolve_base(self):
        parsed = urlparse(self.server)
        if parsed.hostname == GATEWAY_HOST:
            if not parsed.path.startswith('/ex/jira/') or len(parsed.path.split('/')) < 4 \
                    or not parsed.path.split('/')[3]:
                raise ConnectorError(
                    'Server URL %s is missing the cloud id. Use %s<cloudId>, or enter your '
                    'site URL (https://<site>.atlassian.net) and tick "Scoped API Token".'
                    % (self.server, GATEWAY_PREFIX))
            return self.server
        if self.scoped:
            return GATEWAY_PREFIX + (self.cloud_id or self._lookup_cloud_id())
        return self.server

    def _lookup_cloud_id(self):
        if self.server in _CLOUD_IDS:
            return _CLOUD_IDS[self.server]
        url = self.server + '/_edge/tenant_info'
        try:
            response = requests.get(url, timeout=self.timeout, verify=self.verify)
            cloud_id = response.json()['cloudId']
        except Exception as err:
            raise ConnectorError(
                'Could not look up the cloud id at %s (%s). Enter it in the Cloud ID field.'
                % (url, err))
        _CLOUD_IDS[self.server] = cloud_id
        return cloud_id

    # -- auth --------------------------------------------------------------

    def _auth(self):
        if self.auth_type.startswith('Bearer'):
            return {'Authorization': 'Bearer %s' % self.token}, None
        return {}, (self.username, self.token)

    # -- request -----------------------------------------------------------

    def request(self, method, path, params=None, json_body=None, data=None, files=None,
                headers=None, raw=False):
        """Call the API and return the decoded body ({} for an empty reply).

        With raw=True the Response object is returned instead. Non-2xx replies
        raise ConnectorError carrying Jira's own message.
        """
        if not path.startswith('/'):
            path = '/' + path
        url = self.base_url + path
        auth_headers, basic = self._auth()
        merged = {'Accept': 'application/json'}
        if json_body is not None:
            merged['Content-Type'] = 'application/json'
        merged.update(auth_headers)
        merged.update(headers or {})
        if params:
            params = {k: v for k, v in params.items() if v is not None and v != ''}
        method = method.upper()

        attempt = 0
        while True:
            attempt += 1
            logger.info('%s %s', method, url)
            try:
                response = requests.request(
                    method, url, params=params or None, headers=merged, auth=basic,
                    json=json_body, data=data, files=files, verify=self.verify,
                    timeout=self.timeout)
            except requests.exceptions.SSLError as err:
                raise ConnectorError('SSL certificate validation failed for %s: %s' % (url, err))
            except requests.exceptions.Timeout:
                raise ConnectorError('The request to %s timed out after %ss.' % (url, self.timeout))
            except requests.exceptions.ConnectionError as err:
                raise ConnectorError('Could not connect to %s: %s' % (url, err))

            if response.status_code == 429 and attempt < MAX_ATTEMPTS:
                _sleep(self._retry_wait(response, attempt))
                continue
            if response.status_code in (502, 503, 504) and method in ('GET', 'HEAD') \
                    and attempt < MAX_ATTEMPTS:
                _sleep(min(2 ** attempt, MAX_RETRY_WAIT))
                continue
            break

        if raw:
            return response
        if not response.ok:
            details = error_details(response)
            hint = _hint(response.status_code, details)
            message = 'HTTP %s %s %s: %s' % (response.status_code, method, path, details or response.reason)
            if hint:
                message += ' Hint: ' + hint
            raise ConnectorError(message)
        return self.decode(response)

    @staticmethod
    def _retry_wait(response, attempt):
        try:
            wait = float(response.headers.get('Retry-After'))
        except (TypeError, ValueError):
            wait = 2 ** attempt
        return max(0.0, min(wait, MAX_RETRY_WAIT))

    @staticmethod
    def decode(response):
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}

    # -- pagination --------------------------------------------------------

    def paginate_offset(self, path, params, key='values', limit=None, page_size=50):
        """Walk a startAt/maxResults endpoint. `limit` caps the total returned."""
        params = dict(params or {})
        params.setdefault('maxResults', page_size)
        params['startAt'] = int(params.get('startAt') or 0)
        items = []
        while True:
            page = self.request('GET', path, params=params)
            batch = page.get(key) or []
            items.extend(batch)
            if limit and len(items) >= limit:
                return items[:limit]
            if page.get('isLast', True) or not batch:
                return items
            params['startAt'] += len(batch)

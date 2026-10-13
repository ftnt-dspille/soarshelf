"""
Fixtures for the Jira v2 connector tests.

* The FortiSOAR SDK modules are stubbed so the connector imports standalone.
* FakeJira replaces requests.request / requests.get: no network. It records
  every call, answers from routes the test registers, and (through the `fake`
  fixture) fails a test whose operation calls an endpoint that scopes.py does
  not declare for it - which is what keeps the README permission tables true.
"""
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# The checkout directory may be named anything (a GitHub clone is named for the
# repo), so register it as the package `jirav2` instead of relying on its name.
_package = types.ModuleType('jirav2')
_package.__path__ = [str(ROOT)]
sys.modules['jirav2'] = _package


def _install_sdk_stubs():
    if 'connectors' in sys.modules and hasattr(sys.modules['connectors'], '_jirav2_stub'):
        return
    import logging

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__path__ = []
        mod.__dict__.update(attrs)
        sys.modules[name] = mod
        return mod

    class ConnectorError(Exception):
        pass

    class Connector(object):
        pass

    pkg = module('connectors', _jirav2_stub=True)
    core = module('connectors.core')
    module('connectors.core.connector', ConnectorError=ConnectorError, Connector=Connector,
           get_logger=lambda name: logging.getLogger(name))
    utils = module('connectors.cyops_utilities')
    module('connectors.cyops_utilities.builtins', download_file_from_cyops=lambda iri: {})
    pkg.core, pkg.cyops_utilities = core, utils
    integrations = module('integrations')
    module('integrations.crudhub', make_request=lambda iri, method: {})
    integrations.crudhub = sys.modules['integrations.crudhub']


_install_sdk_stubs()

from jirav2 import client as client_module  # noqa: E402
from jirav2.connector import JiraV2  # noqa: E402
from jirav2.scope_data import ENDPOINT_SCOPES  # noqa: E402
from jirav2.scopes import OPERATION_ENDPOINTS  # noqa: E402

SITE = 'https://example.atlassian.net'
GATEWAY = 'https://api.atlassian.com/ex/jira/abc-123'


class Reply(object):
    def __init__(self, status=200, body=None, headers=None, text=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        if text is not None:
            self.content = text.encode()
            self.text = text
        elif body is None:
            self.content, self.text = b'', ''
        else:
            self.text = json.dumps(body)
            self.content = self.text.encode()
        self.reason = {200: 'OK', 201: 'Created', 204: 'No Content', 400: 'Bad Request',
                       401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
                       429: 'Too Many Requests', 503: 'Service Unavailable'}.get(status, 'Status')

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._body is None:
            raise ValueError('no body')
        return self._body


class Call(object):
    def __init__(self, method, url, kwargs):
        self.method = method
        self.url = url
        self.params = kwargs.get('params') or {}
        self.json = kwargs.get('json')
        self.data = kwargs.get('data')
        self.files = kwargs.get('files')
        self.headers = kwargs.get('headers') or {}
        self.auth = kwargs.get('auth')
        self.verify = kwargs.get('verify')
        self.timeout = kwargs.get('timeout')
        self.path = '/' + url.split('://', 1)[1].split('/', 1)[1]
        if self.path.startswith('/ex/jira/'):
            self.path = '/' + self.path.split('/', 4)[4]


def _template_regex(template):
    return re.compile('^' + re.sub(r'\\\{[^}]+\\\}', '[^/]+', re.escape(template)) + '$')


_TEMPLATES = [(key, _template_regex(key.split(' ', 1)[1]), key.split(' ', 1)[0])
              for key in ENDPOINT_SCOPES]


def endpoint_for(method, path):
    """Map a concrete request to the spec template it instantiates, or None."""
    best = None
    for key, regex, verb in _TEMPLATES:
        if verb == method and regex.match(path):
            literal = len(re.sub(r'\{[^}]+\}', '', key))
            if best is None or literal > best[0]:
                best = (literal, key)
    return best[1] if best else None


class FakeJira(object):
    def __init__(self):
        self.calls = []
        self.routes = []
        self.unmatched = []

    def on(self, method, path, body=None, status=200, headers=None, text=None, times=None):
        """Register a reply. `path` is a concrete path (query string ignored)."""
        self.routes.append({'method': method.upper(), 'path': path, 'times': times,
                            'reply': (status, body, headers, text), 'queue': None})
        return self

    def on_sequence(self, method, path, replies):
        """Answer successive calls to one path with successive (status, body) pairs."""
        self.routes.append({'method': method.upper(), 'path': path, 'times': None,
                            'reply': None, 'queue': list(replies)})
        return self

    def request(self, method, url, **kwargs):
        call = Call(method.upper(), url, kwargs)
        self.calls.append(call)
        for route in self.routes:
            if route['method'] == call.method and route['path'] == call.path:
                if route['queue'] is not None:
                    status, body = route['queue'].pop(0) if len(route['queue']) > 1 else route['queue'][0]
                    return Reply(status, body)
                if route['times'] is not None:
                    if route['times'] <= 0:
                        continue
                    route['times'] -= 1
                status, body, headers, text = route['reply']
                return Reply(status, body, headers, text)
        self.unmatched.append(call)
        return Reply(404, {'errorMessages': ['no route for %s %s' % (call.method, call.path)]})

    # -- inspection --------------------------------------------------------

    def only(self):
        assert len(self.calls) == 1, 'expected exactly one call, got %s' % [
            (c.method, c.path) for c in self.calls]
        return self.calls[0]

    def paths(self):
        return [(c.method, c.path) for c in self.calls]

    def endpoints(self):
        return {endpoint_for(c.method, c.path) for c in self.calls}


@pytest.fixture(autouse=True)
def _fresh_cloud_id_cache():
    client_module._CLOUD_IDS.clear()
    yield
    client_module._CLOUD_IDS.clear()


@pytest.fixture
def config():
    return {'server_url': SITE, 'username': 'me@example.com', 'token': 'tok', 'verify_ssl': True}


@pytest.fixture
def fake(monkeypatch, request):
    jira = FakeJira()
    monkeypatch.setattr(client_module.requests, 'request', jira.request)
    monkeypatch.setattr(client_module, '_sleep', lambda seconds: None)
    client_module._CLOUD_IDS.clear()
    yield jira
    marker = request.node.get_closest_marker('op')
    assert not jira.unmatched, 'unrouted calls: %s' % [(c.method, c.path) for c in jira.unmatched]
    if marker is None:
        return
    declared = OPERATION_ENDPOINTS.get(marker.args[0])
    if declared is None:
        return
    used = jira.endpoints()
    assert None not in used, 'call to an endpoint absent from scope_data: %s' % jira.paths()
    assert used <= set(declared), '%s called %s but declares %s' % (marker.args[0], used, declared)


@pytest.fixture
def run(config):
    """run(operation, **params) -> result, through the real Connector.execute."""
    connector = JiraV2()

    def _run(operation, **params):
        return connector.execute(config, operation, params)
    return _run


@pytest.fixture(scope='session')
def site():
    """The online test site (see live_support.py); throwaway issues are deleted at session end."""
    from live_support import get_site, needs_site  # noqa: F401
    found = get_site()
    yield found
    found.cleanup()

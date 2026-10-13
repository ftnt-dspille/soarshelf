"""Test fixtures for the HashiCorp Vault KV connector.

- Stubs the FortiSOAR connector SDK so the connector imports standalone.
- Registers the hyphenated connector directory as the importable virtual
  package ``vaultkv``.
- Serves a ``FakeVault`` KV v2 engine on a loopback ephemeral port using
  only the standard library: token check, versioned reads/writes, and
  metadata listing.
"""

from __future__ import annotations

import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

CONNECTOR_DIR = Path(__file__).resolve().parent.parent

# --- stub the FortiSOAR SDK so the connector imports standalone ----------
if "connectors" not in sys.modules:
    _connectors = types.ModuleType("connectors")
    _connectors.__path__ = []
    _core = types.ModuleType("connectors.core")
    _core.__path__ = []
    _connector_mod = types.ModuleType("connectors.core.connector")

    class ConnectorError(Exception):
        pass

    import logging

    def get_logger(name):
        return logging.getLogger(name)

    class Connector:
        pass

    _connector_mod.ConnectorError = ConnectorError
    _connector_mod.get_logger = get_logger
    _connector_mod.Connector = Connector
    _core.connector = _connector_mod
    _connectors.core = _core
    sys.modules["connectors"] = _connectors
    sys.modules["connectors.core"] = _core
    sys.modules["connectors.core.connector"] = _connector_mod

# --- make the hyphenated dir importable as the 'vaultkv' package ----------
if "vaultkv" not in sys.modules:
    _pkg = types.ModuleType("vaultkv")
    _pkg.__path__ = [str(CONNECTOR_DIR)]
    sys.modules["vaultkv"] = _pkg

from vaultkv.connections import VaultClient  # noqa: E402


class FakeState:
    def __init__(self):
        self.port = 0
        self.reset()

    def reset(self):
        self.token = 'good-token'
        self.next_version = 3
        # KV v2 store: logical secret paths "lab/ai" -> {"value": {...}, "version": N}
        self.store = {
            'lab/ai': {'value': {'api_key': 'faig_old',
                                 'base_url': 'https://gw',
                                 'model': 'gpt-x'},
                       'version': 2},
        }


STATE = FakeState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self):
        return self.headers.get('X-Vault-Token') == STATE.token

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        if not self._authorized():
            self._send(403, {'errors': ['permission denied']})
            return
        if self.path == '/v1/auth/token/lookup-self':
            self._send(200, {'data': {'policies': ['lab-lab'],
                                      'display_name': 'root'}})
            return
        if self.path.startswith('/v1/secret/metadata'):
            if 'list=true' not in (self.path.split('?', 1) + [''])[1]:
                self._send(404, {'errors': ['not found']})
                return
            prefix = self.path.split('?', 1)[0][len('/v1/secret/metadata'):]
            prefix = prefix.strip('/')
            keys = set()
            for path in STATE.store:
                if prefix:
                    if not path.startswith(prefix + '/'):
                        continue
                    rest = path[len(prefix) + 1:]
                else:
                    rest = path
                top = rest.split('/')[0]
                keys.add(top if top == rest else top + '/')
            self._send(200, {'data': {'keys': sorted(keys)}})
            return
        if self.path.startswith('/v1/secret/data/'):
            key = self.path.split('?')[0][len('/v1/secret/data/'):]
            if key not in STATE.store:
                self._send(404, {'errors': ['not found']})
                return
            entry = STATE.store[key]
            version_param = ''
            if '?' in self.path and 'version=' in self.path:
                version_param = [p for p in self.path.split('?')[1].split('&')
                                 if p.startswith('version=')][0].split('=')[1]
            requested = int(version_param) if version_param else entry['version']
            if requested != entry['version']:
                self._send(404, {'errors': ['version not available']})
                return
            self._send(200, {'data': {
                'data': entry['value'],
                'metadata': {'version': entry['version']},
            }})
            return
        self._send(404, {'errors': ['not found']})

    def do_LIST(self):
        # Vault's LIST verb is GET ?list=true on the same path
        self.path = self.path.split('?')[0] + '?list=true'
        self.do_GET()

    def do_POST(self):
        if not self._authorized():
            self._send(403, {'errors': ['permission denied']})
            return
        if self.path.startswith('/v1/secret/data/'):
            key = self.path[len('/v1/secret/data/'):]
            body = self._body()
            STATE.next_version += 1
            STATE.store[key] = {'value': body.get('data', {}),
                               'version': STATE.next_version}
            self._send(200, {'data': {'version': STATE.next_version}})
            return
        self._send(404, {'errors': ['not found']})

    def do_DELETE(self):
        if not self._authorized():
            self._send(403, {'errors': ['permission denied']})
            return
        if self.path.startswith('/v1/secret/data/'):
            key = self.path[len('/v1/secret/data/'):]
            STATE.store.pop(key, None)
            self._send(204, {})
            return
        self._send(404, {'errors': ['not found']})


@pytest.fixture()
def fake():
    STATE.reset()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    STATE.port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield STATE
    server.shutdown()
    server.server_close()


@pytest.fixture()
def config(fake):
    return {
        'server': 'http://127.0.0.1:{0}'.format(STATE.port),
        'token': STATE.token,
        'mount': 'secret',
        'verify_ssl': False,
        'timeout': '10',
    }


def make_client(config, **overrides):
    merged = dict(config)
    merged.update(overrides)
    return VaultClient(
        server=merged['server'],
        token=merged['token'],
        mount=merged.get('mount') or 'secret',
        verify_ssl=merged.get('verify_ssl', False),
        timeout=merged.get('timeout') or 30,
    )

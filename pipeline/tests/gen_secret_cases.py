"""Regenerate tests/fixtures/secret_scan_cases.json from the Python scanner.

The browser pre-flight (site/src/lib/secretScan.ts) is a port of checks/secrets.py and
is tested against this file, so the two cannot drift apart silently. Run after changing
the scanner:  python tests/gen_secret_cases.py
"""
import json
from pathlib import Path

from soarshelf.checks import secrets

IMG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" * 4
CASES = [
    ("clean", {"a": "hello world", "n": 3}),
    ("aws key", {"x": "AKIAABCDEFGHIJKLMNOP"}),
    ("github token", {"x": "ghp_" + "a1B2c3D4e5" * 4}),
    ("slack", {"x": "xoxb-1234567890-abcdefghij"}),
    ("private key", {"k": "-----BEGIN RSA PRIVATE KEY-----\nabc"}),
    ("jwt", {"t": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"}),
    ("bearer", {"h": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789"}),
    ("url creds", {"u": "https://admin:hunter2@example.com/x", "v": "https://user:{{ vars.p }}@host/x"}),
    ("literal secret", {"arguments": {"password": "hunter2hunter2", "api_key": "<your key>", "token": "{{ vars.t }}"}}),
    ("secret with template", {"arguments": {"secret": "hunter2{{ vars.x }}"}}),
    ("short secret", {"arguments": {"password": "abc"}}),
    ("high entropy", {"v": "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE1fG3"}),
    ("hex hash", {"v": "d41d8cd98f00b204e9800998ecf8427ed41d8cd98f00b204e9800998ecf8427e"}),
    ("embedded image", {"logo": IMG}),
    ("templated entropy", {"v": "{{ aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE1fG3 }}"}),
    ("ips", {"v": "10.0.0.5 and 8.8.8.8 and 203.0.113.9 and 45.33.32.156 and 192.168.1.1/24 and 100.64.1.1 and 169.254.1.1"}),
    ("more ips", {"v": "224.0.0.1 240.0.0.1 198.18.0.1 192.0.0.8 172.16.5.5 172.32.0.1 0.0.0.0 255.255.255.255 1.1.1.1"}),
    ("leading zero ip", {"v": "version 01.02.03.04 and 010.1.1.1"}),
    ("email", {"v": "alice@corp-example.com bob@example.com carol@host.test dan@localhost"}),
    ("internal host", {"v": "dc01.corp.local and srv.lan and mail.internal and www.example.com"}),
    ("structural keys", {"uuid": "10.0.0.5", "@id": "admin@corp.com", "arguments": {"uuid": "10.0.0.5"}}),
    ("nested list", {"steps": [{"arguments": {"to": ["a@b.io", "c@d.io"], "x": [{"password": "longsecret123"}]}}]}),
    ("dedupe", {"a": "10.0.0.5", "b": "10.0.0.5", "c": "see 10.0.0.5 again"}),
    ("unicode", {"v": "café \U0001F600 alice@corp-example.com"}),
]
out = []
for name, doc in CASES:
    where = "file.json" if name == "nested list" else ""
    res = [r.to_dict() for r in secrets.scan(doc, where)]
    out.append({"name": name, "doc": doc, "where": where, "expected": res})
Path(__file__).parent.joinpath("fixtures", "secret_scan_cases.json").write_text(
    json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(len(out), "cases")

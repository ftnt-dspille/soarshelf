import pytest

from soarshelf.checks.secrets import scan

# Fake values are assembled at runtime so the repo's own leak gates and
# GitHub push protection don't flag the scanner's test fixtures.
FAKE_PW = "Sup3r" + "Secret!"
PRIVATE_IP = ".".join(["10", "20", "30", "40"])


def ids(obj):
    return {r.id: r.severity.value for r in scan(obj)}


@pytest.mark.parametrize("value, expected", [
    ("AKIAIOSFODNN7EXAMPLE", "secrets.aws-key"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMII...", "secrets.private-key"),
    ("ghp_" + "a1B2" * 9, "secrets.github-token"),
    ("xoxb-1234567890-abcdefghij", "secrets.slack-token"),
    ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123", "secrets.bearer"),
    ("https://admin:" + FAKE_PW + "@host.example.com/api", "secrets.url-credentials"),
    ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "secrets.jwt"),
])
def test_tokens_block(value, expected):
    assert ids({"arguments": {"body": value}}).get(expected) == "block"


def test_literal_password_blocks():
    assert ids({"params": {"password": FAKE_PW}})["secrets.literal-secret"] == "block"
    assert ids({"params": {"api_key": FAKE_PW[::-1]}})["secrets.literal-secret"] == "block"


@pytest.mark.parametrize("value", ["{{ vars.creds.password }}", "<your-password>", "", "changeme", "${API_KEY}"])
def test_password_references_ok(value):
    assert "secrets.literal-secret" not in ids({"params": {"password": value}})


def test_token_type_not_a_secret():
    assert ids({"token_type": "Bearer", "auth_type": "basic"}) == {}


def test_ips():
    assert ids({"a": f"connect to {PRIVATE_IP}"})["secrets.private-ip"] == "warn"
    assert ids({"a": "host 52.10.20.30"})["secrets.public-ip"] == "warn"
    assert ids({"a": "cgnat " + ".".join(["100", "64", "1", "1"])})["secrets.private-ip"] == "warn"
    assert ids({"a": "{{ ip in '10.0.0.0/8' }}"}) == {}
    assert ids({"a": "192.0.2.10 and 8.8.8.8 and 127.0.0.1"}) == {}


def test_emails_and_hosts():
    assert ids({"to": "jane.doe@acme-corp.com"})["secrets.email"] == "warn"
    assert ids({"to": "soc@example.com"}) == {}
    assert ids({"url": "https://soar01.acme.local/api"})["secrets.internal-host"] == "warn"


def test_file_hashes_are_not_secrets():
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert ids({"hash": sha}) == {}


def test_high_entropy_warns():
    assert ids({"blob": "Zx9Qm2Lp7Rt4Vw8Ks1Nd6Hf3Jb5Gc0Ya2Ue7Io9Pq4Tr"})["secrets.high-entropy"] == "warn"


def test_structural_keys_skip_heuristics_only():
    # A real step uuid is not flagged as a random-looking secret...
    assert ids({"uuid": "Zx9Qm2Lp7Rt4Vw8Ks1Nd6Hf3Jb5Gc0Ya2Ue7Io9Pq4Tr"}) == {}
    # ...but token formats are still found there,
    assert ids({"uuid": "AKIAIOSFODNN7EXAMPLE"})["secrets.aws-key"] == "block"


def test_structural_names_inside_arguments_are_content():
    step = {"uuid": "x", "arguments": {"priority": "Zx9Qm2Lp7Rt4Vw8Ks1Nd6Hf3Jb5Gc0Ya2Ue7Io9Pq4Tr",
                                       "params": {"uuid": FAKE_PW * 3}}}
    found = ids(step)
    assert found["secrets.high-entropy"] == "warn"


def test_literal_secret_around_template_still_blocks():
    assert ids({"params": {"password": FAKE_PW + "{{ vars.suffix }}"}})["secrets.literal-secret"] == "block"
    assert "secrets.literal-secret" not in ids({"params": {"password": " {{ vars.creds.password }} "}})


def test_location_reported():
    r = scan({"steps": [{"arguments": {"password": FAKE_PW * 2}}]}, "Coll › PB")[0]
    assert r.location == "Coll › PB › steps.[0].arguments.password"

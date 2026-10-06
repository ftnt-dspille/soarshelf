"""Find credentials and environment details in playbook content.

``block``: something that is almost certainly a live secret.
``warn``:  something that identifies a real environment (internal IPs and
           hostnames, real email addresses) and needs a human to look at it.
"""
from __future__ import annotations

import base64
import binascii
import ipaddress
import math
import re
from collections.abc import Iterator
from typing import Any

from ..model import CheckResult, Severity

# High-confidence token formats. Scanned on the whole string, Jinja included,
# because a secret quoted inside a template is still a secret.
_TOKENS: list[tuple[str, str, re.Pattern[str]]] = [
    ("private-key", "Private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("aws-key", "AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", "Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google-key", "Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-key", "Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}")),
    ("jwt", "JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer", "Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{24,}=*")),
    ("url-credentials", "Credentials in a URL",
     re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@{}]+:(?!\{\{)[^\s/@{}]+@", re.I)),
]

# Argument names whose literal value is a secret.
_SECRET_KEY = re.compile(
    r"^(?:.*[_-])?(password|passwd|pwd|passphrase|secret|client[_-]?secret|api[_-]?key|apikey|"
    r"access[_-]?token|refresh[_-]?token|auth[_-]?token|token|private[_-]?key|secret[_-]?key)$",
    re.I,
)
_TEMPLATE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
_PLACEHOLDER = re.compile(r"^\s*(<[^>]+>|\$\{[^}]+\}|x{3,}|\*{3,}|changeme|your[_ -].*|example.*)\s*$", re.I)

_IPV4 = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(/\d{1,2})?(?![\d.])")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_INTERNAL_HOST = re.compile(
    r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:local|lan|internal|intranet|intra|corp|home|localdomain|ad)\b", re.I)

_DOC_NETS = [ipaddress.ip_network(n) for n in
             ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "127.0.0.0/8", "0.0.0.0/8")]
_PUBLIC_RESOLVERS = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "208.67.222.222"}
_EXAMPLE_DOMAINS = re.compile(r"(^|\.)(example\.(com|org|net)|test|invalid|localhost)$", re.I)

# Structural keys whose values are identifiers, not content.
_SKIP_KEYS = {"uuid", "@type", "@id", "stepType", "triggerStep", "sourceStep", "targetStep",
              "step_iri", "workflowReference", "priority"}


def _walk(node: Any, path: tuple[str, ...], free: bool = False
          ) -> Iterator[tuple[tuple[str, ...], str | None, str, bool]]:
    """Yield (path, key, string, structural) for every string value.

    ``structural`` marks identifier fields (uuid, stepType, ...) of the export
    format itself. Inside ``arguments`` everything is author content, so the
    same key names there are never treated as structural.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            inner = free or k == "arguments"
            if isinstance(v, str):
                yield path + (str(k),), str(k), v, (k in _SKIP_KEYS and not free)
            else:
                yield from _walk(v, path + (str(k),), inner)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                yield path + (f"[{i}]",), None, v, False
            else:
                yield from _walk(v, path + (f"[{i}]",), free)


def _entropy(s: str) -> float:
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


_CANDIDATE = re.compile(r"[A-Za-z0-9+/_=-]{40,}")
_HEXISH = re.compile(r"^[0-9a-fA-F]+$")


_IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"<svg", b"<?xml", b"RIFF")


def _is_image(s: str) -> bool:
    """Base64 of an embedded image (logos, screenshots): long and random, not a secret."""
    if len(s) < 200:
        return False
    try:
        head = base64.b64decode(s[:64] + "=" * (-len(s[:64]) % 4), validate=False)
    except (binascii.Error, ValueError):
        return False
    return head.startswith(_IMAGE_MAGIC)


def _looks_random(s: str) -> bool:
    """A long token with mixed character classes and high entropy.

    Pure hex is skipped: file hashes (IOCs) are normal playbook content.
    """
    if _HEXISH.match(s):
        return False
    classes = sum(bool(re.search(p, s)) for p in (r"[a-z]", r"[A-Z]", r"\d"))
    return classes == 3 and _entropy(s) > 4.5


def scan(doc: Any, where: str = "") -> list[CheckResult]:
    """Scan any JSON value. ``where`` prefixes each finding's location."""
    found: dict[tuple[str, str], CheckResult] = {}

    def hit(id_: str, sev: Severity, title: str, detail: str, path: tuple[str, ...]) -> None:
        loc = " › ".join(p for p in (where, ".".join(path)) if p)
        found.setdefault((id_, detail), CheckResult(f"secrets.{id_}", sev, title, detail, loc))

    for path, key, value, structural in _walk(doc, ()):
        # Token formats are checked everywhere, identifier fields included.
        for id_, label, rx in _TOKENS:
            m = rx.search(value)
            if m:
                hit(id_, Severity.BLOCK, f"{label} found", _mask(m.group(0)), path)
        if structural:
            continue                     # heuristics below would flag UUIDs and IRIs

        # Template expressions are references, not secrets; whatever literal
        # text surrounds them still counts ("hunter2{{ vars.x }}").
        literal = _TEMPLATE.sub("", value).strip()
        if key and _SECRET_KEY.match(key) and literal and not _PLACEHOLDER.match(literal) \
                and len(literal) >= 6:
            hit("literal-secret", Severity.BLOCK, f"Literal value in '{key}'",
                f"{_mask(value)} - reference a connector configuration or a variable instead.", path)

        for m in _CANDIDATE.finditer(value):
            if "{{" not in value and _looks_random(m.group(0)) and not _is_image(m.group(0)):
                hit("high-entropy", Severity.WARN, "Possible secret (random-looking string)",
                    _mask(m.group(0)), path)

        for m in _IPV4.finditer(value):
            ip, cidr = m.group(1), m.group(2)
            addr = ipaddress.ip_address(ip)
            if any(addr in n for n in _DOC_NETS) or ip in _PUBLIC_RESOLVERS:
                continue
            if cidr:
                # Network ranges in logic ("is it in 10.0.0.0/8?") are normal.
                continue
            if addr.is_global:
                hit("public-ip", Severity.WARN, "Public IP address",
                    f"{ip} - use 192.0.2.x / 198.51.100.x / 203.0.113.x for examples.", path)
            else:   # RFC 1918, carrier-grade NAT, link-local and other non-routable space
                hit("private-ip", Severity.WARN, "Internal IP address", ip, path)

        for m in _EMAIL.finditer(value):
            if not _EXAMPLE_DOMAINS.search(m.group(1)):
                hit("email", Severity.WARN, "Email address", m.group(0), path)

        for m in _INTERNAL_HOST.finditer(value):
            hit("internal-host", Severity.WARN, "Internal hostname", m.group(0), path)

    return list(found.values())


def _mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}…{s[-2:]} ({len(s)} chars)"

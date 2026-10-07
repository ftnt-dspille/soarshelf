"""The scanner against its golden cases. The browser port is tested against the same file,
so a change to checks/secrets.py has to be mirrored in site/src/lib/secretScan.ts:
regenerate with `python tests/gen_secret_cases.py`, then run the site tests."""
import json
from pathlib import Path

import pytest

from soarshelf.checks import secrets

CASES = json.loads((Path(__file__).parent / "fixtures" / "secret_scan_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_scan_matches_golden(case):
    assert [r.to_dict() for r in secrets.scan(case["doc"], case["where"])] == case["expected"]


def test_leading_zero_numbers_do_not_crash_the_scan():
    assert secrets.scan({"v": "release 2024.01.02.03 and 010.1.1.1"}) == []

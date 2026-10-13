"""Rules FortiSOAR imposes on connector source, which no unit test of behaviour would catch."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted(p for p in ROOT.glob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
SHIPPED = [p for p in SOURCES if p.parent == ROOT]


@pytest.mark.parametrize('path', SOURCES, ids=lambda p: p.name)
def test_source_is_ascii(path):
    """FortiSOAR loads connector source as latin-1: one en/em dash raises UnicodeEncodeError."""
    bad = [(n, ch) for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
           for ch in line if ord(ch) > 127]
    assert not bad, 'non-ASCII in %s: %s' % (path.name, bad[:3])


@pytest.mark.parametrize('path', SHIPPED, ids=lambda p: p.name)
def test_shipped_code_parses_as_python_3_9(path):
    ast.parse(path.read_text(), feature_version=(3, 9))


def test_json_files_are_ascii():
    for name in ('info.json', 'README.md', 'release_notes.md'):
        text = (ROOT / name).read_text(encoding='utf-8')
        assert all(ord(c) < 128 for c in text), name

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_readme_permission_tables_are_current():
    result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts' / 'gen_docs.py'), '--check'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_action_title_appears_in_the_readme():
    import json
    readme = (ROOT / 'README.md').read_text()
    for op in json.load(open(ROOT / 'info.json'))['operations']:
        if op.get('visible', True):
            assert op['title'] in readme, op['title']

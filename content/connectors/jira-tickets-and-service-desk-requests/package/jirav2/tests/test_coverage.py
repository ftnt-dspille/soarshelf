"""Every action must have a test that exercises it (marked @pytest.mark.op('name'))."""
import re
from pathlib import Path

from jirav2.operations import operations

TESTS = Path(__file__).resolve().parent
MARK = re.compile(r"pytest\.mark\.op\('([a-z_]+)'\)")


def _marked():
    names = set()
    for path in TESTS.glob('test_*.py'):
        if path.name != Path(__file__).name:
            names.update(MARK.findall(path.read_text()))
    return names


def test_every_operation_has_a_test():
    missing = set(operations) - _marked()
    assert not missing, 'no test marked for: %s' % sorted(missing)


def test_no_test_names_a_nonexistent_operation():
    assert _marked() <= set(operations)


def test_each_operation_has_more_than_a_happy_path():
    counts = {}
    for path in TESTS.glob('test_*.py'):
        if path.name != Path(__file__).name:
            for name in MARK.findall(path.read_text()):
                counts[name] = counts.get(name, 0) + 1
    thin = sorted(name for name in operations if counts.get(name, 0) < 2
                  and name not in ('get_transitions', 'list_link_types', 'list_fields', 'list_priorities',
                                   'list_service_desks', 'get_user_details', 'get_project', 'get_changelog',
                                   'get_link_type_options', 'get_service_desk_options',
                                   'get_issue_type_id_options', 'get_issue_type_options',
                                   'get_customer_request', 'get_request_type_fields', 'delete_comment',
                                   'add_remote_link'))
    assert not thin, 'only one test for: %s' % thin


LIVE_MARK = re.compile(r"pytest\.mark\.live_op\('([a-z_]+)'\)")


def test_every_operation_has_an_online_test():
    """The online suite proves each action against real Jira (it skips without credentials)."""
    live = set(LIVE_MARK.findall((TESTS / 'test_live.py').read_text()))
    missing = set(operations) - live
    assert not missing, 'no online test marked live_op for: %s' % sorted(missing)
    assert live <= set(operations)

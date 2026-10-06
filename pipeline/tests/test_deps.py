from soarshelf.deps import collect
from soarshelf.model import ParsedCollection, ParsedPlaybook, Step


def _deps(args):
    pb = ParsedPlaybook(name="p", description="", trigger_step=None, routes=[],
                        steps=[Step(id="s", name="s", type_uuid="", arguments=args)])
    return collect([ParsedCollection(name="c", description="", playbooks=[pb])], set())


def test_resources_as_string_is_one_module():
    assert _deps({"resources": "alerts"}).modules == {"alerts"}


def test_resources_as_list():
    assert _deps({"resources": ["alerts", "incidents"]}).modules == {"alerts", "incidents"}

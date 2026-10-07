"""A "reference a playbook" step records which playbook it runs, so the viewer can link parent and child."""
from soarshelf import graph
from soarshelf.model import ParsedCollection, ParsedPlaybook, Step

REFERENCE = "74932bdc-b8b6-4d24-88c4-1a4dfbc524f3"


def test_reference_steps_point_at_the_child_playbook_by_uuid():
    child = ParsedPlaybook(name="Child", description="", trigger_step=None, steps=[], routes=[], uuid="aaaa-1111")
    step = Step(id="s1", name="Run child", type_uuid=REFERENCE, arguments={"workflowReference": "/api/3/workflows/AAAA-1111"}, x=0, y=0)
    parent = ParsedPlaybook(name="Parent", description="", trigger_step=None, steps=[step], routes=[], uuid="bbbb-2222")
    out = graph.collections_graph([ParsedCollection("C", "", [parent, child])])[0]["playbooks"]
    assert [p["uuid"] for p in out] == ["bbbb-2222", "aaaa-1111"]
    assert out[0]["nodes"][0]["reference"] == "aaaa-1111"
    assert "reference" not in graph.collections_graph([ParsedCollection("C", "", [child])])[0]["playbooks"][0]

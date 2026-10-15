"""Designer notes and blocks reach the viewer: a note is tied to the step it sat
closest to (the viewer lays steps out itself), a block lists its steps."""
from soarshelf import graph
from soarshelf.model import ParsedCollection, ParsedPlaybook, Step


def _groups(steps, groups):
    pb = ParsedPlaybook(name="P", description="", trigger_step=None, steps=steps, routes=[], groups=groups)
    return graph.collections_graph([ParsedCollection("C", "", [pb])])[0]["playbooks"][0]["groups"]


def test_a_note_is_tied_to_the_nearest_step():
    steps = [Step("a", "A", "", {}, x=0, y=0), Step("b", "B", "", {}, x=0, y=400)]
    note = {"uuid": "n1", "type": "note", "name": "Why", "description": "Because.",
            "left": "300", "top": "390", "width": "200", "height": "80"}
    assert _groups(steps, [note]) == [{"id": "n1", "kind": "note", "name": "Why", "text": "Because.", "anchor": "b"}]


def test_steps_in_a_block_are_measured_from_the_block():
    # "b" is at (20, 20) inside a block at (900, 0): really beside the note on the right.
    steps = [Step("a", "A", "", {}, x=0, y=0), Step("b", "B", "", {}, x=20, y=20, group="blk")]
    block = {"uuid": "blk", "type": "block", "name": "Setup", "left": "900", "top": "0"}
    note = {"uuid": "n1", "type": "note", "name": "Here", "left": "1200", "top": "0", "width": "100", "height": "50"}
    out = _groups(steps, [block, note])
    assert out[0] == {"id": "blk", "kind": "block", "name": "Setup", "text": "", "steps": ["b"]}
    assert out[1]["anchor"] == "b"


def test_empty_groups_are_dropped():
    assert _groups([Step("a", "A", "", {})], [{"uuid": "x", "type": "note", "name": "", "description": ""}]) == []


def test_a_note_titled_after_a_step_goes_to_that_step():
    # Notes laid out in a column far to the right sit nearer to the branch steps
    # than to the step they describe.
    steps = [Step("k", "KeyValid", "", {}, x=200, y=640), Step("h", "AlreadyHealthy", "", {}, x=880, y=770),
             Step("f", "FailRotation", "", {}, x=1220, y=1420), Step("d", "Done", "", {}, x=880, y=1420)]
    note = lambda uid, name, left, top: {"uuid": uid, "type": "note", "name": name, "description": "x",
                                         "left": str(left), "top": str(top), "width": "440", "height": "72"}
    out = _groups(steps, [note("n1", "Note: KeyValid", 1220, 640), note("n2", "Note: Done", 1560, 1512)])
    assert [g["anchor"] for g in out] == ["k", "d"]


def test_an_untitled_note_prefers_a_step_in_its_own_row():
    # "b" in the next row is nearer, but the note sits level with "a".
    steps = [Step("a", "A", "", {}, x=0, y=0), Step("b", "B", "", {}, x=600, y=80)]
    note = {"uuid": "n1", "type": "note", "name": "Why", "left": "620", "top": "0", "width": "200", "height": "60"}
    assert _groups(steps, [note])[0]["anchor"] == "a"

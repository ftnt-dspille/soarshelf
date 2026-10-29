from soarshelf.deps import checks, collect, connector_rows, declared_rows
from soarshelf.hubindex import HubIndex
from soarshelf.model import ParsedCollection, ParsedPlaybook, Step
from soarshelf.refs import RefTarget
from soarshelf import setup_guide

HUB = HubIndex(snapshot="x", connectors={"jirav2": {"label": "Jira v2", "version": "1.0.2",
                                                    "versions": ["1.0.2"], "operations": ["create_ticket"]}},
               packs={})

JIRA_CHILD = RefTarget(item="jira-item", name="Jira v2 - Create Ticket",
                       connectors=frozenset({"jirav2"}),
                       ops={"jirav2": frozenset({"create_ticket"})},
                       version={}, refs=frozenset())
REGISTRY = {"cccccccc-cccc-4ccc-8ccc-cccccccccccc": JIRA_CHILD}


def _deps(args):
    pb = ParsedPlaybook(name="p", description="", trigger_step=None, routes=[],
                        steps=[Step(id="s", name="s", type_uuid="", arguments=args)])
    return collect([ParsedCollection(name="c", description="", playbooks=[pb])], set())


def _pb(uuid, steps_args, name="p"):
    return ParsedPlaybook(name=name, description="", trigger_step=None, routes=[],
                          steps=[Step(id=f"s{i}", name=f"step {i}", type_uuid="", arguments=a)
                                 for i, a in enumerate(steps_args)],
                          uuid=uuid)


def test_resources_as_string_is_one_module():
    assert _deps({"resources": "alerts"}).modules == {"alerts"}


def test_resources_as_list():
    assert _deps({"resources": ["alerts", "incidents"]}).modules == {"alerts", "incidents"}


def test_reference_resolves_and_pulls_the_childs_connectors():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/CCCCCCCC-CCCC-4CCC-8CCC-CCCCCCCCCCCC"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(), REGISTRY)
    assert deps.connectors["jirav2"]["via"] == {"jira-item"}
    assert deps.connectors["jirav2"]["operations"] == {"create_ticket"}
    assert deps.missing_refs == []
    assert [(r.item, r.playbook) for r in deps.resolved_refs] == \
        [("jira-item", "Jira v2 - Create Ticket")]


def test_unresolvable_reference_stays_a_warning():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/dddddddd-dddd-4ddd-8ddd-dddddddddddd"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(), REGISTRY)
    assert deps.missing_refs == ["c › p › step 0"]
    assert deps.resolved_refs == []


def test_reference_into_the_same_payload_is_neither_missing_nor_external():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/AAAA-1111"}])
    deps = collect([ParsedCollection("c", "", [parent])], {"aaaa-1111"}, REGISTRY)
    assert deps.missing_refs == [] and deps.resolved_refs == []


def test_resolution_is_transitive_and_cycle_safe():
    a = RefTarget(item="item-a", name="A", connectors=frozenset({"conn-a"}), ops={}, version={},
                  refs=frozenset({"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}))
    b = RefTarget(item="item-b", name="B", connectors=frozenset({"conn-b"}), ops={}, version={},
                  refs=frozenset({"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                                  "cccccccc-cccc-4ccc-8ccc-cccccccccccc"}))
    c = RefTarget(item="item-c", name="C", connectors=frozenset({"conn-c"}), ops={}, version={},
                  refs=frozenset({"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}))
    parent = _pb("pppppppp-pppp-4ppp-8ppp-pppppppppppp",
                 [{"workflowReference": "/api/3/workflows/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(),
                   {"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa": a,
                    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb": b,
                    "cccccccc-cccc-4ccc-8ccc-cccccccccccc": c})
    assert {k: v["via"] for k, v in deps.connectors.items()} == {
        "conn-a": {"item-a"}, "conn-b": {"item-b"}, "conn-c": {"item-c"}}


def test_resolved_reference_is_info_and_missing_is_warn():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/CCCCCCCC-CCCC-4CCC-8CCC-CCCCCCCCCCCC"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(), REGISTRY)
    rows = connector_rows(deps, HUB)
    ids = {r.id: r for r in checks(deps, rows)}
    assert "deps.missing-reference" not in ids
    assert ids["deps.reference-resolved"].severity.name == "INFO"


def test_rows_carry_via():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/CCCCCCCC-CCCC-4CCC-8CCC-CCCCCCCCCCCC"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(), REGISTRY)
    row = next(r for r in connector_rows(deps, HUB) if r["name"] == "jirav2")
    assert row["via"] == ["jira-item"] and row["hub"] == "available"


def test_declared_rows_append_what_the_steps_do_not_show():
    rows = [{"name": "cyops_utilities", "label": "Utilities", "version": None,
             "operations": ["json_to_html"], "hub": "available", "hubVersion": "1.0.0", "via": []}]
    out = declared_rows(rows, ["jirav2", "cyops_utilities"], HUB)
    assert [r["name"] for r in out] == ["cyops_utilities", "jirav2"]
    assert out[-1]["declared"] is True and out[-1]["hub"] == "available" and out[-1]["via"] == []


def test_declared_connector_not_on_hub_counts_as_missing():
    out = declared_rows([], ["acme"], HUB)
    assert out[0]["hub"] == "missing" and out[0]["declared"] is True


def test_setup_guide_sends_the_reader_to_the_referenced_item():
    parent = _pb("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                 [{"workflowReference": "/api/3/workflows/CCCCCCCC-CCCC-4CCC-8CCC-CCCCCCCCCCCC"}])
    deps = collect([ParsedCollection("c", "", [parent])], set(), REGISTRY)
    rows = declared_rows(connector_rows(deps, HUB), [], HUB)
    steps = setup_guide.steps("playbook", rows, [], deps, None, [parent], False, {"slug": "x"})
    kinds = [s["kind"] for s in steps]
    assert "install-connector" in kinds
    assert any(s["title"] == "Get the jira-item item" for s in steps)

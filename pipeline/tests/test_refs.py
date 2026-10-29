"""The playbook registry: what a reference step can resolve to across items."""
import json
import zipfile

from soarshelf.refs import scan


def _workflow(uuid, name, steps):
    return {"@type": "Workflow", "name": name, "description": "", "uuid": uuid, "steps": steps}


PARENT = {
    "type": "workflow_collections",
    "data": [{
        "@type": "WorkflowCollection", "name": "Ticketing", "description": "",
        "workflows": [_workflow("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Create Ticket", [
            {"@type": "WorkflowStep", "name": "Run child",
             "arguments": {"workflowReference": "/api/3/workflows/cccc-cccc/"}},
            {"@type": "WorkflowStep", "name": "HTML",
             "arguments": {"connector": "cyops_utilities", "operation": "json_to_html"}},
        ])],
    }],
}

SAMPLE = {
    "type": "workflow_collections",
    "data": [{
        "@type": "WorkflowCollection", "name": "Sample - Jira v2", "description": "",
        "workflows": [_workflow("cccc-cccc", "Jira v2 - Create Ticket", [
            {"@type": "WorkflowStep", "name": "Create Ticket",
             "arguments": {"connector": "jirav2", "operation": "create_ticket", "version": "1.0.2"}},
        ])],
    }],
}


def _content_with_a_playbook_and_a_connector(tmp_path):
    content = tmp_path / "content"
    pb = content / "playbooks" / "parent-item"
    pb.mkdir(parents=True)
    (pb / "meta.yaml").write_text("title: Parent\n")
    (pb / "playbook.json").write_text(json.dumps(PARENT))
    (pb / "playbook.yaml").write_text("# review view - not a payload\n")
    conn = content / "connectors" / "jira-item" / "package" / "jirav2" / "playbooks"
    conn.mkdir(parents=True)
    (conn / "playbooks.json").write_text(json.dumps(SAMPLE))
    return content


def test_scan_maps_uuids_to_the_item_that_ships_them(tmp_path):
    reg = scan(_content_with_a_playbook_and_a_connector(tmp_path))
    assert set(reg) == {"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "cccc-cccc"}
    child = reg["cccc-cccc"]
    assert (child.item, child.name) == ("jira-item", "Jira v2 - Create Ticket")
    assert child.connectors == frozenset({"jirav2"})
    assert child.ops == {"jirav2": frozenset({"create_ticket"})}
    assert child.version == {"jirav2": "1.0.2"}
    parent = reg["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]
    assert parent.item == "parent-item"
    assert parent.refs == frozenset({"cccc-cccc"})
    assert parent.connectors == frozenset({"cyops_utilities"})


def test_scan_reads_solution_pack_members(tmp_path):
    content = tmp_path / "content"
    sp = content / "solution-packs" / "pack-item"
    sp.mkdir(parents=True)
    wf = _workflow("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", "Pivot",
                   [{"@type": "WorkflowStep", "name": "Ping",
                     "arguments": {"connector": "acme", "operation": "ping"}}])
    with zipfile.ZipFile(sp / "pack.zip", "w") as z:
        z.writestr("playbooks/Collection/pivot.json", json.dumps(wf))
        z.writestr("README.md", "not a playbook")
    reg = scan(content)
    assert reg["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"].item == "pack-item"
    assert reg["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"].connectors == frozenset({"acme"})


def test_scan_skips_an_unreadable_item_without_dying(tmp_path, capsys):
    content = tmp_path / "content"
    bad = content / "playbooks" / "bad-item"
    bad.mkdir(parents=True)
    (bad / "meta.yaml").write_text("title: x\n")
    (bad / "a.json").write_text("{not json")
    (bad / "b.json").write_text("{}")
    assert scan(content) == {}
    assert "bad-item" in capsys.readouterr().out

import yaml

from soarshelf.authors import changed_items, verify


def _repo(tmp_path, items: dict[str, str], maintainers=("boss",)):
    (tmp_path / "content").mkdir(parents=True)
    (tmp_path / "content" / "contributors.yaml").write_text(yaml.safe_dump({m: "maintainer" for m in maintainers}))
    for slug, author in items.items():
        d = tmp_path / "content" / "playbooks" / slug
        d.mkdir(parents=True)
        (d / "meta.yaml").write_text(yaml.safe_dump({"author": author}))
    return tmp_path


def test_changed_items_only_counts_item_paths():
    assert changed_items(["content/playbooks/a/meta.yaml", "content/playbooks/a/playbook.json",
                          "content/contributors.yaml", "site/x.ts"]) == {"content/playbooks/a"}


def test_own_item_ok(tmp_path):
    repo = _repo(tmp_path, {"a": "alice"})
    assert verify(repo, ["content/playbooks/a/meta.yaml"], "Alice", set()) == []


def test_impersonation_rejected(tmp_path):
    repo = _repo(tmp_path, {"a": "boss"})
    errors = verify(repo, ["content/playbooks/a/meta.yaml"], "mallory", set())
    assert errors and "only add or change your own" in errors[0]


def test_deleting_needs_maintainer(tmp_path):
    repo = _repo(tmp_path, {})
    assert verify(repo, ["content/playbooks/gone/meta.yaml"], "alice", set())
    assert verify(repo, ["content/playbooks/gone/meta.yaml"], "boss", set()) == []


def test_bot_may_change_anything(tmp_path):
    repo = _repo(tmp_path, {"a": "alice"})
    assert verify(repo, ["content/playbooks/a/meta.yaml"], "soarshelf-bot[bot]", {"soarshelf-bot[bot]"}) == []


def test_pr_cannot_promote_itself(tmp_path):
    head = _repo(tmp_path / "head", {"a": "boss"}, maintainers=("mallory",))   # PR edits contributors.yaml
    base = _repo(tmp_path / "base", {"a": "boss"}, maintainers=("boss",))
    assert verify(head, ["content/playbooks/a/meta.yaml"], "mallory", set(), trust_repo=base)

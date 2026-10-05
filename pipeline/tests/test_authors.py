import yaml

from soarshelf.authors import changed_items, file_reader, verify


def _tree(root, items: dict[str, str], maintainers=("boss",)):
    (root / "content").mkdir(parents=True)
    (root / "content" / "contributors.yaml").write_text(yaml.safe_dump({m: "maintainer" for m in maintainers}))
    for slug, author in items.items():
        d = root / "content" / "playbooks" / slug
        d.mkdir(parents=True)
        (d / "meta.yaml").write_text(yaml.safe_dump({"author": author}))
    return root


def run(tmp_path, base_items, head_items, who, changed, base_maint=("boss",), head_maint=("boss",), bots=()):
    base = _tree(tmp_path / "base", base_items, base_maint)
    head = _tree(tmp_path / "head", head_items, head_maint)
    return verify(changed, who, set(bots), base, file_reader(base), file_reader(head))


A = ["content/playbooks/a/meta.yaml"]


def test_changed_items_only_counts_item_paths():
    assert changed_items(A + ["content/playbooks/a/playbook.json", "content/contributors.yaml",
                              "site/x.ts"]) == {"content/playbooks/a"}


def test_new_own_item_ok(tmp_path):
    assert run(tmp_path, {}, {"a": "alice"}, "Alice", A) == []


def test_new_item_credited_to_someone_else(tmp_path):
    assert run(tmp_path, {}, {"a": "boss"}, "mallory", A)


def test_taking_over_existing_item_rejected(tmp_path):
    # mallory edits alice's item and rewrites author to herself
    errors = run(tmp_path, {"a": "alice"}, {"a": "mallory"}, "mallory", A)
    assert errors and "belongs to 'alice'" in errors[0]


def test_editing_own_existing_item_ok(tmp_path):
    assert run(tmp_path, {"a": "alice"}, {"a": "alice"}, "alice", A) == []


def test_deleting_needs_maintainer(tmp_path):
    assert run(tmp_path, {"a": "alice"}, {}, "alice", A)
    assert run(tmp_path / "m", {"a": "alice"}, {}, "boss", A) == []


def test_pr_cannot_promote_itself(tmp_path):
    assert run(tmp_path, {"a": "boss"}, {"a": "boss"}, "mallory", A, base_maint=("boss",), head_maint=("mallory",))


def test_bot_may_change_anything(tmp_path):
    assert run(tmp_path, {"a": "alice"}, {"a": "bob"}, "soarshelf-bot[bot]", A, bots=("soarshelf-bot[bot]",)) == []


def test_cli_against_real_git(tmp_path):
    import subprocess

    from soarshelf.cli import main

    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    _tree(tmp_path, {"a": "alice"})
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "content/playbooks/a/meta.yaml").write_text(yaml.safe_dump({"author": "mallory"}))
    git("commit", "-qam", "takeover")
    head = git("rev-parse", "HEAD")
    git("checkout", "-q", base)

    import io, sys
    sys.stdin = io.StringIO("content/playbooks/a/meta.yaml\n")
    try:
        rc = main(["verify-authors", "--repo", str(tmp_path), "--base", base, "--head", head, "--pr-author", "mallory"])
    finally:
        sys.stdin = sys.__stdin__
    assert rc == 1

import yaml

from soarshelf.authors import changed_items, file_reader, verify


IDS = {"boss": 1, "alice": 2, "bob": 3, "mallory": 666}


def _tree(root, items: dict, maintainers=("boss",)):
    (root / "content").mkdir(parents=True)
    (root / "content" / "contributors.yaml").write_text(
        yaml.safe_dump({m: {"trust": "maintainer", "id": IDS[m]} for m in maintainers}))
    for slug, author in items.items():
        d = root / "content" / "playbooks" / slug
        d.mkdir(parents=True)
        meta = author if isinstance(author, dict) else {"author": author, "author_id": IDS[author]}
        (d / "meta.yaml").write_text(yaml.safe_dump(meta))
    return root


def run(tmp_path, base_items, head_items, who, changed, base_maint=("boss",), head_maint=("boss",), bots=(),
        uid=None):
    base = _tree(tmp_path / "base", base_items, base_maint)
    head = _tree(tmp_path / "head", head_items, head_maint)
    return verify(changed, who, set(bots), base, file_reader(base), file_reader(head),
                  pr_author_id=uid if uid is not None else IDS.get(who.lower()))


A = ["content/playbooks/a/meta.yaml"]


def test_changed_items_only_counts_item_paths():
    items, errors = changed_items(A + ["content/playbooks/a/playbook.json", "content/contributors.yaml", "site/x.ts"])
    assert items == {"content/playbooks/a"} and errors == []


def test_unclassifiable_content_paths_fail():
    for bad in ['content/playbooks/"weird slug"/meta.yaml', "content/playbooks/Caps/meta.yaml",
                "content/other/x/meta.yaml", "content/playbooks/loose.json"]:
        assert changed_items([bad])[1], bad


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


def test_reclaimed_maintainer_login_is_not_a_maintainer(tmp_path):
    # "boss" renamed their account; someone else registered the old login
    assert run(tmp_path, {"a": "alice"}, {}, "boss", A, uid=4242)


def test_tier_without_id_grants_nothing(tmp_path):
    base = _tree(tmp_path / "b", {"a": "alice"}, ())
    (base / "content" / "contributors.yaml").write_text("boss: maintainer\n")
    assert verify(A, "boss", set(), base, file_reader(base), file_reader(_tree(tmp_path / "h", {}, ())), pr_author_id=1)


def test_item_bound_to_author_id(tmp_path):
    item = {"author": "alice", "author_id": 2}
    assert run(tmp_path / "1", {"a": item}, {"a": item}, "alice", A) == []
    errors = run(tmp_path / "2", {"a": item}, {"a": item}, "alice", A, uid=4242)
    assert errors and "belongs to" in errors[0]
    # and a new item can't claim someone else's id, or leave it out
    assert run(tmp_path / "3", {}, {"a": {"author": "mallory", "author_id": 2}}, "mallory", A)
    assert run(tmp_path / "4", {}, {"a": {"author": "mallory"}}, "mallory", A)


def test_item_without_author_id_needs_maintainer(tmp_path):
    legacy = {"author": "alice"}
    claimed = {"author": "alice", "author_id": 4242}
    assert run(tmp_path / "1", {"a": legacy}, {"a": claimed}, "alice", A, uid=4242)
    assert run(tmp_path / "2", {"a": legacy}, {"a": legacy}, "boss", A) == []


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
    class _In:
        buffer = io.BytesIO(b"content/playbooks/a/meta.yaml\0")
    sys.stdin = _In()
    try:
        rc = main(["verify-authors", "--repo", str(tmp_path), "--base", base, "--head", head, "--pr-author", "mallory",
                   "--pr-author-id", "666"])
    finally:
        sys.stdin = sys.__stdin__
    assert rc == 1


def test_owns_needs_login_and_account_id(tmp_path):
    from soarshelf.cli import main
    item = tmp_path / "x"
    item.mkdir()
    (item / "meta.yaml").write_text("author: Alice\nauthor_id: 2\n")
    assert main(["owns", "--item", str(item), "--login", "alice", "--id", "2"]) == 0
    assert main(["owns", "--item", str(item), "--login", "alice", "--id", "3"]) == 1
    assert main(["owns", "--item", str(item), "--login", "bob", "--id", "2"]) == 1
    assert main(["owns", "--item", str(tmp_path / "missing"), "--login", "alice", "--id", "2"]) == 1
    (item / "meta.yaml").write_text("author: alice\n")          # added by a maintainer
    assert main(["owns", "--item", str(item), "--login", "alice", "--id", "2"]) == 1


def test_only_maintainers_add_verification_records(tmp_path):
    mine = {"author": "alice", "author_id": IDS["alice"]}
    faked = {**mine, "tested": [{"platform": "8.0.0", "version": "1.0.0", "result": "ran"}]}
    errors = run(tmp_path, {"a": mine}, {"a": faked}, "alice", A)
    assert errors and "'tested'" in errors[0]
    assert run(tmp_path / "new", {}, {"a": faked}, "alice", A)                     # not on a new item either
    assert run(tmp_path / "keep", {"a": faked}, {"a": {**faked, "title": "x"}}, "alice", A) == []  # unchanged is fine
    assert run(tmp_path / "boss", {"a": mine}, {"a": faked}, "boss", A) == []

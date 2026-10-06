import json

from soarshelf import add as add_mod
from soarshelf.add import _REPO_URL, form_defaults


def test_repo_url_forms():
    assert _REPO_URL.match("https://github.com/o/connector-x").groups() == ("o", "connector-x", None, None)
    assert _REPO_URL.match("https://github.com/o/r.git").groups()[:2] == ("o", "r")
    assert _REPO_URL.match("https://github.com/o/kit/tree/main/widgets-src/w").groups() == ("o", "kit", "main", "widgets-src/w")
    assert not _REPO_URL.match("https://gitlab.com/o/r")


def test_defaults_from_manifests():
    c = form_defaults({"name": "x", "label": "X Tool", "description": "Does x.\nMore.", "version": "1.2.0"})
    assert c == {"title": "X Tool", "summary": "Does x.", "version": "1.2.0"}
    w = form_defaults({"name": "w", "title": "W", "subTitle": "Shows w", "version": "1.0.0", "metadata": {}})
    assert w["title"] == "W" and w["summary"] == "Shows w"


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    content = tmp_path / "content"
    (content / "connectors").mkdir(parents=True)
    (content / "contributors.yaml").write_text("me: {trust: maintainer, id: 7}\n")
    manifest = tmp_path / "info.json"
    manifest.write_text(json.dumps({"name": "my-conn", "label": "Look up assets", "version": "1.0.0",
                                    "description": "Looks up assets.", "configuration": {"fields": []},
                                    "operations": [{"operation": "get", "title": "Get"}]}))
    monkeypatch.setattr(add_mod, "github_identity", lambda: ("me", 7))
    form = {"useCases": ["utility"], "source": "https://github.com/me/my-conn"}
    res, written = add_mod.add(str(manifest), form, content, dry_run=True)
    assert res.decision == "review" and written is None
    assert not any((content / "connectors").iterdir())
    res, written = add_mod.add(str(manifest), dict(form), content, dry_run=False)
    assert written and (written / "info.json").exists()
    assert "author_id: 7" in (written / "meta.yaml").read_text()

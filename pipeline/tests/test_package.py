import hashlib
import io
import json
import tarfile

import pytest
import yaml
from PIL import Image

from soarshelf import package
from soarshelf.build import payload_of, process_item
from soarshelf.hubindex import HubIndex
from soarshelf.model import RejectedUpload
from soarshelf.process import process
from soarshelf.submission import intake

CONNECTOR = {"name": "my-conn", "label": "My Connector", "version": "1.2.0", "description": "Looks things up.",
             "configuration": {"fields": []}, "operations": [{"operation": "get", "title": "Get"}]}


def _png(w, h, extra=b""):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue() + extra


def _tgz(files, links=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        for name, target in links:
            ti = tarfile.TarInfo(name)
            ti.type, ti.linkname = tarfile.SYMTYPE, target
            tf.addfile(ti)
    return buf.getvalue()


def _conn_files(**extra):
    return {"my-conn/info.json": json.dumps(CONNECTOR).encode(), "my-conn/connector.py": b"print('hi')\n",
            "my-conn/requirements.txt": b"requests==2.32.0\n", **extra}


def _write(tmp_path, files, name="my-conn_1.2.0.tgz", links=()):
    p = tmp_path / name
    p.write_bytes(_tgz(files, links))
    return p


HUB = HubIndex(snapshot="2026-01-01", connectors={}, packs={})

META = {"slug": "my-conn", "title": "Look things up", "summary": "Looks things up somewhere.",
        "use_cases": ["utility"], "author": "me"}


def test_tgz_connector_is_hosted_without_a_source_link(tmp_path):
    res = process(dict(META), _write(tmp_path, _conn_files()), "maintainer", HUB)
    assert res.decision == "review"
    assert res.detail["download"]["filename"] == "my-conn_1.2.0.tgz"
    assert res.detail["displayName"] == "My Connector"
    assert not any(c["id"] == "meta.source" for c in res.detail["checks"])


def test_manifest_alone_still_needs_source(tmp_path, write_json):
    res = process(dict(META), write_json(CONNECTOR, "info.json"), "maintainer", HUB)
    assert res.decision == "reject" and res.detail["download"] is None


def test_download_is_rebuilt_from_the_committed_source(tmp_path):
    content = tmp_path / "content"
    (content / "connectors").mkdir(parents=True)
    (content / "contributors.yaml").write_text("me: {trust: maintainer, id: 7}\n")
    up = _write(tmp_path, _conn_files(**{"my-conn/__pycache__/x.pyc": b"\x00junk"}))
    form = {"title": "Look things up", "summary": "Looks things up somewhere.", "useCases": ["utility"],
            "rightsConfirmed": True}
    res = intake(up, form, "me", content, author_id=7)
    assert res.written and (res.written / "package/my-conn/connector.py").exists()
    assert not (res.written / "package/my-conn/__pycache__").exists()
    assert payload_of(res.written) == res.written / "package"
    a = process_item(res.written, {"me": ("maintainer", 7)}, HUB)
    b = process_item(res.written, {"me": ("maintainer", 7)}, HUB)
    assert a.download == b.download
    assert a.detail["download"]["sha256"] == hashlib.sha256(a.download).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(a.download)) as tf:
        names = tf.getnames()
        assert "my-conn/connector.py" in names and all(m.mtime == 0 and m.uid == 0 for m in tf.getmembers())
    assert yaml.safe_load((res.written / "meta.yaml").read_text())["author_id"] == 7


def test_macos_tar_metadata_files_are_dropped_not_read(tmp_path):
    files = _conn_files(**{"my-conn/images/icon.png": _png(32, 32),
                           "my-conn/images/._icon.png": b"\x00\x05\x16\x07AppleDouble"})
    res = process(dict(META), _write(tmp_path, files), "maintainer", HUB)
    assert res.decision == "review" and "my-conn/images/._icon.png" not in res.files


def test_connector_update_matches_on_manifest_name(tmp_path):
    content = tmp_path / "content"
    (content / "connectors").mkdir(parents=True)
    (content / "contributors.yaml").write_text("{}\n")
    form = {"title": "Look things up", "summary": "Looks things up somewhere.", "useCases": ["utility"],
            "rightsConfirmed": True}
    first = intake(_write(tmp_path, _conn_files()), form, "me", content, author_id=7)
    newer = {**CONNECTOR, "version": "1.3.0"}
    files = _conn_files(**{"my-conn/info.json": json.dumps(newer).encode()})
    res = intake(_write(tmp_path, files, "my-conn_1.3.0.tgz"), {**form, "title": "Renamed"}, "me", content, author_id=7)
    assert res.update and res.slug == first.slug and res.previous_version == "1.2.0"
    assert yaml.safe_load((res.written / "meta.yaml").read_text())["version"] == "1.3.0"
    assert json.loads((res.written / "package/my-conn/info.json").read_text())["version"] == "1.3.0"
    # the same name from someone else is refused, not listed twice
    other = intake(_write(tmp_path, files, "x.tgz"), form, "you", content, author_id=8)
    assert other.decision == "reject" and len(list((content / "connectors").iterdir())) == 1


@pytest.mark.parametrize("files,links,why", [
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "my-conn/lib.so": b"\x7fELF"}, (), "package.file-types"),
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "../evil.py": b"x"}, (), "package.path"),
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "my-conn/a\nb.py": b"x"}, (), "package.path"),
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode()}, [("my-conn/x.py", "/etc/passwd")], "package.link"),
    ({"a/info.json": json.dumps(CONNECTOR).encode(), "b/x.py": b"x"}, (), "package.layout"),
    ({"my-conn/connector.py": b"x"}, (), "package.manifest"),
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "my-conn/x.py": b"a\x00b"}, (), "package.binary"),
])
def test_unsafe_packages_rejected(tmp_path, files, links, why):
    res = process(dict(META), _write(tmp_path, files, links=links), "maintainer", HUB)
    assert res.decision == "reject" and res.detail["checks"][0]["id"] == why


def test_images_are_reencoded_and_screenshots_found(tmp_path):
    widget = {"name": "w", "title": "My Widget", "subTitle": "Shows things", "version": "1.0.0",
              "metadata": {"description": "d", "pages": ["Dashboard"]}}
    files = {"w-1.0.0/info.json": json.dumps(widget).encode(), "w-1.0.0/view.html": b"<div></div>",
             "w-1.0.0/images/view.png": _png(800, 500, extra=b"<script>alert(1)</script>"),
             "w-1.0.0/images/icon.png": _png(32, 32)}
    res = process(dict(META, slug="w"), _write(tmp_path, files, "w-1.0.0.tgz"), "maintainer", HUB)
    assert res.detail["type"] == "widget" and res.detail["displayName"] == "My Widget"
    assert [s["name"] for s in res.detail["screenshots"]] == ["images/view.png"]
    shot = res.assets["shots/1.png"]
    assert b"<script>" not in shot and Image.open(io.BytesIO(shot)).size == (800, 500)
    assert b"<script>" not in res.files["w-1.0.0/images/view.png"]


def test_review_hints_point_at_risky_code():
    hints = {r.id for r in package.review_hints({
        "c/connector.py": b"import subprocess\nexec(payload)\n",
        "c/view.js": b"var t = localStorage.getItem('x'); fetch('https://evil.example.org/x')\n",
        "c/lib/jquery.min.js": b"eval(x)\n"})}
    assert {"package.shell.py", "package.dynamic-code.py", "package.storage.js", "package.external-call.js"} <= hints
    assert "package.dynamic-code.js" not in hints     # vendored library ignored


def test_non_latin1_strings_flagged_but_not_comments():
    hints = {r.id: r for r in package.review_hints({
        "c/a.py": "msg = 'done \u2014 ok'\n# a comment \u2014 fine\n".encode()})}
    assert hints["package.non-latin1"].detail == "c/a.py:1"


def test_tgz_bomb_rejected(tmp_path, monkeypatch):
    from soarshelf import config
    monkeypatch.setattr(config, "MAX_PACKAGE_UNCOMPRESSED", 1000)
    with pytest.raises(RejectedUpload):
        package.read_tgz(_tgz({"c/info.json": b"x" * 5000}))


def test_manifest_cannot_steer_the_download_path(tmp_path):
    bad = dict(CONNECTOR, name="../../escape", version="1.0/../x")
    files = {"my-conn/info.json": json.dumps(bad).encode(), "my-conn/connector.py": b"x\n"}
    res = process(dict(META), _write(tmp_path, files), "maintainer", HUB)
    assert res.filename == "my-conn.tgz" and "/" not in res.detail["download"]["filename"]


def test_gzip_bomb_stops_at_the_cap(monkeypatch):
    import gzip
    from soarshelf import config
    monkeypatch.setattr(config, "MAX_PACKAGE_UNCOMPRESSED", 10_000)
    bomb = gzip.compress(b"\0" * 5_000_000)
    with pytest.raises(RejectedUpload):
        package._gunzip_capped(bomb)


def test_huge_image_refused_before_decoding(monkeypatch):
    from soarshelf import config
    monkeypatch.setattr(config, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(RejectedUpload):
        package.clean_images({"w/images/a.png": _png(50, 50)})


def test_operation_parameters_are_published_trimmed(tmp_path):
    conn = {**CONNECTOR,
            "configuration": {"fields": [
                {"name": "server", "title": "Server", "type": "text", "required": True, "visible": True},
                {"name": "password", "title": "Password", "type": "password", "value": "hunter2", "visible": True},
                {"name": "internal", "title": "Internal", "type": "text", "visible": False}]},
            "operations": [{"operation": "send", "title": "Send", "description": "Sends  it.",
                            "output_schema": {"status": "", "id": ""},
                            "parameters": [
                                {"name": "mode", "title": "Mode", "type": "select", "required": True, "visible": True,
                                 "options": ["A", "B"], "value": "A", "tooltip": "Pick one",
                                 "onchange": {"B": [{"name": "extra", "title": "Extra", "type": "json", "visible": True,
                                                     "value": {"k": 1}}]}}]}]}
    res = process(dict(META), _write(tmp_path, _conn_files(**{"my-conn/info.json": json.dumps(conn).encode()})),
                  "maintainer", HUB)
    op = res.detail["operations"][0]
    assert op["description"] == "Sends it." and op["output"] == ["status", "id"]
    mode = op["parameters"][0]
    assert mode == {"name": "mode", "title": "Mode", "type": "select", "required": True, "description": "Pick one",
                    "value": "A", "options": ["A", "B"],
                    "onchange": {"B": [{"name": "extra", "title": "Extra", "type": "json", "required": False,
                                        "value": '{"k": 1}'}]}}
    cfg = res.detail["configuration"]
    assert [f["name"] for f in cfg] == ["server", "password"] and "value" not in cfg[1]


def test_trimmed_manifest_keeps_parameters_when_read_again(write_json):
    from soarshelf.process import _connector
    from soarshelf.intake import Upload
    conn = {**CONNECTOR, "operations": [{"operation": "get", "title": "Get", "output_schema": {"a": 1},
                                         "parameters": [{"name": "q", "title": "Q", "type": "text", "visible": True}]}]}
    _, body, ops = _connector(Upload("connector", "info.json", b"", conn), HUB)
    _, _, again = _connector(Upload("connector", "info.json", b"", json.loads(body)), HUB)
    assert again == ops and ops[0]["parameters"][0]["name"] == "q" and ops[0]["output"] == ["a"]


def test_long_parameter_text_is_cut_at_a_word():
    from soarshelf.process import _text
    out = _text("word " * 200, 50)
    assert len(out) <= 50 and out.endswith("word…")


@pytest.mark.parametrize("field", [
    {"name": "pw", "title": "Pw", "type": "Password", "value": "x1"},
    {"name": "api_key", "title": "Key", "type": "text", "value": "x2"},
    {"name": "x", "title": "Client Secret", "type": "text", "value": "x3"},
    {"name": "x", "title": "X", "type": "secretbox", "value": "x4"},
])
def test_secret_like_defaults_are_never_published(field):
    from soarshelf.process import _params
    out = _params([{**field, "visible": True}, {"name": "m", "title": "Mode", "type": "select", "value": "A",
                                                "onchange": {"A": [{**field, "visible": True}]}}])
    assert "value" not in out[0] and "value" not in out[1]["onchange"]["A"][0] and out[1]["value"] == "A"

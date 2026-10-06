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


@pytest.mark.parametrize("files,links,why", [
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "my-conn/lib.so": b"\x7fELF"}, (), "package.file-types"),
    ({"my-conn/info.json": json.dumps(CONNECTOR).encode(), "../evil.py": b"x"}, (), "package.path"),
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


def test_tgz_bomb_rejected(tmp_path, monkeypatch):
    from soarshelf import config
    monkeypatch.setattr(config, "MAX_PACKAGE_UNCOMPRESSED", 1000)
    with pytest.raises(RejectedUpload):
        package.read_tgz(_tgz({"c/info.json": b"x" * 5000}))

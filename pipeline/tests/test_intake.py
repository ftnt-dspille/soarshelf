import io
import json
import zipfile

import pytest

from soarshelf import config
from soarshelf.intake import read_upload
from soarshelf.model import RejectedUpload


def _zip(tmp_path, members: dict[str, bytes], name="pack.zip", symlink: str | None = None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, data in members.items():
            zf.writestr(n, data)
        if symlink:
            zi = zipfile.ZipInfo(symlink)
            zi.external_attr = (0o120777 << 16)
            zf.writestr(zi, "/etc/passwd")
    p = tmp_path / name
    p.write_bytes(buf.getvalue())
    return p


def _rejected(path) -> str:
    with pytest.raises(RejectedUpload) as exc:
        read_upload(path)
    return exc.value.result.id


PACK_INFO = json.dumps({"name": "myPack", "version": "1.0.0", "type": "solutionpack"}).encode()


def test_playbook_accepted(write_json, doc):
    assert read_upload(write_json(doc)).kind == "playbook"


def test_wrong_extension(tmp_path):
    p = tmp_path / "evil.exe"
    p.write_bytes(b"MZ")
    assert _rejected(p) == "intake.type"


def test_oversize_json(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MAX_PLAYBOOK_BYTES", 10)
    p = tmp_path / "big.json"
    p.write_text('{"type": "workflow_collections", "data": []}')
    assert _rejected(p) == "intake.size"


def test_invalid_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{not json")
    assert _rejected(p) == "intake.json"


def test_deeply_nested_json(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text("[" * 200 + "]" * 200)
    assert _rejected(p) == "intake.depth"


def test_unknown_json_shape(write_json):
    assert _rejected(write_json({"hello": "world"})) == "intake.type"


def test_zip_path_traversal(tmp_path):
    p = _zip(tmp_path, {"info.json": PACK_INFO, "../../etc/cron.d/x": b"boom"})
    assert _rejected(p) == "intake.zip-path"


def test_zip_control_characters_in_name(tmp_path):
    p = _zip(tmp_path, {"info.json": PACK_INFO, "a\nb.json": b"{}"})
    assert _rejected(p) == "intake.zip-path"


def test_zip_symlink(tmp_path):
    p = _zip(tmp_path, {"info.json": PACK_INFO}, symlink="link")
    assert _rejected(p) == "intake.zip-symlink"


def test_zip_bomb_ratio(tmp_path):
    p = _zip(tmp_path, {"info.json": PACK_INFO, "zeros.json": b"0" * 5_000_000})
    assert _rejected(p) == "intake.zip-ratio"


def test_zip_too_many_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MAX_ZIP_ENTRIES", 3)
    p = _zip(tmp_path, {f"f{i}.json": b"{}" for i in range(5)})
    assert _rejected(p) == "intake.zip-entries"


def test_config_export_rejected(tmp_path):
    p = _zip(tmp_path, {"info.json": json.dumps({"contents": {}}).encode()})
    assert _rejected(p) == "intake.pack-identity"


def test_not_a_zip(tmp_path):
    p = tmp_path / "pack.zip"
    p.write_bytes(b"PK\x03\x04garbage")
    assert _rejected(p) == "intake.zip"


def test_pack_accepted(tmp_path):
    p = _zip(tmp_path, {"myPack/info.json": PACK_INFO})
    up = read_upload(p)
    assert up.kind == "solution-pack" and "myPack/info.json" in up.members

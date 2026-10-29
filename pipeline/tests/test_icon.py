"""Connector icons come from uploaded packages, so they are re-drawn, never copied through."""
import io
import struct
import zlib

from PIL import Image

from soarshelf.process import ICON_MAX_BYTES, _clean_icon


def _png(size=(32, 32), fmt="PNG", **kw) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(out, fmt, **kw)
    return out.getvalue()


def test_valid_icon_is_redrawn_as_a_small_png():
    out = _clean_icon(_png((300, 200)))
    assert out and out.startswith(b"\x89PNG")
    with Image.open(io.BytesIO(out)) as im:
        assert max(im.size) <= 96


def test_appended_payload_does_not_survive():
    out = _clean_icon(_png() + b"<script>alert(1)</script>MZ\x90\x00")
    assert out and b"<script" not in out and b"MZ\x90" not in out


def test_metadata_text_does_not_survive():
    from PIL import PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "<img src=x onerror=alert(1)>")
    assert b"onerror" not in _clean_icon(_png(pnginfo=info))


def test_svg_and_html_are_refused():
    assert _clean_icon(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>') is None
    assert _clean_icon(b"<html><script>alert(1)</script></html>") is None


def test_not_an_image_and_truncated_files_are_refused():
    assert _clean_icon(b"MZ" + b"\x00" * 100) is None
    assert _clean_icon(_png((64, 64))[:60]) is None


def test_oversized_dimensions_and_bytes_are_refused():
    # a tiny file that claims to be huge (decompression bomb)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    bomb = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 60000, 60000, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" * 100)) + chunk(b"IEND", b""))
    assert _clean_icon(bomb) is None
    assert _clean_icon(b"\x89PNG" + b"0" * ICON_MAX_BYTES) is None


# --- hand-sourced icons (pipeline/data/icons-local) ----------------------------

def test_hand_icon_beats_package_and_hub(tmp_path, monkeypatch):
    import shutil

    from soarshelf import build

    local, hub, site = tmp_path / "local", tmp_path / "hub", tmp_path / "site" / "icons"
    for d in (local, hub, site):
        d.mkdir(parents=True)
    (local / "code-runner.png").write_bytes(b"hand")
    (hub / "code-runner.png").write_bytes(b"hub")
    monkeypatch.setattr(build, "LOCAL_ICON_DIR", local)
    monkeypatch.setattr(build, "ICON_DIR", hub)
    icons: dict[str, str] = {}
    assert build._hand_icon("code-runner", site, icons) is True
    assert icons == {"code-runner": "/icons/code-runner.png"}
    assert (site / "code-runner.png").read_bytes() == b"hand"


def test_hand_icon_absent_falls_through(tmp_path, monkeypatch):
    from soarshelf import build

    monkeypatch.setattr(build, "LOCAL_ICON_DIR", tmp_path / "missing")
    icons: dict[str, str] = {}
    assert build._hand_icon("virustotal", tmp_path, icons) is False
    assert icons == {}

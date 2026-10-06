"""First contact with an uploaded file: size, type and archive safety.

Nothing downstream ever sees bytes that did not pass through here. Every
failure raises :class:`RejectedUpload` with a ``block`` result, so the caller
can report it without processing the file any further.
"""
from __future__ import annotations

import io
import json
import posixpath
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .model import CheckResult, RejectedUpload, Severity


@dataclass
class Upload:
    kind: str                        # "playbook" | "solution-pack" | "connector" | "widget"
    filename: str
    raw: bytes
    data: Any = None                 # parsed JSON (playbook / connector manifest)
    members: dict[str, bytes] | None = None   # pack: path -> bytes, all safe


def _reject(id_: str, title: str, detail: str = "") -> RejectedUpload:
    return RejectedUpload(CheckResult(f"intake.{id_}", Severity.BLOCK, title, detail))


def _depth(obj: Any, limit: int) -> int:
    """Nesting depth, iterative so a hostile file cannot blow the stack."""
    deepest = 0
    stack = [(obj, 1)]
    while stack:
        node, d = stack.pop()
        if d > limit:
            return d
        deepest = max(deepest, d)
        if isinstance(node, dict):
            stack.extend((v, d + 1) for v in node.values())
        elif isinstance(node, list):
            stack.extend((v, d + 1) for v in node)
    return deepest


def load_json(raw: bytes, what: str) -> Any:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _reject("encoding", f"{what} is not UTF-8 text", str(exc)) from exc
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise _reject("json", f"{what} is not valid JSON", str(exc)[:200]) from exc
    if _depth(data, config.MAX_JSON_DEPTH) > config.MAX_JSON_DEPTH:
        raise _reject("depth", f"{what} is nested more than {config.MAX_JSON_DEPTH} levels deep")
    return data


def _safe_members(raw: bytes) -> dict[str, bytes]:
    """Read a zip into memory, refusing anything that looks hostile."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise _reject("zip", "File is not a readable zip archive", str(exc)) from exc

    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > config.MAX_ZIP_ENTRIES:
        raise _reject("zip-entries", f"Archive has {len(infos)} files (limit {config.MAX_ZIP_ENTRIES})")
    total = sum(i.file_size for i in infos)
    if total > config.MAX_ZIP_UNCOMPRESSED:
        raise _reject("zip-size", "Archive expands beyond the size limit",
                      f"{total} bytes uncompressed, limit {config.MAX_ZIP_UNCOMPRESSED}")

    out: dict[str, bytes] = {}
    for i in infos:
        name = i.filename
        norm = posixpath.normpath(name)
        if name.startswith(("/", "\\")) or norm.startswith("..") or ":" in name.split("/")[0] or "\\" in name:
            raise _reject("zip-path", "Archive contains an unsafe path", name)
        if i.flag_bits & 0x1:
            raise _reject("zip-encrypted", "Archive contains an encrypted member", name)
        mode = i.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise _reject("zip-symlink", "Archive contains a symbolic link", name)
        if i.compress_size and i.file_size / i.compress_size > config.MAX_ZIP_RATIO:
            raise _reject("zip-ratio", "Archive member has a suspicious compression ratio", name)
        data = zf.read(i)                       # CRC is verified here
        if len(data) != i.file_size:
            raise _reject("zip-size", "Archive member size does not match its header", name)
        out[norm] = data
    return out


def is_widget_manifest(data: Any) -> bool:
    """A widget's info.json: name, title and a metadata block, and no connector operations."""
    if not isinstance(data, dict) or "operations" in data or data.get("type") == "connector":
        return False
    return data.get("type") == "widget" or (
        isinstance(data.get("name"), str) and isinstance(data.get("title"), str) and isinstance(data.get("metadata"), dict))


def read_upload(path: Path) -> Upload:
    """Classify and safely load one uploaded file."""
    raw = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix == ".json":
        if len(raw) > config.MAX_PLAYBOOK_BYTES:
            raise _reject("size", "Playbook file is too large",
                          f"{len(raw)} bytes, limit {config.MAX_PLAYBOOK_BYTES}")
        data = load_json(raw, path.name)
        if isinstance(data, dict) and data.get("type") == "workflow_collections" and isinstance(data.get("data"), list):
            return Upload("playbook", path.name, raw, data=data)
        if isinstance(data, dict) and data.get("type") == "connector" or (
                isinstance(data, dict) and "operations" in data and "configuration" in data):
            return Upload("connector", path.name, raw, data=data)
        if is_widget_manifest(data):
            return Upload("widget", path.name, raw, data=data)
        raise _reject("type", "Unrecognised JSON file",
                      "Expected a playbook collection export (type: workflow_collections), "
                      "a connector manifest or a widget manifest (info.json).")

    if suffix == ".zip":
        if len(raw) > config.MAX_PACK_BYTES:
            raise _reject("size", "Solution pack is too large",
                          f"{len(raw)} bytes, limit {config.MAX_PACK_BYTES}")
        members = _safe_members(raw)
        roots = [m for m in members if posixpath.basename(m) == "info.json" and m.count("/") <= 1]
        if len(roots) != 1:
            raise _reject("pack-root", "Archive is not a solution pack export",
                          "Expected exactly one info.json at the archive root.")
        info = load_json(members[roots[0]], "info.json")
        if not (isinstance(info, dict) and info.get("name") and info.get("version")):
            raise _reject("pack-identity", "Archive is a configuration export, not a solution pack",
                          "Configuration exports can carry environment data; export it as a solution pack instead.")
        return Upload("solution-pack", path.name, raw, data=info, members=members)

    raise _reject("type", f"File type {suffix or '(none)'} is not accepted",
                  "Upload a playbook export (.json) or a solution pack (.zip).")

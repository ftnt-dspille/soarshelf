"""Connector and widget packages: the ``.tgz`` an author already has.

An uploaded package is unpacked here, cleaned, and committed as plain source
(``content/<type>/<slug>/package/``) so the reviewer reads every file in the
pull request. The download is rebuilt from that committed source on every
build, byte for byte the same, so what people install is what was reviewed.
The uploaded archive itself is never served.
"""
from __future__ import annotations

import gzip
import io
import posixpath
import re
import tarfile
from pathlib import Path

from . import config
from .model import CheckResult, RejectedUpload, Severity

# Reviewable text, plus images and fonts. Anything else is refused.
TEXT_SUFFIXES = (".py", ".json", ".md", ".txt", ".rst", ".html", ".htm", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
                 ".css", ".scss", ".less", ".yaml", ".yml",
                 ".cfg", ".ini", ".toml", ".csv", ".xml", ".svg", ".j2", ".jinja", ".sh", ".map")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif")
OTHER_SUFFIXES = (".ico", ".woff", ".woff2", ".ttf", ".eot")
TEXT_NAMES = ("license", "licence", "readme", "notice", "changelog", "requirements", "makefile")
# Build leftovers dropped without complaint.
_JUNK_DIRS = ("__pycache__", ".git", ".idea", ".vscode", "node_modules", ".pytest_cache")
_JUNK_FILES = (".ds_store", "thumbs.db")


def _reject(id_: str, title: str, detail: str = "") -> RejectedUpload:
    return RejectedUpload(CheckResult(f"package.{id_}", Severity.BLOCK, title, detail))


def _is_junk(path: str) -> bool:
    """Build leftovers, editor/VCS state and dotfiles (.gitignore, .env.example): never part of an install."""
    parts = path.lower().split("/")
    return (any(p in _JUNK_DIRS or p.startswith(".") for p in parts[:-1]) or parts[-1] in _JUNK_FILES
            or parts[-1].endswith(".pyc") or parts[-1].startswith("."))


def _named_text(base: str) -> bool:
    """LICENSE, README.md, cytoscape.LICENSE, requirements-dev.txt and the like."""
    return any(part.split("-")[0] in TEXT_NAMES for part in base.split("."))


def _allowed(path: str) -> bool:
    base = posixpath.basename(path).lower()
    return base.endswith(TEXT_SUFFIXES + IMAGE_SUFFIXES + OTHER_SUFFIXES) or _named_text(base)


def is_text(path: str) -> bool:
    base = posixpath.basename(path).lower()
    return base.endswith(TEXT_SUFFIXES) or _named_text(base)


def _check_path(name: str) -> str:
    norm = posixpath.normpath(name.lstrip("./")) if name.startswith("./") else posixpath.normpath(name)
    if name.startswith(("/", "\\")) or norm.startswith("..") or "\\" in name or ":" in norm.split("/")[0]:
        raise _reject("path", "Archive contains an unsafe path", name)
    return norm


def read_tgz(raw: bytes) -> dict[str, bytes]:
    """Every regular file in a gzipped tar, refusing links, devices and bombs."""
    try:
        data = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    except (OSError, EOFError) as exc:
        raise _reject("gzip", "File is not a readable .tgz", str(exc)) from exc
    if len(data) > config.MAX_PACKAGE_UNCOMPRESSED:
        raise _reject("size", "Package expands beyond the size limit",
                      f"{len(data)} bytes uncompressed, limit {config.MAX_PACKAGE_UNCOMPRESSED}")
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:")
        infos = tf.getmembers()
    except tarfile.TarError as exc:
        raise _reject("tar", "File is not a readable .tgz", str(exc)) from exc
    out: dict[str, bytes] = {}
    for i in infos:
        if i.isdir():
            continue
        name = _check_path(i.name)
        if not i.isfile():
            raise _reject("link", "Package contains a link or special file", i.name)
        f = tf.extractfile(i)
        out[name] = f.read() if f else b""
    return out


def read_dir(root: Path) -> dict[str, bytes]:
    """A committed package folder, read the same way as an upload."""
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise _reject("link", "Package contains a link", str(p.relative_to(root)))
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def normalise(files: dict[str, bytes]) -> tuple[str, dict[str, bytes], list[str]]:
    """Drop build leftovers and check the layout.

    Returns the top folder name, the kept files and the names of dropped ones.
    """
    dropped = sorted(n for n in files if _is_junk(n))
    kept = {n: b for n, b in files.items() if n not in dropped}
    if not kept:
        raise _reject("empty", "Package is empty")
    if len(kept) > config.MAX_PACKAGE_FILES:
        raise _reject("files", f"Package has {len(kept)} files (limit {config.MAX_PACKAGE_FILES})")
    tops = {n.split("/")[0] for n in kept}
    if len(tops) != 1 or any("/" not in n for n in kept):
        raise _reject("layout", "Package must hold one folder with info.json inside",
                      "Package the connector or widget folder itself, e.g. my-connector/info.json.")
    top = tops.pop()
    if f"{top}/info.json" not in kept:
        raise _reject("manifest", "Package has no info.json", f"Expected {top}/info.json.")
    refused = sorted(n for n in kept if not _allowed(n))
    if refused:
        raise _reject("file-types", "Package contains files that can't be reviewed",
                      "Compiled code, archives and other binaries aren't accepted; list dependencies in "
                      f"requirements.txt instead. Found: {', '.join(refused[:5])}"
                      + (f" and {len(refused) - 5} more" if len(refused) > 5 else ""))
    disguised = sorted(n for n, b in kept.items() if is_text(n) and b"\x00" in b)
    if disguised:
        raise _reject("binary", "Package contains binary data in a text file", ", ".join(disguised[:5]))
    return top, kept, dropped


def clean_images(files: dict[str, bytes]) -> dict[str, bytes]:
    """Re-encode every raster image: strips metadata and anything appended to it."""
    from PIL import Image, UnidentifiedImageError

    out = dict(files)
    for name, raw in files.items():
        if not name.lower().endswith(IMAGE_SUFFIXES):
            continue
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                if im.width * im.height > config.MAX_IMAGE_PIXELS:
                    raise _reject("image", "Image is too large", name)
                fmt = "PNG" if name.lower().endswith(".png") else ("GIF" if name.lower().endswith(".gif") else "JPEG")
                if fmt == "JPEG" and im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                buf = io.BytesIO()
                im.save(buf, format=fmt, optimize=True)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise _reject("image", "Image could not be read", f"{name}: {exc}") from exc
        out[name] = buf.getvalue()
    return out


def build_tgz(files: dict[str, bytes]) -> bytes:
    """The same files always give the same bytes: sorted, no owners, no times."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        dirs = sorted({"/".join(n.split("/")[:i]) for n in files for i in range(1, n.count("/") + 1)})
        for d in dirs:
            ti = tarfile.TarInfo(d)
            ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, 0
            tf.addfile(ti)
        for name in sorted(files):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.mtime = len(files[name]), 0o644, 0
            tf.addfile(ti, io.BytesIO(files[name]))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as gz:
        gz.write(tar_buf.getvalue())
    return out.getvalue()


# --- hints for the reviewer ------------------------------------------------------
# None of these reject anything: connectors legitimately call APIs and some
# legitimately run code. They tell the reviewer where to look first.

_PY_RISKS = [
    ("dynamic-code", "Runs dynamic code (eval/exec)", re.compile(r"\b(?:eval|exec|compile)\s*\(")),
    ("shell", "Runs shell commands", re.compile(r"\bsubprocess\b|\bos\.(?:system|popen|exec\w*|spawn\w*)\s*\(|\bpty\.spawn")),
    ("raw-network", "Opens raw sockets", re.compile(r"\bsocket\.socket\s*\(|\bparamiko\b|\btelnetlib\b")),
    ("unsafe-load", "Loads pickled or marshalled data", re.compile(r"\b(?:pickle|marshal|dill)\.loads?\s*\(")),
    ("native", "Loads native code or imports by name", re.compile(r"\bctypes\b|\bcffi\b|__import__\s*\(|importlib\.import_module")),
    ("encoded", "Decodes embedded data", re.compile(r"\b(?:base64\.b(?:64|32|16)decode|codecs\.decode|zlib\.decompress)\s*\(")),
]
_JS_RISKS = [
    ("dynamic-code", "Runs dynamic code (eval / new Function)", re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|setTimeout\s*\(\s*['\"]")),
    ("storage", "Reads browser storage (session tokens live there)", re.compile(r"\b(?:localStorage|sessionStorage)\b|document\.cookie")),
    ("external-call", "Calls an absolute URL from the browser", re.compile(r"\b(?:fetch|axios\.\w+|\$http\.\w+|open)\s*\(\s*['\"`]https?://")),
    ("encoded", "Decodes embedded data", re.compile(r"\batob\s*\(|String\.fromCharCode\s*\(\s*\d")),
]
_URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_BENIGN_HOSTS = re.compile(r"(^|\.)(w3\.org|example\.(com|net|org)|json-schema\.org|schemas\.\w+\.\w+|github\.com|"
                           r"githubusercontent\.com|python\.org|mozilla\.org|apache\.org|opensource\.org|semver\.org|"
                           r"angularjs\.org|jquery\.com|d3js\.org|c3js\.org|fortinet\.com)$", re.I)


def _vendored(name: str) -> bool:
    base = posixpath.basename(name).lower()
    return ".min." in base or "/vendor/" in f"/{name.lower()}" or "/lib/" in f"/{name.lower()}"


def review_hints(files: dict[str, bytes]) -> list[CheckResult]:
    hits: dict[str, tuple[str, list[str]]] = {}
    hosts: dict[str, None] = {}
    for name, raw in sorted(files.items()):
        if not is_text(name):
            continue
        text = raw.decode("utf-8", "replace")
        lower = name.lower()
        risks = _PY_RISKS if lower.endswith(".py") else _JS_RISKS if lower.endswith((".js", ".html", ".htm")) and not _vendored(name) else []
        for n, line in enumerate(text.splitlines(), 1):
            for id_, title, rx in risks:
                if rx.search(line):
                    hits.setdefault(id_ + lower[-3:], (title, []))[1].append(f"{name}:{n}")
            if not _vendored(name):
                for m in _URL.finditer(line):
                    if not _BENIGN_HOSTS.search(m.group(1)):
                        hosts[m.group(1).lower()] = None
        if lower.endswith(".py") and any(len(line) > 1000 for line in text.splitlines()):
            hits.setdefault("long-lines", ("Very long lines in Python (possible obfuscation)", []))[1].append(name)
    out = [CheckResult(f"package.{k}", Severity.WARN, title,
                       "; ".join(where[:5]) + (f"; and {len(where) - 5} more" if len(where) > 5 else ""))
           for k, (title, where) in hits.items()]
    if hosts:
        out.append(CheckResult("package.hosts", Severity.INFO, "Hosts named in the code", ", ".join(list(hosts)[:15])))
    req = next((b for n, b in files.items() if posixpath.basename(n).lower() == "requirements.txt"), None)
    if req:
        loose = [ln.strip() for ln in req.decode("utf-8", "replace").splitlines()
                 if ln.strip() and not ln.strip().startswith("#") and "==" not in ln]
        pkgs = [ln.strip() for ln in req.decode("utf-8", "replace").splitlines() if ln.strip() and not ln.startswith("#")]
        if pkgs:
            out.append(CheckResult("package.requirements", Severity.INFO, "Python dependencies",
                                   ", ".join(pkgs[:15]) + (f" ({len(loose)} not pinned to a version)" if loose else "")))
    return out


def screenshots(files: dict[str, bytes], top: str) -> list[tuple[str, bytes, int, int]]:
    """Images worth showing on the item page: not icons, at most six."""
    from PIL import Image

    out = []
    for name in sorted(files):
        if not name.lower().endswith(IMAGE_SUFFIXES):
            continue
        with Image.open(io.BytesIO(files[name])) as im:
            w, h = im.size
        if w >= 320 and h >= 200:
            out.append((name[len(top) + 1:], files[name], w, h))
    return out[:6]

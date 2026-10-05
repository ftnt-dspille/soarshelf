"""``soarshelf`` command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_ICON = {"pass": "✓", "info": "·", "warn": "!", "block": "✗"}


def _check(args: argparse.Namespace) -> int:
    from .hubindex import HubIndex
    from .process import process

    meta = yaml.safe_load(Path(args.meta).read_text()) if args.meta else {
        "title": args.file.stem, "summary": "self-check", "use_cases": ["utility"]}
    meta.setdefault("slug", args.file.stem)
    res = process(meta, args.file, args.trust, HubIndex.load())
    if args.clean_out and res.download is not None:
        args.clean_out.write_bytes(res.download)
        print(f"cleaned file written to {args.clean_out}", file=sys.stderr)
    if args.json:
        detail = {k: v for k, v in res.detail.items() if not k.startswith("_")}
        print(json.dumps({"decision": res.decision, "reasons": res.reasons, "item": detail}, indent=1))
    else:
        for c in res.detail["checks"]:
            loc = f"  [{c['location']}]" if c.get("location") else ""
            print(f" {_ICON[c['severity']]} {c['title']}{loc}")
            if c.get("detail") and c["severity"] != "pass":
                print(f"     {c['detail']}")
        print(f"\nDecision for a '{args.trust}' contributor: {res.decision.upper()}")
        for r in res.reasons:
            print(f"  - {r}")
    return 1 if res.decision == "reject" else 0


def _build(args: argparse.Namespace) -> int:
    from .build import build
    return build(args.content, args.out)


def _hub_index(args: argparse.Namespace) -> int:
    from .hubindex import DATA_DIR, FINGERPRINTS, HUB_INDEX, build_fingerprints, build_hub_index, fetch_catalog

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    hub = build_hub_index(fetch_catalog(args.catalog) if args.catalog else fetch_catalog())
    HUB_INDEX.write_text(json.dumps(hub, indent=1, ensure_ascii=False) + "\n")
    print(f"hub index: {len(hub['connectors'])} connectors, {len(hub['solutionPacks'])} packs → {HUB_INDEX}")
    if args.packs_dir:
        packs = [p for p in args.packs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]
        fp = build_fingerprints(packs)
        FINGERPRINTS.write_text(json.dumps(fp, indent=1) + "\n")
        print(f"fingerprints: {len(fp['uuids'])} uuids, {len(fp['structures'])} structures from {len(packs)} packs")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="soarshelf", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="run every check on a file, as the site would")
    c.add_argument("file", type=Path)
    c.add_argument("--meta", type=Path, help="meta.yaml for the listing (optional)")
    c.add_argument("--trust", default="new", choices=["new", "contributor", "trusted", "maintainer"])
    c.add_argument("--json", action="store_true")
    c.add_argument("--clean-out", type=Path, help="write the sanitized file (what gets published) here")
    c.set_defaults(fn=_check)

    b = sub.add_parser("build", help="build site data from content/")
    b.add_argument("--content", type=Path, default=Path("content"))
    b.add_argument("--out", type=Path, default=Path("site/static"))
    b.set_defaults(fn=_build)

    h = sub.add_parser("hub-index", help="regenerate the Content Hub snapshot (maintainers)")
    h.add_argument("--catalog", default=None, help="content-hub.json URL or file (default: the public catalog)")
    h.add_argument("--packs-dir", type=Path, help="unpacked official solution packs, for fingerprints")
    h.set_defaults(fn=_hub_index)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

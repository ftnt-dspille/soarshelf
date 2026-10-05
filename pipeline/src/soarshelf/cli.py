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


def _intake_submission(args: argparse.Namespace) -> int:
    from .submission import intake

    form = json.loads(args.meta.read_text())
    res = intake(args.file, form, args.author, args.content)
    args.report.write_text(json.dumps(res.to_dict(), indent=1, ensure_ascii=False))
    print(f"{res.decision}: {res.written or 'nothing written'}")
    return 0          # the decision is in the report; a reject is not a pipeline failure


def _verify_authors(args: argparse.Namespace) -> int:
    from .authors import git_reader, verify

    # NUL-separated (`git diff -z`): git would otherwise quote and escape
    # unusual path names, and a mangled path could slip past the gate.
    changed = [p for p in sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\0") if p]
    bots = {b for b in (args.bot or []) if b}
    errors = verify(changed, args.pr_author, bots, args.repo,
                    base=git_reader(args.repo, args.base), head=git_reader(args.repo, args.head))
    for e in errors:
        print(f"✗ {e}")
    if not errors:
        print(f"✓ all changed items are credited to {args.pr_author}")
    return 1 if errors else 0


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

    i = sub.add_parser("intake-submission", help="check an upload and add it to content/ (submission Action)")
    i.add_argument("--file", type=Path, required=True)
    i.add_argument("--meta", type=Path, required=True, help="SubmissionMeta JSON from the upload form")
    i.add_argument("--author", required=True, help="authenticated GitHub login of the uploader")
    i.add_argument("--content", type=Path, default=Path("content"))
    i.add_argument("--report", type=Path, required=True, help="where to write the JSON report")
    i.set_defaults(fn=_intake_submission)

    v = sub.add_parser("verify-authors", help="PR gate: changed items must be credited to the PR author")
    v.add_argument("--pr-author", required=True)
    v.add_argument("--repo", type=Path, default=Path("."), help="checkout of the BASE branch")
    v.add_argument("--base", required=True, help="base commit")
    v.add_argument("--head", required=True, help="PR head commit (read with git show, never checked out)")
    v.add_argument("--bot", action="append", help="login allowed to change any item (repeatable)")
    v.set_defaults(fn=_verify_authors)

    h = sub.add_parser("hub-index", help="regenerate the Content Hub snapshot (maintainers)")
    h.add_argument("--catalog", default=None, help="content-hub.json URL or file (default: the public catalog)")
    h.add_argument("--packs-dir", type=Path, help="unpacked official solution packs, for fingerprints")
    h.set_defaults(fn=_hub_index)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

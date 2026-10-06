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
    res = intake(args.file, form, args.author, args.content, author_id=args.author_id)
    args.report.write_text(json.dumps(res.to_dict(), indent=1, ensure_ascii=False))
    print(f"{res.decision}: {res.written or 'nothing written'}")
    return 0          # the decision is in the report; a reject is not a pipeline failure


def _add(args: argparse.Namespace) -> int:
    from .add import add

    form = {"title": args.title, "summary": args.summary, "useCases": args.use_case, "tags": args.tag or [],
            "version": args.version, "minVersion": args.min_version,
            "description": args.description.read_text() if args.description else ""}
    if args.source:
        form["source"] = args.source
    form = {k: v for k, v in form.items() if v}
    res, written = add(args.src, form, args.content, dry_run=args.dry_run)
    for c in res.checks:
        if c["severity"] != "pass":
            loc = f"  [{c['location']}]" if c.get("location") else ""
            print(f" {_ICON[c['severity']]} {c['title']}{loc}")
            if c.get("detail"):
                print(f"     {c['detail']}")
    print(f"\n{res.decision.upper()}" + "".join(f"\n  - {r}" for r in res.reasons))
    if written:
        print(f"written: {written}  (commit it on a branch and open a pull request)")
    elif args.dry_run and res.decision != "reject":
        print("dry run: nothing written")
    return 1 if res.decision == "reject" else 0


def _pr_body(args: argparse.Namespace) -> int:
    from .submission import pr_body

    print(pr_body(json.loads(args.report.read_text()), args.login, args.id), end="")
    return 0


def _owns(args: argparse.Namespace) -> int:
    """Exit 0 when the item exists and was uploaded from this GitHub account."""
    import yaml

    meta_path = args.item / "meta.yaml"
    if not meta_path.is_file():
        return 1
    meta = yaml.safe_load(meta_path.read_text()) or {}
    same = (str(meta.get("author") or "").lower() == args.login.lower()
            and isinstance(meta.get("author_id"), int) and meta["author_id"] == args.id)
    return 0 if same else 1


def _verify_authors(args: argparse.Namespace) -> int:
    from .authors import git_reader, verify

    # NUL-separated (`git diff -z`): git would otherwise quote and escape
    # unusual path names, and a mangled path could slip past the gate.
    changed = [p for p in sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\0") if p]
    bots = {b for b in (args.bot or []) if b}
    errors = verify(changed, args.pr_author, bots, args.repo,
                    base=git_reader(args.repo, args.base), head=git_reader(args.repo, args.head),
                    pr_author_id=args.pr_author_id)
    for e in errors:
        print(f"✗ {e}")
    if not errors:
        print(f"✓ all changed items are credited to {args.pr_author}")
    return 1 if errors else 0


def _pack_base(dirname: str) -> str:
    """'sOARFramework-3.4.0' -> 'sOARFramework'; a name without a version is returned as is."""
    base, _, ver = dirname.rpartition("-")
    return base if base and ver[:1].isdigit() else dirname


def _hub_index(args: argparse.Namespace) -> int:
    from .hubindex import DATA_DIR, FINGERPRINTS, HUB_INDEX, build_fingerprints, build_hub_index, fetch_catalog

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    hub = build_hub_index(fetch_catalog(args.catalog) if args.catalog else fetch_catalog())
    HUB_INDEX.write_text(json.dumps(hub, indent=1, ensure_ascii=False) + "\n")
    print(f"hub index: {len(hub['connectors'])} connectors, {len(hub['solutionPacks'])} packs, {len(hub['widgets'])} widgets → {HUB_INDEX}")
    if args.packs_dir:
        # Only packs the Content Hub catalog lists: a local packs folder also
        # holds your own and modified packs, which must not count as official.
        dirs = [p for p in args.packs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]
        packs = [p for p in dirs if _pack_base(p.name) in hub["solutionPacks"]]
        skipped = sorted(p.name for p in dirs if p not in packs)
        if skipped:
            print(f"skipped {len(skipped)} packs not in the catalog: {', '.join(skipped)}")
        fp = build_fingerprints(packs)
        FINGERPRINTS.write_text(json.dumps(fp, indent=1) + "\n")
        print(f"fingerprints: {len(fp['uuids'])} uuids, {len(fp['structures'])} structures from {len(packs)} packs")
    return 0


def _test_live(args: argparse.Namespace) -> int:
    from . import verify

    item = next((d for d in sorted(args.content.glob(f"*/{args.slug}")) if (d / "meta.yaml").exists()), None)
    if item is None:
        print(f"no item {args.slug!r} under {args.content}", file=sys.stderr)
        return 2
    try:
        entry = verify.run(item, instance=args.instance, playbooks=args.run or [], calls=args.call or [], on_record=args.on_record,
                           expect=dict(e.split("=", 1) for e in args.expect or []),
                           inputs=json.loads(args.inputs or "{}"), answers=json.loads(args.answers or "{}"),
                           timeout=args.timeout, keep=args.keep)
    except verify.VerifyError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    if args.record:
        verify.record(item, entry, args.notes or "")
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
    i.add_argument("--author-id", type=int, required=True, help="numeric GitHub id of the uploader")
    i.add_argument("--content", type=Path, default=Path("content"))
    i.add_argument("--report", type=Path, required=True, help="where to write the JSON report")
    i.set_defaults(fn=_intake_submission)

    a = sub.add_parser("add", help="add your own item to content/ from a file or GitHub repo (maintainers)")
    a.add_argument("src", help="playbook .json, pack .zip, info.json, or https://github.com/OWNER/REPO[/tree/BRANCH/PATH]")
    a.add_argument("--title", help="defaults to the manifest's label/title")
    a.add_argument("--summary", help="defaults to the manifest's description")
    a.add_argument("--use-case", action="append", required=True, help="repeatable, 1 to 3")
    a.add_argument("--tag", action="append")
    a.add_argument("--description", type=Path, help="markdown file for the long description")
    a.add_argument("--source", help="source repository URL (set automatically for a GitHub URL)")
    a.add_argument("--version")
    a.add_argument("--min-version")
    a.add_argument("--content", type=Path, default=Path("content"))
    a.add_argument("--dry-run", action="store_true", help="run every check, write nothing")
    a.set_defaults(fn=_add)

    b2 = sub.add_parser("pr-body", help="markdown body for a submission PR (submission Action)")
    b2.add_argument("--report", type=Path, required=True)
    b2.add_argument("--login", required=True)
    b2.add_argument("--id", required=True)
    b2.set_defaults(fn=_pr_body)

    o = sub.add_parser("owns", help="exit 0 if the item was uploaded by this account (submission Action)")
    o.add_argument("--item", type=Path, required=True)
    o.add_argument("--login", required=True)
    o.add_argument("--id", type=int, required=True)
    o.set_defaults(fn=_owns)

    v = sub.add_parser("verify-authors", help="PR gate: changed items must be credited to the PR author")
    v.add_argument("--pr-author", required=True)
    v.add_argument("--pr-author-id", type=int, required=True, help="numeric GitHub id of the PR author")
    v.add_argument("--repo", type=Path, default=Path("."), help="checkout of the BASE branch")
    v.add_argument("--base", required=True, help="base commit")
    v.add_argument("--head", required=True, help="PR head commit (read with git show, never checked out)")
    v.add_argument("--bot", action="append", help="login allowed to change any item (repeatable)")
    v.set_defaults(fn=_verify_authors)

    h = sub.add_parser("hub-index", help="regenerate the Content Hub snapshot (maintainers)")
    h.add_argument("--catalog", default=None, help="content-hub.json URL or file (default: the public catalog)")
    h.add_argument("--packs-dir", type=Path, help="unpacked official solution packs, for fingerprints")
    h.set_defaults(fn=_hub_index)

    t = sub.add_parser("test-live", help="import (and run) an item on a live FortiSOAR; --record saves the result")
    t.add_argument("slug")
    t.add_argument("--instance", help="pyfsr instance alias (~/.pyfsr/instances.toml); default instance if omitted")
    t.add_argument("--run", action="append", metavar="PLAYBOOK", help="run this playbook to completion (repeatable)")
    t.add_argument("--call", action="append", metavar="PLAYBOOK",
                   help="run a referenced playbook from a scratch caller, with its --inputs as arguments")
    t.add_argument("--on-record", metavar="MODULE/UUID",
                   help="start the --call caller from this existing record (read, never changed)")
    t.add_argument("--expect", action="append", metavar="KEY=VALUE",
                   help="the called playbook's final result must have this value (repeatable)")
    t.add_argument("--inputs", help='JSON {"playbook name": {input: value}}')
    t.add_argument("--answers", help="JSON answers for manual input prompts, by title or variable name")
    t.add_argument("--timeout", type=float, default=180)
    t.add_argument("--keep", action="store_true", help="leave the scratch copy on the box")
    t.add_argument("--record", action="store_true", help="write the result to the item's meta.yaml")
    t.add_argument("--notes", help="short public note for the record (no hosts or dates)")
    t.add_argument("--content", type=Path, default=Path("content"))
    t.set_defaults(fn=_test_live)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

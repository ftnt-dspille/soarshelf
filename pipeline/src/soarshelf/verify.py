"""Test an item's download on a live FortiSOAR and record the result in its meta.yaml.

What it does, for playbooks and solution packs:

1. Builds the item exactly as the site does, so the file tested is the file people
   download.
2. Gives every collection, playbook, step, route and group a fresh UUID and prefixes
   each collection name, so the copy can't collide with or overwrite anything already
   on the box (much of this content came from our own boxes).
3. Imports it and checks every playbook and step arrived.
4. Optionally runs named playbooks to completion. Only playbooks with a manual or
   referenced trigger are switched on in the copy; record, schedule and API
   triggers stay off so nothing fires on its own.
5. Deletes the copy (``--keep`` leaves it for a look in the UI).

The box comes from the pyfsr instance registry, so no host or credential is
written anywhere in this repo. ``--record`` adds a ``tested`` entry to meta.yaml
naming only the platform version.
"""
from __future__ import annotations

import io
import json
import posixpath
import re
import uuid as uuidlib
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from . import config

PREFIX = "soarshelf-verify · "
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
# Triggers that never fire on their own: safe to switch on in a scratch copy.
SAFE_TRIGGERS = {"Manual trigger", "Referenced"}


class VerifyError(Exception):
    pass


def collections_from_download(kind: str, body: bytes) -> list[dict[str, Any]]:
    """The playbook collections inside a download, as import-ready collection objects."""
    if kind == "playbook":
        doc = json.loads(body)
        return [c for c in doc.get("data") or [] if isinstance(c, dict)]
    if kind == "solution-pack":
        z = zipfile.ZipFile(io.BytesIO(body))
        meta: dict[str, dict[str, Any]] = {}
        pbs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for n in sorted(z.namelist()):
            parts = n.split("/")
            if "playbooks" not in parts or not n.endswith(".json"):
                continue
            folder = posixpath.dirname(n)
            if posixpath.basename(folder) == "playbooks":
                continue  # pack-level files such as tags.json, not a collection
            if posixpath.basename(n) == "collection.metadata.json":
                meta[folder] = json.loads(z.read(n))
            else:
                pbs[folder].append(json.loads(z.read(n)))
        return [{**meta.get(f, {"name": posixpath.basename(f)}), "workflows": w} for f, w in pbs.items()]
    raise VerifyError(f"live testing covers playbooks and solution packs, not {kind}s")


def _defined_uuids(collections: list[dict[str, Any]]) -> set[str]:
    """UUIDs the export itself defines. Anything else (step types, picklists,
    connectors) belongs to the platform and must keep its value."""
    out: set[str] = set()
    for c in collections:
        out.add(str(c.get("uuid") or ""))
        for w in c.get("workflows") or []:
            out.add(str(w.get("uuid") or ""))
            for key in ("steps", "routes", "groups"):
                for o in w.get(key) or []:
                    if isinstance(o, dict):
                        out.add(str(o.get("uuid") or ""))
    return {u for u in out if UUID_RE.fullmatch(u)}


def scratch_copy(collections: list[dict[str, Any]], run: set[str]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Fresh UUIDs everywhere, prefixed names, and only safe triggers switched on.
    Returns the copy and {playbook name: new uuid}."""
    copy = json.loads(_remap(json.dumps(collections), _defined_uuids(collections)))
    names: dict[str, str] = {}
    for c in copy:
        c["name"] = PREFIX + str(c.get("name") or "collection")
        c.pop("id", None)
        c.pop("@id", None)
        for w in c.get("workflows") or []:
            names[w["name"]] = w["uuid"]
            w["isActive"] = w["name"] in run or _trigger(w) == "Referenced"
            if w["isActive"] and _trigger(w) not in SAFE_TRIGGERS:
                raise VerifyError(f"{w['name']!r} has a {_trigger(w)} trigger; only manual or "
                                  "referenced playbooks are run on a shared box")
    missing = run - names.keys()
    if missing:
        raise VerifyError(f"no playbook named {', '.join(sorted(missing))}")
    return copy, names


HARNESS = "soarshelf-verify call: "


def harness(target: str, target_uuid: str, args: dict[str, Any], module: str | None = None) -> dict[str, Any]:
    """A throwaway manual playbook that calls ``target`` with ``args``, the way a parent
    playbook would. Referenced playbooks only get ``vars.input.params`` from a caller,
    so running one directly would test it with empty inputs. With ``module`` the caller
    starts from a record of that module and passes it on as ``vars.input.records``.

    Compiled with the fsr_playbooks CLI (``fsrpb``, or $FSRPB), a test-only tool."""
    import os
    import shutil
    import subprocess
    import tempfile

    fsrpb = os.environ.get("FSRPB") or shutil.which("fsrpb")
    if not fsrpb:
        raise VerifyError("--call needs the fsr_playbooks CLI: put fsrpb on PATH or set FSRPB")
    reserved = {"name", "type", "next", "workflowReference", "apply_async", "pass_parent_env", "pass_input_record"}
    if reserved & args.keys():
        raise VerifyError(f"argument names clash with step keys: {sorted(reserved & args.keys())}")
    doc = {"collection": "soarshelf-verify harness", "playbooks": [{
        "name": HARNESS + target,
        "steps": [
            {"name": "Start", "type": "start", "next": "Call", **({"module": module} if module else {})},
            {"name": "Call", "type": "workflow_reference", "workflowReference": f"/api/3/workflows/{target_uuid}",
             **args, "apply_async": False, "pass_parent_env": False, "pass_input_record": bool(module),
             "next": "Result"},
            {"name": "Result", "type": "set_variable", "vars": {"soarshelf_result": "{{ vars.steps.Call | tojson }}"}},
        ]}]}
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "h.yaml", Path(tmp) / "h.json"
        src.write_text(yaml.safe_dump(doc, sort_keys=False))
        r = subprocess.run([fsrpb, "compile", str(src), "-o", str(out)], capture_output=True, text=True)
        if r.returncode:
            raise VerifyError(f"harness didn't compile: {(r.stderr or r.stdout).strip()[-600:]}")
        (w,) = json.loads(out.read_text())["data"][0]["workflows"]
    # The compiler derives UUIDs from names; make them fresh like the rest of the copy.
    wrap = [{"workflows": [w]}]
    fresh = json.loads(_remap(json.dumps(wrap), _defined_uuids(wrap)))[0]["workflows"][0]
    fresh["isActive"] = True
    return fresh


def _remap(text: str, uuids: set[str]) -> str:
    """Give each export-defined UUID a fresh one, wherever it appears and in any case."""
    for old in {u.lower() for u in uuids}:
        text = re.sub(re.escape(old), str(uuidlib.uuid4()), text, flags=re.I)
    return text


def _trigger(w: dict[str, Any]) -> str:
    """The playbook's trigger, from the step ``triggerStep`` names. If that doesn't
    resolve, or any other trigger-type step is unsafe, it's ``Unknown`` so the
    playbook is never switched on: a step list could put a manual step first while
    the real trigger fires on record creation."""
    want = str(w.get("triggerStep") or "").rsplit("/", 1)[-1].lower()
    steps = [(str(s.get("uuid") or "").lower(), str(s.get("stepType") or "").rsplit("/", 1)[-1].lower())
             for s in w.get("steps") or [] if isinstance(s, dict)]
    uuids = [u for u, _ in steps]
    # Empty or repeated step ids make "the trigger step" ambiguous: never guess.
    if not want or "" in uuids or len(set(uuids)) != len(uuids):
        return "Unknown"
    hits = [t for u, t in steps if u == want]
    label = config.TRIGGER_LABELS.get(hits[0], "Unknown") if len(hits) == 1 else "Unknown"
    others = [config.TRIGGER_LABELS[t] for u, t in steps if t in config.TRIGGER_LABELS and u != want]
    return label if label in SAFE_TRIGGERS and all(o in SAFE_TRIGGERS for o in others) else "Unknown"


def _button_answers(client: Any) -> None:
    """Let an answer be ``{"option": "<button>", "inputs": {...}}``.

    pyfsr's auto-answer hands every answer to ``manual_input.answer`` as a single
    value, which only works for a prompt with exactly one field. Prompts that just
    show a result and a button have none, so on this client only, a dict answer
    with an ``option`` key presses that button with those inputs."""
    mi = client.manual_input
    original = mi.answer

    def answer(value: Any = None, **kw: Any) -> Any:
        if isinstance(value, dict) and "option" in value:
            return original(option=value["option"], inputs=value.get("inputs") or {}, **kw)
        return original(value, **kw)

    mi.answer = answer


def _platform(client: Any) -> str:
    raw = client.system.version()
    v = raw.get("version") if isinstance(raw, dict) else str(raw)
    m = re.match(r"\d+\.\d+\.\d+", str(v or ""))
    if not m:
        raise VerifyError(f"could not read the platform version: {raw!r}")
    return m.group(0)


def run(item: Path, *, instance: str | None, playbooks: list[str], calls: list[str], on_record: str | None,
        inputs: dict[str, Any], expect: dict[str, str] | None = None,
        answers: dict[str, Any], timeout: float, keep: bool) -> dict[str, Any]:
    """Import (and optionally run) one item on a live box. Returns the test entry."""
    from pyfsr.instances import InstanceRegistry

    from .build import load_trust, process_item
    from .hubindex import HubIndex

    res = process_item(item, load_trust(item.parent.parent), HubIndex.load())
    if res.download is None or res.decision == "reject":
        raise VerifyError(f"{item.name} doesn't build: {'; '.join(res.reasons)}")
    kind = res.detail["type"]
    source = collections_from_download(kind, res.download)
    copy, uuids = scratch_copy(source, set(playbooks) | set(calls))
    for name in calls:
        w = next(w for c in copy for w in c["workflows"] if w["name"] == name)
        if _trigger(w) != "Referenced":
            raise VerifyError(f"--call is for referenced playbooks; use --run for {name!r}")
    module, record_uuid = (on_record.split("/", 1) if on_record else (None, None))
    if on_record and not (module and UUID_RE.fullmatch(record_uuid or "")):
        raise VerifyError("--on-record takes module/uuid, e.g. alerts/<uuid>")
    harnesses = {name: harness(name, uuids[name], inputs.get(name) or {}, module) for name in calls}
    if harnesses:
        copy[0]["workflows"] += harnesses.values()

    client = _connect(InstanceRegistry.load(), instance)
    _button_answers(client)
    platform = _platform(client)
    print(f"{item.name} v{res.detail['version']} → FortiSOAR {platform}")
    created: list[str] = []
    try:
        for c in copy:
            got = client.workflow_collections.import_export({"type": "workflow_collections", "data": [c]})
            created += [g.uuid for g in got if getattr(g, "uuid", None)]
        for c in copy:
            want_steps = sum(len(w.get("steps") or []) for w in c["workflows"])
            want_pbs = len(c["workflows"])
            live = client.post("/api/query/workflows", data={
                "logic": "AND", "filters": [{"field": "collection.name", "operator": "eq",
                                             "value": c["name"], "type": "primitive"}]},
                params={"$limit": 1000, "$relationships": "true"})
            rows = live.get("hydra:member") or []
            got_steps = sum(len(w.get("steps") or []) for w in rows)
            print(f"  imported {c['name'][len(PREFIX):]}: {len(rows)}/{want_pbs} playbooks, "
                  f"{got_steps}/{want_steps} steps")
            if len(rows) != want_pbs or got_steps != want_steps:
                raise VerifyError("the import is missing playbooks or steps")
        ran = []
        for name in playbooks:
            r = client.playbooks.run_and_wait(playbook_uuid=uuids[name], inputs=inputs.get(name),
                                              answers=answers or None, timeout=timeout)
            print(f"  ran {name}: {r.status}")
            if not r.succeeded:
                raise VerifyError(f"{name} ended {r.status}: {_why(client, r)}")
            ran.append(name)
        for name, h in harnesses.items():
            r = client.playbooks.run_and_wait(playbook_uuid=h["uuid"], answers=answers or None, timeout=timeout,
                                              **({"record_uuid": record_uuid, "module": module} if module else {}))
            # A caller and everything it calls share one task id, and pyfsr may hand back
            # any of those runs, so read each run from the log by playbook name.
            runs = client.playbooks.log_list(task_id=r.task_id, limit=100).get("hydra:member") or []
            unfinished = [f"{x.get('name')}: {x.get('status')}" for x in runs if x.get("status") != "finished"]
            print(f"  called {name}: {len(runs) - len(unfinished)}/{len(runs)} runs finished")
            if unfinished or not runs:
                raise VerifyError(f"{name} via a caller: {'; '.join(unfinished) or 'no runs logged'}; {_why(client, r)}")
            last_step, result = _final_result(client, runs, name)
            print(f"    {last_step} → {json.dumps(result, default=str)[:300]}")
            _check_expect(name, result, expect or {})
            ran.append(name)
    finally:
        if keep:
            print(f"  kept on the box: {', '.join(c['name'] for c in copy)}")
        else:
            for u in created:
                # Only ever delete what this run made: check the scratch name first.
                if client.workflow_collections.get(u, relationships=False).name.startswith(PREFIX):
                    client.workflow_collections.delete(u, hard=True)
            print(f"  removed {len(created)} scratch collection(s)")
    return {"platform": platform, "version": res.detail["version"], "sha256": res.detail["download"]["sha256"],
            "result": "ran" if ran else "imported", "playbooks": ran}


def _connect(registry: Any, instance: str | None, tries: int = 5) -> Any:
    """Log in, waiting out the auth service when it's briefly overloaded (it answers
    400 after many logins in a row and recovers on its own)."""
    import time

    for i in range(tries):
        try:
            return registry.client(instance)
        except Exception as exc:  # noqa: BLE001 - only login errors reach here
            if i == tries - 1 or "Authentication failed (400)" not in str(exc):
                raise
            time.sleep(20 * (i + 1))
    raise AssertionError("unreachable")


def _final_result(client: Any, runs: list[dict[str, Any]], name: str) -> tuple[str, dict[str, Any]]:
    """What ``name`` handed back: the result of its last finished step."""
    mine = [x for x in runs if x.get("name") == name]
    m = re.search(r"/(\d+)/?$", str(mine[0].get("@id") or "")) if mine else None
    if not m:
        raise VerifyError(f"no run of {name!r} in the log")
    steps = client.playbooks.run_env(m.group(1)).steps or {}
    done = [(n, st) for n, st in steps.items() if st.status == "finished" and st.end_time]
    if not done:
        return "", {}
    n, st = max(done, key=lambda d: d[1].end_time)
    return n, st.result if isinstance(st.result, dict) else {"result": st.result}


def _check_expect(name: str, got: dict[str, Any], expect: dict[str, str]) -> None:
    """Finishing isn't working: compare the playbook's final result with what it should be."""
    if not expect:
        return
    wrong = {k: got.get(k) for k, v in expect.items() if str(got.get(k)) != v}
    if wrong:
        raise VerifyError(f"{name} finished but returned {wrong}, expected "
                          f"{ {k: expect[k] for k in wrong} }")
    print(f"    as expected: {expect}")


def _why(client: Any, r: Any) -> str:
    """The failing step and its error, as far as the run log says."""
    if r.failure and (r.failure.failing_step or r.failure.error_message):
        return f"{r.failure.failing_step}: {r.failure.error_message}"[:800]
    bad = [f"{st.name}: {st.status} {st.result_preview or ''}".strip() for st in r.steps
           if st.status not in ("finished", "skipped")]
    if bad:
        return "; ".join(bad)[:800]
    try:
        f = client.playbooks.run_failure(r.pk)
        if f:
            return f"{f.failing_step}: {f.error_message}"[:800]
    except Exception:  # noqa: BLE001 - best effort; the status alone still fails the test
        pass
    return "no detail in the run log"


def record(item: Path, entry: dict[str, Any], notes: str = "") -> None:
    """Add or replace the meta.yaml ``tested`` entry for this platform and version."""
    f = item / "meta.yaml"
    meta = yaml.safe_load(f.read_text()) or {}
    e = {k: v for k, v in {**entry, "notes": notes}.items() if v not in ("", [], None)}
    keep = [t for t in meta.get("tested") or []
            if not (isinstance(t, dict) and str(t.get("platform")) == e["platform"]
                    and str(t.get("version")) == e["version"])]
    # A run outranks an import of the same version; never downgrade one.
    old = [t for t in meta.get("tested") or [] if t not in keep]
    if old and old[0].get("result") == "ran" and e["result"] == "imported":
        print("  kept the existing 'ran' entry")
        return
    meta["tested"] = [e] + keep
    f.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
    print(f"  recorded: {e['result']} on {e['platform']}")

/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
// Pure data module for ztpRunReport: no Angular, no DOM, no HTTP. Everything
// here is a function of the three record collections the controller fetches
// (devices, steps, run groups), so the aggregation, the failure roll-up, the
// chart geometry and the CSV can all be exercised headless in jest.
//
// Field names are confirmed against a live 8.0 box carrying the ZTPf2 modules:
//   ztpf_devices             name, managementIP, platform, firmware,
//                            connectionStatus, configStatus, ztpfRunning,
//                            ztpfArtifacts.ztfGroup, ztpfManagers.name
//   ztpf_device_automation_steps
//                            stepNumber, name, triggerKey, queueStatus{itemValue,color},
//                            outputStatusMessage, stepStart/StopTimestamp,
//                            ztpfDevices{name}, ztpfRunGroups{name} | ztpfGroup(string)
//   ztpf_run_groups          name, totalDevices, totalSteps, totalStepsComplete,
//                            totalStepsCompletePercent, totalRunningTime(Seconds),
//                            ztpfRunning, createDate
(function (root) {
  var R = {};

  // ---- status vocabulary -------------------------------------------------
  // The same nine values ztpAutomationGraph draws, and for the same reason: the
  // failure value is "Fail", not "Failed". Testing for the wrong spelling is how
  // that widget once decided no run had ever failed.
  R.STATUS = {
    "New":          { color: "#b6a6b4", order: 0 },
    "Preparing":    { color: "#e91784", order: 1 },
    "Input Needed": { color: "#b1ae06", order: 2 },
    "Ready":        { color: "#0e12f6", order: 3 },
    "Queued":       { color: "#b517ef", order: 4 },
    "Running":      { color: "#07b7f6", order: 5 },
    "Complete":     { color: "#34ca46", order: 6 },
    "Fail":         { color: "#ff0000", order: 7 },
    "Cancelled":    { color: "#808080", order: 8 }
  };
  var PENDING  = { "New": 1, "Preparing": 1, "Input Needed": 1, "Ready": 1, "Queued": 1 };
  var TERMINAL = { "Complete": 1, "Fail": 1, "Cancelled": 1 };
  var UNKNOWN_COLOR = "#9aa0a6";

  /** ---- ONE canonical spelling, and a loud bucket for everything else -----
   *
   *  A step carries THREE picklists that disagree on purpose:
   *    status       the step's OUTCOME          -- Complete / Fail / Canceled
   *    queueStatus  the worker-queue state      -- often left at Running
   *    outputStatus whether the output was clean -- OK / Exceptions Found
   *
   *  `status` is the outcome and therefore the source of truth. queueStatus is
   *  kept only as a fallback for a record that has no outcome yet. Reading
   *  queueStatus as though it were the outcome is what badged finished runs
   *  IN PROGRESS: one lab box had 683 steps parked at queueStatus=Running
   *  against 1179 that had actually completed.
   *
   *  SYNONYMS exist because the vocabulary is not stable across boxes --
   *  "Canceled" on one, "Cancelled" on another. An unmapped spelling used to
   *  fall through to pending, and pending reads as still-running, so a single
   *  letter could hold a finished fleet at IN PROGRESS. Everything now lands
   *  on a canonical value or in UNMAPPED, which the UI can surface -- silence
   *  is what made the last two of these cost a day each. */
  var SYNONYM = {
    "canceled": "Cancelled", "cancelled": "Cancelled",
    "complete": "Complete",  "completed": "Complete",
    "fail": "Fail",          "failed": "Fail",       "failure": "Fail",
    // The run group's own picklist spells its outcomes "Fail Detected" /
    // "Abort Detected" (live-verified); unmapped, both badged UNKNOWN.
    "fail detected": "Fail", "abort detected": "Cancelled",
    "aborted": "Cancelled",
    "running": "Running",    "in progress": "Running", "inprogress": "Running",
    "queued": "Queued",      "pending": "Queued",
    "ready": "Ready",        "new": "New",
    "preparing": "Preparing", "input needed": "Input Needed"
  };
  // Every value seen that no synonym covers, so a new picklist entry surfaces
  // instead of quietly counting as pending.
  var UNMAPPED = {};
  function normalizeStatus(v) {
    var raw = pick(v);
    if (raw === null || raw === undefined || raw === "") return "";
    var key = String(raw).trim().toLowerCase();
    var hit = SYNONYM[key];
    if (hit) return hit;
    UNMAPPED[String(raw).trim()] = (UNMAPPED[String(raw).trim()] || 0) + 1;
    return String(raw).trim();
  }
  R.normalizeStatus = normalizeStatus;
  R.unmappedStatuses = function () { return Object.keys(UNMAPPED).sort(); };
  R.resetUnmappedStatuses = function () { UNMAPPED = {}; };
  /** The outcome of a step, preferring the OUTCOME field over the queue state.
   *  Callers pass either a record or an aggregate row. */
  function resolveStatus(outcome, queue) {
    var a = normalizeStatus(outcome);
    if (a) return a;
    return normalizeStatus(queue);
  }
  R.resolveStatus = resolveStatus;

  /** Unwrap a picklist ({itemValue,color}) or pass a bare string through. */
  function pick(p) {
    if (p == null) return "";
    if (typeof p === "string") return p;
    return p.itemValue || p.value || "";
  }
  R.pick = pick;

  function statusColor(v) {
    var k = R.STATUS[v];
    return (k && k.color) || UNKNOWN_COLOR;
  }
  R.statusColor = statusColor;

  /** A related record can arrive as an object, a one-element array, or null. */
  /** `recordTags` is the platform's tag field, and it does NOT come back in
   *  one shape. On a record fetched through /api/query it serialises as a
   *  plain array of strings; elsewhere the same field arrives as an array of
   *  {name}/{itemValue} objects, and on an untagged record it is null rather
   *  than []. Normalising in one place keeps that mess out of the templates,
   *  where a `.name` on a string silently renders nothing.
   *
   *  Order is normalised too (case-insensitive), so a tag row redraws to the
   *  same DOM across refreshes instead of shuffling under the cursor. */
  function tagList(rec) {
    var raw = rec && rec.recordTags;
    if (!raw) return [];
    if (!isArray(raw)) raw = [raw];
    var seen = {}, out = [];
    raw.forEach(function (t) {
      var name = typeof t === "string" ? t
        : (t && (t.name || t.itemValue || t.tag)) || "";
      name = String(name).trim();
      if (!name || seen[name.toLowerCase()]) return;
      seen[name.toLowerCase()] = true;
      out.push(name);
    });
    return out.sort(function (a, b) {
      return a.toLowerCase().localeCompare(b.toLowerCase());
    });
  }
  R.tagList = tagList;

  function isArray(v) { return Object.prototype.toString.call(v) === "[object Array]"; }

  function relName(rel) {
    if (!rel) return "";
    if (Array.isArray(rel)) return rel.length ? relName(rel[0]) : "";
    return rel.name || "";
  }
  R.relName = relName;

  /** The run group a step belongs to. `ztpfRunGroups` is the real relation but
   *  it comes back null on steps staged outside a dispatched run; those carry a
   *  bare `ztpfGroup` string instead. Reading only the relation silently drops
   *  them from every total. */
  function stepGroup(step) {
    return relName(step && step.ztpfRunGroups) || (step && step.ztpfGroup) || "";
  }
  R.stepGroup = stepGroup;

  function stepDevice(step) { return relName(step && step.ztpfDevices); }
  R.stepDevice = stepDevice;

  function stepStatus(step) {
    return resolveStatus(step && step.status, step && step.queueStatus);
  }
  R.stepStatus = stepStatus;

  /** Seconds a step took. stepTimeSeconds is frequently null on real records,
   *  so derive from the timestamps when it is and report 0 rather than NaN. */
  function stepSeconds(step) {
    if (!step) return 0;
    var n = Number(step.stepTimeSeconds);
    if (n > 0) return n;
    var a = Number(step.stepStartTimestamp), b = Number(step.stepStopTimestamp);
    if (a > 0 && b > a) return b - a;
    return 0;
  }
  R.stepSeconds = stepSeconds;

  // ---- per-device roll-up ------------------------------------------------
  /** One row per device, with its step tallies and a single verdict.
   *  `steps` may cover many runs per device; `scope` picks which count:
   *    "latest" - only the device's newest run group (what the graph shows)
   *    "all"    - every step record the fetch returned
   *  Latest is the default because "does this device have anything failed"
   *  almost always means "in the run that just happened", not "ever". */
  function deviceRows(devices, steps, opts) {
    opts = opts || {};
    var scope = opts.scope === "all" ? "all" : "latest";
    var byDevice = {};
    (devices || []).forEach(function (d) {
      byDevice[d.name] = {
        name: d.name,
        uuid: d.uuid,
        managementIP: d.managementIP || "",
        platform: d.platform || "",
        firmware: d.firmware || "",
        adom: d.adom || "",
        manager: relName(d.ztpfManagers),
        connectionStatus: d.connectionStatus || "",
        configStatus: d.configStatus || "",
        running: !!d.ztpfRunning,
        latestGroup: (d.ztpfArtifacts && d.ztpfArtifacts.ztfGroup) || "",
        counts: {}, total: 0, complete: 0, failed: 0, pending: 0, running_: 0,
        seconds: 0, failures: [], steps: [], groups: {}, verdict: "no-data"
      };
    });

    // Newest group per device, derived from the steps themselves. The device
    // record's ztpfArtifacts.ztfGroup is a snapshot that can name a group whose
    // records are not in this fetch, so the steps win when they disagree.
    var newest = {};
    (steps || []).forEach(function (s) {
      var dn = stepDevice(s); if (!dn) return;
      var g = stepGroup(s); if (!g) return;
      var t = Number(s.createDate) || 0;
      if (!newest[dn] || t > newest[dn].t) newest[dn] = { t: t, g: g };
    });

    (steps || []).forEach(function (s) {
      var dn = stepDevice(s); if (!dn) return;
      var row = byDevice[dn];
      // A step can name a device that the device fetch did not return (deleted,
      // or past the page cap). Synthesise a row rather than dropping the step.
      if (!row) {
        row = byDevice[dn] = {
          name: dn, uuid: "", managementIP: "", platform: "", firmware: "",
          adom: "", manager: "", connectionStatus: "", configStatus: "",
          running: false, latestGroup: "", counts: {}, total: 0, complete: 0,
          failed: 0, pending: 0, running_: 0, seconds: 0, failures: [],
          steps: [], groups: {}, verdict: "no-data", orphan: true
        };
      }
      var g = stepGroup(s);
      row.groups[g] = true;
      if (scope === "latest" && newest[dn] && g !== newest[dn].g) return;

      var st = stepStatus(s) || "Unknown";
      row.counts[st] = (row.counts[st] || 0) + 1;
      row.total += 1;
      row.seconds += stepSeconds(s);
      row.steps.push({ n: Number(s.stepNumber) || 0, st: st });
      if (st === "Complete") row.complete += 1;
      else if (st === "Fail") {
        row.failed += 1;
        row.failures.push({
          device: dn, group: g,
          stepNumber: Number(s.stepNumber) || 0,
          name: s.name || "", triggerKey: s.triggerKey || "",
          message: s.outputStatusMessage || "",
          when: Number(s.stepStopTimestamp) || Number(s.modifyDate) || 0,
          uuid: s.uuid || ""
        });
      } else if (st === "Running") row.running_ += 1;
      else if (PENDING[st]) row.pending += 1;
    });

    var rows = Object.keys(byDevice).map(function (k) { return byDevice[k]; });
    rows.forEach(function (r) {
      r.groupCount = Object.keys(r.groups).length;
      r.shownGroup = (newest[r.name] && newest[r.name].g) || r.latestGroup || "";
      r.failures.sort(function (a, b) { return a.stepNumber - b.stepNumber; });
      r.successRate = r.total ? Math.round((r.complete / r.total) * 1000) / 10 : 0;
      r.verdict = deviceVerdict(r);
      r.ribbon = ribbon(r);
    });
    // Failures first, then most steps -- the reason someone opens this page is
    // to find what broke, so it must not be below the fold.
    rows.sort(function (a, b) {
      if ((b.failed > 0) !== (a.failed > 0)) return b.failed - a.failed;
      if (b.failed !== a.failed) return b.failed - a.failed;
      return (b.total - a.total) || a.name.localeCompare(b.name);
    });
    return rows;
  }
  R.deviceRows = deviceRows;

  // ---- aggregate-backed roll-up -----------------------------------------
  /** Same row shape as deviceRows(), built from SERVER-SIDE aggregation
   *  instead of from every step record.
   *
   *  The widget used to fetch a projected page of 1000 step records -- 5.7 MB
   *  on a modest lab fleet -- and tally them in the browser. It only ever
   *  needed two things from that payload: per-device COUNTS, and the detail of
   *  the steps that FAILED. The platform can do the counting itself:
   *
   *    POST /api/query/<module>  aggregates: [
   *      {groupby ztpfDevices.name} {groupby ztpfRunGroups.name}
   *      {groupby queueStatus.itemValue} {sum stepTimeSeconds}
   *      {max createDate} {countdistinct *} ]
   *
   *  Measured on a live fleet: 5,743,519 bytes -> 1,188. The reason the win is
   *  so large is not row count, it is that a groupby on a RELATION returns the
   *  related name as a scalar -- `__selectFields` cannot do that, so the old
   *  projection still dragged the entire ztpfDevices object back on every row.
   *
   *  `aggRows` are those rows: {device, grp, status, secs, newest, total}.
   *  `failures` are full records for the few steps whose status is Fail,
   *  fetched separately -- that is the only place step DETAIL is ever read.
   */
  function deviceRowsFromAggregate(devices, aggRows, failures, opts) {
    opts = opts || {};
    var scope = opts.scope === "all" ? "all" : "latest";
    var byDevice = {};
    (devices || []).forEach(function (d) { byDevice[d.name] = blankRow(d); });

    // Newest group per device. `newest` is a max(createDate) and arrives as a
    // datetime STRING ("2026-08-17 18:05:59.099607"), not the epoch integer the
    // record fields carry -- compare as strings, never Number() it.
    var newest = {};
    (aggRows || []).forEach(function (r) {
      var dn = r && r.device, g = r && r.grp;
      if (!dn || !g) return;
      var t = String(r.newest || "");
      if (!newest[dn] || t > newest[dn].t) newest[dn] = { t: t, g: g };
    });

    (aggRows || []).forEach(function (r) {
      var dn = r && r.device; if (!dn) return;
      var row = byDevice[dn];
      if (!row) { row = byDevice[dn] = blankRow({ name: dn }); row.orphan = true; }
      var g = r.grp || "";
      if (g) row.groups[g] = true;
      if (scope === "latest" && newest[dn] && g !== newest[dn].g) return;

      var st = resolveStatus(r.status, r.queueStatus) || "Unknown";
      var n = Number(r.total) || 0;
      row.counts[st] = (row.counts[st] || 0) + n;
      row.total += n;
      row.seconds += Number(r.secs) || 0;
      if (st === "Complete") row.complete += n;
      else if (st === "Fail") row.failed += n;
      else if (st === "Running") row.running_ += n;
      else if (PENDING[st]) row.pending += n;
    });

    // Failure DETAIL rides in from the filtered fetch, scoped the same way.
    (failures || []).forEach(function (s) {
      var dn = stepDevice(s); if (!dn) return;
      var row = byDevice[dn];
      if (!row) { row = byDevice[dn] = blankRow({ name: dn }); row.orphan = true; }
      var g = stepGroup(s);
      if (scope === "latest" && newest[dn] && g !== newest[dn].g) return;
      row.failures.push({
        device: dn, group: g,
        stepNumber: Number(s.stepNumber) || 0,
        name: s.name || "", triggerKey: s.triggerKey || "",
        message: s.outputStatusMessage || "",
        when: Number(s.stepStopTimestamp) || Number(s.modifyDate) || 0,
        uuid: s.uuid || ""
      });
    });

    var rows = Object.keys(byDevice).map(function (k) { return byDevice[k]; });
    rows.forEach(function (r) {
      r.groupCount = Object.keys(r.groups).length;
      r.shownGroup = (newest[r.name] && newest[r.name].g) || r.latestGroup || "";
      r.failures.sort(function (a, b) { return a.stepNumber - b.stepNumber; });
      r.successRate = r.total ? Math.round((r.complete / r.total) * 1000) / 10 : 0;
      r.verdict = deviceVerdict(r);
      r.ribbon = ribbonFromCounts(r);
    });
    rows.sort(sortRows);
    return rows;
  }
  R.deviceRowsFromAggregate = deviceRowsFromAggregate;

  function blankRow(d) {
    d = d || {};
    return {
      name: d.name, uuid: d.uuid || "",
      managementIP: d.managementIP || "", platform: d.platform || "",
      firmware: d.firmware || "", adom: d.adom || "",
      manager: relName(d.ztpfManagers),
      connectionStatus: d.connectionStatus || "", configStatus: d.configStatus || "",
      running: !!d.ztpfRunning,
      tags: tagList(d),
      latestGroup: (d.ztpfArtifacts && d.ztpfArtifacts.ztfGroup) || "",
      counts: {}, total: 0, complete: 0, failed: 0, pending: 0, running_: 0,
      seconds: 0, failures: [], steps: [], groups: {}, verdict: "no-data"
    };
  }

  function sortRows(a, b) {
    if ((b.failed > 0) !== (a.failed > 0)) return b.failed - a.failed;
    if (b.failed !== a.failed) return b.failed - a.failed;
    return (b.total - a.total) || a.name.localeCompare(b.name);
  }

  /** The grid card's ribbon, DERIVED rather than read per step.
   *  An aggregate knows how many steps are in each state but not which step is
   *  which -- except for the failures, whose real stepNumbers come from the
   *  detail fetch. ZTP steps execute in order, so the honest reconstruction is:
   *  pin each known failure at its own position, then fill the rest
   *  complete -> running -> queued, which is the order a sequential pipeline
   *  actually progresses through. The failure positions are real; the
   *  boundary between complete and queued is inferred. */
  function ribbonFromCounts(r) {
    var total = r.total;
    if (!total) return [];
    var failedAt = {};
    r.failures.forEach(function (f) {
      if (f.stepNumber >= 1 && f.stepNumber <= total) failedAt[f.stepNumber - 1] = true;
    });
    var fill = [];
    for (var i = 0; i < r.complete; i++) fill.push(verdictColor("healthy"));
    for (var j = 0; j < r.running_; j++) fill.push(verdictColor("running"));
    while (fill.length < total) fill.push(verdictColor("pending"));

    var out = [], k = 0;
    for (var n = 0; n < total; n++) {
      if (failedAt[n]) out.push(verdictColor("failed"));
      else out.push(fill[k++] || verdictColor("pending"));
    }
    return out.length <= RIBBON_MAX ? out : bucketRibbon(out);
  }

  /** Shared with ribbon(): squeeze a long run to a fixed width, each bucket
   *  taking its WORST cell so one failure cannot be averaged out of sight. */
  function bucketRibbon(cells) {
    var rank = {}; rank[verdictColor("failed")] = 0; rank[verdictColor("running")] = 1;
    rank[verdictColor("pending")] = 2; rank[verdictColor("healthy")] = 3;
    var per = cells.length / RIBBON_MAX, out = [];
    for (var i = 0; i < RIBBON_MAX; i++) {
      var b = cells.slice(Math.floor(i * per), Math.floor((i + 1) * per));
      out.push(b.reduce(function (a, c) {
        return (rank[c] == null ? 2 : rank[c]) < (rank[a] == null ? 2 : rank[a]) ? c : a;
      }, b.length ? b[0] : verdictColor("pending")));
    }
    return out;
  }

  /** A device's steps, in order, as a short array of colours -- the grid card
   *  draws it as a ribbon so the shape of a run is readable without opening
   *  anything. Capped at RIBBON_MAX: a device with 200 steps would otherwise
   *  render 200 sub-pixel slivers, which is noise, not a picture. Over the cap
   *  the steps are bucketed and each bucket takes its WORST status, so a lone
   *  failure inside a long run can never be averaged out of sight. */
  var RIBBON_MAX = 24;
  var RIBBON_RANK = { Fail: 0, Running: 1, Complete: 3 };
  function ribbonRank(st) { return RIBBON_RANK[st] != null ? RIBBON_RANK[st] : 2; }
  function ribbonColor(st) {
    if (st === "Fail") return verdictColor("failed");
    if (st === "Running") return verdictColor("running");
    if (st === "Complete") return verdictColor("healthy");
    return verdictColor("pending");
  }
  function ribbon(r) {
    var steps = (r && r.steps) || [];
    if (!steps.length) return [];
    var ordered = steps.slice().sort(function (a, b) { return a.n - b.n; });
    if (ordered.length <= RIBBON_MAX) {
      return ordered.map(function (s) { return ribbonColor(s.st); });
    }
    var per = ordered.length / RIBBON_MAX, out = [];
    for (var i = 0; i < RIBBON_MAX; i++) {
      var bucket = ordered.slice(Math.floor(i * per), Math.floor((i + 1) * per));
      var worst = bucket.reduce(function (a, s) {
        return ribbonRank(s.st) < ribbonRank(a) ? s.st : a;
      }, bucket.length ? bucket[0].st : "Queued");
      out.push(ribbonColor(worst));
    }
    return out;
  }
  R.ribbon = ribbon;

  /** One word for a device's state. `failed` outranks everything: a run that
   *  carried on past a broken step and finished still needs attention. */
  function deviceVerdict(r) {
    if (!r.total) return "no-data";
    if (r.failed > 0) return "failed";
    if (r.running_ > 0 || r.running) return "running";
    if (r.pending > 0) return "pending";
    return "healthy";
  }
  R.deviceVerdict = deviceVerdict;

  // ---- run-group roll-up -------------------------------------------------
  /** Run groups joined to the failure counts derived from the step records.
   *  The module's own totalStepsComplete/Percent are trusted for completion,
   *  but it carries NO failure count -- so a group can read 100% complete and
   *  still contain a failed step. That join is the whole point of this table. */
  /** The platform reports `-1` for both runtime fields while a group is still
   *  running -- it is a sentinel, not a duration. It is truthy, so it survives
   *  a `|| ""` fallback and renders as a literal "-1" in the runtime column.
   *  Scrub it here so every consumer (table, CSV, PDF) sees "unknown". */
  function runtimeSeconds(g) {
    var n = Number(g && g.totalRunningTimeSeconds);
    return isFinite(n) && n >= 0 ? n : 0;
  }
  function runtimeText(g) {
    var t = g && g.totalRunningTime;
    if (t === null || t === undefined) return "";
    t = String(t).trim();
    if (!t || t.charAt(0) === "-") return "";
    return t;
  }
  R.runtimeText = runtimeText;
  R.runtimeSeconds = runtimeSeconds;

  /** When a run group finished, as an epoch second, or 0 while it is running.
   *
   *  The module carries no completion timestamp of its own -- only a start
   *  (createDate) and a duration. Adding the duration to the start is exact
   *  when the platform reported one, and `modifyDate` is the honest fallback:
   *  the last thing that touched the record was its final step reporting in.
   *  A running group returns 0 rather than `now`, because a completion time
   *  that advances every time you look at it is not a completion time. */
  function groupFinishedAt(g) {
    if (!g) return 0;
    if (g.ztpfRunning) return 0;
    var start = Number(g.createDate) || 0;
    var secs = runtimeSeconds(g);
    if (start && secs > 0) return start + secs;
    return Number(g.modifyDate) || 0;
  }
  R.groupFinishedAt = groupFinishedAt;

  /** A run group's verdict FROM ITS OWN STATUS FIELD.
   *
   *  The run group carries the outcome the platform decided on, and that is
   *  what the row must say. The previous reading rolled the verdict up out of
   *  the steps instead, which is how a group whose every step had completed --
   *  5 of 5, 100% -- still badged IN PROGRESS: one step's queue row had never
   *  been reset, and the roll-up believed it over the group's own "Complete".
   *
   *  Returns "" when the group carries no status, so the caller can fall back
   *  to the step roll-up for a record the automation has not stamped yet. */
  var GROUP_STATUS_VERDICT = {
    "Complete":  "healthy",
    "Fail":      "failed",
    "Cancelled": "cancelled",
    "Running":   "running",
    "Queued":    "pending",
    "New":       "pending",
    "Preparing": "pending",
    "Ready":     "pending",
    "Input Needed": "pending"
  };
  function groupStatusVerdict(status) {
    var c = normalizeStatus(status);
    if (!c) return "";
    // An unmapped spelling is NOT progress -- that assumption is what held a
    // finished fleet at IN PROGRESS. It reads as its own state instead.
    return GROUP_STATUS_VERDICT[c] || "unknown";
  }
  R.groupStatusVerdict = groupStatusVerdict;

  function runGroupRows(groups, steps, limit) {
    var failByGroup = {}, stepsByGroup = {}, devsByGroup = {};
    (steps || []).forEach(function (s) {
      var g = stepGroup(s); if (!g) return;
      stepsByGroup[g] = (stepsByGroup[g] || 0) + 1;
      if (stepStatus(s) === "Fail") failByGroup[g] = (failByGroup[g] || 0) + 1;
      var dn = stepDevice(s);
      if (dn) { (devsByGroup[g] = devsByGroup[g] || {})[dn] = true; }
    });
    var rows = (groups || []).map(function (g) {
      var seen = devsByGroup[g.name] ? Object.keys(devsByGroup[g.name]) : [];
      return {
        name: g.name, uuid: g.uuid,
        totalDevices: Number(g.totalDevices) || 0,
        totalSteps: Number(g.totalSteps) || 0,
        stepsSeen: stepsByGroup[g.name] || 0,
        complete: Number(g.totalStepsComplete) || 0,
        percent: Number(g.totalStepsCompletePercent) || 0,
        failed: failByGroup[g.name] || 0,
        runtime: runtimeText(g),
        seconds: runtimeSeconds(g),
        running: !!g.ztpfRunning,
        // The run group's OWN outcome picklist. This is the authority on how
        // the run ended -- see groupStatusVerdict for why it outranks the
        // step roll-up that used to decide it.
        status: normalizeStatus(g.status),
        startedAt: Number(g.createDate) || 0,
        finishedAt: groupFinishedAt(g),
        tags: tagList(g),
        devices: seen.sort(),
        createDate: Number(g.createDate) || 0
      };
    });
    rows.sort(function (a, b) { return b.createDate - a.createDate; });
    return limit > 0 ? rows.slice(0, limit) : rows;
  }
  R.runGroupRows = runGroupRows;

  /** Run-group roll-up from the aggregate, not from a page of step records.
   *  The aggregate already carries every {device, grp, status, total} tuple, so
   *  the per-group device list and step count come out of it for free -- no
   *  second request. Only the failure COUNT wants the detail slice, and that is
   *  every Fail step by construction (the filter is queueStatus eq Fail), so it
   *  cannot undercount the way a truncated step page could. */
  function runGroupRowsFromAggregate(groups, aggRows, failures, limit) {
    var stepsByGroup = {}, devsByGroup = {}, failByGroup = {};
    (aggRows || []).forEach(function (r) {
      var g = r && r.grp; if (!g) return;
      stepsByGroup[g] = (stepsByGroup[g] || 0) + (Number(r.total) || 0);
      if (r.device) (devsByGroup[g] = devsByGroup[g] || {})[r.device] = true;
    });
    (failures || []).forEach(function (s) {
      var g = stepGroup(s); if (!g) return;
      failByGroup[g] = (failByGroup[g] || 0) + 1;
    });
    var rows = (groups || []).map(function (g) {
      var seen = devsByGroup[g.name] ? Object.keys(devsByGroup[g.name]) : [];
      return {
        name: g.name, uuid: g.uuid,
        totalDevices: Number(g.totalDevices) || 0,
        totalSteps: Number(g.totalSteps) || 0,
        stepsSeen: stepsByGroup[g.name] || 0,
        complete: Number(g.totalStepsComplete) || 0,
        percent: Number(g.totalStepsCompletePercent) || 0,
        failed: failByGroup[g.name] || 0,
        runtime: runtimeText(g),
        seconds: runtimeSeconds(g),
        running: !!g.ztpfRunning,
        // The run group's OWN outcome picklist. This is the authority on how
        // the run ended -- see groupStatusVerdict for why it outranks the
        // step roll-up that used to decide it.
        status: normalizeStatus(g.status),
        startedAt: Number(g.createDate) || 0,
        finishedAt: groupFinishedAt(g),
        tags: tagList(g),
        devices: seen.sort(),
        createDate: Number(g.createDate) || 0
      };
    });
    rows.sort(function (a, b) { return b.createDate - a.createDate; });
    return limit > 0 ? rows.slice(0, limit) : rows;
  }
  R.runGroupRowsFromAggregate = runGroupRowsFromAggregate;

  // ---- group -> device -> phase hierarchy --------------------------------
  /** The run group is the unit people actually dispatch: one ZTP run pushes a
   *  batch of devices, and the question afterwards is "how did THAT run go, and
   *  which of its devices are stuck where". The flat device table answered a
   *  different question -- "what is wrong anywhere in the fleet" -- and buried
   *  the batch that a human just kicked off under every device that ever ran.
   *
   *  The whole first level of this hierarchy is FREE. The step aggregate is
   *  already grouped by {device, grp, status}, which is exactly a group x device
   *  x status cube: the per-device rows inside a group are a reshape of rows we
   *  already have, not a second request. Only the PHASE list -- which named step
   *  passed and which failed -- needs step records, and that is fetched lazily
   *  per (group, device) when someone expands one. See the controller's
   *  loadPhases.
   */
  function groupDeviceRows(aggRows, failures, deviceIndex) {
    var idx = deviceIndex || {};
    var byGroup = {};

    function rowFor(bucket, g, dn) {
      var row = bucket[dn];
      if (row) return row;
      // The device record supplies the identity columns (IP, platform, and the
      // uuid a deep link needs); the cube supplies the counts. A device the
      // device fetch never returned still gets a row -- dropping it would make
      // the group's device count disagree with the rows listed under it.
      row = bucket[dn] = blankRow(idx[dn] || { name: dn });
      if (!idx[dn]) row.orphan = true;
      row.group = g;
      return row;
    }

    (aggRows || []).forEach(function (r) {
      var g = r && r.grp, dn = r && r.device;
      if (!g || !dn) return;
      var row = rowFor(byGroup[g] || (byGroup[g] = {}), g, dn);
      var st = resolveStatus(r.status, r.queueStatus) || "Unknown";
      var n = Number(r.total) || 0;
      row.counts[st] = (row.counts[st] || 0) + n;
      row.total += n;
      row.seconds += Number(r.secs) || 0;
      if (st === "Complete") row.complete += n;
      else if (st === "Fail") row.failed += n;
      else if (st === "Running") row.running_ += n;
      else if (PENDING[st]) row.pending += n;
    });

    // Failure detail is scoped to the group it happened IN -- not to the
    // device's latest run, the way the flat table scopes it. Inside a group the
    // only failures that belong on a row are that run's.
    (failures || []).forEach(function (s) {
      var dn = stepDevice(s), g = stepGroup(s);
      if (!dn || !g) return;
      // A failure in a group the aggregate never reported is still real: the
      // aggregate can be silently truncated, the failures fetch is complete by
      // construction (its filter IS queueStatus eq Fail).
      var row = rowFor(byGroup[g] || (byGroup[g] = {}), g, dn);
      row.failures.push({
        device: dn, group: g,
        stepNumber: Number(s.stepNumber) || 0,
        name: s.name || "", triggerKey: s.triggerKey || "",
        message: s.outputStatusMessage || "",
        when: Number(s.stepStopTimestamp) || Number(s.modifyDate) || 0,
        uuid: s.uuid || ""
      });
    });

    var out = {};
    Object.keys(byGroup).forEach(function (g) {
      var rows = Object.keys(byGroup[g]).map(function (k) { return byGroup[g][k]; });
      rows.forEach(function (r) {
        r.groupCount = 1;
        r.shownGroup = g;
        r.failures.sort(function (a, b) { return a.stepNumber - b.stepNumber; });
        r.successRate = r.total ? Math.round((r.complete / r.total) * 1000) / 10 : 0;
        r.verdict = deviceVerdict(r);
        r.ribbon = ribbonFromCounts(r);
        // The expand/lazy-fetch key. A device name is NOT unique across the
        // hierarchy -- the same device appears in every run it took part in --
        // so keying expansion or the phase cache by name alone would open the
        // same device in every group at once.
        r.key = g + "::" + r.name;
      });
      rows.sort(sortRows);
      out[g] = rows;
    });
    return out;
  }
  R.groupDeviceRows = groupDeviceRows;

  /** Index a device-record fetch by name, so the hierarchy can hang identity
   *  columns off the aggregate's bare device name. */
  function indexDevices(devices) {
    var idx = {};
    (devices || []).forEach(function (d) { if (d && d.name) idx[d.name] = d; });
    return idx;
  }
  R.indexDevices = indexDevices;

  /** Run-group rows with their device rows attached and a verdict of their own.
   *  This is what the Groups layout renders top to bottom. */
  function groupTree(groupRows, aggRows, failures, devices) {
    var perGroup = groupDeviceRows(aggRows, failures, indexDevices(devices));
    return (groupRows || []).map(function (g) {
      var rows = perGroup[g.name] || [];
      var tally = { failed: 0, running: 0, pending: 0, healthy: 0, "no-data": 0 };
      rows.forEach(function (r) { tally[r.verdict] = (tally[r.verdict] || 0) + 1; });
      var out = shallow({}, g);
      out.deviceRows = rows;
      out.tally = tally;
      out.devicesSeen = rows.length;
      // The group's own totalDevices wins when it is larger: a device that was
      // dispatched but has not produced a single step record yet is still in
      // the run, and belongs in the denominator.
      out.deviceTotal = Math.max(Number(g.totalDevices) || 0, rows.length);
      out.verdict = groupVerdict(out);
      // PRECOMPUTED, not called from the template. `ng-repeat="s in groupBar(g)"`
      // builds a new array every digest, ng-repeat sees a changed collection
      // every time, and the digest never settles -- $rootScope:infdig, which
      // presents as a page that renders its text but never applies an ng-class
      // (Angular bails out before those watchers run, so every verdict colour
      // silently disappears). Same trap the VERDICTS constant exists for.
      out.bar = groupBar(out);
      // A run carries a tag of its own (the wave it belongs to) AND pulls in
      // whatever its devices are tagged with. Both matter on the run row: the
      // run tag says which batch this was, the device tags say what kind of
      // kit is in it. Showing only one of the two makes a tagged fleet look
      // untagged, so the row renders the union and remembers which is which.
      // `g` here is a run-group ROW, which has already normalised recordTags
      // into `tags` -- reading recordTags off it again finds nothing. The
      // tagList fallback keeps this honest if a raw record is ever passed in.
      out.ownTags = (g.tags && g.tags.length) ? g.tags : tagList(g);
      // Device tags EXCLUDE the run's own. A device usually repeats the wave
      // tag of the run it was dispatched in, and drawing that twice on one row
      // -- once solid, once dashed -- is just noise that reads like a bug.
      out.deviceTags = withoutTags(unionTags(rows), out.ownTags);
      out.tags = mergeTags(out.ownTags, out.deviceTags);
      out.strip = rows.map(function (r) {
        return { name: r.name, color: verdictColor(r.verdict), verdict: r.verdict };
      });
      return out;
    });
  }
  R.groupTree = groupTree;

  /** Every distinct tag across the device rows of one run. */
  function unionTags(rows) {
    var seen = {}, out = [];
    (rows || []).forEach(function (r) {
      (r.tags || []).forEach(function (t) {
        if (seen[t.toLowerCase()]) return;
        seen[t.toLowerCase()] = true;
        out.push(t);
      });
    });
    return out.sort(function (a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()); });
  }
  R.unionTags = unionTags;

  function mergeTags(a, b) {
    var seen = {}, out = [];
    (a || []).concat(b || []).forEach(function (t) {
      if (!t || seen[t.toLowerCase()]) return;
      seen[t.toLowerCase()] = true;
      out.push(t);
    });
    return out;
  }
  R.mergeTags = mergeTags;

  function withoutTags(list, drop) {
    var skip = {};
    (drop || []).forEach(function (t) { skip[String(t).toLowerCase()] = true; });
    return (list || []).filter(function (t) { return !skip[String(t).toLowerCase()]; });
  }
  R.withoutTags = withoutTags;

  /** The tag vocabulary for the filter bar, commonest first then alphabetical.
   *
   *  Counted in RUNS, not devices, because the bar sits above a list of runs
   *  and a chip reading 12 must select 12 rows. Counting tag uses instead
   *  would put "wave04 (37)" above a filter that yields four runs -- the same
   *  class of self-contradicting number as the failed-count bug. */
  function allTags(tree) {
    var n = {};
    (tree || []).forEach(function (g) {
      (g.tags || []).forEach(function (t) { n[t] = (n[t] || 0) + 1; });
    });
    return Object.keys(n).map(function (t) { return { name: t, count: n[t] }; })
      .sort(function (a, b) {
        return (b.count - a.count) || a.name.toLowerCase().localeCompare(b.name.toLowerCase());
      });
  }
  R.allTags = allTags;

  /** Does this run, or any device in it, carry one of the wanted tags?
   *  OR within the tag set: picking wave04 and wave006 asks for both waves,
   *  which is what a row of chips reads as. */
  function groupHasTag(g, want) {
    if (!want || !want.length) return true;
    for (var i = 0; i < want.length; i++) {
      var w = String(want[i]).toLowerCase();
      var own = (g.tags || []);
      for (var j = 0; j < own.length; j++) {
        if (String(own[j]).toLowerCase() === w) return true;
      }
    }
    return false;
  }
  R.groupHasTag = groupHasTag;

  function deviceHasTag(r, want) {
    if (!want || !want.length) return true;
    for (var i = 0; i < want.length; i++) {
      var w = String(want[i]).toLowerCase();
      var own = (r.tags || []);
      for (var j = 0; j < own.length; j++) {
        if (String(own[j]).toLowerCase() === w) return true;
      }
    }
    return false;
  }
  R.deviceHasTag = deviceHasTag;

  // This module is deliberately framework-free, so a two-line shallow copy
  // stands in for angular.extend.
  function shallow(dst, src) {
    for (var k in src) if (Object.prototype.hasOwnProperty.call(src, k)) dst[k] = src[k];
    return dst;
  }

  /** One word for a whole run. Same precedence as a device: anything failed
   *  outranks anything moving, which outranks waiting. Note it reads the DEVICE
   *  tally, not the step percentage: a group at 100% step completion that
   *  contains a failed device is not a success, and reading
   *  `totalStepsCompletePercent` alone is exactly how that gets called one. */
  function groupVerdict(g) {
    if (!g) return "no-data";
    var t = g.tally || {};
    if ((t.failed || 0) > 0 || (g.failed || 0) > 0) return "failed";
    if (g.running || (t.running || 0) > 0) return "running";
    if ((t.pending || 0) > 0) return "pending";
    if ((t.healthy || 0) > 0) return "healthy";
    return "no-data";
  }
  R.groupVerdict = groupVerdict;

  /** The ordered phase list for one device in one run -- the bottom of the
   *  drill-down, built from the lazily fetched step records. `ok` / `bad` are
   *  precomputed rather than left to the template, because a template that
   *  tests status strings inline is where the "Fail" vs "Failed" spelling bug
   *  gets reintroduced. */
  function phaseRows(steps) {
    return (steps || []).map(function (s, i) {
      var st = stepStatus(s) || "Unknown";
      var id = stepRecordId(s);
      return {
        // A STABLE, unique identity for `track by`. Without one, ng-repeat
        // rebuilds every <li> on each refresh and the list visibly flashes;
        // with a non-unique one Angular throws ngRepeat:dupes. The uuid is
        // both when it is present -- the index only backstops a record that
        // arrived without any id at all.
        key: id || ("i" + i + ":" + (Number(s.stepNumber) || 0)),
        stepNumber: Number(s.stepNumber) || 0,
        name: s.name || "(unnamed step)",
        triggerKey: s.triggerKey || "",
        status: st,
        color: ribbonColor(st),
        ok: st === "Complete",
        bad: st === "Fail",
        active: st === "Running",
        message: s.outputStatusMessage || "",
        // A step that has not run has not taken any time. Timestamps can be
        // present on a queued record (staged, then re-queued), and reporting
        // "7s" next to QUEUED reads as a step that ran and is somehow still
        // waiting.
        seconds: (st === "Complete" || st === "Fail" || st === "Running")
          ? stepSeconds(s) : 0,
        when: Number(s.stepStopTimestamp) || Number(s.createDate) || 0,
        uuid: id
      };
    }).sort(function (a, b) { return a.stepNumber - b.stepNumber; });
  }
  R.phaseRows = phaseRows;

  /** uuid preferred, else the @id tail -- a step record fetched through the
   *  query endpoint sometimes carries only the IRI. */
  function stepRecordId(s) {
    if (!s) return "";
    if (s.uuid) return s.uuid;
    if (s["@id"]) { var p = String(s["@id"]).split("/"); return p[p.length - 1]; }
    return s.id != null ? String(s.id) : "";
  }
  R.stepRecordId = stepRecordId;

  /** A run's progress as one bar, in the same four-colour vocabulary the device
   *  bars use -- but counted over that group's DEVICES. */
  function groupBar(g) {
    var rows = (g && g.deviceRows) || [];
    var t = rows.length || 1;
    var c = (g && g.tally) || {};
    return [
      { key: "healthy", value: c.healthy || 0, pct: (c.healthy || 0) / t * 100, color: verdictColor("healthy") },
      { key: "running", value: c.running || 0, pct: (c.running || 0) / t * 100, color: verdictColor("running") },
      { key: "pending", value: c.pending || 0, pct: (c.pending || 0) / t * 100, color: verdictColor("pending") },
      { key: "failed",  value: c.failed  || 0, pct: (c.failed  || 0) / t * 100, color: verdictColor("failed") }
    ].filter(function (s) { return s.value > 0; });
  }
  R.groupBar = groupBar;

  /** Free-text + verdict filter over the hierarchy. A group SURVIVES if its own
   *  name matches or if any device under it matches, and when it survives on a
   *  device match it is returned carrying ONLY the matching devices -- typing a
   *  device name should show you that device's run, not its run plus forty
   *  siblings you did not ask about. The returned groups are copies, so
   *  narrowing the view never mutates the built tree. */
  function filterGroups(tree, query, verdicts, tags) {
    var q = (query || "").trim().toLowerCase();
    var want = verdicts && Object.keys(verdicts).filter(function (k) { return verdicts[k]; });
    var hasVerdict = !!(want && want.length);
    var wantTags = tags && Object.keys(tags).filter(function (k) { return tags[k]; });
    var hasTag = !!(wantTags && wantTags.length);
    if (!q && !hasVerdict && !hasTag) return tree || [];
    var out = [];
    (tree || []).forEach(function (g) {
      // A tag filter is answered by the RUN first. When the tag is the run's
      // own (the wave), every device in it belongs to that wave and the run
      // survives whole; narrowing to the subset of devices that happen to
      // repeat the tag on themselves would hide most of the batch you asked
      // for. Only when the run does not carry the tag itself does the filter
      // fall through to its devices.
      if (hasTag && !groupHasTag(g, wantTags)) return;
      var tagIsOwn = !hasTag || groupHasTag({ tags: g.ownTags }, wantTags);
      var byName = !!q && String(g.name || "").toLowerCase().indexOf(q) !== -1;
      var kept = (g.deviceRows || []).filter(function (r) {
        if (hasVerdict && want.indexOf(r.verdict) === -1) return false;
        if (hasTag && !tagIsOwn && !deviceHasTag(r, wantTags)) return false;
        // A text hit on the GROUP NAME keeps every device in it -- you asked
        // for the run, so you get the run (still narrowed by any verdict chip).
        if (!q || byName) return true;
        return deviceHaystack(r).indexOf(q) !== -1;
      });
      if (kept.length) out.push(withDevices(g, kept));
      // A group whose name matches but that has no device rows at all (nothing
      // dispatched yet) is still a real answer to the search, as long as no
      // verdict chip is narrowing to a state it cannot have.
      else if ((byName || (hasTag && !q)) && !hasVerdict) out.push(withDevices(g, []));
    });
    return out;
  }
  R.filterGroups = filterGroups;

  function deviceHaystack(r) {
    return [r.name, r.managementIP, r.platform, r.firmware, r.adom, r.manager,
            r.connectionStatus, r.shownGroup, r.verdict]
      .concat(r.tags || [])
      .concat((r.failures || []).map(function (x) {
        return x.name + " " + x.message + " " + x.triggerKey;
      }))
      .join(" ").toLowerCase();
  }

  function withDevices(g, rows) {
    var c = shallow({}, g);
    c.deviceRows = rows;
    c.devicesSeen = rows.length;
    // The bar and the tally describe what is ON SCREEN. Carrying the unfiltered
    // ones over would draw a four-device bar above one visible device.
    var tally = { failed: 0, running: 0, pending: 0, healthy: 0, "no-data": 0 };
    rows.forEach(function (r) { tally[r.verdict] = (tally[r.verdict] || 0) + 1; });
    c.tally = tally;
    c.bar = groupBar(c);
    // The DEVICE tag set describes what is on screen, same rule as the bar --
    // but the run's OWN tag is a property of the run and survives filtering.
    c.deviceTags = withoutTags(unionTags(rows), c.ownTags);
    c.tags = mergeTags(c.ownTags, c.deviceTags);
    return c;
  }

  /** The hierarchy as one flat CSV: a row per device per run, so the export
   *  carries the same group-first shape the screen does. */
  R.csvGroupDevices = function (tree) {
    var rows = [];
    (tree || []).forEach(function (g) {
      (g.deviceRows || []).forEach(function (r) {
        rows.push([g.name, g.createDate ? new Date(g.createDate * 1000).toISOString() : "",
                   r.name, r.managementIP, r.platform, r.firmware, r.verdict,
                   r.total, r.complete, r.failed, r.pending, r.running_,
                   r.successRate, humanSeconds(r.seconds),
                   (r.failures || []).map(function (f) {
                     return "#" + f.stepNumber + " " + f.name + ": " + (f.message || "");
                   }).join(" | ")]);
      });
    });
    return toCsv(["Run group", "Created", "Device", "Management IP", "Platform",
                  "Firmware", "Verdict", "Steps", "Complete", "Failed", "Pending",
                  "Running", "Success rate %", "Duration", "Failures"], rows);
  };

  // ---- KPIs --------------------------------------------------------------
  function kpis(devRows, groupRows, steps) {
    var failedDevices = devRows.filter(function (r) { return r.failed > 0; });
    var totalSteps = 0, failedSteps = 0, completeSteps = 0;
    (steps || []).forEach(function (s) {
      totalSteps += 1;
      var st = stepStatus(s);
      if (st === "Fail") failedSteps += 1;
      else if (st === "Complete") completeSteps += 1;
    });
    var timed = groupRows.filter(function (g) { return g.seconds > 0; });
    var avg = timed.length
      ? Math.round(timed.reduce(function (a, g) { return a + g.seconds; }, 0) / timed.length)
      : 0;
    return {
      devices: devRows.length,
      devicesFailed: failedDevices.length,
      devicesRunning: devRows.filter(function (r) { return r.verdict === "running"; }).length,
      runGroups: groupRows.length,
      runGroupsFailed: groupRows.filter(function (g) { return g.failed > 0; }).length,
      steps: totalSteps,
      stepsComplete: completeSteps,
      stepsFailed: failedSteps,
      // Step-level rate. Kept for the drill-down and the CSV/PDF; it is NOT
      // what the report leads with -- see deviceSuccessRate.
      successRate: totalSteps ? Math.round((completeSteps / totalSteps) * 1000) / 10 : 0,
      devicesHealthy: devRows.filter(function (r) { return r.verdict === "healthy"; }).length,
      devicesPending: devRows.filter(function (r) { return r.verdict === "pending"; }).length,
      //: THE headline rate: devices that finished every step / devices in scope.
      deviceSuccessRate: devRows.length
        ? Math.round((devRows.filter(function (r) { return r.verdict === "healthy"; }).length /
                      devRows.length) * 1000) / 10
        : 0,
      avgSeconds: avg,
      avgRuntime: humanSeconds(avg)
    };
  }
  R.kpis = kpis;

  // ---- device outcome ----------------------------------------------------
  /** The report's unit of success is the DEVICE, not the step. A fleet where
   *  980 of 1000 steps completed is not "98% healthy" if the 20 that failed are
   *  spread across every device in it -- that fleet has finished nothing. Step
   *  tallies still exist below (they answer "why did THIS device fail"), but
   *  every headline number, the donut and the success rate count devices. */
  var VERDICT = {
    failed:    { label: "Failed",      color: "#f2555a", order: 0 },
    running:   { label: "In progress", color: "#38bdf8", order: 1 },
    pending:   { label: "Queued",      color: "#5b6673", order: 2 },
    // "Complete", not "Upgraded". The verdict is about whether the automation
    // FINISHED, and this report covers runs that never touch firmware.
    exception: { label: "Exceptions",  color: "#f0a63a", order: 3 },
    healthy:   { label: "Complete",    color: "#35c98a", order: 4 },
    // Reachable only from a run group's OWN status field -- a device roll-up
    // has no way to say either of these.
    cancelled: { label: "Cancelled",   color: "#808080", order: 5 },
    unknown:   { label: "Unknown",     color: "#9aa0a6", order: 6 },
    "no-data": { label: "No data",     color: "#6b7280", order: 7 }
  };
  R.VERDICT = VERDICT;
  function verdictColor(v) { return (VERDICT[v] || VERDICT["no-data"]).color; }
  function verdictLabel(v) { return (VERDICT[v] || VERDICT["no-data"]).label; }
  R.verdictColor = verdictColor;
  R.verdictLabel = verdictLabel;

  /** Device-verdict mix, shaped like statusTally so the same donut renders it. */
  function verdictTally(devRows) {
    var t = {};
    (devRows || []).forEach(function (r) {
      var v = r.verdict || "no-data";
      t[v] = (t[v] || 0) + 1;
    });
    return Object.keys(t).map(function (k) {
      return { key: k, label: verdictLabel(k), value: t[k], color: verdictColor(k),
               order: VERDICT[k] ? VERDICT[k].order : 99 };
    }).sort(function (a, b) { return a.order - b.order; });
  }
  R.verdictTally = verdictTally;

  /** The one-sentence answer the report opens with. Ordered by what an analyst
   *  has to act on: a failure outranks progress, progress outranks "all good".
   *  `focus` is the device the headline is about, so a layout can promote it. */
  function headline(devRows) {
    var rows = devRows || [];
    var failed = rows.filter(function (r) { return r.verdict === "failed"; });
    var running = rows.filter(function (r) { return r.verdict === "running"; });
    var pending = rows.filter(function (r) { return r.verdict === "pending"; });
    var healthy = rows.filter(function (r) { return r.verdict === "healthy"; });
    if (!rows.length) {
      return { level: "none", text: "No devices in scope.", detail: "", focus: null };
    }
    if (failed.length) {
      var worst = failed.slice().sort(function (a, b) { return b.failed - a.failed; })[0];
      var f = worst.failures && worst.failures[0];
      return {
        level: "failed",
        text: failed.length + " of " + rows.length + " device" +
              (rows.length === 1 ? "" : "s") + " failed",
        detail: f ? worst.name + " stopped at step " + f.stepNumber + " -- " + f.name : worst.name,
        focus: worst
      };
    }
    if (running.length || pending.length) {
      return {
        level: "running",
        text: (running.length + pending.length) + " of " + rows.length +
              " devices still running",
        detail: healthy.length + " complete, " + running.length + " running, " +
                pending.length + " queued. No failures.",
        focus: running[0] || pending[0]
      };
    }
    // NOTHING failed, nothing moving -- but "all complete" is only true if
    // every device actually ran. A device with no steps in scope has verdict
    // "no-data", and counting it as a success is how this banner came to read
    // "All 18 devices complete" directly above a KPI tile reading 44.4%: 8
    // devices had finished and 10 had never reported a step.
    var nodata = rows.filter(function (r) { return r.verdict === "no-data"; });
    if (nodata.length) {
      return {
        level: healthy.length ? "running" : "none",
        text: healthy.length + " of " + rows.length + " devices complete",
        detail: nodata.length + " device" + (nodata.length === 1 ? " has" : "s have") +
                " no steps in scope -- nothing has been dispatched to " +
                (nodata.length === 1 ? "it" : "them") + ".",
        focus: nodata[0]
      };
    }
    return {
      level: "healthy",
      text: "All " + rows.length + " devices complete",
      detail: "No device has a failed step in scope.",
      focus: null
    };
  }
  R.headline = headline;

  // ---- run-scoped headline + KPIs ---------------------------------------
  /** The Runs layout needs its OWN summary, and this is not a nicety.
   *
   *  The fleet roll-up above the list counts each device ONCE, in its LATEST
   *  run. The list below counts every device in every run it took part in. So
   *  a device that failed on Monday and succeeded on Tuesday is `healthy` in
   *  the fleet roll-up and `failed` in Monday's run -- both true, both useful,
   *  and completely baffling stacked on one screen: the KPI tile read "0
   *  failed" while the Failed chip under it filtered the list down to a run
   *  with two failed devices.
   *
   *  So when the list is about runs, everything above it is about runs too.
   *  The unit here is the DEVICE RUN (a device in one run) -- the same thing
   *  the rows and the chips count, which is the whole point. */
  function runKpis(tree, totalRuns) {
    var rows = tree || [];
    var t = { failed: 0, running: 0, pending: 0, healthy: 0, "no-data": 0 };
    var devices = {}, seen = 0;
    rows.forEach(function (g) {
      (g.deviceRows || []).forEach(function (r) {
        t[r.verdict] = (t[r.verdict] || 0) + 1;
        devices[r.name] = true;
        seen += 1;
      });
    });
    var timed = rows.filter(function (g) { return g.seconds > 0; });
    var avg = timed.length
      ? Math.round(timed.reduce(function (a, g) { return a + g.seconds; }, 0) / timed.length)
      : 0;
    return {
      runs: rows.length,
      runsTotal: totalRuns || rows.length,
      runsFailed: rows.filter(function (g) { return g.verdict === "failed"; }).length,
      runsRunning: rows.filter(function (g) { return g.verdict === "running"; }).length,
      deviceRuns: seen,
      devices: Object.keys(devices).length,
      failed: t.failed, running: t.running, pending: t.pending, healthy: t.healthy,
      noData: t["no-data"],
      successRate: seen ? Math.round((t.healthy / seen) * 1000) / 10 : 0,
      avgSeconds: avg,
      avgRuntime: humanSeconds(avg)
    };
  }
  R.runKpis = runKpis;

  /** One sentence about the runs on screen, in the same precedence the rest of
   *  the widget uses: a failure outranks progress, progress outranks done. */
  function runHeadline(tree, k) {
    var rows = tree || [];
    if (!rows.length) return { level: "none", text: "No runs in scope.", detail: "", focus: null };
    var failedRuns = rows.filter(function (g) { return g.verdict === "failed"; });
    if (failedRuns.length) {
      var worst = failedRuns[0];   // newest first, which is the one to act on
      var d = (worst.deviceRows || []).filter(function (r) { return r.verdict === "failed"; })[0];
      var f = d && d.failures && d.failures[0];
      return {
        level: "failed",
        text: failedRuns.length + " of " + rows.length + " run" +
              (rows.length === 1 ? "" : "s") + " had a device fail",
        detail: f ? d.name + " stopped at step " + f.stepNumber + " -- " + f.name +
                    " (" + worst.name + ")"
                  : k.failed + " device runs failed",
        focus: worst
      };
    }
    var moving = k.running + k.pending;
    if (moving) {
      return {
        level: "running",
        text: moving + " device run" + (moving === 1 ? "" : "s") + " still in flight",
        detail: k.healthy + " complete, " + k.running + " running, " + k.pending +
                " queued, across " + rows.length + " runs. No failures.",
        focus: rows.filter(function (g) { return g.verdict === "running"; })[0] || rows[0]
      };
    }
    return {
      level: "healthy",
      text: "All " + rows.length + " run" + (rows.length === 1 ? "" : "s") + " completed",
      detail: k.deviceRuns + " device run" + (k.deviceRuns === 1 ? "" : "s") +
              " across " + k.devices + " device" + (k.devices === 1 ? "" : "s") +
              ", no failures.",
      focus: null
    };
  }
  R.runHeadline = runHeadline;

  // ---- time range --------------------------------------------------------
  /** The ranges offered above the run list. `days: 0` means no date filter.
   *
   *  A ZTP operator reads this board to see what the last batch did, and a run
   *  from six weeks ago is noise in that question -- but the widget shipped
   *  with no date axis at all, so the list was "the newest N runs" for whatever
   *  N the row limit happened to be, which answers a different question on a
   *  quiet box than on a busy one. */
  var RANGES = [
    { id: "24h", label: "24 hours", days: 1 },
    { id: "48h", label: "48 hours", days: 2 },
    { id: "72h", label: "72 hours", days: 3 },
    { id: "5d",  label: "5 days",   days: 5 },
    { id: "7d",  label: "7 days",   days: 7 },
    { id: "15d", label: "15 days",  days: 15 },
    { id: "30d", label: "30 days",  days: 30 },
    { id: "60d", label: "60 days",  days: 60 },
    { id: "90d", label: "90 days",  days: 90 },
    { id: "all", label: "All time", days: 0 }
  ];
  R.RANGES = RANGES;

  function rangeById(id) {
    for (var i = 0; i < RANGES.length; i++) if (RANGES[i].id === id) return RANGES[i];
    return null;
  }
  R.rangeById = rangeById;

  /** The lower bound of a range as an ISO-8601 string, or "" for all time.
   *
   *  ISO, not epoch, and that is not a style choice: `createDate gte <number>`
   *  is a 500 DriverException from the query API, while the same filter with
   *  an ISO string works. A range filter that 500s would take the whole widget
   *  down, so the encoding is pinned by a test. */
  function rangeStartISO(id, now) {
    var r = rangeById(id);
    if (!r || !r.days) return "";
    var ms = (now ? now.getTime() : Date.now()) - r.days * 86400000;
    return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
  }
  R.rangeStartISO = rangeStartISO;

  function rangeLabel(id) {
    var r = rangeById(id);
    return r ? r.label : "All time";
  }
  R.rangeLabel = rangeLabel;

  function humanSeconds(n) {
    n = Number(n) || 0;
    if (n <= 0) return "--";
    if (n < 60) return n + "s";
    var m = Math.floor(n / 60), s = n % 60;
    if (m < 60) return m + "m" + (s ? " " + s + "s" : "");
    var h = Math.floor(m / 60);
    return h + "h " + (m % 60) + "m";
  }
  R.humanSeconds = humanSeconds;

  // ---- charts (geometry only; the template renders the SVG) --------------
  /** Status tally across the supplied steps, ordered by the picklist's own
   *  order index so the legend reads New -> Cancelled every time. */
  function statusTally(steps) {
    var t = {};
    (steps || []).forEach(function (s) {
      var v = stepStatus(s) || "Unknown";
      t[v] = (t[v] || 0) + 1;
    });
    return Object.keys(t).map(function (k) {
      return { label: k, value: t[k], color: statusColor(k),
               order: (R.STATUS[k] && R.STATUS[k].order != null) ? R.STATUS[k].order : 99 };
    }).sort(function (a, b) { return a.order - b.order; });
  }
  R.statusTally = statusTally;

  /** Donut arcs as SVG path `d` strings. Hand-rolled rather than pulled from a
   *  chart library: FortiSOAR serves widgets under a CSP that blocks CDN
   *  scripts, and a vendored chart bundle would dwarf this whole widget. */
  function donut(slices, opts) {
    opts = opts || {};
    var cx = opts.cx || 90, cy = opts.cy || 90;
    var r = opts.r || 78, inner = opts.inner != null ? opts.inner : 48;
    var total = slices.reduce(function (a, s) { return a + s.value; }, 0);
    if (!total) return { total: 0, arcs: [], cx: cx, cy: cy, r: r, inner: inner };
    var angle = -Math.PI / 2, arcs = [];
    slices.forEach(function (s) {
      var frac = s.value / total;
      // A single slice covering the whole circle cannot be drawn as one arc --
      // start and end land on the same point and the path collapses to nothing.
      // One full-circle status is the COMMON case here (everything Complete),
      // so this is the branch that matters, not an edge case.
      if (frac >= 0.999999) {
        arcs.push({ label: s.label, value: s.value, color: s.color, percent: 100,
                    full: true, d: fullRing(cx, cy, r, inner) });
        angle += Math.PI * 2;
        return;
      }
      var a0 = angle, a1 = angle + frac * Math.PI * 2;
      arcs.push({
        label: s.label, value: s.value, color: s.color,
        percent: Math.round(frac * 1000) / 10, full: false,
        d: ringSegment(cx, cy, r, inner, a0, a1)
      });
      angle = a1;
    });
    return { total: total, arcs: arcs, cx: cx, cy: cy, r: r, inner: inner };
  }
  R.donut = donut;

  function ptOn(cx, cy, r, a) {
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }
  function ringSegment(cx, cy, r, inner, a0, a1) {
    var large = (a1 - a0) > Math.PI ? 1 : 0;
    var o0 = ptOn(cx, cy, r, a0), o1 = ptOn(cx, cy, r, a1);
    var i1 = ptOn(cx, cy, inner, a1), i0 = ptOn(cx, cy, inner, a0);
    return "M" + f(o0) + " A" + r + "," + r + " 0 " + large + ",1 " + f(o1) +
           " L" + f(i1) + " A" + inner + "," + inner + " 0 " + large + ",0 " + f(i0) + " Z";
  }
  function fullRing(cx, cy, r, inner) {
    // Two half-arcs out and two back: the only way to close a complete annulus
    // in one path.
    return "M" + (cx - r) + "," + cy +
           " A" + r + "," + r + " 0 1,1 " + (cx + r) + "," + cy +
           " A" + r + "," + r + " 0 1,1 " + (cx - r) + "," + cy + " Z" +
           " M" + (cx - inner) + "," + cy +
           " A" + inner + "," + inner + " 0 1,0 " + (cx + inner) + "," + cy +
           " A" + inner + "," + inner + " 0 1,0 " + (cx - inner) + "," + cy + " Z";
  }
  function f(p) { return (Math.round(p[0] * 100) / 100) + "," + (Math.round(p[1] * 100) / 100); }

  /** Per-device stacked bar: complete / running / pending / failed, as
   *  percentages so devices with different step counts stay comparable. */
  function deviceBars(devRows) {
    return devRows.map(function (r) {
      var t = r.total || 1;
      return {
        name: r.name, total: r.total, failed: r.failed, verdict: r.verdict,
        segments: [
          // Deliberately the VERDICT palette, not the raw picklist colors. The
          // ZTP picklist ships pure #ff0000 for Fail and a magenta Queued, so a
          // bar of mostly-queued steps screamed as loudly as a failing one.
          // Here colour means one thing: red = act, blue = moving, grey =
          // waiting, green = done.
          { key: "complete", value: r.complete,  pct: r.complete / t * 100,  color: verdictColor("healthy") },
          { key: "running",  value: r.running_,  pct: r.running_ / t * 100,  color: verdictColor("running") },
          { key: "pending",  value: r.pending,   pct: r.pending / t * 100,   color: verdictColor("pending") },
          { key: "failed",   value: r.failed,    pct: r.failed / t * 100,    color: verdictColor("failed") }
        ].filter(function (s) { return s.value > 0; })
      };
    });
  }
  R.deviceBars = deviceBars;

  /** Completion percentage over the most recent run groups, oldest to newest,
   *  as a sparkline polyline plus the points for hover targets. */
  function completionTrend(groupRows, opts) {
    opts = opts || {};
    var w = opts.width || 520, h = opts.height || 90, pad = 6, take = opts.take || 24;
    var rows = groupRows.slice(0, take).slice().reverse();
    if (!rows.length) return { points: [], line: "", area: "", width: w, height: h };
    var n = rows.length;
    var pts = rows.map(function (g, i) {
      var x = n === 1 ? w / 2 : pad + (i * (w - pad * 2)) / (n - 1);
      var y = h - pad - (Math.max(0, Math.min(100, g.percent)) / 100) * (h - pad * 2);
      return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10,
               name: g.name, percent: g.percent, failed: g.failed };
    });
    var line = pts.map(function (p) { return p.x + "," + p.y; }).join(" ");
    var area = "M" + pts[0].x + "," + (h - pad) + " L" + line.split(" ").join(" L") +
               " L" + pts[pts.length - 1].x + "," + (h - pad) + " Z";
    return { points: pts, line: line, area: area, width: w, height: h };
  }
  R.completionTrend = completionTrend;

  /** Step counts over time, one series per status, for the Charts layout's
   *  line chart.
   *
   *  Bucketed on each STEP's own create time (`f.when`, from the `createDate`
   *  groupby in FACT_AGGREGATES), not the run group's start -- a run that
   *  dispatches steps over several hours (or one still in flight) used to
   *  attribute all of them to the single moment the run began, which drew a
   *  spike where the box actually saw a spread.
   *
   *  `hourly` selects the bucket width: true for the hour-scoped ranges
   *  (24h/48h/72h), false for day-scoped ones and All time -- see
   *  R.isHourlyRange, which the caller uses to decide it from `range`. */
  // "Exceptions" is deliberately absent: it is the OUTPUT-clean axis
  // (outputStatus), not a step STATUS (queueStatus) -- see the note on
  // stepFacts about the two picklists disagreeing on purpose. A step can be
  // Complete and still carry an exception, so plotting it as a fifth status
  // would double-count that step against a status line it also belongs to.
  var LINE_SERIES_DEFS = [
    { key: "complete",   label: "Complete",   color: verdictColor("healthy") },
    { key: "running",    label: "Running",    color: verdictColor("running") },
    { key: "pending",    label: "Queued",     color: verdictColor("pending") },
    { key: "failed",     label: "Failed",     color: verdictColor("failed") }
  ];
  R.LINE_SERIES_DEFS = LINE_SERIES_DEFS;

  /** 24h/48h/72h read as one hour of granularity; everything else (a day
   *  count in the dozens, or the whole box) reads by day -- an hourly bucket
   *  over 90 days is 2160 empty points. */
  function isHourlyRange(rangeId) {
    var r = rangeById(rangeId);
    return !!(r && r.days > 0 && r.days <= 3);
  }
  R.isHourlyRange = isHourlyRange;

  /** Bucket-key formatter for the x-axis: "9/18 3p" for an hourly bucket,
   *  "9/18" for a daily one -- c3's own category axis draws whichever of
   *  these labels fit without the widget having to thin them itself.
   *
   *  The hourly label ALWAYS carries the date, not just the hour. A 48h/72h
   *  window spans more than one calendar day, so "3p" alone repeats once a
   *  day -- c3's category axis is keyed by the label string, so two distinct
   *  buckets sharing a label collapse onto one tick and their tooltips read
   *  as duplicate entries for the same status. Carrying the date makes every
   *  label unique across the whole span, which is what the axis and the
   *  tooltip both actually need. */
  function bucketLabel(t, hourly) {
    var d = new Date(t * 1000);
    var day = (d.getMonth() + 1) + "/" + d.getDate();
    if (hourly) {
      var h24 = d.getHours(), h12 = h24 % 12 || 12;
      return day + " " + h12 + (h24 < 12 ? "a" : "p");
    }
    return day;
  }

  /** The epoch second a bucket containing `t` STARTS at, aligned to the
   *  browser's own LOCAL calendar day/hour -- never to a fixed 86400/3600s
   *  stride off the raw epoch. `Math.floor(t / 86400) * 86400` looks like an
   *  obvious "start of day", but it is the start of the UTC day, and epoch
   *  day boundaries only line up with LOCAL midnight in UTC itself. In any
   *  other zone (US Central, UTC-5, found this live) a "daily" bucket ran
   *  7pm-to-7pm local instead of midnight-to-midnight -- a run dispatched at
   *  3:40pm on the 17th landed in the bucket labelled "9/16", because that
   *  bucket's fixed-width span covered 7pm on the 16th through 7pm on the
   *  17th. Building the boundary from the LOCAL Date fields instead makes it
   *  agree with what a person actually calls "today". */
  function bucketStart(t, hourly) {
    var d = new Date(t * 1000);
    if (hourly) d.setMinutes(0, 0, 0); else d.setHours(0, 0, 0, 0);
    return Math.floor(d.getTime() / 1000);
  }
  R.bucketStart = bucketStart;

  /** The next bucket boundary after `startSec`, stepping by CALENDAR unit
   *  (next hour / next day) rather than a fixed 3600/86400 -- a fixed stride
   *  drifts across a DST change (a local "day" is 23 or 25 hours twice a
   *  year), and `setHours`/`setDate` land on the right wall-clock instant on
   *  either side of one. */
  function bucketNext(startSec, hourly) {
    var d = new Date(startSec * 1000);
    if (hourly) d.setHours(d.getHours() + 1); else d.setDate(d.getDate() + 1);
    return Math.floor(d.getTime() / 1000);
  }
  R.bucketNext = bucketNext;

  /** The full, CONTIGUOUS bucket span the axis is meant to cover -- not just
   *  the buckets that happen to have data. A fixed range (24h, 7d, ...) spans
   *  exactly "range ago" through now, zero-filled where nothing happened, so
   *  a quiet stretch draws as a flat line at 0 rather than skipping straight
   *  past it and silently compressing the timeline. All Time has no "ago" to
   *  start from, so it starts at the EARLIEST bucket that actually has a
   *  count -- an arbitrarily old fixed start would draw years of empty axis
   *  for a box that has only ever run for a week. */
  function bucketSpan(hourly, rangeDays, now, earliestData, latestData, customStart, customEnd) {
    var end = bucketStart(now, hourly);
    var start;
    // A CUSTOM date range is a fixed window the operator picked, not a
    // relative "N days ago" nor the data's own extent -- it has to span
    // exactly what was asked for, zero-filled the same way a preset range is,
    // so a quiet stretch inside the picked window still draws as a flat line
    // rather than vanishing from the axis.
    if (customStart != null && customEnd != null) {
      start = bucketStart(customStart, hourly);
      end = bucketStart(customEnd, hourly);
    } else if (rangeDays > 0) {
      var d = new Date(end * 1000);
      if (hourly) d.setHours(d.getHours() - (rangeDays * 24 - 1));
      else d.setDate(d.getDate() - (rangeDays - 1));
      start = Math.floor(d.getTime() / 1000);
    } else if (earliestData != null) {
      start = bucketStart(earliestData, hourly);
      end = Math.max(end, bucketStart(latestData || now, hourly));
    } else {
      return [];
    }
    var keys = [];
    for (var t = start; t <= end; t = bucketNext(t, hourly)) keys.push(t);
    return keys;
  }
  R.bucketSpan = bucketSpan;

  // Same canonical-status -> series-key mapping R.withFacts uses for the
  // progress tally (see its comment on why PENDING and the unknown bucket
  // are handled the way they are) -- kept in one place so the chart and the
  // KPI tiles can never disagree on what "Running" counts as.
  function lineSeriesKey(status) {
    if (status === "Complete") return "complete";
    if (status === "Fail") return "failed";
    if (status === "Running") return "running";
    if (PENDING[status]) return "pending";
    return null;
  }

  /** Same zero-filled, per-step bucketing R.lineSeries used to do its own
   *  SVG math from -- now shaped as c3 wants it: one `categories` label per
   *  bucket and one `columns` entry per status, c3's own id/name for that
   *  series column being the series LABEL (c3 keys a line/legend/tooltip by
   *  the first cell of its column, not by an separate id field). */
  function lineChartData(facts, opts) {
    opts = opts || {};
    var hourly = !!opts.hourly;
    var now = opts.now || Math.floor(Date.now() / 1000);
    var raw = {}, earliest = null, latest = null;
    (facts || []).forEach(function (f) {
      var t = Number(f.when) || 0;
      if (!t) return;
      var key = lineSeriesKey(f.status);
      if (!key) return;
      var t0 = bucketStart(t, hourly);
      if (earliest == null || t0 < earliest) earliest = t0;
      if (latest == null || t0 > latest) latest = t0;
      var b = raw[t0];
      if (!b) {
        b = { t: t0 };
        LINE_SERIES_DEFS.forEach(function (d) { b[d.key] = 0; });
        raw[t0] = b;
      }
      b[key] += f.steps || 0;
    });
    var keys = bucketSpan(hourly, opts.rangeDays || 0, now, earliest, latest,
                          opts.rangeStart, opts.rangeEnd);
    if (!keys.length) {
      return { hourly: hourly, categories: [], columns: [], colors: {}, totals: {},
               bucketStarts: [], bucketEnds: [], seriesLabels: [] };
    }
    var rows = keys.map(function (k) {
      if (raw[k]) return raw[k];
      var b = { t: k };
      LINE_SERIES_DEFS.forEach(function (d) { b[d.key] = 0; });
      return b;
    });
    var categories = rows.map(function (b) { return bucketLabel(b.t, hourly); });
    var columns = LINE_SERIES_DEFS.map(function (d) {
      return [d.label].concat(rows.map(function (b) { return b[d.key]; }));
    });
    var colors = {}, totals = {};
    LINE_SERIES_DEFS.forEach(function (d) {
      colors[d.label] = d.color;
      totals[d.label] = rows.reduce(function (a, b) { return a + b[d.key]; }, 0);
    });
    // The epoch second each bucket STARTS (and ends) at, same order as
    // categories/columns. Click-to-filter needs this: the display label
    // ("9/18 3p") is lossy and does not roundtrip to an exact epoch (it drops
    // the year, and a label alone can't recover which side of a DST change a
    // bucket falls on), so a click handler reads the bucket's span straight
    // from here instead of re-parsing what's on screen. `bucketEnds` is its
    // own array rather than "start + a fixed width": a calendar day is 23 or
    // 25 hours on a DST change, so the width isn't fixed either.
    var bucketStarts = rows.map(function (b) { return b.t; });
    var bucketEnds = bucketStarts.map(function (t) { return bucketNext(t, hourly); });
    return {
      hourly: hourly, categories: categories, columns: columns, colors: colors,
      totals: totals, bucketStarts: bucketStarts, bucketEnds: bucketEnds,
      seriesLabels: LINE_SERIES_DEFS.map(function (d) { return d.label; })
    };
  }
  R.lineChartData = lineChartData;

  // A small, stable palette for facets that carry no picklist colour of their
  // own (run group, device, action, trigger, tag) -- statuses keep using
  // R.STATUS's actual colours instead of this. Cycled by index, not hashed by
  // name: a hash can collide two adjacent slices onto the same colour, and a
  // pie chart where neighbours are indistinguishable is the one chart that
  // cannot afford that.
  var FACET_PALETTE = ["#2aa8c9", "#f0a63a", "#35c98a", "#f2555a", "#8b7cf6",
    "#38bdf8", "#e9578c", "#b1ae06", "#5b6673", "#0e12f6"];
  R.FACET_PALETTE = FACET_PALETTE;

  /** A facet's vocabulary (already counted in STEPS by R.chartFacetVocab) as
   *  a c3 donut's `data.columns` + `data.colors` -- c3 draws its own arcs,
   *  hole title and legend from this, so this function only has to shape
   *  the numbers, not the geometry R.facetDonut used to compute by hand.
   *  Status keeps its own picklist colour; everything else cycles the
   *  neutral palette above, same as before. */
  function facetPieData(axis, vocabRows) {
    var columns = [], colors = {}, total = 0;
    (vocabRows || []).forEach(function (v, i) {
      columns.push([v.name, v.count]);
      colors[v.name] = axis === "status" ? statusColor(v.name) : FACET_PALETTE[i % FACET_PALETTE.length];
      total += v.count;
    });
    return { columns: columns, colors: colors, total: total };
  }
  R.facetPieData = facetPieData;

  // ---- filtering ---------------------------------------------------------
  /** Free-text + verdict filter over device rows. The search matches anything
   *  a reader can see on the row, including the text of its failures, so
   *  typing a step name finds the devices it broke on. */
  function filterDevices(rows, query, verdicts) {
    var q = (query || "").trim().toLowerCase();
    var want = verdicts && Object.keys(verdicts).filter(function (k) { return verdicts[k]; });
    return rows.filter(function (r) {
      if (want && want.length && want.indexOf(r.verdict) === -1) return false;
      if (!q) return true;
      var hay = [r.name, r.managementIP, r.platform, r.firmware, r.adom, r.manager,
                 r.connectionStatus, r.shownGroup, r.verdict]
        .concat(r.failures.map(function (x) { return x.name + " " + x.message + " " + x.triggerKey; }))
        .join(" ").toLowerCase();
      return hay.indexOf(q) !== -1;
    });
  }
  R.filterDevices = filterDevices;

  // ---- CSV ---------------------------------------------------------------
  /** RFC4180 quoting. A step's outputStatusMessage routinely contains commas
   *  and newlines, and a naive join turns one failure into three broken rows. */
  function csvCell(v) {
    if (v == null) return "";
    var s = String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  R.csvCell = csvCell;

  function toCsv(headers, rows) {
    var out = [headers.map(csvCell).join(",")];
    rows.forEach(function (r) { out.push(r.map(csvCell).join(",")); });
    // CRLF: Excel on Windows treats a bare LF file as one long line.
    return out.join("\r\n") + "\r\n";
  }
  R.toCsv = toCsv;

  R.csvDevices = function (rows) {
    return toCsv(
      ["Device", "Management IP", "Platform", "Firmware", "ADOM", "Manager",
       "Connection", "Config", "Run group", "Verdict", "Steps", "Complete",
       "Failed", "Pending", "Running", "Success rate %", "Duration"],
      rows.map(function (r) {
        return [r.name, r.managementIP, r.platform, r.firmware, r.adom, r.manager,
                r.connectionStatus, r.configStatus, r.shownGroup, r.verdict,
                r.total, r.complete, r.failed, r.pending, r.running_,
                r.successRate, humanSeconds(r.seconds)];
      }));
  };

  R.csvFailures = function (rows) {
    var fails = [];
    rows.forEach(function (r) { fails = fails.concat(r.failures); });
    return toCsv(
      ["Device", "Run group", "Step #", "Step name", "Trigger", "Message", "When"],
      fails.map(function (f) {
        return [f.device, f.group, f.stepNumber, f.name, f.triggerKey, f.message,
                f.when ? new Date(f.when * 1000).toISOString() : ""];
      }));
  };

  R.csvRunGroups = function (rows) {
    return toCsv(
      ["Run group", "Created", "Devices", "Steps", "Complete", "Complete %",
       "Failed", "Runtime", "Running", "Device names"],
      rows.map(function (g) {
        return [g.name, g.createDate ? new Date(g.createDate * 1000).toISOString() : "",
                g.totalDevices, g.totalSteps, g.complete, g.percent, g.failed,
                g.runtime, g.running ? "yes" : "no", g.devices.join(" ")];
      }));
  };


  // ======================================================================
  // THE FACET MODEL
  // ======================================================================
  /* What this report is actually about.
   *
   *  The widget shipped as a FIRMWARE UPGRADE report: it counted "devices
   *  upgraded", and a device that finished every step it was given read as
   *  upgraded whether or not an upgrade was any part of the run. That is a
   *  guess about the content of the automation, and it is wrong as soon as a
   *  run does pre-checks, config diffs, or an HA identity sweep -- which is
   *  most of them.
   *
   *  The vocabulary this module now speaks is the one the DATA speaks:
   *
   *    run group  -- the batch someone dispatched         (ztpf_run_groups)
   *    device     -- what it ran against                  (ztpfDevices)
   *    step       -- one numbered thing in that run       (name, stepNumber)
   *    action     -- the automation behind the step       (ztpfAutomationActions)
   *    status     -- how the step ended                   (queueStatus)
   *    exception  -- whether the step's OUTPUT was clean  (outputStatus)
   *
   *  "Action" is the axis that makes this generic. Whatever the automation
   *  does -- upgrade, collect, diff, roll back, anything added next year --
   *  it arrives as a named action on a step, and every roll-up below counts
   *  it without knowing what it means.
   *
   *  `exception` deserves a note because two status-shaped fields on one
   *  record is confusing: `queueStatus` says whether the step RAN (Complete /
   *  Fail / Cancelled / Queued / Running), and `outputStatus` says whether
   *  what it produced was clean ("OK" / "Exceptions Found"). A step can be
   *  Complete and still have found exceptions -- a config diff that ran
   *  perfectly and reported drift -- and collapsing the two loses exactly the
   *  finding the run was dispatched to make.
   */

  // A facet value the record did not carry. Rendered as a chip like any other,
  // because "which steps have no action attached" is a real question and an
  // absent chip silently drops those rows out of every count.
  var NO_VALUE = "(none)";
  R.NO_VALUE = NO_VALUE;

  function facetValue(v) {
    var s = (v == null || v === "") ? "" : String(v);
    return s || NO_VALUE;
  }
  R.facetValue = facetValue;

  /** Normalise the step aggregate into FACTS: one row per distinct
   *  (run, device, action, status, exception) with a step count and a time.
   *
   *  This is the whole filter substrate, and it is one query. A `groupby` on a
   *  relation returns the related record's NAME as a scalar, which
   *  `__selectFields` cannot do at any price -- projecting `ztpfDevices` drags
   *  the manager's entire sourceData dump along with it, which is how the
   *  unprojected step collection reached 14 MB and froze the tab. The same
   *  fleet as facts is a few hundred small rows. */
  /** HOW LONG A STEP TOOK, as an axis.
   *
   *  Duration is the one interesting property of a step that is a NUMBER, and
   *  a number cannot be a chip: there is no vocabulary of 431-second steps to
   *  offer. So it is bucketed, and the buckets are the ones an operator
   *  already thinks in -- "under a minute" is the routine CLI read, "ten
   *  minutes and up" is a firmware push. Fixed edges rather than quantiles:
   *  a quantile bucket renames itself every time the window changes, so the
   *  same chip would select a different thing on Monday than on Friday.
   *
   *  The ORDER is the bucket order, never the count order every other axis
   *  uses. A scale drawn out of sequence is not a scale. */
  var DURATIONS = [
    { name: "< 1 min",  min: 0,   max: 60 },
    { name: "1-3 min",  min: 60,  max: 180 },
    { name: "3-5 min",  min: 180, max: 300 },
    { name: "5-10 min", min: 300, max: 600 },
    { name: "10+ min",  min: 600, max: Infinity }
  ];
  R.DURATIONS = DURATIONS;
  var DURATION_ORDER = {};
  DURATIONS.forEach(function (b, i) { DURATION_ORDER[b.name] = i; });

  /** The bucket a step's clock falls in. A step with no recorded time is not
   *  "under a minute" -- it is unmeasured, and saying otherwise would file
   *  every queued step into the fastest bucket and make that chip a lie. */
  function durationBucket(secs) {
    var n = Number(secs);
    if (!isFinite(n) || n <= 0) return NO_VALUE;
    for (var i = 0; i < DURATIONS.length; i++) {
      if (n < DURATIONS[i].max) return DURATIONS[i].name;
    }
    return DURATIONS[DURATIONS.length - 1].name;
  }
  R.durationBucket = durationBucket;

  /** Normalise the step aggregate into FACTS: one row per distinct
   *  (run, device, action, status, exception, duration) with a step count and
   *  a time.
   *
   *  This is the whole filter substrate, and it is one query. A `groupby` on a
   *  relation returns the related record's NAME as a scalar, which
   *  `__selectFields` cannot do at any price -- projecting `ztpfDevices` drags
   *  the manager's entire sourceData dump along with it, which is how the
   *  unprojected step collection reached 14 MB and froze the tab. The same
   *  fleet as facts is a few hundred small rows. */
  /** `groupStatusIndex`/`deviceStatusIndex` are name -> status lookups built
   *  from the run-group and device records already fetched for other reasons
   *  (see runGroupRowsFromAggregate's `status`, and ztpf_devices'
   *  `connectionStatus`). They ride in here rather than being derived from the
   *  step aggregate itself because the step cube has no idea what the GROUP or
   *  the DEVICE it belongs to is currently reading as -- only what the step
   *  did. */
  function stepFacts(aggRows, groupStatusIndex, deviceStatusIndex) {
    var gIdx = groupStatusIndex || {}, dIdx = deviceStatusIndex || {};
    return (aggRows || []).map(function (r) {
      var grp = facetValue(r && r.grp);
      var device = facetValue(r && r.device);
      return {
        group: grp,
        device: device,
        action: facetValue(r && r.action),
        // The run group's / device's OWN status, at the moment this window was
        // read -- distinct from `status` below, which is the STEP's outcome.
        // A run can be "Complete" while one of its steps still reads "Queued"
        // (a step the automation staged but never actually dispatched), so
        // these two axes disagree on purpose.
        groupStatus: facetValue(gIdx[grp]),
        deviceStatus: facetValue(dIdx[device]),
        // The TRIGGER KEY -- what KIND of automation the step was, as opposed
        // to which named action it belonged to. One action is a sequence of
        // steps of several kinds, so this is the axis that answers "show me
        // every firmware push" across the actions that merely contain one.
        trigger: facetValue(r && r.trigger),
        status: facetValue(resolveStatus(r && r.status, r && r.queueStatus)),
        exception: facetValue(r && r.exception),
        // The record's own finished flag, grouped alongside the rest so
        // "how many steps are still in flight" is a sum over the cube rather
        // than an inference from a status vocabulary that lies about it.
        done: !!(r && r.done),
        // How long ONE step of this fact took. The cube groups BY the clock
        // column rather than summing it, so every row here is a set of steps
        // that all took the same time -- which is the only shape a duration
        // bucket can be read out of. Summing first could say "these 9 steps
        // took 40 minutes" and never say whether that was one long one.
        duration: durationBucket(r && r.secs),
        steps: Number(r && r.n) || 0,
        seconds: (Number(r && r.secs) || 0) * (Number(r && r.n) || 0),
        // This step's own create time -- see R.stepTimeSeries, which buckets
        // on it directly rather than on the run group's start.
        when: Number(r && r.when) || 0
      };
    }).filter(function (f) { return f.group !== NO_VALUE; });
  }
  R.stepFacts = stepFacts;

  // The step-level axes, in the order the filter panel stacks them. Group name
  // and tag are group-level and handled separately -- a run either carries the
  // tag or it does not, there is no "some of its steps do".
  var STEP_FACETS = ["device", "action", "trigger", "status", "exception", "duration",
                     "groupStatus", "deviceStatus"];
  R.STEP_FACETS = STEP_FACETS;

  /** Hang each run's own facts off it, plus the distinct values it contains.
   *  Precomputed because the filter runs on every keystroke and the template
   *  must never build an array in an expression (see groupBar for what that
   *  costs). */
  function attachFacts(tree, facts) {
    var byGroup = {};
    (facts || []).forEach(function (f) {
      (byGroup[f.group] = byGroup[f.group] || []).push(f);
    });
    return (tree || []).map(function (g) {
      var mine = byGroup[g.name] || [];
      var out = shallow({}, g);
      out.facts = mine;
      STEP_FACETS.forEach(function (axis) {
        var seen = {};
        mine.forEach(function (f) { seen[f[axis]] = true; });
        out[axis + "s"] = Object.keys(seen).sort();
      });
      out.stepsSeen = mine.reduce(function (a, f) { return a + f.steps; }, 0);
      // The run's OWN tags -- the wave it was dispatched as. Split out under
      // the name the run row draws, and left as the only tag set here: the
      // fact cube knows a run's devices by NAME and nothing else, so there is
      // no honest way to attribute a device's own tags to a run from it. A
      // dashed "device tag" chip sourced from a different query would be
      // drawing one module's tags on another module's row.
      out.ownTags = (g.tags && g.tags.length) ? g.tags : tagList(g);
      out.deviceTags = [];
      out.tags = out.ownTags;
      return out;
    });
  }
  R.attachFacts = attachFacts;

  /** The chips to offer, counted in STEPS -- the same unit the pie charts
   *  already use. A run-counted chip and a step-counted pie reading the same
   *  window used to disagree on purpose ("Upgrade Firmware (4)" above a pie
   *  slice reading 96), which read as the two disagreeing about the fleet
   *  rather than answering two different questions on purpose. Steps
   *  everywhere is the one reading an operator does not have to reconcile.
   *
   *  Everything here is derived from the run groups IN THE CURRENT TIME SCALE
   *  and nothing else. A chip that selects nothing is worse than an absent
   *  chip, and a vocabulary read from the whole box would be full of them. */
  function facetVocab(tree) {
    var out = { group: {}, tag: {}, device: {}, action: {}, trigger: {},
                status: {}, exception: {}, duration: {}, groupStatus: {}, deviceStatus: {} };
    (tree || []).forEach(function (g) {
      var mine = g.facts || [];
      var n = mine.reduce(function (a, f) { return a + f.steps; }, 0);
      out.group[g.name] = (out.group[g.name] || 0) + n;
      (g.tags || []).forEach(function (t) { out.tag[t] = (out.tag[t] || 0) + n; });
      mine.forEach(function (f) {
        STEP_FACETS.forEach(function (axis) {
          out[axis][f[axis]] = (out[axis][f[axis]] || 0) + f.steps;
        });
      });
    });
    var vocab = {};
    Object.keys(out).forEach(function (axis) {
      var cmp = axis === "group" ? byNameDesc : axis === "duration" ? byDurationOrder : byCountThenName;
      vocab[axis] = Object.keys(out[axis]).map(function (name) {
        return { name: name, count: out[axis][name] };
      }).sort(cmp);
    });
    return vocab;
  }
  R.facetVocab = facetVocab;

  /** Same shape as facetVocab, but counted in STEPS rather than in run
   *  groups -- what a chart slice needs ("how many steps") instead of what a
   *  filter chip needs ("how many rows would this select"). facetVocab's own
   *  run-count is right for a chip: a chip reading 12 has to select 12 rows.
   *  It is wrong for a pie, where a run group with one exception among forty
   *  clean steps would put "Exceptions Found" at parity with "OK".
   *
   *  group/tag are summed off each run's own filtered step total
   *  (g.steps.total, from R.withFacts) since every step belongs to exactly
   *  one run group. The STEP_FACETS axes are summed directly off each
   *  surviving fact's own step count. Both read `factsView` -- the facts a
   *  filter already narrowed to -- so a pie drawn while chips are active
   *  describes the same slice of the cube the rest of the page does. */
  function chartFacetVocab(tree) {
    var out = { group: {}, tag: {}, device: {}, action: {}, trigger: {},
                status: {}, exception: {}, duration: {}, groupStatus: {}, deviceStatus: {} };
    (tree || []).forEach(function (g) {
      var n = (g.steps && g.steps.total) || 0;
      out.group[g.name] = (out.group[g.name] || 0) + n;
      (g.tags || []).forEach(function (t) { out.tag[t] = (out.tag[t] || 0) + n; });
      (g.factsView || g.facts || []).forEach(function (f) {
        STEP_FACETS.forEach(function (axis) {
          out[axis][f[axis]] = (out[axis][f[axis]] || 0) + f.steps;
        });
      });
    });
    var vocab = {};
    Object.keys(out).forEach(function (axis) {
      var cmp = axis === "duration" ? byDurationOrder : byCountThenName;
      vocab[axis] = Object.keys(out[axis]).map(function (name) {
        return { name: name, count: out[axis][name] };
      }).filter(function (v) { return v.name !== NO_VALUE && v.count > 0; }).sort(cmp);
    });
    return vocab;
  }
  R.chartFacetVocab = chartFacetVocab;

  // Run names carry their dispatch time (ztpf-<epoch>-<id>), so newest-first
  // is what a reverse name sort gives, and it matches the list underneath.
  function byNameDesc(a, b) { return b.name.localeCompare(a.name); }
  // Fixed bucket order (<1m .. 10m+), not by count -- a duration axis reads
  // as a scale, and a scale that reshuffles itself by whichever bucket is
  // biggest this window is illegible.
  function byDurationOrder(a, b) {
    return (DURATION_ORDER[a.name] || 0) - (DURATION_ORDER[b.name] || 0);
  }
  function byCountThenName(a, b) {
    return (b.count - a.count) ||
           a.name.toLowerCase().localeCompare(b.name.toLowerCase());
  }

  /** The truthy keys of a `{value: bool}` selection map. */
  function chosen(map) {
    var out = [];
    Object.keys(map || {}).forEach(function (k) { if (map[k]) out.push(k); });
    return out;
  }
  R.chosen = chosen;

  function factHaystack(f) {
    return (f.device + " " + f.action + " " + f.trigger + " " + f.status + " " +
            f.exception + " " + f.duration).toLowerCase();
  }

  /** Narrow the run list.
   *
   *  OR within an axis, AND across axes. Ticking two devices asks for either
   *  of them -- that is what a row of chips reads as -- while ticking a device
   *  AND an action asks for that device doing that action, which is the only
   *  reading under which the two chips together are more specific than one.
   *
   *  A run SURVIVES when at least one of its steps satisfies every active
   *  step-level axis AT ONCE. Testing the axes independently against the run
   *  would keep a run that merely contains the device somewhere and the action
   *  somewhere else, and then the step list under it would be empty -- a row
   *  that matches nothing you asked for.
   *
   *  The survivor is a COPY carrying `factsView`: the facts that actually
   *  matched. Everything above the list -- the summary, the progress bar, the
   *  counts -- is computed from that, which is what makes the numbers describe
   *  what is on screen rather than what was fetched. */
  function filterRunGroups(tree, sel, query) {
    var q = (query || "").trim().toLowerCase();
    var groups = chosen(sel && sel.group);
    var tags = chosen(sel && sel.tag);
    var axes = STEP_FACETS.filter(function (a) { return chosen(sel && sel[a]).length; });
    var want = {};
    axes.forEach(function (a) {
      want[a] = {};
      chosen(sel[a]).forEach(function (v) { want[a][v] = true; });
    });
    var out = [];
    (tree || []).forEach(function (g) {
      if (groups.length && groups.indexOf(g.name) === -1) return;
      if (tags.length && !groupHasTag(g, tags)) return;
      var nameHit = !!q && String(g.name || "").toLowerCase().indexOf(q) !== -1;
      var kept = (g.facts || []).filter(function (f) {
        for (var i = 0; i < axes.length; i++) {
          if (!want[axes[i]][f[axes[i]]]) return false;
        }
        // A text hit on the run NAME keeps the whole run: you asked for the
        // run, so you get the run, still narrowed by whatever chips are on.
        if (!q || nameHit) return true;
        return factHaystack(f).indexOf(q) !== -1;
      });
      if (kept.length) { out.push(withFacts(g, kept)); return; }
      // A run with no steps yet -- dispatched moments ago, nothing reported --
      // is still a true answer to a name or tag filter, and it must survive an
      // EMPTY filter or the unfiltered list would silently drop it. It is not
      // an answer to a step-level chip, which asks a question about steps this
      // run does not have.
      if (axes.length) return;
      if (!q || nameHit) out.push(withFacts(g, []));
    });
    return out;
  }
  R.filterRunGroups = filterRunGroups;

  function withFacts(g, facts) {
    var c = shallow({}, g);
    c.factsView = facts;
    c.narrowed = facts.length !== (g.facts || []).length;
    // Steps SHOWN, and their outcome mix -- the numbers on the run row.
    var t = { total: 0, complete: 0, failed: 0, running: 0, pending: 0,
              cancelled: 0, exceptions: 0, seconds: 0, unknown: 0,
              done: 0, inFlight: 0, unknownValues: {} };
    var devs = {};
    facts.forEach(function (f) {
      t.total += f.steps;
      t.seconds += f.seconds;
      devs[f.device] = true;
      // IN FLIGHT comes from stepDone and from nothing else. Every status-
      // derived version of this number counted finished steps whose queue row
      // was never reset -- which is the entire reason the summary read
      // "683 steps in flight" over a fleet that had finished.
      if (f.done) t.done += f.steps; else t.inFlight += f.steps;
      // f.status is already canonical -- every producer runs it through
      // resolveStatus -- so PENDING here means genuinely queued, and the
      // final branch means a value no synonym covers. Those get their own
      // bucket rather than joining pending: pending reads as still-running,
      // which is exactly how one unmapped spelling ("Canceled") held finished
      // runs at IN PROGRESS.
      if (f.status === "Complete") t.complete += f.steps;
      else if (f.status === "Fail") t.failed += f.steps;
      else if (f.status === "Running") t.running += f.steps;
      else if (f.status === "Cancelled") t.cancelled += f.steps;
      else if (PENDING[f.status]) t.pending += f.steps;
      else {
        t.unknown += f.steps;
        if (f.status) t.unknownValues[f.status] = (t.unknownValues[f.status] || 0) + f.steps;
      }
      if (f.exception === "Exceptions Found") t.exceptions += f.steps;
    });
    c.steps = t;
    c.deviceNames = Object.keys(devs).sort();
    // THE PROGRESS BAR. Denominator is the run's OWN totalSteps while the view
    // is unnarrowed -- that is the run's declared size, and it counts steps
    // that have not produced a record yet, which a fact-derived total cannot.
    // Once a filter narrows the view the declared total is the wrong
    // denominator: it would draw 6 of 44 for a filter that selected 6 of 6.
    var denom = c.narrowed ? t.total : Math.max(Number(g.totalSteps) || 0, t.total);
    var done = c.narrowed ? t.complete
                          : Math.max(Number(g.complete) || 0, t.complete);
    c.progress = {
      total: denom,
      complete: Math.min(done, denom),
      percent: denom ? Math.round(Math.min(done, denom) / denom * 100) : 0
    };
    c.bar = stepBar(t, denom);
    c.verdict = runVerdict(c);
    return c;
  }
  R.withFacts = withFacts;

  /** The run row's bar, in STEPS. Segments are drawn against the declared
   *  total, so the unfilled tail is the work that has not reported yet --
   *  a bar normalised to what HAS reported always reads 100% and says
   *  nothing. */
  function stepBar(t, denom) {
    var d = denom || t.total || 1;
    return [
      { key: "complete",  value: t.complete,  color: statusColor("Complete") },
      { key: "failed",    value: t.failed,    color: statusColor("Fail") },
      { key: "running",   value: t.running,   color: statusColor("Running") },
      { key: "cancelled", value: t.cancelled, color: statusColor("Cancelled") },
      { key: "pending",   value: t.pending,   color: statusColor("Queued") }
    ].filter(function (s) { return s.value > 0; })
     .map(function (s) { s.pct = s.value / d * 100; return s; });
  }
  R.stepBar = stepBar;

  /** A run's state, from its steps. Failure outranks exceptions, exceptions
   *  outrank progress, progress outranks done -- the precedence the rest of
   *  the widget already uses, one level down. */
  function runVerdict(g) {
    // ztpfRunning WINS OVER EVERYTHING. It is the automation's own live flag,
    // set for the duration of the run and cleared when it's done -- while it's
    // set the group is running regardless of what its status picklist (which
    // can lag, or hold a spelling the verdict table doesn't map) says.
    if (g && g.running) return "running";
    // THE RUN GROUP'S OWN STATUS WINS. It is the outcome the platform decided
    // on for this run, and every other reading here is an inference from the
    // steps underneath it. Inferring was the bug: a group at 5 of 5 steps,
    // 100% complete, badged IN PROGRESS because one step's queue row had
    // never been reset. The group said "Complete" the whole time.
    var own = groupStatusVerdict(g && g.status);
    if (own) return own;
    // No status on the record -- a run the automation has not stamped yet.
    // Fall back to the step roll-up, in the precedence the widget has always
    // used one level down.
    var t = (g && g.steps) || {};
    if (t.failed > 0) return "failed";
    if (t.running > 0 || t.pending > 0) return "running";
    if (t.exceptions > 0) return "exception";
    // Steps whose status no synonym covers are NOT progress. Counting them as
    // running is the bug this whole normalizer exists to stop, so they fall
    // through to the completed reading and surface via t.unknownValues.
    if (t.total > 0) return "healthy";
    return "no-data";
  }
  R.runVerdict = runVerdict;

  /** The summary band, recomputed from the runs ON SCREEN.
   *
   *  Every number here is a sum over `factsView`, which is the filtered slice,
   *  so narrowing to one action changes the summary to be about that action.
   *  A summary that keeps describing the fetch while the list describes the
   *  filter is the defect this widget already shipped once, at the device
   *  level: a "0 failed" tile directly above a chip that had filtered the list
   *  down to a run with two failures. */
  function runSummary(view) {
    var rows = view || [];
    var devs = {}, acts = {}, trigs = {};
    var t = { total: 0, complete: 0, failed: 0, running: 0, pending: 0,
              cancelled: 0, exceptions: 0, seconds: 0, done: 0, inFlight: 0,
              queued: 0, runningNow: 0 };
    var declared = 0, declaredDone = 0, timed = 0, timedSecs = 0;
    // Every fact's own per-step clock, so Step Run Times can report the
    // spread (min/max) and not just the mean -- an average of 40s means
    // something different beside a 5s..3m range than beside a 35s..45s one.
    // This is the STEP's own time, not the run group's wall-clock span: a
    // run can take twenty minutes end to end while every step in it ran in
    // under thirty seconds, if most of that twenty minutes was queued.
    // EXACT, not an average of an average: the fact cube groups BY
    // stepTimeSeconds (see FACT_AGGREGATES), so every fact is a set of steps
    // that all took precisely the same time, and f.seconds / f.steps
    // recovers that one number rather than blending several.
    var runSeconds = [];
    // The RUN GROUP's own wall-clock duration, one entry per timed group --
    // distinct from runSeconds above (a per-STEP clock). A run can take twenty
    // minutes end to end while every step in it ran in under thirty seconds;
    // "Run Group Times" answers "how long did the batch take", "Step Run
    // Times" answers "how long did one step take", and averaging one into the
    // other would blend two different clocks into a number that answers
    // neither question.
    var groupSeconds = [];
    // A run group is DONE when it has reported every step it declared. This
    // reads the two counters the run group record keeps itself -- totalSteps
    // and totalStepsComplete -- rather than asking the step rows, because the
    // declared total counts steps that have not produced a record yet and a
    // roll-up over records cannot see those at all.
    var runsDone = 0, runsInProgress = 0;
    rows.forEach(function (g) {
      var s = g.steps || {};
      ["total", "complete", "failed", "running", "pending", "cancelled",
       "exceptions", "seconds", "done", "inFlight"].forEach(function (k) { t[k] += s[k] || 0; });
      var dTotal = Number(g.totalSteps) || 0;
      var dDone = Number(g.complete) || 0;
      if (dTotal > 0 && dDone >= dTotal) runsDone += 1;
      else if (dTotal > 0) runsInProgress += 1;
      if (g.seconds > 0) groupSeconds.push(g.seconds);
      (g.deviceNames || []).forEach(function (d) { devs[d] = true; });
      (g.factsView || []).forEach(function (f) {
        acts[f.action] = true;
        if (f.trigger && f.trigger !== NO_VALUE) trigs[f.trigger] = true;
        // Counted off the EXACT status value, not off the pending/running
        // buckets beside them. These two numbers are tiles, and a tile
        // selects one chip: if "Steps queued" counted New and Ready as well,
        // clicking it would narrow the list to fewer steps than the tile
        // just claimed -- which is the self-contradicting number this whole
        // band was rebuilt to stop producing.
        if (f.status === "Queued") t.queued += f.steps;
        if (f.status === "Running") t.runningNow += f.steps;
        if (f.steps > 0 && f.seconds > 0) {
          timed += f.steps;
          timedSecs += f.seconds;
          runSeconds.push(f.seconds / f.steps);
        }
      });
      declared += (g.progress && g.progress.total) || 0;
      declaredDone += (g.progress && g.progress.complete) || 0;
    });
    var avg = timed ? Math.round(timedSecs / timed) : 0;
    var minSecs = runSeconds.length ? Math.min.apply(null, runSeconds) : 0;
    var maxSecs = runSeconds.length ? Math.max.apply(null, runSeconds) : 0;
    var avgGroupSecs = groupSeconds.length
      ? Math.round(groupSeconds.reduce(function (a, n) { return a + n; }, 0) / groupSeconds.length)
      : 0;
    var minGroupSecs = groupSeconds.length ? Math.min.apply(null, groupSeconds) : 0;
    var maxGroupSecs = groupSeconds.length ? Math.max.apply(null, groupSeconds) : 0;
    return {
      runs: rows.length,
      runsFailed: rows.filter(function (g) { return g.verdict === "failed"; }).length,
      runsRunning: rows.filter(function (g) { return g.verdict === "running"; }).length,
      devices: Object.keys(devs).length,
      actions: Object.keys(acts).length,
      // Action TYPES -- distinct trigger keys. "12 actions of 4 types" is the
      // shape of a run window; the two numbers answer different questions and
      // collapsing them loses the one about variety.
      triggers: Object.keys(trigs).length,
      steps: t.total,
      // Steps sitting at exactly status=Queued / status=Running -- the two
      // values the new tiles select. See the note in the fold above.
      queued: t.queued,
      runningNow: t.runningNow,
      complete: t.complete,
      failed: t.failed,
      running: t.running,
      pending: t.pending,
      cancelled: t.cancelled,
      exceptions: t.exceptions,
      // Steps the platform has marked finished, and those it has not.
      stepsDone: t.done,
      inFlight: t.inFlight,
      // Run groups by declared progress -- see runsDone above.
      runsDone: runsDone,
      runsInProgress: runsInProgress,
      percent: declared ? Math.round(declaredDone / declared * 100) : 0,
      avgSeconds: avg,
      avgRuntime: humanSeconds(avg),
      minSeconds: minSecs,
      minRuntime: humanSeconds(minSecs),
      maxSeconds: maxSecs,
      maxRuntime: humanSeconds(maxSecs),
      // The run GROUP's own wall-clock -- see groupSeconds above.
      avgGroupSeconds: avgGroupSecs,
      avgGroupRuntime: humanSeconds(avgGroupSecs),
      minGroupSeconds: minGroupSecs,
      minGroupRuntime: humanSeconds(minGroupSecs),
      maxGroupSeconds: maxGroupSecs,
      maxGroupRuntime: humanSeconds(maxGroupSecs)
    };
  }
  R.runSummary = runSummary;

  /** THE HEADLINE. One sentence, and it is about PROBLEMS.
   *
   *  It answers the only question worth putting at 19px: did anything go
   *  wrong, and if so how much of it. Failures and exceptions are named
   *  together because they are different findings -- a step that died and a
   *  step that ran perfectly and reported drift -- and an operator has to
   *  know which of the two they are looking at before anything else on the
   *  page is worth reading.
   *
   *  Everything ELSE the window contains -- how many runs, how many devices,
   *  how new, what was slow -- now belongs to the narrative underneath. The
   *  old second line said "across 2 of 5 runs, newest ztpf-...", which is
   *  exactly the kind of thing the narrative says better and in words.
   *
   *  The level drives the colour of the whole band: a failure makes it red,
   *  exceptions alone make it amber. Nothing else changes it, because
   *  "something is in flight" is not a problem and must not look like one.
   */
  function runVerdictLine(view, s) {
    var rows = view || [];
    var t = s || {};
    if (!rows.length) return { level: "none", text: "No runs match." };
    var failed = t.failed || 0;
    var exc = t.exceptions || 0;
    function steps(n) { return n + " step" + (n === 1 ? "" : "s"); }
    if (failed && exc) {
      return { level: "failed",
               text: steps(failed) + " failed, " + exc + " with exceptions" };
    }
    if (failed) {
      return { level: "failed", text: steps(failed) + " failed, no exceptions" };
    }
    if (exc) {
      return { level: "exception",
               text: steps(exc) + " with exceptions, none failed" };
    }
    // The quiet case still has to carry a number, or a clean window reads as
    // a window that was never read.
    return { level: "healthy", text: steps(t.steps || 0) + ", no reported problems" };
  }
  R.runVerdictLine = runVerdictLine;

  /** The step list under an expanded run, from the per-run aggregate.
   *  Ordered by device then step number, which is how the run was executed. */
  function groupStepRows(aggRows) {
    return (aggRows || []).map(function (r) {
      var status = facetValue(resolveStatus(r && r.status, r && r.queueStatus));
      var exception = facetValue(r && r.exception);
      var uuid = (r && r.uuid) || "";
      return {
        // The step's own uuid when the aggregate carried one -- it is unique
        // by construction, which the device/number/name triple is not: two
        // runs of the same playbook against the same device collide on it,
        // and a colliding `track by` is an ngRepeat:dupes throw.
        key: uuid || (facetValue(r && r.device) + "#" +
             (Number(r && r.stepNumber) || 0) + "#" + facetValue(r && r.step)),
        uuid: uuid,
        device: facetValue(r && r.device),
        stepNumber: Number(r && r.stepNumber) || 0,
        name: facetValue(r && r.step),
        action: facetValue(r && r.action),
        trigger: facetValue(r && r.trigger),
        status: status,
        color: statusColor(status),
        exception: exception,
        // The platform's own sentence about the output -- "No exceptions
        // found.", or what it found. Surfaced on hover over the exception
        // cell rather than in a column of its own: it is a paragraph, and a
        // paragraph per row would be the whole table.
        message: (r && r.message) || "",
        // stepDone is the record's OWN "is this finished" flag, and it is the
        // only honest source for it. Deriving in-flight from the status
        // counted every step whose queue row was left at Running, which on
        // one lab box was 683 steps that had all actually finished.
        done: r ? !!r.done : false,
        bad: status === "Fail",
        flagged: exception === "Exceptions Found",
        startedAt: aggStamp(r && r.startedAt),
        finishedAt: aggStamp(r && r.finishedAt),
        // Precomputed, not built in the template: an ng-repeat expression that
        // returns a fresh value every digest is how this widget has twice
        // arrived at $rootScope:infdig.
        when: stampRange(aggStamp(r && r.startedAt), aggStamp(r && r.finishedAt)),
        seconds: Number(r && r.secs) || 0,
        // The same bucket the chip selects, computed on the row itself so the
        // step list can be narrowed by the duration axis like any other.
        duration: durationBucket(r && r.secs)
      };
    }).sort(function (a, b) {
      return a.device.localeCompare(b.device) || (a.stepNumber - b.stepNumber);
    });
  }

  /** An aggregate `max` over a timestamp column comes back as a FORMATTED UTC
   *  string ("2026-09-15 18:35:42"), not as the epoch the record stores. Safari
   *  rejects that spelling outright from `new Date`, so it is parsed by hand
   *  and returned as epoch seconds -- the unit every other stamp here uses. */
  function aggStamp(v) {
    if (v == null || v === "") return 0;
    if (typeof v === "number") return v;
    var n = Number(v);
    if (isFinite(n) && n > 0) return n;
    var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(String(v));
    if (!m) return 0;
    return Math.round(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) / 1000);
  }
  R.aggStamp = aggStamp;

  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function hms(d) {
    return pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
  }
  function dmy(d) { return pad2(d.getDate()) + "/" + pad2(d.getMonth() + 1); }

  /** A step's clock as ONE readable cell.
   *
   *  Start and stop are two columns' worth of width and almost always the same
   *  day, so a run that took ninety seconds renders as "15/09 18:35:42 -
   *  18:37:12" and only spells the date twice when the step actually crossed
   *  midnight. A step still running shows its start and says so rather than
   *  showing a stop time it does not have.
   *
   *  Local time, deliberately: every other stamp on this dashboard is local
   *  (see the controller's `stamp`), and one column in UTC beside them would
   *  be read as the same clock and quietly be hours out. */
  function stampRange(startSecs, stopSecs) {
    var a = Number(startSecs) || 0, b = Number(stopSecs) || 0;
    if (!a && !b) return "";
    if (!a) return dmy(new Date(b * 1000)) + " " + hms(new Date(b * 1000));
    var da = new Date(a * 1000);
    if (!b) return dmy(da) + " " + hms(da) + " - running";
    var db = new Date(b * 1000);
    var sameDay = da.getFullYear() === db.getFullYear() &&
                  da.getMonth() === db.getMonth() && da.getDate() === db.getDate();
    return sameDay
      ? dmy(da) + " " + hms(da) + " - " + hms(db)
      : dmy(da) + " " + hms(da) + " - " + dmy(db) + " " + hms(db);
  }
  R.stampRange = stampRange;

  R.groupStepRows = groupStepRows;

  /** Apply the active step-level chips to one run's step list, so the rows
   *  under a run are the rows the filter selected -- not the whole run with
   *  the interesting ones buried in it. */
  function filterStepRows(rows, sel, query) {
    var q = (query || "").trim().toLowerCase();
    var axes = STEP_FACETS.filter(function (a) { return chosen(sel && sel[a]).length; });
    if (!axes.length && !q) return rows || [];
    return (rows || []).filter(function (r) {
      for (var i = 0; i < axes.length; i++) {
        if (chosen(sel[axes[i]]).indexOf(r[axes[i]]) === -1) return false;
      }
      if (!q) return true;
      return (r.device + " " + r.name + " " + r.action + " " + r.trigger + " " +
              r.status + " " + r.exception + " " + r.duration)
             .toLowerCase().indexOf(q) !== -1;
    });
  }
  R.filterStepRows = filterStepRows;

  // ======================================================================
  // THE DEVICE VIEW
  // ======================================================================
  /** The same facts, pivoted onto the DEVICE instead of the run group.
   *
   *  It is built from `runsView` -- the runs that survived the filter, each
   *  carrying only the facts that survived it -- and NOT from a second query.
   *  That is what makes one filter panel serve both views: a chip narrows the
   *  fact cube once, and the two layouts are two folds of the same narrowed
   *  cube. A device view sourced from its own fetch would answer a subtly
   *  different question than the chips above it claim to be asking, which is
   *  the class of defect this widget has already shipped twice.
   *
   *  `deviceIndex` supplies the identity columns the cube cannot carry -- the
   *  device's own status picklist, its IP and platform, and the uuid a deep
   *  link needs. A device the record fetch never returned still gets a row:
   *  dropping it would make the step counts disagree with the run view.
   */
  function deviceGridRows(view, deviceIndex) {
    var idx = deviceIndex || {};
    var byDevice = {};
    (view || []).forEach(function (g) {
      (g.factsView || []).forEach(function (f) {
        var row = byDevice[f.device];
        if (!row) {
          var rec = idx[f.device] || {};
          row = byDevice[f.device] = {
            name: f.device,
            uuid: rec.uuid || "",
            managementIP: rec.managementIP || "",
            platform: rec.platform || "",
            firmware: rec.firmware || "",
            // The DEVICE's own status picklist ("Ok"), which is a different
            // question from how its steps went -- it is about the box, not
            // about the run.
            status: pick(rec.status) || "",
            connectionStatus: rec.connectionStatus || "",
            configStatus: rec.configStatus || "",
            tags: tagList(rec),
            orphan: !idx[f.device],
            steps: 0, complete: 0, failed: 0, running: 0, pending: 0,
            cancelled: 0, exceptions: 0, unknown: 0, done: 0, inFlight: 0,
            seconds: 0, runs: 0,
            // The LAST run this device took part in, and its clock. "Last"
            // is by the run's start, not by whichever fact was walked last.
            lastRun: "", lastRunAt: 0, lastRunStartedAt: 0, lastRunFinishedAt: 0,
            lastRunStatus: "", lastRunVerdict: "",
            // name -> start time. Kept (as a sorted ARRAY below) because an
            // expanded device row lists its steps from every run group it
            // appears in, not only from its last one.
            runNames: {}
          };
        }
        row.steps += f.steps;
        row.seconds += f.seconds;
        if (f.done) row.done += f.steps; else row.inFlight += f.steps;
        if (f.status === "Complete") row.complete += f.steps;
        else if (f.status === "Fail") row.failed += f.steps;
        else if (f.status === "Running") row.running += f.steps;
        else if (f.status === "Cancelled") row.cancelled += f.steps;
        else if (PENDING[f.status]) row.pending += f.steps;
        else row.unknown += f.steps;
        if (f.exception === "Exceptions Found") row.exceptions += f.steps;
        var at = Number(g.startedAt) || Number(g.createDate) || 0;
        if (!row.runNames[g.name]) { row.runNames[g.name] = at || 1; row.runs += 1; }
        if (!row.lastRun || at > row.lastRunAt) {
          row.lastRun = g.name;
          row.lastRunAt = at;
          row.lastRunStartedAt = at;
          row.lastRunFinishedAt = Number(g.finishedAt) || 0;
          row.lastRunStatus = g.status || "";
          row.lastRunVerdict = g.verdict || "";
          row.lastRunUuid = g.uuid || "";
        }
      });
    });
    return Object.keys(byDevice).map(function (k) {
      var r = byDevice[k];
      // Newest run first, which is the order the expanded row reads in: the
      // run you are most likely looking for is the one at the top.
      r.runGroups = Object.keys(r.runNames).sort(function (a, b) {
        return (r.runNames[b] - r.runNames[a]) || a.localeCompare(b);
      });
      delete r.runNames;
      r.percent = r.steps ? Math.round(r.complete / r.steps * 100) : 0;
      // The device row's verdict is about THE RUN it last took part in, which
      // is the run whose steps are listed when the row is expanded. Reading
      // the device's own status field here instead would badge a healthy box
      // green above a list of failed steps.
      r.verdict = deviceRunVerdict(r);
      r.bar = stepBar({ complete: r.complete, failed: r.failed, running: r.running,
                        cancelled: r.cancelled, pending: r.pending,
                        total: r.steps }, r.steps);
      return r;
    }).sort(function (a, b) {
      // Anything failed first -- that is what the grid is scanned for --
      // then the newest run, then by name so the order is stable.
      return (b.failed > 0) - (a.failed > 0) ||
             (b.lastRunAt - a.lastRunAt) ||
             a.name.localeCompare(b.name);
    });
  }
  R.deviceGridRows = deviceGridRows;

  /** One word for a device's showing across the filtered runs. Same
   *  precedence the rest of the widget uses; in-flight is read from stepDone,
   *  never from a status. */
  function deviceRunVerdict(r) {
    if (!r || !r.steps) return "no-data";
    if (r.failed > 0) return "failed";
    if (r.inFlight > 0) return "running";
    if (r.exceptions > 0) return "exception";
    if (r.unknown > 0 && !r.complete) return "unknown";
    if (r.cancelled > 0 && !r.complete) return "cancelled";
    return "healthy";
  }
  R.deviceRunVerdict = deviceRunVerdict;

  /** The steps of ONE device inside one run, in the run view's own shape but
   *  without the device column -- the caller already knows the device, and
   *  repeating it down every row of a device's own drill-down is noise. */
  function deviceStepRows(rows, deviceName) {
    return (rows || []).filter(function (r) { return r.device === deviceName; })
      .sort(function (a, b) { return a.stepNumber - b.stepNumber; });
  }
  R.deviceStepRows = deviceStepRows;

  /** Every step this device took across EVERY run group in the filtered
   *  window, newest run first.
   *
   *  The device row used to list only its LAST run, which made the grid a
   *  worse answer than the run view for the one question it is the right
   *  shape for: what has happened to this box lately. A device that ran in
   *  four dispatches showed the steps of one of them and gave no sign that
   *  the other three existed.
   *
   *  Each row is stamped with the run group it came from, because once the
   *  rows span several runs the step number alone no longer says which
   *  sequence it belongs to -- that is the column the grid now draws first.
   *
   *  `filterRows` is the caller's chip pass, applied per run before the
   *  device cut, so the grid shows exactly what the filter panel above it
   *  claims is in scope. A run whose steps have not been fetched yet is
   *  skipped rather than treated as empty. */
  function deviceStepRowsAcross(runNames, byRun, device, filterRows) {
    var out = [];
    (runNames || []).forEach(function (name) {
      var all = (byRun || {})[name];
      if (!all) return;
      deviceStepRows(filterRows ? filterRows(all, name) : all, device)
        .forEach(function (r) { out.push(shallow({ group: name }, r)); });
    });
    return out;
  }
  R.deviceStepRowsAcross = deviceStepRowsAcross;

  /* ====================================================================
     THE HEADLINE NARRATIVE
     ====================================================================

     One varied paragraph over the filtered window, in place of a fixed
     sentence nobody reads twice.

     WHAT IT IS ALLOWED TO SAY. Every clause below is a reading of the fact
     cube that is already on screen. The variation is a SELECTION among true
     observations, never an invention of one: an observation whose data is
     missing, or whose answer is not actually interesting (a "most common"
     with nothing to be more common than), is not in the pool to be picked at
     all. That is the whole safety argument for making a dashboard chatty --
     a sentence that is sometimes wrong is worse than no sentence, because
     the reader cannot tell which load they are on.

     WHAT IT CANNOT SAY. Anything needing the step's output TEXT -- "the most
     verbose output was..." -- is deliberately absent. outputText is a
     document per step and is fetched only by an export asked for by name;
     guessing at it from the row counts would be the one clause here that is
     not a reading of anything.

     It is computed once per filter pass and stored. Calling it from a
     template expression would return a new string every digest, which is
     $rootScope:infdig -- twice this widget's bug.  */

  function narrBucket(map, key, f) {
    if (!key || key === NO_VALUE) return;
    var b = map[key] || (map[key] = { name: key, steps: 0, seconds: 0,
                                      failed: 0, exceptions: 0 });
    b.steps += f.steps;
    b.seconds += f.seconds;
    if (f.status === "Fail") b.failed += f.steps;
    if (f.exception === "Exceptions Found") b.exceptions += f.steps;
  }

  /** The biggest bucket by `key`, or null when nothing scores above zero --
   *  or when only ONE bucket exists, because "the most common of one" is a
   *  sentence that tells the reader nothing they could not see. */
  function narrTop(map, key, needsRivals) {
    var all = Object.keys(map).map(function (k) { return map[k]; });
    if (!all.length) return null;
    if (needsRivals && all.length < 2) return null;
    all.sort(function (a, b) { return (b[key] - a[key]) || a.name.localeCompare(b.name); });
    return all[0][key] > 0 ? all[0] : null;
  }

  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  /** "5 days", "3 hours", "12 minutes" -- the age of a timestamp, for the
   *  openers that lead with when rather than with what. */
  function ageWords(secs, nowSecs) {
    var d = Math.max(0, (nowSecs || 0) - (Number(secs) || 0));
    if (d < 90 * 60) return plural(Math.max(1, Math.round(d / 60)), "minute");
    if (d < 36 * 3600) return plural(Math.max(1, Math.round(d / 3600)), "hour");
    return plural(Math.max(1, Math.round(d / 86400)), "day");
  }

  function narrStamp(secs) {
    var d = new Date((Number(secs) || 0) * 1000);
    return dmy(d) + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  }

  /** Roll the window up into the handful of superlatives the narrative is
   *  allowed to draw on. Exported so a test can assert the reading without
   *  going through the sentence-picking. */
  function narrativeFacts(view) {
    var rows = view || [];
    var trig = {}, dev = {}, act = {};
    var firstAt = 0, longest = null;
    rows.forEach(function (g) {
      var at = Number(g.startedAt) || 0;
      if (at && (!firstAt || at < firstAt)) firstAt = at;
      if ((Number(g.seconds) || 0) > 0 &&
          (!longest || g.seconds > longest.seconds)) longest = g;
      (g.factsView || []).forEach(function (f) {
        narrBucket(trig, f.trigger, f);
        narrBucket(dev, f.device, f);
        narrBucket(act, f.action, f);
      });
    });
    // Slowest is an AVERAGE, not a total: a type that ran two hundred quick
    // steps is not slower than one that ran a single firmware upgrade.
    Object.keys(trig).forEach(function (k) {
      trig[k].avg = trig[k].steps ? Math.round(trig[k].seconds / trig[k].steps) : 0;
    });
    Object.keys(act).forEach(function (k) {
      act[k].avg = act[k].steps ? Math.round(act[k].seconds / act[k].steps) : 0;
    });
    Object.keys(dev).forEach(function (k) {
      dev[k].problems = dev[k].failed + dev[k].exceptions;
    });
    return {
      firstAt: firstAt,
      longestRun: longest,
      commonType: narrTop(trig, "steps", true),
      slowestType: narrTop(trig, "avg", true),
      slowestAction: narrTop(act, "avg", true),
      excType: narrTop(trig, "exceptions", false),
      failType: narrTop(trig, "failed", false),
      busiestDevice: narrTop(dev, "steps", true),
      worstDevice: narrTop(dev, "problems", false),
      busiestAction: narrTop(act, "steps", true)
    };
  }
  R.narrativeFacts = narrativeFacts;

  /** The paragraph. `opts`: {rangeLabel, now, rand} -- `rand` injected so a
   *  test can pin which sentence comes out, `now` so "5 days ago" is not a
   *  reading of the wall clock in a fixture. */
  function reportNarrative(view, s, opts) {
    var rows = view || [];
    var sum = s || {};
    var o = opts || {};
    var rand = o.rand || Math.random;
    var now = o.now || Math.floor(Date.now() / 1000);
    var label = o.rangeLabel || "";
    if (!rows.length) return "";

    var F = narrativeFacts(rows);
    function pick(pool) { return pool[Math.floor(rand() * pool.length) % pool.length]; }

    var nRuns = sum.runs || rows.length;
    var runs = plural(nRuns, "run group");
    var have = nRuns === 1 ? "has" : "have";
    var steps = plural(sum.steps || 0, "step");
    var devs = plural(sum.devices || 0, "device");
    var types = plural(sum.triggers || 0, "action type");

    // ---- the opener: the same counts, said four different ways ----------
    var openers = [];
    if (F.firstAt) {
      openers.push("Starting " + narrStamp(F.firstAt) + ", " + runs + " " + have + " run " +
                   steps + " on " + devs + " with " + types + ".");
      openers.push(ageWords(F.firstAt, now) + " ago this window opened: " + steps +
                   " on " + devs + ", in " + runs + ".");
    }
    if (label) {
      // "The last All time" is not a sentence. The unbounded window is the
      // one range label that is not a duration, so it gets its own opening
      // rather than being forced through a phrase built for "7 days".
      var opening = /^all\b/i.test(label) ? "All time holds "
                                          : "The last " + label + " holds ";
      openers.push(opening + steps + " across " + runs + " and " + devs + ".");
    }
    openers.push("Across " + runs + ", " + devs + " " +
                 ((sum.devices || 0) === 1 ? "has" : "have") + " taken " + steps +
                 " of " + types.replace(/^(\d+) /, "$1 different ") + ".");

    // ---- the highlights: only what is true of THIS window ---------------
    // Keyed by subject so two clauses about the same thing cannot both be
    // picked -- "the most common type was X, and the slowest was X" reads as
    // a bug even when both halves are correct.
    var pool = [];
    function add(key, text, name) {
      if (text) pool.push({ key: key, name: name || "", text: text });
    }

    if (F.commonType) {
      add("common", "The most common action type was " + F.commonType.name +
          " at " + plural(F.commonType.steps, "step") + ".", F.commonType.name);
    }
    if (F.slowestType && F.slowestType.avg > 0) {
      add("slow", "The slowest action type was " + F.slowestType.name +
          ", averaging " + humanSeconds(F.slowestType.avg) + " a step.", F.slowestType.name);
    }
    if (F.slowestAction && F.slowestAction.avg > 0) {
      add("slow", "The slowest automation action was " + F.slowestAction.name +
          " at " + humanSeconds(F.slowestAction.avg) + " a step.", F.slowestAction.name);
    }
    if (F.busiestAction) {
      add("common", "Most of the work was " + F.busiestAction.name +
          " (" + plural(F.busiestAction.steps, "step") + ").", F.busiestAction.name);
    }
    if (F.excType) {
      add("exception", "The action type raising the most exceptions was " +
          F.excType.name + ", with " + plural(F.excType.exceptions, "step") +
          " worth reading.", F.excType.name);
    }
    if (F.failType) {
      add("failure", "Failures cluster in " + F.failType.name + " -- " +
          plural(F.failType.failed, "step") + " of it did not finish.", F.failType.name);
    }
    if (F.worstDevice) {
      add("device", "The device with the most to answer for was " +
          F.worstDevice.name + " (" + plural(F.worstDevice.problems, "step") +
          " failed or flagged).", F.worstDevice.name);
    } else if (F.busiestDevice) {
      add("device", F.busiestDevice.name + " carried the most steps, " +
          F.busiestDevice.steps + " of them.", F.busiestDevice.name);
    }
    if (F.longestRun) {
      add("run", "The longest dispatch was " + F.longestRun.name + ", " +
          humanSeconds(F.longestRun.seconds) + " end to end.", F.longestRun.name);
    }
    if (!sum.failed && !sum.exceptions && sum.steps) {
      add("clean", "Nothing failed and nothing raised an exception.");
    }

    var out = [pick(openers)];
    var usedKeys = {}, usedNames = {};
    // Two highlights at most. A third turns a paragraph worth reading into a
    // list worth skipping, which is the wall this panel replaced.
    for (var i = 0; i < 2 && pool.length; i++) {
      var choice = pick(pool);
      usedKeys[choice.key] = true;
      if (choice.name) usedNames[choice.name] = true;
      out.push(choice.text);
      pool = pool.filter(function (c) {
        return !usedKeys[c.key] && !(c.name && usedNames[c.name]);
      });
    }
    return out.join(" ");
  }
  R.reportNarrative = reportNarrative;

  /** THE NARRATIVE SUMMARY -- the left-hand panel.
   *
   *  Everything the operator is NOT going to click: totals, counts and the
   *  average clock. The clickable tiles beside it own the three numbers that
   *  select a filter, and nothing appears in both places -- a number that is
   *  a button in one panel and prose in the other teaches that neither is
   *  reliably clickable.
   *
   *  ZEROES ARE OMITTED, which is the whole point of prose over a tile grid.
   *  "0 run groups running" is a sentence that costs a line and says nothing;
   *  a quiet window should read as a short summary rather than as a wall of
   *  noughts. Only the four genuine totals are unconditional, because their
   *  absence would read as data missing rather than as nothing happening. */
  function summaryLines(s) {
    var v = s || {};
    var out = [];
    function add(key, label, value, show) {
      if (show === false) return;
      out.push({ key: key, label: label, value: value });
    }
    // Title Case throughout -- these read as labels on a stat line, not as
    // sentence fragments.
    // NOT the run total: that is the hero number at the left of the band, and
    // a figure that appears twice in one box teaches that neither copy is the
    // one to read.
    add("runsRunning", "Run Groups Running", v.runsInProgress || 0, (v.runsInProgress || 0) > 0);
    add("runsDone", "Run Groups Done", v.runsDone || 0, (v.runsDone || 0) > 0);
    add("devices", "Devices", v.devices || 0);
    add("steps", "Steps", v.steps || 0);
    add("inFlight", "Steps In Flight", v.inFlight || 0, (v.inFlight || 0) > 0);
    add("actions", "Automation Actions", v.actions || 0);
    // "12 automation actions of 3 types" is the shape of a run window, and the
    // second half is not implied by the first -- one type across twelve
    // actions says something different from twelve of them. Dropped only when
    // it is zero, which is the rule for everything here.
    add("triggers", "Action Types", v.triggers || 0, (v.triggers || 0) > 0);
    // Run Time gets its OWN line below this list now (Min/Avg/Mean/Max), not a
    // single averaged fact buried among the counts -- see view.html's
    // hl-runtime block, which reads v.min/avg/mean/maxRuntime directly.
    return out;
  }
  R.summaryLines = summaryLines;

  /** A count as a share of the steps on screen. Returned as a whole number
   *  because the tile has room for "43%" and not for "42.7%", and because a
   *  decimal point on a count of 7 is false precision. */
  function pctOf(n, total) {
    var d = Number(total) || 0;
    if (d <= 0) return 0;
    return Math.round((Number(n) || 0) / d * 100);
  }
  R.pctOf = pctOf;

  // ======================================================================
  // THE SUMMARY IS MADE OF FILTERS
  // ======================================================================
  /** Split a sentence into plain text and the words that are FILTER VALUES.
   *
   *  The headline and the narrative are written out of the same vocabulary
   *  the chips are built from -- they name devices, actions, action types,
   *  statuses and run groups because those are the only things there are to
   *  name. So every one of those words is already a filter the reader can
   *  apply, and making them click is not decoration: it removes the step
   *  where you read "the device with the most problems was FG1" and then go
   *  hunting through eighty chips for FG1.
   *
   *  Done by matching the sentence against the vocabulary rather than by
   *  having each sentence declare its own links. That is the point: a
   *  narrative phrasing added next year becomes clickable without anyone
   *  remembering to wire it, and a value that has LEFT the window silently
   *  stops being a link instead of becoming one that selects nothing.
   *
   *  Three rules keep it honest:
   *   - longest match wins, so "Remote CLI Script" never renders as a link to
   *     "Remote CLI" with three stray words after it;
   *   - matches respect word boundaries, so a device called "FG1" is not
   *     found inside "FG10";
   *   - values shorter than MIN_LINK characters are skipped entirely. A
   *     status value of "Ok" would otherwise turn every "ok" in an English
   *     sentence into a filter.
   */
  var MIN_LINK = 3;
  function isWordChar(c) { return !!c && /[A-Za-z0-9_]/.test(c); }

  /** value -> axis, built from the vocabulary actually on offer. Later axes
   *  do not overwrite earlier ones: a name that is both a device and an
   *  action is ambiguous, and the first axis in FACET order is the one the
   *  reader is most likely to mean. */
  function linkIndex(vocab, axes) {
    var idx = {};
    (axes || Object.keys(vocab || {})).forEach(function (axis) {
      // A vocabulary axis is only an ARRAY once a fetch has landed -- before
      // that every axis is the empty selection map the controller starts
      // with. A mount that filters before its first response would otherwise
      // throw in here and take the whole tile down with it.
      var list = (vocab || {})[axis];
      if (!list || typeof list.length !== "number") return;
      list.forEach(function (v) {
        var name = v && v.name;
        if (!name || name === NO_VALUE) return;
        if (String(name).length < MIN_LINK) return;
        if (!idx[name]) idx[name] = axis;
      });
    });
    return idx;
  }
  R.linkIndex = linkIndex;

  function linkify(text, idx) {
    var str = text == null ? "" : String(text);
    if (!str) return [];
    var keys = Object.keys(idx || {});
    if (!keys.length) return [{ text: str }];
    keys.sort(function (a, b) { return b.length - a.length || a.localeCompare(b); });
    var lower = str.toLowerCase();
    var out = [], plain = "", i = 0;
    function flush() { if (plain) { out.push({ text: plain }); plain = ""; } }
    while (i < str.length) {
      var hit = null;
      for (var k = 0; k < keys.length; k++) {
        var key = keys[k];
        if (lower.substr(i, key.length) !== key.toLowerCase()) continue;
        if (isWordChar(str.charAt(i - 1))) continue;
        if (isWordChar(str.charAt(i + key.length))) continue;
        hit = key;
        break;
      }
      if (hit) {
        flush();
        // The text is kept as the SENTENCE spells it, not as the vocabulary
        // does -- the link carries the value it filters on separately, so a
        // sentence never has to be written in the box's capitalisation.
        out.push({ text: str.substr(i, hit.length), axis: idx[hit], value: hit });
        i += hit.length;
      } else {
        plain += str.charAt(i);
        i += 1;
      }
    }
    flush();
    return out;
  }
  R.linkify = linkify;

  // ======================================================================
  // THE VIEW IS ADDRESSABLE
  // ======================================================================
  /** Encode / decode the whole reading position -- time scale, layout, search
   *  box and every chip -- as ONE query parameter.
   *
   *  The point is handover. "The firmware pushes that failed on FG1 last
   *  fortnight" takes six clicks to reach and is currently impossible to send
   *  to anyone: the recipient gets the dashboard's default window and a
   *  description of where to click. A widget whose state lives only in its
   *  own memory cannot be cited, and a report nobody can cite gets
   *  screenshotted instead, which is how a number outlives the data.
   *
   *  ONE parameter, namespaced, rather than a dozen: this widget is a tenant
   *  on a page it does not own, and scattering `device=`/`status=` across the
   *  host's query string is how two tiles come to fight over a key.
   *
   *  The spelling is deliberately not JSON. A bookmarked URL is a thing
   *  people look at, and `?rr=l:grid~f.status:Fail` survives being read aloud
   *  and pasted into a ticket in a way that a percent-encoded object does
   *  not. Values are still encoded, because a run group name is allowed to
   *  contain anything at all. */
  var ST_PAIR = "~", ST_KV = ":", ST_MULTI = "|";

  function stEnc(v) {
    return encodeURIComponent(String(v == null ? "" : v))
      .replace(/~/g, "%7E").replace(/:/g, "%3A").replace(/\|/g, "%7C");
  }
  function stDec(v) { try { return decodeURIComponent(String(v || "")); } catch (e) { return ""; } }

  function encodeState(st) {
    var o = st || {}, out = [];
    if (o.range) out.push("r" + ST_KV + stEnc(o.range));
    if (o.layout) out.push("l" + ST_KV + stEnc(o.layout));
    if (o.q) out.push("q" + ST_KV + stEnc(o.q));
    var f = o.facet || {};
    // Sorted, so the same reading position always encodes to the same string
    // -- otherwise every digest looks like a change and the address bar is
    // rewritten forever.
    Object.keys(f).sort().forEach(function (axis) {
      var vals = (f[axis] || []).slice().sort();
      if (!vals.length) return;
      out.push("f." + axis + ST_KV + vals.map(stEnc).join(ST_MULTI));
    });
    return out.join(ST_PAIR);
  }
  R.encodeState = encodeState;

  /** The inverse, and it must never throw: this reads a string a human may
   *  well have hand-edited, and a malformed one has to degrade to "no filters
   *  requested" rather than to a widget that will not mount. */
  function decodeState(str) {
    var out = { facet: {} };
    String(str || "").split(ST_PAIR).forEach(function (pair) {
      if (!pair) return;
      var cut = pair.indexOf(ST_KV);
      if (cut < 0) return;
      var k = pair.slice(0, cut), v = pair.slice(cut + 1);
      if (k === "r") out.range = stDec(v);
      else if (k === "l") out.layout = stDec(v);
      else if (k === "q") out.q = stDec(v);
      else if (k.indexOf("f.") === 0 && k.length > 2) {
        var vals = v.split(ST_MULTI).map(stDec).filter(function (x) { return x !== ""; });
        if (vals.length) out.facet[k.slice(2)] = vals;
      }
    });
    return out;
  }
  R.decodeState = decodeState;

  /** RUN GROUPS, summarised -- one row per dispatch, no step detail. */
  R.csvRunGroupsView = function (view) {
    return toCsv(
      ["Run group", "Status", "Verdict", "Created", "Completed", "Devices",
       "Steps declared", "Steps reported", "Complete", "Complete %", "Failed",
       "Exceptions", "In flight", "Runtime", "Tags"],
      (view || []).map(function (g) {
        var t = g.steps || {}, pr = g.progress || {};
        return [g.name, g.status || "", g.verdict || "",
                g.createDate ? new Date(g.createDate * 1000).toISOString() : "",
                g.finishedAt ? new Date(g.finishedAt * 1000).toISOString() : "",
                (g.deviceNames || []).length || g.totalDevices || 0,
                pr.total || 0, t.total || 0, t.complete || 0, pr.percent || 0,
                t.failed || 0, t.exceptions || 0, t.inFlight || 0,
                g.runtime || "", (g.tags || []).join(" ")];
      }));
  };

  /** DEVICES, summarised -- one row per device, no step detail. */
  R.csvDeviceGrid = function (rows) {
    return toCsv(
      ["Device", "Management IP", "Platform", "Firmware", "Device status",
       "Verdict", "Last run group", "Run started", "Run completed", "Runs",
       "Steps", "Complete", "Complete %", "Failed", "In flight", "Exceptions",
       "Duration"],
      (rows || []).map(function (r) {
        return [r.name, r.managementIP, r.platform, r.firmware, r.status,
                r.verdict, r.lastRun,
                r.lastRunStartedAt ? new Date(r.lastRunStartedAt * 1000).toISOString() : "",
                r.lastRunFinishedAt ? new Date(r.lastRunFinishedAt * 1000).toISOString() : "",
                r.runs, r.steps, r.complete, r.percent, r.failed, r.inFlight,
                r.exceptions, humanSeconds(r.seconds)];
      }));
  };

  /** STEPS -- one row per step, and the opposite of the two above.
   *
   *  The run group and the device are COLUMNS here rather than the thing being
   *  summarised, so the sheet can be pivoted on either. It carries the clock,
   *  both status fields, the platform's message about the output, and the
   *  step's own output text -- which is why this export exists at all, and
   *  why it is the one that will wrap in a spreadsheet. `outputText` is not on
   *  the step rows the dashboard draws (it is a document per step); the caller
   *  fetches it and passes it in by uuid.
   */
  R.csvSteps = function (rows, textByUuid) {
    var txt = textByUuid || {};
    return toCsv(
      ["Run group", "Device", "Step #", "Step name", "Automation action",
       "Action type", "Status", "Output status", "Output status message",
       "Started", "Stopped", "Seconds", "Done", "Output text"],
      (rows || []).map(function (s) {
        return [s.group || "", s.device, s.stepNumber, s.name, s.action,
                s.trigger, s.status, s.exception, s.message || "",
                s.startedAt ? new Date(s.startedAt * 1000).toISOString() : "",
                s.finishedAt ? new Date(s.finishedAt * 1000).toISOString() : "",
                s.seconds, s.done ? "yes" : "no",
                txt[s.uuid] == null ? "" : String(txt[s.uuid])];
      }));
  };

  /** The step rows of every run on screen, flattened and stamped with the run
   *  they came from -- the substrate for the step export and the PDF. */
  R.flattenStepRows = function (view) {
    var out = [];
    (view || []).forEach(function (g) {
      (g.stepRows || []).forEach(function (s) {
        var c = shallow({}, s);
        c.group = g.name;
        out.push(c);
      });
    });
    return out;
  };

  R.csvRunSteps = function (view) {
    return R.csvSteps(R.flattenStepRows(view), {});
  };

  // ======================================================================
  // THE STEP REPORT
  // ======================================================================
  /** Render a step's `outputMarkdown` as HTML.
   *
   *  ESCAPE FIRST, THEN TRANSFORM -- that ordering is the entire security
   *  argument, not a detail. The text is written by whatever automation the
   *  run happened to carry, and it is being painted into the dashboard's own
   *  DOM. Every `<` becomes `&lt;` before a single tag is produced, so the
   *  HTML that comes out is built ONLY from markup this function emits. There
   *  is no sanitiser to trust and nothing for a crafted report to slip
   *  through: by the time we are matching `**bold**`, the input can no longer
   *  contain a tag.
   *
   *  Deliberately small. It covers what these reports actually use, measured
   *  across 50 live reports on two boxes: headings, bullets, bold, inline
   *  code, fenced blocks and tables. Nothing else appeared -- no links, no
   *  raw HTML, no blockquotes, no numbered lists.
   *
   *  LINKS ARE NOT RENDERED, and that is deliberate rather than unfinished.
   *  No report used one, and an anchor is the one construct where escaping the
   *  text is not enough on its own: the href is a separate injection surface
   *  (a `javascript:` URL), so it would need its own scheme allow-list to be
   *  safe. A link that renders as its literal source is a readable
   *  non-event; a link that runs something is not. */
  function mdEscape(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  R.mdEscape = mdEscape;

  // A sentinel for parked code spans, built around a RAW "<".
  //
  // The input is escaped before this runs, so escaped text cannot contain a
  // raw "<" -- which makes this token one a report is structurally incapable
  // of forging. A plain-text sentinel is forgeable, and that is not
  // theoretical: a report containing the literal placeholder had its text
  // replaced by a different span's contents. The only other raw "<" in flight
  // is the markup this function emits itself, and none of it matches.
  var MD_SLOT = "<mdcode";

  /** Inline spans, on ALREADY-ESCAPED text. Code is parked first: a backtick
   *  span is literal by definition, so `**` inside one must not become bold. */
  function mdInline(text) {
    var out = mdEscape(text);
    var code = [];
    out = out.replace(/`([^`]+)`/g, function (_, c) {
      code.push(c);
      return MD_SLOT + (code.length - 1) + ">";
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/<mdcode(\d+)>/g, function (m, i) {
      var hit = code[Number(i)];
      return hit === undefined ? m
        : '<code class="md-code-inline">' + hit + "</code>";
    });
    return out;
  }
  R.mdInline = mdInline;

  var MD_ROW = /^\s*\|(.*)\|\s*$/;
  // A separator row is what turns two pipe-lines into a TABLE rather than two
  // lines that merely contain pipes -- which matters here, because these
  // reports are full of CLI output carrying them.
  var MD_SEP = /^\s*\|[\s:|-]*-[\s:|-]*\|\s*$/;

  function mdCells(line) {
    var m = MD_ROW.exec(line);
    return (m ? m[1] : line).split("|").map(function (c) { return c.trim(); });
  }

  function renderMarkdown(src) {
    if (src == null || src === "") return "";
    var lines = String(src).replace(/\r\n?/g, "\n").split("\n");
    var out = [], i = 0, para = [];

    function flushPara() {
      if (!para.length) return;
      // Single newlines are meaningful in these reports -- they are mostly
      // device output -- so they survive as <br> rather than being collapsed
      // the way a prose renderer would.
      out.push("<p>" + para.map(mdInline).join("<br>") + "</p>");
      para = [];
    }

    while (i < lines.length) {
      var line = lines[i];

      if (/^\s*```+\s*[A-Za-z0-9_+-]*\s*$/.test(line)) {
        flushPara();
        var body = [];
        i += 1;
        while (i < lines.length && !/^\s*```+\s*$/.test(lines[i])) {
          body.push(lines[i]); i += 1;
        }
        i += 1;   // the closing fence, or the end of input
        out.push('<pre class="md-code"><code>' + mdEscape(body.join("\n")) +
                 "</code></pre>");
        continue;
      }

      if (MD_ROW.test(line) && i + 1 < lines.length && MD_SEP.test(lines[i + 1])) {
        flushPara();
        var head = mdCells(line);
        i += 2;
        var rows = [];
        while (i < lines.length && MD_ROW.test(lines[i]) && !MD_SEP.test(lines[i])) {
          rows.push(mdCells(lines[i])); i += 1;
        }
        var t = ['<table class="md-table"><thead><tr>'];
        head.forEach(function (h) { t.push("<th>" + mdInline(h) + "</th>"); });
        t.push("</tr></thead><tbody>");
        rows.forEach(function (r) {
          t.push("<tr>");
          // Padded to the header width: a short row must not silently shift
          // the columns of the row under it.
          for (var c = 0; c < head.length; c++) {
            t.push("<td>" + mdInline(r[c] == null ? "" : r[c]) + "</td>");
          }
          t.push("</tr>");
        });
        t.push("</tbody></table>");
        out.push(t.join(""));
        continue;
      }

      var h = /^\s*(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
      if (h) {
        flushPara();
        // h4-h6: this is a fragment inside a dashboard, not a page of its own,
        // so it must not open at h1 and break the host document's outline.
        var lvl = Math.min(6, 3 + h[1].length);
        out.push("<h" + lvl + ' class="md-h' + h[1].length + '">' +
                 mdInline(h[2]) + "</h" + lvl + ">");
        i += 1;
        continue;
      }

      if (/^\s*[-*+]\s+/.test(line)) {
        flushPara();
        var items = [];
        while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*+]\s+/, "")); i += 1;
        }
        out.push('<ul class="md-list">' + items.map(function (x) {
          return "<li>" + mdInline(x) + "</li>";
        }).join("") + "</ul>");
        continue;
      }

      if (/^\s*([-*_])\s*(\1\s*){2,}$/.test(line)) {
        flushPara(); out.push('<hr class="md-hr">'); i += 1; continue;
      }

      if (!line.trim()) { flushPara(); i += 1; continue; }
      para.push(line);
      i += 1;
    }
    flushPara();
    return out.join("");
  }
  R.renderMarkdown = renderMarkdown;

  // ---- Run Automation --------------------------------------------------
  // The button hands a set of devices to a record-context (Manual) playbook
  // -- by default "Add Steps to Device from Profile", which then asks for the
  // automation profile itself. The widget only chooses the devices.
  var AUTO_DEVICE_FIELDS = ["uuid", "name", "managementIP", "platform", "firmware", "ztpfRunning"];

  // Devices in `status` (default "Ok") that are not mid-run. The second
  // filter mirrors the playbook's own display condition (ztpfRunning neq
  // true): offering a device the Execute menu would hide is offering a run
  // the playbook was written to refuse.
  function automationDeviceQuery(status) {
    return {
      logic: "AND",
      filters: [
        { field: "status.itemValue", operator: "eq", value: status || "Ok" },
        { field: "ztpfRunning", operator: "neq", value: true }
      ],
      __selectFields: AUTO_DEVICE_FIELDS.slice(),
      sort: [{ field: "name", direction: "ASC" }]
    };
  }

  // The action endpoint is keyed by the trigger step's ROUTE, not the
  // playbook uuid (a uuid there is a 404). `$triggerOnly=true` returns just
  // that step; prefer the one `triggerStep` names, fall back to any step
  // carrying a route.
  function automationRoute(workflow) {
    var steps = (workflow && workflow.steps) || [];
    var trig = String((workflow && workflow.triggerStep) || "").split("/").pop();
    var hit = steps.filter(function (s) { return s && s.uuid === trig; })[0] ||
      steps.filter(function (s) { return s && s.arguments && s.arguments.route; })[0];
    return (hit && hit.arguments && hit.arguments.route) || null;
  }

  // Exactly the body the platform's own Execute menu posts
  // (playbookService.triggerPlaybookAction → ACTION_TRIGGER + route).
  function automationTriggerBody(playbookUuid, devices) {
    return {
      __resource: "ztpf_devices",
      __uuid: playbookUuid,
      records: (devices || []).map(function (d) {
        return d["@id"] || ("/api/3/ztpf_devices/" + d.uuid);
      })
    };
  }

  function automationMatches(device, text) {
    var q = String(text || "").trim().toLowerCase();
    if (!q) return true;
    return ["name", "managementIP", "platform", "firmware"].some(function (k) {
      return String((device && device[k]) || "").toLowerCase().indexOf(q) !== -1;
    });
  }

  R.automationDeviceQuery = automationDeviceQuery;
  R.automationRoute = automationRoute;
  R.automationTriggerBody = automationTriggerBody;
  R.automationMatches = automationMatches;

  if (typeof module !== "undefined" && module.exports) module.exports = R;
  root.ztpReport = R;
})(typeof window !== "undefined" ? window : globalThis);

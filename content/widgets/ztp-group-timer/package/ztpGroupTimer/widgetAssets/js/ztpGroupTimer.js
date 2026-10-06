/* Copyright start
   MIT License
   Copyright (c) 2026 Fortinet Inc
   Copyright end */
"use strict";
// Pure logic, no Angular -- unit-tested directly under jsdom (see
// tests/ztpGroupTimer.test.js) and loaded by the controller off `window`,
// exactly as the <script> tag in view.html provides it in the browser. See
// ztpRunReport/widget/widgetAssets/js/ztpReport.js for the same split.
(function (root) {
  var R = {};

  /** The run's own start/stop, derived from its steps rather than read off a
   *  field the group record doesn't have. `start` is the earliest step that
   *  has begun; `stop` is only ever set once EVERY step in the group is
   *  DONE. Returns epoch SECONDS (the field's own unit -- confirmed against
   *  a live appliance: 1787775831 is 2026, not 1970+ms), or null for either
   *  edge with nothing to report yet.
   *
   *  "Done" is `stepDone`, never "has a stepStopTimestamp" -- found live: a
   *  step can carry a stop timestamp while its own `status` still reads
   *  Running (the platform stamps it on an attempt boundary, not only on the
   *  step's true finish), and a step still Queued behind it has NEITHER
   *  timestamp at all. A timestamp-presence check missed both cases and
   *  froze the clock with two steps still to run. ztpRunReport hit the same
   *  shape of bug for its own "steps in flight" tile and fixed it the same
   *  way -- see its stepFacts comment: stepDone is authoritative because
   *  every other signal can lag or lie about a step actually being over. */
  function computeWindow(steps) {
    var starts = [], stops = [], allDone = true;
    (steps || []).forEach(function (s) {
      var start = s && s.stepStartTimestamp;
      var stop = s && s.stepStopTimestamp;
      if (start) starts.push(start);
      if (stop) stops.push(stop);
      if (!(s && s.stepDone)) allDone = false;
    });
    if (!starts.length) return { start: null, stop: null };
    var start = Math.min.apply(null, starts);
    var stop = (allDone && stops.length) ? Math.max.apply(null, stops) : null;
    return { start: start, stop: stop };
  }
  R.computeWindow = computeWindow;

  /** "idle" -- no step has started yet, nothing to show but a zeroed clock.
   *  "running" -- started, not every step has stopped: the clock ticks off
   *  wall-clock time against `nowSec`.
   *  "stopped" -- every started step has stopped: the clock is frozen at
   *  stop - start, and stays that reading regardless of `nowSec`. */
  function timerState(win) {
    if (!win || win.start == null) return "idle";
    return win.stop == null ? "running" : "stopped";
  }
  R.timerState = timerState;

  /** Seconds on the clock face right now. `nowSec` is the caller's own
   *  clock -- never Date.now() read in here -- so a tick and a unit test can
   *  both drive this off a value they control. */
  function elapsedSeconds(win, nowSec) {
    if (!win || win.start == null) return 0;
    var end = win.stop != null ? win.stop : nowSec;
    return Math.max(0, Math.round(end - win.start));
  }
  R.elapsedSeconds = elapsedSeconds;

  function pad2(n) { return n < 10 ? "0" + n : "" + n; }

  /** HH:MM:SS, hours uncapped at 24 -- a firmware push that ran overnight
   *  reads as "26:04:11", not a wrapped "02:04:11" that looks like a much
   *  shorter run. */
  function formatClock(totalSeconds) {
    var s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return pad2(h) + ":" + pad2(m) + ":" + pad2(sec);
  }
  R.formatClock = formatClock;

  /** "1h 2m 3s" -- only the units that matter at this magnitude, the same
   *  convention ztpReport.humanSeconds uses for run/step times elsewhere in
   *  this fleet's widgets. */
  function formatCompact(totalSeconds) {
    var s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    if (s < 60) return s + "s";
    var m = Math.floor(s / 60), sec = s % 60;
    if (m < 60) return m + "m" + (sec ? " " + sec + "s" : "");
    var h = Math.floor(m / 60);
    return h + "h " + (m % 60) + "m";
  }
  R.formatCompact = formatCompact;

  /** {h, m, s} as zero-padded STRINGS -- what a flip/segment display digit
   *  pair renders directly, so the template never formats digits itself. */
  function digitParts(totalSeconds) {
    var s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    return {
      h: pad2(Math.floor(s / 3600)),
      m: pad2(Math.floor((s % 3600) / 60)),
      s: pad2(s % 60)
    };
  }
  R.digitParts = digitParts;

  R.THEMES = [
    { id: "digital", label: "Digital (LCD)" },
    { id: "flip", label: "Flip digits" },
    { id: "minimal", label: "Minimal text" },
    { id: "ring", label: "Spinner ring" },
    { id: "badge", label: "Compact badge" }
  ];

  if (typeof module !== "undefined" && module.exports) module.exports = R;
  root.ztpGroupTimer = R;
})(typeof window !== "undefined" ? window : globalThis);

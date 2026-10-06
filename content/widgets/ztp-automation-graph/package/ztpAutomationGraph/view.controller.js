/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
// @ts-check
// VIEW controller. Harness/SOAR resolves the name as `<name><ver>DevCtrl`
// (ztpAutomationGraph1040DevCtrl); `widget bump` rewrites that suffix -- never
// hand-edit it. See KNOWLEDGEBASE.md + plans/sorted-foraging-clarke.md.
//
// Mapping rules + the data model live in the typed module widgetAssets/js/
// ztpGraph.ts (compiled to ztpGraph.js, loaded via <script> as window.ztpGraph).
// This controller only orchestrates: read device -> fetch canonical step
// records -> map via ztpGraph -> render with Cytoscape -> poll for live status
// -> deep-link on tap. Field names confirmed live (memory ztp-device-automation-
// steps-schema). The embedded device.ztpfArtifact.steps[] summary is STALE --
// we always fetch canonical queueStatus separately (plan §3/§4/§6).
(function () {
  "use strict";
  angular
    .module("cybersponse")
    .controller("ztpAutomationGraph1040DevCtrl", ztpAutomationGraph1040DevCtrl);

  ztpAutomationGraph1040DevCtrl.$inject = [
    "$scope", "config", "$state", "FormEntityService",
    "$http", "$window", "$timeout",
  ];

  /** @param {object} $scope @param {object} config @param {object} $state
   *  @param {object} FormEntityService @param {object} $http
   *  @param {object} $window @param {object} $timeout */
  function ztpAutomationGraph1040DevCtrl($scope, config, $state, FormEntityService,
                                        $http, $window, $timeout) {
    var zg = $window.ztpGraph;
    var STEP_MODULE = "ztpf_device_automation_steps";
    var DEVICE_MODULE = "ztpf_devices";
    var DEVICE_TIMEOUT_MS = 5000;
    // Well past any real run history: 22 steps x many runs, and the filter runs
    // client-side. Kept finite so a runaway device cannot hang the panel.
    var STEP_PAGE = 500;

    $scope.config = angular.extend(
      {}, { title: "ZTP Automation Step Graph", pollSeconds: 6, idlePollSeconds: 20,
            openInNewTab: true,
            orientation: "LR", graphHeight: 380, graphWidth: 0, align: "center",
            blinkCurrent: true, nodeStyle: "chip" },
      config || {});
    // Height of the (bounded, scrollable) graph viewport. Long runs scroll inside
    // it rather than growing the panel. Clamped to a sane range.
    var gh = Number($scope.config.graphHeight);
    if (!(gh > 0)) gh = 380;
    gh = Math.max(160, Math.min(1200, gh));
    $scope.graphHeightPx = gh + "px";
    // Max width the whole widget may use. 0/blank = the full panel (a col-lg-12
    // row measures 2265px on the box, which is more width than a run of a dozen
    // steps has any use for). A number caps it; the cap lands on the widget ROOT,
    // so the header, legend and graph all narrow together, and availWidth() --
    // which measures the graph wrap INSIDE the root -- sees the capped width and
    // lays the zig-zag out to it. With align=center the capped widget centers.
    var gw = Number($scope.config.graphWidth);
    $scope.graphMaxWidth = (gw > 0) ? Math.max(320, Math.min(4000, gw)) + "px" : "100%";
    $scope.state = "loading";   // loading|ready|empty|error
    $scope.mode = "empty";      // empty|queued|running|completed
    $scope.error = "";
    $scope.deviceName = "";
    $scope.runGroup = "";
    $scope.truncated = "";
    $scope.localOrder = null;
    // Built from the run, not hardcoded. The old fixed list named five states,
    // two of which are in no picklist ("Added", and "Failed" -- the real value is
    // "Fail"), and pinned stale colours: it drew Running in yellow while the
    // nodes rendered it cyan from the picklist, so the legend contradicted the
    // graph it was explaining. buildLegend() reads the statuses actually present,
    // with each status's own colour, in picklist order.
    $scope.legend = [];

    function buildLegend(steps) {
      var seen = {};
      var out = [];
      for (var i = 0; i < steps.length; i++) {
        var si = zg.statusInfo(steps[i]);
        if (!si.value || seen[si.value]) continue;
        seen[si.value] = true;
        out.push({ value: si.value, color: si.color, order: si.order, badge: si.badge });
      }
      out.sort(function (a, b) { return a.order - b.order; });
      return out;
    }

    var cy = null;          // cytoscape instance
    var lastLayoutSig = null; // topology signature of the last laid-out graph
    var pollTimer = null;   // setTimeout handle
    var deviceId = "";
    var deviceArtifact = null;
    var ztpfRunning = false;

    // Inline SVG icons (white glyph on transparent) -- no external asset files.
    function svgUri(svg) {
      return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
    }
    // Glyphs are centered in the 0 0 24 24 viewBox and drawn WHITE, so they sit on
    // the node's dark fill (see cytoscapeStyle) with high contrast on every status
    // color -- a white glyph directly on a yellow "Running" fill washed out. Inner
    // detail uses the node-fill slate so it reads on the white shapes.
    // Glyph BODIES (no <svg> wrapper) so a status badge can be composed into the
    // same image -- see iconUri. Drawn WHITE on the node's dark slate fill; a
    // white glyph directly on the status colour washed out on light statuses.
    // Inner detail uses the node-fill slate so it reads on the white shapes.
    //
    // One glyph per FAMILY of ztpfActionType, not per category. The old map was
    // keyed on category, so all seven FortiManager action types in live use
    // (Remote CLI, Proxy API, DeviceDB, JSON RPC, Install Device Config, Upgrade
    // Device Firmware, Upgrade Preflight) drew the identical document icon --
    // 232 of the 300 step records on the lab box.
    var ICON_BODY = {
      // Terminal prompt: Remote CLI / Remote TCL.
      cli: '<rect x="3" y="5" width="18" height="14" rx="2" fill="#fff"/><path d="M6.5 9.5l3 2.5-3 2.5" stroke="#2b3648" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/><rect x="11.5" y="14" width="6" height="1.6" rx=".8" fill="#2b3648"/>',
      // Braces: Proxy API / JSON RPC (a REST/JSON call, not a shell).
      api: '<path d="M9.6 4.5C7.2 4.5 7.6 8.4 7.6 9.6c0 1.3-1 2.4-2.4 2.4 1.4 0 2.4 1.1 2.4 2.4 0 1.2-.4 5.1 2 5.1" stroke="#fff" stroke-width="1.7" fill="none" stroke-linecap="round"/><path d="M14.4 4.5c2.4 0 2 3.9 2 5.1 0 1.3 1 2.4 2.4 2.4-1.4 0-2.4 1.1-2.4 2.4 0 1.2.4 5.1-2 5.1" stroke="#fff" stroke-width="1.7" fill="none" stroke-linecap="round"/>',
      // Database drum: DeviceDB/PolicyDB, install/refresh/authorize, provisioning.
      configdb: '<ellipse cx="12" cy="6.4" rx="7" ry="2.6" fill="#fff"/><path d="M5 6.4v11.2c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6.4" fill="#fff"/><path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6" stroke="#2b3648" stroke-width="1.3" fill="none"/>',
      // Chip with an up arrow: Upgrade Device Firmware / Upgrade Preflight.
      firmware: '<rect x="5.5" y="5.5" width="13" height="13" rx="2" fill="#fff"/><path d="M12 15.5v-6M12 9.5l-2.6 2.6M12 9.5l2.6 2.6" stroke="#2b3648" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 3.2v2M15 3.2v2M9 18.8v2M15 18.8v2M3.2 9h2M3.2 15h2M18.8 9h2M18.8 15h2" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>',
      // Two panes with a delta: Diff Step Output / Validate Step Output / Report.
      analysis: '<rect x="3.5" y="5" width="7.5" height="14" rx="1.5" fill="#fff"/><rect x="13" y="5" width="7.5" height="14" rx="1.5" fill="#fff"/><rect x="5.2" y="8" width="4" height="1.4" rx=".7" fill="#2b3648"/><rect x="5.2" y="11" width="4" height="1.4" rx=".7" fill="#2b3648"/><rect x="14.7" y="8" width="4" height="1.4" rx=".7" fill="#2b3648"/><rect x="14.7" y="13.4" width="4" height="1.4" rx=".7" fill="#2b3648"/>',
      // Clock: Wait for Condition / Playbook -- something that gates the flow.
      control: '<circle cx="12" cy="12" r="8" fill="#fff"/><path d="M12 7.2V12l3.2 2" stroke="#2b3648" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
      generic: '<circle cx="12" cy="12" r="5.5" fill="#fff"/>',
    };

    // Status badges, composed into the bottom-right of the same 24x24 viewBox.
    // These are the states a colour alone does not communicate: a run parked on
    // Input Needed looks identical to one merely queued if you are not reading
    // hues, and Fail vs Cancelled are both "stopped".
    var BADGE_BODY = {
      attention: '<circle cx="18.4" cy="18.4" r="5.4" fill="#b1ae06" stroke="#1f2836" stroke-width="1.3"/><rect x="17.6" y="15.4" width="1.6" height="3.8" rx=".8" fill="#fff"/><rect x="17.6" y="20.1" width="1.6" height="1.6" rx=".8" fill="#fff"/>',
      fail: '<circle cx="18.4" cy="18.4" r="5.4" fill="#ff0000" stroke="#1f2836" stroke-width="1.3"/><path d="M16.5 16.5l3.8 3.8M20.3 16.5l-3.8 3.8" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
      cancelled: '<circle cx="18.4" cy="18.4" r="5.4" fill="#808080" stroke="#1f2836" stroke-width="1.3"/><path d="M15.9 20.9l5-5" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
    };

    // Compose family glyph + optional badge into ONE data URI. Cytoscape can take
    // an array of background-images, but building a single image keeps the node
    // style independent of that feature and of the bundled cytoscape version.
    // Memoized: there are at most (families x badges) distinct results, and this
    // is called per node on every restyle.
    var iconCache = {};
    function iconUri(family, badge) {
      var key = family + "|" + (badge || "");
      if (!iconCache[key]) {
        iconCache[key] = svgUri(
          '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">' +
          (ICON_BODY[family] || ICON_BODY.generic) +
          (badge && BADGE_BODY[badge] ? BADGE_BODY[badge] : "") +
          "</svg>");
      }
      return iconCache[key];
    }

    // Detect whether the widget sits on a dark panel (SOAR 8.0 default) by walking
    // up to the first ancestor with an opaque background and testing its luminance.
    // Drives $scope.dark (CSS) + the cytoscape label/edge/fill colors.
    function detectDark() {
      try {
        // Start at .ztp-ag's PARENT, not #ztp-cy: the canvas has its own
        // hardcoded opaque background (#fbfcfd light / dark when already
        // toggled), so starting there always reads the widget's own paint
        // instead of the host panel and can never detect a dark host.
        var root = document.querySelector(".ztp-ag");
        var el = root ? root.parentElement : null;
        while (el) {
          var bg = $window.getComputedStyle(el).backgroundColor;
          var m = bg && bg.match(/rgba?\(([^)]+)\)/);
          if (m) {
            var p = m[1].split(",").map(function (x) { return parseFloat(x); });
            var a = p.length > 3 ? p[3] : 1;
            if (a > 0.1) {
              return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) < 128;
            }
          }
          el = el.parentElement;
        }
      } catch (e) { /* default light */ }
      return false;
    }
    $scope.dark = false;

    function getDevice() {
      try {
        var e = FormEntityService.get();
        if (!e) return null;
        if (e.originalData) return e.originalData;        // { originalData: record }
        if (e["@id"] || e.uuid || e.ztpfArtifact) return e; // bare record
        if (e.fields) return e.fields;                     // entity.fields
        return null;
      } catch (err) { return null; }
    }

    // Adopt the device-level inputs (artifact run-group + running flag) from a
    // device record.
    function adoptDevice(dev) {
      if (!dev) return null;
      deviceArtifact = dev.ztpfArtifact || null;
      ztpfRunning = !!dev.ztpfRunning;
      return dev;
    }

    // Re-read the device FROM THE BOX. FormEntityService hands back the record
    // the PAGE loaded and never refetches it, so ztpfRunning stayed true for the
    // life of the panel: a run that finished an hour ago still forced mode
    // "running" (deriveGraphMode ORs the flag in), and the badge contradicted 22
    // Complete steps sitting right under it. The steps come over HTTP every poll
    // -- the flag that overrides them has to as well.
    // Fire-and-forget: it updates the cached flag for the NEXT pass and never
    // gates the render. Gating it (a $q.all over both requests) meant a slow or
    // unreachable box stalled the GRAPH -- the steps are the payload, the device
    // flag only a modifier, and an 8s upstream timeout blew the render budget
    // and drew nothing at all. Bounded so a hung request can't pile up either.
    function refreshDeviceFlag(id) {
      $http.get("/api/3/" + DEVICE_MODULE + "/" + id, { timeout: DEVICE_TIMEOUT_MS })
        .then(function (resp) { adoptDevice((resp && resp.data) || null); })
        .catch(function () { /* keep the last known values */ });
    }

    // A device accumulates one step record per step PER RUN, and the run group is
    // only knowable after the fetch -- so the whole history has to come back and
    // be filtered client-side. Without an explicit $limit the API serves its
    // default page of 30: a device on its second 22-step run holds 44 records,
    // page 1 carried only 8 of the current group, and the graph drew steps 15-22
    // with the first fourteen simply absent. Ask for far more than a run can be,
    // and say so out loud if the box still has more to give.
    function fetchSteps(id) {
      return $http.get("/api/3/" + STEP_MODULE, { params: { ztpfDevices: id, $limit: STEP_PAGE } })
        .then(function (resp) {
          var d = resp && resp.data;
          var members = (d && d["hydra:member"]) || (Array.isArray(d) ? d : []);
          var total = d && d["hydra:totalItems"];
          if (total > members.length) {
            // Truncated again. Draw what we have rather than nothing, but do not
            // let it look complete -- a silently short graph is the bug above.
            $scope.truncated = "Showing " + members.length + " of " + total +
              " step records for this device; older runs may be missing.";
          } else {
            $scope.truncated = "";
          }
          return members;
        });
    }

    function schedulePoll(seconds) {
      cancelPoll();
      var ms = Math.max(2, Number(seconds) || 6) * 1000;
      // Raw setTimeout (not $timeout) so the harness render-state settle doesn't
      // chase the poll chain waiting for quiescence. refresh runs inside
      // $applyAsync to enter a digest.
      pollTimer = $window.setTimeout(function () { $scope.$applyAsync(refresh); }, ms);
    }
    function cancelPoll() {
      if (pollTimer) { $window.clearTimeout(pollTimer); pollTimer = null; }
    }

    function refresh() {
      if (!deviceId) { $scope.state = "error"; $scope.error = "No device record."; return; }
      // Re-read the device each pass: ztpfRunning flips and ztpfArtifact.ztfGroup
      // is re-stamped when a new run starts, and the values captured in init()
      // are from whenever the panel was opened.
      refreshDeviceFlag(deviceId);
      fetchSteps(deviceId).then(function (steps) {
        var latest = zg.filterLatestRunGroup(steps, deviceArtifact);
        $scope.mode = zg.deriveGraphMode(latest, ztpfRunning);
        // Name the group we are actually DRAWING. Reading it off the artifact
        // instead meant the header chip could disagree with the graph below it.
        $scope.runGroup = (latest.length ? zg.runGroupName(latest[0]) : "") ||
                          (deviceArtifact && deviceArtifact.ztfGroup) || "";
        if (!latest.length) {
          $scope.state = "empty"; $scope.legend = [];
          schedulePoll($scope.config.idlePollSeconds);
          return;
        }
        $scope.state = "ready";
        $scope.legend = buildLegend(latest);
        // Defer to the next digest so the ng-if="state==='ready'" container is
        // in the DOM before cytoscape reads its size.
        $timeout(function () { renderGraph(latest, $scope.mode); });
        // Keep polling while the run-group is non-terminal.
        // "blocked" polls too: the run resumes the moment someone supplies the
        // missing input, and the widget should notice without a page reload.
        if ($scope.mode === "running" || $scope.mode === "queued" || $scope.mode === "blocked") {
          schedulePoll($scope.config.pollSeconds);
        } else {
          // A finished run does NOT end the widget's life: the next ZTPf2 run
          // creates a new run-group, and stopping here left the completed graph
          // frozen on screen until someone reloaded the page. Keep a slower
          // idle poll so the new group is picked up and rendered on its own.
          schedulePoll($scope.config.idlePollSeconds);
        }
      }).catch(function (err) {
        $scope.state = "error";
        $scope.error = (err && err.status ? "HTTP " + err.status + ": " : "Failed to load steps: ") +
                       (err && err.statusText ? err.statusText : String(err));
        cancelPoll();
      });
    }

    function cytoscapeStyle(mode) {
      var queued = mode === "queued";
      var dark = $scope.dark;
      // The chip fill is a fixed dark slate on both themes (status reads via the
      // colored ring, not the fill) so the WHITE icon always has contrast -- a
      // status-colored fill washed out the icon on light statuses. Labels + edges
      // do flip with the theme so they read on the canvas.
      var nodeFill = "#2b3648";
      var labelColor = dark ? "#e8ebf0" : "#3a4657";
      var labelOutline = dark ? "#171e29" : "#ffffff";
      var edgeColor = dark ? "#5b6675" : "#b7bdc7";
      // Two node presentations (config.nodeStyle):
      //   "chip" -- compact 52² square, icon centered, title sits BELOW the node.
      //   "card" -- wide rectangle, icon pinned left, title INSIDE the rectangle.
      var iconOf = function (n) { return iconUri(n.data("icon"), n.data("badge")); };
      var nodeStyle;
      if (isCardNode()) {
        nodeStyle = {
          "background-color": nodeFill,
          "background-image": iconOf,
          // Icon pinned to the left edge; label fills the remaining width, so the
          // background is fixed-px (not %) and left-anchored rather than centered.
          "background-width": "26px", "background-height": "26px",
          "background-position-x": "14px", "background-position-y": "50%",
          "background-fit": "none", "background-clip": "node",
          "label": "data(label)", "text-valign": "center", "text-halign": "center",
          "text-wrap": "wrap", "text-max-width": "128px",
          // Nudge the centered label right of the icon so the two don't overlap.
          "text-margin-x": 18, "color": "#e8ebf0", "font-size": 11, "font-weight": 600,
          "border-width": 4, "border-color": "data(color)", "width": 196, "height": 50,
          "shape": "round-rectangle", "text-outline-width": 0,
        };
      } else {
        nodeStyle = {
          "background-color": nodeFill,
          "background-image": iconOf,
          "background-width": "50%", "background-height": "50%",
          "background-fit": "contain", "background-clip": "node",
          "label": "data(label)", "text-valign": "bottom", "text-halign": "center",
          "text-wrap": "wrap", "text-max-width": "120px",
          "text-margin-y": 7, "color": labelColor, "font-size": 12, "font-weight": 600,
          "border-width": 4, "border-color": "data(color)", "width": 52, "height": 52,
          "shape": "round-rectangle", "text-outline-width": 3, "text-outline-color": labelOutline,
        };
      }
      var s = [
        { selector: "node", style: nodeStyle },
        { selector: "node.current", style: { "border-width": 5 } },
        { selector: "edge", style: {
          "width": 2, "line-color": edgeColor,
          "target-arrow-color": edgeColor, "target-arrow-shape": "triangle",
          "arrow-scale": 1.1, "curve-style": "bezier",
        }},
      ];
      if (queued) {
        s.push({ selector: "edge", style: { "line-color": edgeColor, "line-style": "dashed" }});
        s.push({ selector: "node", style: { "cursor": "grab" }});
      }
      return s;
    }

    // Wide "card" node (title inside the rectangle) vs the default compact chip.
    function isCardNode() {
      return String($scope.config.nodeStyle || "chip").toLowerCase() === "card";
    }

    // Normalize config.orientation to one of LR|RL|TB|BT|GRID (default LR).
    function orientation() {
      var o = String($scope.config.orientation || "LR").toUpperCase();
      return (o === "RL" || o === "TB" || o === "BT" || o === "GRID") ? o : "LR";
    }

    // How much width the graph is actually allowed to use. Measured from the
    // viewport box's PARENT (.ztp-ag__graph-wrap, a plain block that always
    // spans the column) -- the box itself carries an inline width we set, so
    // reading it would just echo our own last guess back at us.
    //
    // Nothing used to measure this at all: every branch of sizeGraph derived
    // the box width from a hardcoded per-step stride, so on a col-lg-12 row
    // with 2265px available the graph pinned itself to 211px.
    function availWidth() {
      var inner = document.getElementById("ztp-cy");
      var box = inner && inner.parentElement;
      var host = box && box.parentElement;
      return (host && host.clientWidth) || (box && box.clientWidth) || 0;
    }

    // Per-step stride of the zig-zag grid. Card nodes are 196px wide, chips 52px
    // with a label up to 120px under them.
    function gridStride() {
      return isCardNode() ? { x: 230, y: 120 } : { x: 175, y: 118 };
    }

    // Column count for the zig-zag, from the width actually available -- NOT
    // ceil(sqrt(n)). sqrt gave a square regardless of the panel: 22 steps became
    // 5 columns / 1220px, which then had to be scaled down to fit a narrow panel
    // (or wasted most of a wide one). Shared by sizeGraph and layoutFor so the
    // surface and the layout can never disagree about the shape.
    function gridCols(n) {
      n = Math.max(1, n || 1);
      var avail = availWidth();
      var cols = avail > 0
        ? Math.floor((avail - GRAPH_PAD * 2) / gridStride().x)
        : Math.ceil(Math.sqrt(n));            // pre-attach: no measurement yet
      return Math.max(1, Math.min(n, cols));
    }

    function layoutFor(els) {
      // Prefer dagre (nice directed flow); fall back to the built-in breadthfirst
      // if the cytoscape-dagre extension didn't register (e.g. it loaded before
      // cytoscape/dagre). Register it defensively once.
      var C = $window.cytoscape;
      if (C && C.use && $window.cytoscapeDagre && !C._ztpDagreRegistered) {
        try { C.use($window.cytoscapeDagre); } catch (e) { /* already registered */ }
        C._ztpDagreRegistered = true;
      }
      var orient = orientation();
      // Zig-zag: pack steps into rows that wrap, so a long run stays readable
      // instead of one endless line.
      //
      // This is a `preset` with positions we compute, not cytoscape's `grid`.
      // `grid` fills strictly row-major, so step 5 (end of row 1) connected back
      // to step 6 (start of row 2) with an edge flying the full width of the
      // panel -- readable as a grid, but not as a FLOW, which is the whole point
      // of the graph. Odd rows are reversed (boustrophedon) so the run snakes:
      // each step is adjacent to the next one, and the row change is a short
      // vertical hop at whichever edge the run reached.
      if (orient === "GRID") {
        var cols = gridCols(els.nodes.length);
        var stride = gridStride();
        var pos = {};
        els.nodes.slice()
          .sort(function (a, b) { return (a.data.stepNumber || 0) - (b.data.stepNumber || 0); })
          .forEach(function (nd, i) {
            var row = Math.floor(i / cols);
            var col = i % cols;
            if (row % 2 === 1) col = cols - 1 - col;   // snake back on odd rows
            pos[nd.data.id] = { x: col * stride.x, y: row * stride.y };
          });
        return { name: "preset", fit: false, animate: false,
                 positions: function (n) { return pos[n.id()]; } };
      }
      if ($window.cytoscapeDagre) {
        // dagre rankDir accepts LR|RL|TB|BT directly.
        return { name: "dagre", rankDir: orient, nodeSep: 36, rankSep: 70, animate: false, fit: false };
      }
      var rootId = els.nodes.length ? els.nodes[0].data.id : undefined;
      var opts = { name: "breadthfirst", directed: true, circle: false, spacingFactor: 1.15, animate: false, fit: false };
      if (rootId) opts.roots = [rootId];
      return opts;
    }

    // Size the inner cytoscape surface to the step count + orientation so the
    // bounded .ztp-ag__cy viewport either shrinks to fit (few steps) or scrolls
    // (long run) instead of running off-screen or shrinking nodes to dots.
    // Horizontal flows grow in width; vertical flows grow in height; grid both.
    function sizeGraph(nodeCount) {
      var inner = document.getElementById("ztp-cy");
      var box = inner && inner.parentElement; // .ztp-ag__cy viewport
      if (!inner || !box) return;
      var orient = orientation();
      var n = Math.max(1, nodeCount || 0);
      var viewH = box.clientHeight || 380;
      // Card nodes are ~196px wide, so horizontal flows need a wider per-step
      // stride and the vertical column needs to be wider to hold them.
      var card = isCardNode();
      // Single source for the stride, shared with the zig-zag layout -- two
      // copies of these numbers is how the surface and the layout drift apart.
      var PER_H = gridStride().x, PER_V = 120, PAD = 70;
      // A card node is 196px wide + 8px of border and dagre pads 30px a side,
      // so a vertical column of cards needs ~264px. The old 220 was NARROWER than
      // the 240 used for 52px chips -- inverted, and it was what forced the
      // width-constrained zoom that squashed the whole run (see fitGraphTop).
      var VCOL = card ? 280 : 240;
      // The box uses border-box sizing, so its inner content area is (width - 2*border).
      // Make the box a few px WIDER than the inner surface so an exact-fit graph
      // doesn't trip a phantom scrollbar; a genuinely-too-wide run still clamps to
      // 100% and scrolls.
      var SLACK = 4;
      if (orient === "GRID") {
        var cols = gridCols(n);
        var rows = Math.ceil(n / cols);
        var cw = cols * PER_H + PAD;
        inner.style.width = cw + "px";
        inner.style.height = Math.max(viewH, rows * PER_V + PAD) + "px";
        box.style.width = "min(" + (cw + SLACK) + "px, 100%)";
      } else if (orient === "TB" || orient === "BT") {
        // Single column -- keep the box narrow (don't span the panel); the run
        // grows downward and scrolls.
        var vw = VCOL;
        inner.style.width = vw + "px";
        inner.style.height = Math.max(viewH, n * PER_V + PAD) + "px";
        box.style.width = "min(" + (vw + SLACK) + "px, 100%)";
      } else { // LR | RL
        var w = n * PER_H + PAD;
        inner.style.width = w + "px";
        inner.style.height = "100%";
        box.style.width = "min(" + (w + SLACK) + "px, 100%)";
      }
      box.style.maxWidth = "100%";
    }

    function renderGraph(steps, mode, retries) {
      retries = retries || 0;
      var els = zg.toElements(steps, { mode: mode, stepModule: STEP_MODULE });
      var container = document.getElementById("ztp-cy");
      if (!container) {  // view not linked yet -- retry briefly
        if (retries < 40) { $timeout(function () { renderGraph(steps, mode, retries + 1); }, 50); }
        return;
      }
      var C = $window.cytoscape;
      if (!C) { $scope.state = "error"; $scope.error = "Cytoscape failed to load."; return; }
      $scope.dark = detectDark();
      // Topology signature: orientation + the ordered node ids. When it's
      // unchanged (a status poll on the same run), we update node data IN PLACE
      // and skip re-layout/re-fit -- otherwise every poll re-fit nudged the zoom.
      var sig = orientation() + "|" + els.nodes.map(function (n) { return n.data.id; }).join(",");
      try {
        if (!cy) {
          // Size the surface BEFORE cytoscape reads the container, so the first
          // frame lands in roughly the right box; fitGraphTop then sets the
          // final size/zoom/pan from the real post-layout bounding box.
          sizeGraph(els.nodes.length);
          // NO `layout` option here: the constructor would run it before the
          // layoutstop handler below is bound, so the fit-and-top-align never
          // fired on first render and the graph kept cytoscape's own centred
          // fit. Bind the handlers first, then run the layout explicitly.
          cy = C({ container: container, elements: els, style: cytoscapeStyle(mode),
            wheelSensitivity: 0.2, minZoom: 0.4, maxZoom: 1.2,
          });
          cy.on("tap", "node", onNodeTap);
          cy.on("dragfree", "node", onDragFree);
          cy.on("layoutstop", fitGraphTop);
          $window.__ztpCy = cy; // expose for debugging / e2e node-tap driving
          cy.layout(layoutFor(els)).run();
          lastLayoutSig = sig;
          startCurrentPulse();
        } else if (sig === lastLayoutSig) {
          // Same run -- refresh status/label/color in place, preserve pan/zoom.
          // BOTH data AND classes must be re-applied: status/color live in data
          // (border-color: data(color)), but the "current" flag + status-*/mode
          // classes live in the class list. Updating only data froze the pulse and
          // class-keyed styling on whichever node was current at FIRST render, so a
          // poll that advanced the run (step 1 Complete → step 2 Running) never
          // moved the highlight. cy.node.classes(str) replaces the whole class set.
          els.nodes.forEach(function (nd) {
            var node = cy.getElementById(nd.data.id);
            if (node && node.length) {
              node.data(nd.data);
              if (nd.classes != null) node.classes(nd.classes);
            }
          });
          cy.style().json(cytoscapeStyle(mode));
          // Repaint the status ring explicitly, AFTER re-applying the stylesheet.
          // The sheet maps border-color to data(color), but replacing a node's
          // whole data object doesn't reliably re-run that mapper on the live
          // cytoscape build -- the ring stayed frozen at the first-render color
          // while the poll fetched new queueStatus. A direct per-element style
          // (bypass) always repaints and out-ranks the mapper, so the ring tracks
          // the live status.
          els.nodes.forEach(function (nd) {
            if (!nd.data.color) return;
            var node = cy.getElementById(nd.data.id);
            if (node && node.length) { node.style("border-color", nd.data.color); }
          });
          startCurrentPulse();
        } else {
          // Topology changed (steps added/removed, or the orientation config
          // changed) -- re-seed the surface and re-layout. The status-only poll
          // path above deliberately does NOT resize: it would re-inflate the
          // surface fitGraphTop had just sized and throw away the user's scroll.
          sizeGraph(els.nodes.length);
          cy.json({ elements: els });
          cy.style().json(cytoscapeStyle(mode));
          if (cy.resize) cy.resize();
          cy.layout(layoutFor(els)).run();
          lastLayoutSig = sig;
          startCurrentPulse();
        }
      } catch (e) {
        $scope.state = "error";
        $scope.error = "Graph render failed: " + (e && (e.message || e));
      }
    }

    var GRAPH_PAD = 16;

    // Fit + TOP-align the graph inside the bounded viewport, and size the surface
    // to what the layout actually produced.
    //
    // Why not the layout's own `fit`: it derives ONE uniform zoom from whichever
    // axis is tighter and then CENTERS the result in the container. For a TB run
    // in a narrow column that meant the WIDTH picked the zoom (a 196px card into
    // a 220px surface -> 0.79), the vertical extent shrank with it, and the
    // leftover height was split evenly above and below -- live on a 22-step run
    // that was pan.y 307 against a 367px viewport, i.e. the user scrolled to the
    // top and saw a whole screen of empty canvas before step 1. Fit also zoomed
    // IN on short runs, blowing the chips up.
    //
    // So: pick the zoom from the axis the viewport actually constrains (a
    // vertical/grid flow scrolls down, so only its width must fit; a horizontal
    // flow scrolls sideways, so only its height must), never magnify past 1,
    // size the surface to the content at that zoom so there is no slack left to
    // centre into, and pin the flow to the start of the scroll axis.
    function fitGraphTop() {
      if (!cy) return;
      var inner = document.getElementById("ztp-cy");
      var box = inner && inner.parentElement;   // .ztp-ag__cy viewport
      if (!inner || !box) return;
      var bb = cy.elements().boundingBox();
      if (!bb || !(bb.w > 0) || !(bb.h > 0)) return;
      var orient = orientation();
      var widthBound = (orient === "TB" || orient === "BT" || orient === "GRID");
      var availW = Math.max(1, box.clientWidth - GRAPH_PAD * 2);
      var availH = Math.max(1, box.clientHeight - GRAPH_PAD * 2);
      var z = widthBound ? availW / bb.w : availH / bb.h;
      z = Math.max(0.4, Math.min(1, z));
      var w = Math.max(availW, bb.w * z) + GRAPH_PAD * 2;
      var h = Math.max(availH, bb.h * z) + GRAPH_PAD * 2;
      inner.style.width = Math.round(w) + "px";
      inner.style.height = Math.round(h) + "px";
      if (cy.resize) cy.resize();
      cy.zoom(z);
      // Start of the scroll axis, centred on the other one. bb.x1/y1 are the
      // content's own origin (dagre does not start at 0), so subtract them.
      cy.pan({
        x: (widthBound ? (w - bb.w * z) / 2 : GRAPH_PAD) - bb.x1 * z,
        y: (widthBound ? GRAPH_PAD : (h - bb.h * z) / 2) - bb.y1 * z,
      });
      box.scrollTop = 0;
      box.scrollLeft = 0;
    }

    var pulseAnims = [];
    var pulseStopped = false;
    function stopCurrentPulse() {
      pulseStopped = true;
      for (var i = 0; i < pulseAnims.length; i++) { try { pulseAnims[i].stop(); } catch (e) { /* noop */ } }
      pulseAnims = [];
    }
    function startCurrentPulse() {
      stopCurrentPulse();
      if (!cy) return;
      // Blinking the current step is opt-out (config.blinkCurrent, default on).
      // Disabled → the .current node keeps its static thicker ring (§node.current
      // style) but doesn't breathe.
      if ($scope.config.blinkCurrent === false) return;
      pulseStopped = false;
      // cytoscape's animation() has NO loop/alternate options (they're silently
      // ignored -- the earlier version played border 5→10 ONCE and froze). Drive a
      // real loop by chaining grow→shrink on each animation's completion promise.
      // Pulse the ring WIDTH only so a Running node keeps its status color while it
      // breathes (a fixed color override buried the status).
      var LO = 5, HI = 12, DUR = 700, EASE = "ease-in-out-sine";
      cy.nodes(".current").forEach(function (n) {
        function step(toWidth, next) {
          if (pulseStopped || !cy) return;
          var a = n.animation({ style: { "border-width": toWidth }, duration: DUR, easing: EASE });
          pulseAnims.push(a);
          a.play().promise("complete").then(function () { if (!pulseStopped) next(); });
        }
        var grow = function () { step(HI, shrink); };
        var shrink = function () { step(LO, grow); };
        grow();
      });
    }

    // Tapping a node opens an in-widget detail modal (step info + an "Open"
    // button that deep-links the record). We show a modal rather than navigating
    // straight away so the user can read status/error/run-group in context first.
    function onNodeTap(evt) {
      var d = evt.target.data();
      if (!d || !d.recordId) return;
      $scope.selectedStep = {
        stepNumber: d.stepNumber,
        name: d.name || "",
        label: d.label || "",
        status: d.status || "unknown",
        color: d.color,
        runGroup: d.runGroup || "",
        error: d.error || "",
        recordId: d.recordId,
        url: "/modules/view-panel/" + STEP_MODULE + "/" + d.recordId,
      };
      $scope.$applyAsync();
    }
    $scope.selectedStep = null;
    $scope.closeStep = function () { $scope.selectedStep = null; };
    $scope.openSelectedStep = function () {
      var sel = $scope.selectedStep;
      if (!sel || !sel.url) return;
      if ($scope.config.openInNewTab) $window.open(sel.url, "_blank");
      else $window.location.href = sel.url;
    };

    function onDragFree() {
      // Queued-only, LOCAL reorder (visual). Persisting the new step-number order
      // is a mutating call -- OUT OF SCOPE per plan §8; captured here for a
      // future "Save order" action. Nothing is written to the box.
      if ($scope.mode !== "queued" || !cy) return;
      $scope.localOrder = cy.nodes().sort(function (a, b) {
        return a.position("x") - b.position("x");
      }).map(function (n) { return { id: n.data("recordId"), label: n.data("label") }; });
      $scope.$applyAsync();
    }

    function init() {
      deviceId = ($state.params && $state.params.id) || "";
      var dev = adoptDevice(getDevice());
      $scope.deviceName = (dev && dev.name) || deviceId || "";
      if (!zg) { $scope.state = "error"; $scope.error = "ztpGraph module failed to load."; return; }
      refresh();
    }

    $scope.$on("$destroy", function () {
      cancelPoll();
      stopCurrentPulse();
      if (cy) { try { cy.destroy(); } catch (e) {} cy = null; }
    });

    init();
  }
})();

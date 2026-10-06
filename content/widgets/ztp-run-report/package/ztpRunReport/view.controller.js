/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
// VIEW controller. The harness/SOAR resolves the controller name as
// `<name><numericVersion>DevCtrl` -- ztpRunReport1055DevCtrl for v1.0.0.
// `widget bump` rewrites this suffix on a version change; never hand-edit it.
//
// A fleet-level report over the ZTPf2 modules: every device, what its latest
// run group did, and what failed. The per-run picture lives in
// ztpAutomationGraph; this is the layer above it.
//
// All mapping/aggregation lives in widgetAssets/js/ztpReport.js (window.ztpReport)
// so it can be unit-tested without Angular. This controller only fetches,
// orchestrates, and owns the two exports.
(function () {
  angular
    .module("cybersponse")
    .controller("ztpRunReport1055DevCtrl", ztpRunReport1055DevCtrl);

  ztpRunReport1055DevCtrl.$inject = ["$scope", "config", "$http", "$window", "$timeout", "$q", "$sce", "$location"];

  function ztpRunReport1055DevCtrl($scope, config, $http, $window, $timeout, $q, $sce, $location) {
    var R = $window.ztpReport;
    var DEVICE_MODULE = "ztpf_devices";
    var STEP_MODULE = "ztpf_device_automation_steps";
    var GROUP_MODULE = "ztpf_run_groups";
    // Read ONLY to turn an action NAME into the uuid its arrow links to. The
    // fact cube knows actions by name (a groupby on a relation returns the
    // name and nothing else), and a widget cannot deep-link to a name. It is a
    // tiny module -- seventeen rows on the lab fleet -- so this is one cheap
    // query rather than a relation the step aggregate cannot project anyway.
    var ACTION_MODULE = "ztpf_automation_actions";

    $scope.config = angular.extend({}, {
      title: "ZTP Run Report",
      scope: "latest",          // latest | all -- which steps count per device
      runGroupLimit: 25,        // rows in the run-group table
      stepPage: 1000,           // step records to pull
      groupPage: 500,
      refreshSecs: 0,           // 0 = manual only
      layout: "groups",         // groups | answer | console | grid -- see LAYOUTS
      showTrend: true,
      showRunGroups: true,
      openInNewTab: true,       // deep links: new tab, or navigate in place
      // How many runs open themselves on load. A ZTP operator almost always
      // wants the run they just dispatched, and making them click to see it is
      // the single biggest thing that made this widget feel like a wall.
      autoExpandGroups: 1,
      // Phase lists to fetch BEFORE anyone clicks, so the first drill-down is
      // instant. Failed devices first -- they are what the click is for.
      // 0 turns prefetching off.
      prefetchDevices: 4,
      // How far back the run list reaches. The widget shipped with no date
      // axis, so it showed "the newest N runs" -- which is a different
      // question on a quiet box than on a busy one. A week is the batch an
      // operator is still answering for.
      range: "7d",
      // Tags are how this fleet is actually organised (a run carries its wave,
      // a device carries what kind of kit it is), so they are on by default.
      showTags: true,
      // Run Automation: pick devices, hand them to a Manual playbook. The
      // playbook is found by NAME at click time, so the same config works on
      // every box it is imported into (the uuid and route differ per box).
      showRunAutomation: true,
      automationPlaybook: "Add Steps to Device from Profile",
      automationDeviceStatus: "Ok"
    }, config || {});

    // TWO FOLDS OF ONE CUBE, not two widgets and not four.
    //
    // The filter panel and the summary band sit ABOVE this switch and belong
    // to neither view: a chip narrows the fact cube once, and each layout is
    // a different pivot of the same narrowed cube. That is what lets the two
    // agree by construction -- the device view is built from `runsView`, the
    // very rows the run view is drawing, so there is no second source for the
    // two to drift apart.
    //
    // The Answer and Console layouts are gone. Both were flat FLEET readings
    // that counted each device once in its latest run, while everything else
    // on the page counts device-runs inside the filtered window -- two
    // different questions stacked on one screen, which is exactly how a KPI
    // tile came to read "0 failed" above a list with two failures in it.
    // Charts sits FIRST, to the left of the two table pivots -- it is a third
    // reading of the same filtered cube (over time, and by facet), not a
    // fourth thing bolted onto the end of the list.
    $scope.LAYOUTS = [
      { id: "charts", label: "Charts",     hint: "Steps over time, and by facet", icon: "charts" },
      { id: "groups", label: "Run Groups", hint: "Run group -> its steps",        icon: "groups" },
      { id: "grid",   label: "Devices",    hint: "Device -> the steps of its last run", icon: "grid" }
    ];
    var LAYOUT_IDS = ["charts", "groups", "grid"];
    // Runs is the default because a ZTP device is almost never interesting on
    // its own: it was dispatched as part of a batch, and "did MY run work" is
    // the question. The flat layouts stay for fleet-wide sweeps.
    $scope.layout = LAYOUT_IDS.indexOf($scope.config.layout) >= 0
      ? $scope.config.layout : "groups";
    $scope.setLayout = function (id) {
      if (LAYOUT_IDS.indexOf(id) < 0) return;
      $scope.layout = id;
      // Switching to the device view needs the step rows its drill-downs are
      // built from. They are cached per run, so this is a no-op once warm.
      if (id === "grid") loadDeviceGridSteps();
      // Switching TO Charts mounts every chart-card div fresh -- c3 needs a
      // render pass the moment those bind targets exist, not just on the
      // next data change (see renderCharts()).
      if (id === "charts") $timeout(renderCharts, 0, false);
      writeUrlState();
      snapshot();
    };
    $scope.isLayout = function (id) { return $scope.layout === id; };

    // ---- Charts layout: which chart cards are minimized -------------------
    // Kept in the URL, not just in scope -- a minimized chart is a reading
    // preference for THIS dashboard link (an operator's "just show me the
    // pie charts" bookmark), and it has to survive a page reload and a
    // dashboard refresh (which remounts the whole controller, see the SESSION
    // note below) the same way. `history.replaceState` never touches the
    // widget's own network history and never fires a navigation, so it cannot
    // interfere with the host dashboard's own routing.
    var CHARTS_MIN_PARAM = "rrChartsMin";
    function readChartsMinFromUrl() {
      var out = {};
      try {
        var qs = ($window.location && $window.location.search) || "";
        var m = qs.match(new RegExp("[?&]" + CHARTS_MIN_PARAM + "=([^&]*)"));
        if (!m) return out;
        decodeURIComponent(m[1]).split(",").forEach(function (id) {
          if (id) out[id] = true;
        });
      } catch (e) { /* no location, or a sandboxed frame -- start blank */ }
      return out;
    }
    $scope.chartsMinimized = readChartsMinFromUrl();
    function writeChartsMinToUrl() {
      try {
        if (!$window.history || !$window.history.replaceState || !$window.location) return;
        var ids = Object.keys($scope.chartsMinimized).filter(function (id) {
          return $scope.chartsMinimized[id];
        });
        var loc = $window.location;
        var qs = (loc.search || "").replace(
          new RegExp("[?&]" + CHARTS_MIN_PARAM + "=[^&]*"), "");
        if (ids.length) {
          qs += (qs ? "&" : "?") + CHARTS_MIN_PARAM + "=" + encodeURIComponent(ids.join(","));
        }
        $window.history.replaceState(null, "", loc.pathname + qs + (loc.hash || ""));
      } catch (e) { /* sandboxed iframe with no history API -- state stays in scope only */ }
    }
    $scope.isChartMinimized = function (id) { return !!$scope.chartsMinimized[id]; };
    $scope.toggleChartMin = function (id) {
      $scope.chartsMinimized[id] = !$scope.chartsMinimized[id];
      if (!$scope.chartsMinimized[id]) delete $scope.chartsMinimized[id];
      writeChartsMinToUrl();
      snapshot();
      // Minimizing/expanding adds or removes this card's bind div -- see
      // renderCharts()'s chartCardVisible gate.
      $timeout(renderCharts, 0, false);
    };

    // ---- Charts layout: focus one chart full-width ------------------------
    // Same URL-survives-a-remount treatment as chartsMinimized, but a single
    // id rather than a set -- only one chart can be "the" chart at a time.
    // Focusing does not clear that chart's OWN minimized flag test -- a
    // focused chart is always shown open, so isChartMinimized is simply never
    // consulted for it (see the template gate).
    var CHART_FOCUS_PARAM = "rrChartFocus";
    function readChartFocusFromUrl() {
      try {
        var qs = ($window.location && $window.location.search) || "";
        var m = qs.match(new RegExp("[?&]" + CHART_FOCUS_PARAM + "=([^&]*)"));
        return m ? decodeURIComponent(m[1]) : "";
      } catch (e) { return ""; }
    }
    $scope.chartFocus = readChartFocusFromUrl();
    // A focus link is a link INTO the charts layout, not just a hint for once
    // you get there -- `layout` defaults to "groups" (see above), so a bare
    // rrChartFocus param would land on the run-group table with the chart it
    // named never mounted at all. The reverse case (chartsMinimized set,
    // chartFocus empty) is left alone: a minimized chart is a preference for
    // WHEN you do open Charts, not a reason to force you there.
    if ($scope.chartFocus) $scope.layout = "charts";
    function writeChartFocusToUrl() {
      try {
        if (!$window.history || !$window.history.replaceState || !$window.location) return;
        var loc = $window.location;
        var qs = (loc.search || "").replace(
          new RegExp("[?&]" + CHART_FOCUS_PARAM + "=[^&]*"), "");
        if ($scope.chartFocus) {
          qs += (qs ? "&" : "?") + CHART_FOCUS_PARAM + "=" + encodeURIComponent($scope.chartFocus);
        }
        $window.history.replaceState(null, "", loc.pathname + qs + (loc.hash || ""));
      } catch (e) { /* sandboxed iframe with no history API -- state stays in scope only */ }
    }
    $scope.isChartFocused = function (id) { return $scope.chartFocus === id; };
    $scope.hasChartFocus = function () { return !!$scope.chartFocus; };
    $scope.toggleChartFocus = function (id) {
      $scope.chartFocus = ($scope.chartFocus === id) ? "" : id;
      writeChartFocusToUrl();
      snapshot();
      // Focusing swaps which cards' bind divs exist in the DOM at all --
      // every other chart's div is removed by ng-if, not just resized.
      $timeout(renderCharts, 0, false);
    };

    // ---- Charts layout: c3 chart instances ---------------------------------
    // Point hover (both the line's tooltip and a donut's hole-centre echo),
    // legend click-to-toggle-visibility, and the y-axis/arc geometry itself
    // are now c3's own job -- see renderCharts() below. This widget only
    // hands c3 the DATA (lineChart/facetDonuts, built in applyFilter) and a
    // bind target; nothing here tracks a hover or a hidden-series map by
    // hand any more.
    //
    // One c3 instance per mount point, keyed the same way the template names
    // its divs ("line", "pie-<facetId>"). Destroyed and rebuilt (never
    // patched) on focus/minimize, because those change the CONTAINER's own
    // size and c3 does not notice a resize it wasn't told about -- see
    // c3charts' own renderChart for the equivalent "destroy before
    // re-generate" rule this mirrors.
    var charts = {};
    function chartDomId(id) { return "rr-chart-" + id + "-" + $scope.$id; }
    $scope.chartDomId = chartDomId;
    function destroyChart(id) {
      if (!charts[id]) return;
      try { charts[id].destroy(); } catch (e) { /* already torn down with its DOM */ }
      delete charts[id];
    }
    // c3.js loads from a dynamic <script> tag in view.html (see the comment
    // there) -- on a fast first paint the aggregate fetch can resolve before
    // the CDN download finishes, so window.c3 isn't there yet. Retry on a
    // short timer instead of failing silent, same fix c3charts already
    // shipped for the identical race (its c3-load-race test documents why).
    var c3RenderRetries = 0;
    function renderCharts() {
      if (!$scope.isLayout("charts") || !$scope.lineChart) return;
      if (typeof window === "undefined" || !window.c3 || !window.c3.generate) {
        if (c3RenderRetries++ < 100) { $timeout(renderCharts, 50, false); }
        return;
      }
      c3RenderRetries = 0;
      renderLineChart();
      $scope.FACETS.forEach(function (f) {
        if ($scope.facetDonuts[f.id]) renderPieChart(f.id);
        else destroyChart("pie-" + f.id);
      });
    }
    function chartCardVisible(id) {
      // Mirrors the template's own ng-if on a chart-card: focused-elsewhere
      // or minimized both remove the bind target from the DOM, and c3.generate
      // against a missing element throws.
      if ($scope.hasChartFocus() && !$scope.isChartFocused(id)) return false;
      return !$scope.isChartMinimized(id);
    }
    /** "bar" (stacked) is the default -- a day's steps are a total that
     *  breaks down by status, and a stack reads that total at a glance in a
     *  way four overlapping lines don't. "line" is kept one click away for
     *  anyone who wants to compare a single status's trend across buckets,
     *  which a stack makes harder to eyeball. */
    $scope.chartType = "bar";
    $scope.toggleChartType = function () {
      $scope.chartType = $scope.chartType === "bar" ? "line" : "bar";
      renderLineChart();
    };
    function renderLineChart() {
      destroyChart("line");
      if (!chartCardVisible("line") || !$scope.lineChart.columns.length) return;
      var el = document.getElementById(chartDomId("line"));
      if (!el) return;
      var isBar = $scope.chartType === "bar";
      charts.line = window.c3.generate({
        bindto: el,
        data: {
          x: "x",
          columns: [["x"].concat($scope.lineChart.categories)].concat($scope.lineChart.columns),
          type: isBar ? "bar" : "line",
          // Stacking is a `groups` entry, not a chart-type option -- without
          // it a "bar" type still draws four side-by-side bars per bucket.
          groups: isBar ? [$scope.lineChart.seriesLabels] : [],
          // `colors` is a `data.*` option, not a chart-root one -- c3 silently
          // falls back to its own default palette if it lands as a sibling of
          // `data` instead of inside it.
          colors: $scope.lineChart.colors,
          // Click-to-filter: narrow the rest of the dashboard to the bucket
          // that was clicked, the same "click a chart element" convention the
          // pie slices already use (see renderPieChart's onclick below).
          // `d.index` is the bucket position, which maps straight onto
          // lineChart.bucketStarts -- see toggleDateBucket for why the epoch
          // comes from there and not from re-parsing the display label.
          // Shift-click turns a single bucket into a RANGE from the first
          // click -- c3 doesn't pass the native event to onclick, but it
          // dispatches through d3's own click handler, which leaves
          // window.d3.event set for the duration of that dispatch, same as
          // any other d3 click callback would read it.
          onclick: function (d) {
            var shift = !!(window.d3 && window.d3.event && window.d3.event.shiftKey);
            $scope.$apply(function () { toggleDateBucket(d.index, shift); });
          }
        },
        axis: {
          x: {
            type: "category",
            // An hourly window can carry up to 72+ buckets -- one tick per
            // bucket has no room to draw and c3 wraps/clips each label to a
            // couple of unreadable characters (see the 72h screenshot this
            // fixed: "9/18 8p" truncated down to "9/1"). `culling` thins the
            // ticks c3 actually DRAWS to however many fit; the bucket data
            // itself is untouched, so hover/click still hit every bucket.
            tick: { culling: { max: $scope.lineChart.hourly ? 12 : 20 }, multiline: false,
                    rotate: $scope.lineChart.hourly ? 45 : 0 },
            height: $scope.lineChart.hourly ? 50 : 30
          },
          y: { padding: { bottom: 0 } }
        },
        point: { r: 3.5 },
        legend: { position: "bottom" }
      });
    }
    /** Clicking a bucket sets the Time Scale's own Date Range to that
     *  bucket's day/hour and re-fetches -- the SAME action as picking that
     *  window in the custom range picker, not a second, graph-local filter
     *  living beside it. A click used to narrow the chart's own reading in
     *  place while leaving the Time Scale row showing something else
     *  entirely, which was two different filters answering for one page.
     *
     *  SHIFT-clicking a second bucket turns that single day into a RANGE:
     *  the first click is the anchor, and every shift-click after it widens
     *  or narrows the span to run from the anchor through whatever was just
     *  clicked (in whichever order, so shift-clicking backwards from the
     *  anchor still works). The anchor is remembered by its epoch bounds,
     *  not by bucket index -- the click that follows re-fetches under the
     *  narrowed window, which rebuilds the chart under DIFFERENT buckets
     *  entirely (a 7-day view of days rescales to a view of hours), so an
     *  index from the old chart could never be compared against the new
     *  one. Leaving the range is one click on the "&times; clear" banner or
     *  another Time Scale chip, same as leaving any other custom pick. */
    var chartRangeAnchor = null;   // {start, end} of the bucket that opened this range
    function toggleDateBucket(index, extend) {
      var starts = $scope.lineChart && $scope.lineChart.bucketStarts;
      var ends = $scope.lineChart && $scope.lineChart.bucketEnds;
      if (!starts || starts[index] == null) return;
      var clickedStart = starts[index], clickedEnd = ends[index];
      if (extend && chartRangeAnchor) {
        setCustomRangeFromEpoch(Math.min(chartRangeAnchor.start, clickedStart),
                                 Math.max(chartRangeAnchor.end, clickedEnd));
      } else {
        chartRangeAnchor = { start: clickedStart, end: clickedEnd };
        setCustomRangeFromEpoch(clickedStart, clickedEnd);
      }
      $scope.range = "custom";
      $scope.customRangeOpen = false;
      $scope.load({ background: true });
    }
    $scope._toggleDateBucket = toggleDateBucket;
    function renderPieChart(facetId) {
      var id = "pie-" + facetId;
      destroyChart(id);
      var d = $scope.facetDonuts[facetId];
      if (!chartCardVisible(id) || !d || !d.columns.length) return;
      var el = document.getElementById(chartDomId(id));
      if (!el) return;
      charts[id] = window.c3.generate({
        bindto: el,
        data: {
          columns: d.columns, type: "donut", colors: d.colors,
          // Native click-to-filter, replacing the hand-drawn arc's own
          // data-ng-click -- same $scope.facetToggle the filter chips call,
          // so a slice and its chip are still the same action by
          // construction. $apply is needed: c3's click handler runs outside
          // Angular's digest.
          onclick: function (data) { $scope.$apply(function () { $scope.facetToggle(facetId, data.id); }); }
        },
        donut: { title: "Total: " + d.total, label: { format: function (v) { return v; } } },
        legend: {
          position: "right",
          // Overridden rather than left to c3's default (which hides the
          // clicked slice): a legend click here is a FILTER, the same
          // action clicking the slice itself performs, not a toggle of
          // what's drawn.
          item: { onclick: function (id) { $scope.$apply(function () { $scope.facetToggle(facetId, id); }); } }
        }
      });
    }

    // `loading` means THERE IS NOTHING TO SHOW -- it blanks the body. A timed
    // refresh must never set it: the data on screen is still true while the
    // next read is in flight, and tearing the page down to say so is the
    // flash. `refreshing` is the quiet counterpart, and it only dims a
    // timestamp -- nothing moves.
    $scope.loading = true;
    $scope.refreshing = false;
    $scope.error = null;
    $scope.refreshError = "";
    $scope.truncated = "";
    $scope.generatedAt = null;
    // ALWAYS A DOT. The search box lives inside an `ng-if`, which creates a
    // CHILD scope, and `ng-model` on a bare primitive writes a NEW property on
    // that child -- shadowing this one. The model updated, the controller never
    // saw it, and the table stayed unfiltered. Binding through an object goes
    // via the prototype chain and reaches this scope.
    $scope.filter = { q: "" };
    $scope.verdictFilter = {};       // verdict -> bool, empty object = no filter
    $scope.tagFilter = {};           // tag name -> bool, empty object = no filter
    $scope.tagVocab = [];            // [{name, count}] for the filter bar

    // ---- the facet filters ----------------------------------------------
    /** Six axes, each a {value: true} map. They are held in ONE object so the
     *  whole selection snapshots, clears and tests as a unit -- and so the
     *  template can drive every facet through the same three functions
     *  instead of six near-identical copies of them.
     *
     *  Every vocabulary below is derived from the run groups inside the
     *  current TIME SCALE, and from nothing else. The time scale is therefore
     *  not a seventh chip: it is the question the other six are asked about,
     *  which is why it gets a row to itself above them. */
    $scope.FACETS = [
      { id: "tag",       label: "Tag",              hint: "Tags on the run groups in this window" },
      { id: "group",     label: "Run group",        hint: "Which dispatches to show" },
      { id: "groupStatus", label: "Run Group Status", hint: "The run group's own outcome" },
      { id: "deviceStatus", label: "Device Status",  hint: "The device record's own status" },
      { id: "status",    label: "Step status",      hint: "How the step ended" },
      { id: "exception", label: "Step exception",   hint: "Whether the step's output was clean" },
      // HOW LONG IT TOOK, bucketed -- see R.DURATIONS for why the edges are
      // fixed rather than computed. Directly under the exception axis because
      // it answers the same shape of question: not "what ran" but "what about
      // the way it ran is worth a second look".
      { id: "duration",  label: "Step time",        hint: "How long the step took to run" },
      // The step's triggerKey: what KIND of automation it was. An action is a
      // sequence of steps of several kinds, so this axis finds every firmware
      // push across the actions that merely contain one. It sits ABOVE the
      // named action because it is the coarser cut of the same question.
      { id: "trigger",   label: "Automation action type", hint: "The trigger key on the step" },
      { id: "action",    label: "Automation action", hint: "The action behind each step" },
      { id: "device",    label: "Device",           hint: "Every device that appears in these runs" }
    ];
    var FACET_IDS = $scope.FACETS.map(function (f) { return f.id; });
    var FACET_BY_ID = {};
    $scope.FACETS.forEach(function (f) { FACET_BY_ID[f.id] = f; });
    // CHARTS reads the same facets in a different LAYOUT: the three
    // "which dispatch/tag/box" axes are their own row because they identify
    // WHO ran, and the rest -- how it went -- sit in a second row below
    // them. Reordering FACETS itself would also reorder the filter panel's
    // rows, which nobody asked for; these are template-only view orders,
    // each rendered into its OWN grid so the split is a real row break, not
    // just a DOM-order hint an auto-fit grid is free to ignore.
    $scope.CHART_FACETS_TOP = ["tag", "group", "device"].map(function (id) { return FACET_BY_ID[id]; });
    $scope.CHART_FACETS_MID = ["groupStatus", "deviceStatus", "status", "exception"]
      .map(function (id) { return FACET_BY_ID[id]; });
    $scope.CHART_FACETS_BOTTOM = ["duration", "trigger", "action"]
      .map(function (id) { return FACET_BY_ID[id]; });
    function blankFacets() {
      var o = {};
      FACET_IDS.forEach(function (id) { o[id] = {}; });
      return o;
    }
    $scope.facet = blankFacets();        // axis -> {value: true}
    $scope.vocab = blankFacets();        // axis -> [{name, count}] (replaced on build)
    // Which axes are drawn expanded. A fleet can have eighty run groups and
    // sixty actions in one window; eighty chips above the list IS the wall
    // this widget was built to stop being. Anything past FACET_PEEK collapses
    // to the first few plus a "+N more", and the axis remembers its own state.
    $scope.facetOpen = {};
    $scope.FACET_PEEK = 8;
    // Below this many values, an axis never collapses at all -- "+2 more"
    // behind six short chips saved no room and just added a click for
    // nothing. Hiding only kicks in once there is a real crowd to trim.
    $scope.FACET_MIN_TO_HIDE = 6;
    // Axis -> how many chips actually FIT on the first line, measured from the
    // rendered row. FACET_PEEK is only the cap; the real limit is the width of
    // the tile, which no constant can know. See fitFacetRows.
    $scope.facetFit = {};
    $scope.RANGES = R.RANGES;
    $scope.range = R.rangeById($scope.config.range) ? $scope.config.range : "7d";

    // ---- custom date range --------------------------------------------
    // A fifth, freeform way to set the Time Scale, sitting beside the fixed
    // chips rather than inside R.RANGES -- its label is built from whatever
    // dates were picked, which the static chip row (rendered by "track by
    // r.id") has no way to show. Picking the SAME date for from and to means
    // "that whole day" -- an operator asking for one day types it once, not
    // twice -- so the time fields default to 00:00/23:59 and only need
    // touching to narrow further.
    $scope.customRange = { fromDate: "", fromTime: "00:00", toDate: "", toTime: "23:59" };
    $scope.customRangeOpen = false;
    $scope.toggleCustomRange = function () {
      $scope.customRangeOpen = !$scope.customRangeOpen;
    };
    /** `ng-model` on `input[type=date]` binds a Date object at LOCAL midnight
     *  of the picked day (Angular's own `input[date]` directive constructs it
     *  via `new Date(year, month, date)`, not `Date.UTC` -- confirmed live by
     *  reading the real input's DOM `.value` after typing into it). Two bugs
     *  found live from getting this wrong: first, string-concatenating the
     *  Date produced its `toString()` output glued to a time suffix, which
     *  `new Date()` could not parse, so every custom range silently failed to
     *  apply. Second, constructing the reverse direction with `Date.UTC`
     *  instead of local fields landed one calendar day EARLIER in any
     *  negative-UTC-offset zone -- invisible in a screenshot because the
     *  native date input renders low-contrast against this widget's dark
     *  theme, so it read as simply blank rather than wrong. Local getters
     *  throughout, both ways, is what keeps the picker, the fetch and the
     *  chart agreeing on which day was actually picked. */
    function toDateStr(v) {
      if (!v) return "";
      if (typeof v === "string") return v;
      var d = new Date(v);
      if (isNaN(d.getTime())) return "";
      function pad(n) { return n < 10 ? "0" + n : "" + n; }
      return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    }
    /** The picked window as epoch seconds, or null while incomplete. Reused by
     *  rangeFilters (the server-side fetch bound), isHourlyRange's custom
     *  counterpart, and the chart's own bucket span -- one function, so the
     *  fetch and the chart can never disagree about what "custom" means. */
    function customRangeBounds() {
      var c = $scope.customRange;
      var fromDate = c && toDateStr(c.fromDate);
      if (!fromDate) return null;
      var toDate = toDateStr(c.toDate) || fromDate;
      var start = new Date(fromDate + "T" + (c.fromTime || "00:00") + ":00");
      var end = new Date(toDate + "T" + (c.toTime || "23:59") + ":59");
      if (isNaN(start.getTime()) || isNaN(end.getTime()) || end < start) return null;
      return { startSec: Math.floor(start.getTime() / 1000), endSec: Math.floor(end.getTime() / 1000) };
    }
    $scope._customRangeBounds = customRangeBounds;
    $scope.isCustomRange = function () { return $scope.range === "custom"; };
    $scope.customRangeLabel = function () {
      var c = $scope.customRange;
      var from = c && toDateStr(c.fromDate);
      if (!from) return "Custom";
      var to = toDateStr(c && c.toDate) || from;
      return from === to ? from : (from + " - " + to);
    };
    /** Apply the picked dates as the Time Scale. Re-fetches, exactly as any
     *  other range change does -- see setRange. */
    $scope.applyCustomRange = function () {
      if (!customRangeBounds()) return;
      $scope.range = "custom";
      $scope.customRangeOpen = false;
      $scope.load({ background: true });
    };
    /** Leave the custom range entirely -- back to the configured default
     *  Time Scale, same as the widget's own cold-start range. */
    $scope.clearChartRange = function () {
      $scope.range = R.rangeById($scope.config.range) ? $scope.config.range : "7d";
      chartRangeAnchor = null;
      $scope.load({ background: true });
    };
    /** Set the custom range directly from picked epoch seconds -- what a chart
     *  bucket click (or a shift-click range) hands in, see toggleDateBucket.
     *  Formats back into the same fromDate/fromTime fields the picker itself
     *  edits, so the two stay one representation. */
    function setCustomRangeFromEpoch(startSec, endSec) {
      function parts(sec) {
        var d = new Date(sec * 1000);
        function pad(n) { return n < 10 ? "0" + n : "" + n; }
        // A Date object at LOCAL midnight -- the same shape Angular's own
        // input[type=date] directive puts in the model (see toDateStr's
        // comment: UTC midnight lands a day early once extracted with local
        // getters, which read as the field going blank on this dark theme).
        var date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        var time = pad(d.getHours()) + ":" + pad(d.getMinutes());
        return { date: date, time: time };
      }
      var from = parts(startSec);
      // The bucket's END is exclusive (bucketNext's boundary), so the last
      // wall-clock second actually IN the bucket is one second earlier --
      // showing the boundary itself in the "to" field would read as the
      // window running one hour/day longer than what was clicked.
      var to = parts(Math.max(startSec, endSec - 1));
      $scope.customRange = { fromDate: from.date, fromTime: from.time,
                              toDate: to.date, toTime: to.time };
    }
    // Bound by ng-repeat, so it must be a STABLE reference -- see view.html.
    $scope.VERDICTS = ["failed", "running", "pending", "healthy"];
    $scope.expanded = {};            // device name -> bool (flat layouts)
    $scope.devices = [];
    $scope.groups = [];
    $scope.kpi = null;

    // ---- groups layout state ---------------------------------------------
    // Keyed by NAME / "<group>::<device>", never by object reference: every
    // rebuild (and every auto-refresh) produces fresh row objects, so a
    // reference-keyed open state would silently collapse the whole tree on the
    // first refresh. Same reason $scope.selectedName exists below.
    $scope.tree = [];                // all run groups, devices attached
    $scope.treeView = [];            // the filtered slice actually rendered
    $scope.openGroup = {};           // group name -> bool
    $scope.openDevice = {};          // "<group>::<device>" -> bool
    $scope.phases = {};              // "<group>::<device>" -> phase rows
    $scope.phaseState = {};          // same key -> "loading" | "error" | "ok"
    $scope.phaseError = {};          // same key -> message
    $scope.phasePending = {};        // same key -> bool, a request is in flight

    // ---- ZTPF run list state ---------------------------------------------
    $scope.runs = [];                // run groups in range, facts attached
    $scope.runsView = [];            // the filtered runs -- what every total counts
    $scope.runsShown = [];           // runsView capped at the row limit -- what the list draws
    $scope.runRowsExtra = 0;         // rows added by "show more"
    $scope.summary = null;           // recomputed from runsView, always
    $scope.verdictLine = null;
    $scope.stepRows = {};            // run name -> step rows (all of them)
    $scope.stepState = {};           // run name -> "loading" | "error" | "ok"
    $scope.stepError = {};           // run name -> message

    // ---- device view state ------------------------------------------------
    // Rebuilt from runsView on every filter pass, so it is a pivot of the
    // rows on screen rather than a second reading of the box.
    $scope.deviceGrid = [];
    $scope.openDeviceRow = {};       // device name -> bool
    $scope.deviceStepIndex = {};     // device name -> its filtered step rows

    // ---- step drill-down state --------------------------------------------
    // The step's rendered report (outputMarkdown), fetched per step on expand.
    // Keyed by the step's uuid, which is the only thing unique across runs.
    $scope.openStep = {};            // step uuid -> bool
    $scope.stepDoc = {};             // step uuid -> markdown text
    $scope.stepDocState = {};        // step uuid -> "loading" | "error" | "ok" | "empty"
    $scope.stepDocError = {};        // step uuid -> message
    // The RENDERED report, as a trusted-HTML value. CACHED, and that is not an
    // optimisation: $sce.trustAsHtml returns a NEW wrapper object every call,
    // so rendering inside the template expression hands ng-bind-html a
    // different value on every digest and the digest never settles
    // ($rootScope:infdig -- a page that renders its text and then silently
    // stops applying ng-class).
    $scope.stepDocHtml_ = {};        // step uuid -> $sce trusted html
    $scope.stepDocRaw = {};          // step uuid -> bool, show the source

    // ---- surviving a dashboard refresh -----------------------------------
    /** The FortiSOAR dashboard has an auto-refresh of its own
     *  (`config.refreshInterval`, in minutes), and it does not ask the widget
     *  to update -- it DESTROYS the tile and constructs the controller again
     *  from nothing. That is the page flash: not a redraw, a remount. Every
     *  in-place trick the background refresh path uses is bypassed, because
     *  the scope those tricks protect no longer exists.
     *
     *  Nothing in a widget can refuse a remount. What it can do is refuse to
     *  start from an empty page: the last good render is parked on $window,
     *  which outlives the controller, and the new instance paints it on its
     *  FIRST digest -- before any request goes out. The fetch then happens in
     *  the background, exactly as it would have. What the eye sees is the same
     *  page continuing, which is what "seamless" means here.
     *
     *  Keyed by title so two tiles of this widget on one board keep their own
     *  state. Nothing here is persisted beyond the page: a reload starts clean.
     */
    var SESSION = $window.__ztpRunReportSession ||
                  ($window.__ztpRunReportSession = {});
    // The key carries the CONFIG, not just the title. Restoring a snapshot
    // taken under different settings would silently defeat them -- change the
    // default range in the modal and the restored state would put the old one
    // straight back, which looks exactly like the setting not working. A
    // settings change lands on a different key, so it mounts clean.
    var SESSION_KEY = "t:" + ($scope.config.title || "ztpRunReport") + "|" +
      [$scope.config.range, $scope.config.scope, $scope.config.layout,
       $scope.config.runGroupLimit, $scope.config.groupPage,
       $scope.config.stepPage, $scope.config.autoExpandGroups,
       $scope.config.prefetchDevices, $scope.config.showTags].join(",");
    // Long enough to cover any dashboard refresh interval, short enough that a
    // tile reopened much later loads fresh rather than showing stale numbers
    // with a stale timestamp under them.
    var SESSION_TTL_MS = 15 * 60 * 1000;

    // The rendered state, and the UI state that makes it feel continuous. The
    // phase CACHE rides along too -- an open run that had to re-fetch its
    // steps after every remount was the second-order flash.
    var SNAPSHOT_KEYS = ["tree", "groups", "allDevices", "allDeviceRecords", "devices", "treeView",
      "kpi", "runKpi", "headline", "runHeadline", "verdictSlices", "verdictDonut",
      "statusSlices", "statusDonut", "trend", "failures", "runGroupsTotal",
      "tagVocab", "truncated", "generatedAt", "selected",
      "openGroup", "openDevice", "phases", "phaseState", "phaseError",
      "verdictFilter", "tagFilter", "filter", "range",
      "facet", "vocab", "facetOpen", "facetsShown", "runs", "runsView", "runsShown", "runRowsExtra", "summary",
      "groupIds",
      "verdictLine", "summaryLines", "narrative", "facetFit",
      "verdictParts", "narrativeParts",
      "stepRows", "stepState", "stepError",
      "deviceGrid", "openDeviceRow", "deviceStepIndex", "layout",
      "openStep", "stepDoc", "stepDocState", "stepDocHtml_", "stepDocRaw",
      "actionIds", "deviceIds", "lineChart", "facetDonuts", "chartsMinimized", "chartFocus",
      "chartType", "customRange"];

    function snapshot() {
      var box = { at: Date.now(), data: {} };
      SNAPSHOT_KEYS.forEach(function (k) { box.data[k] = $scope[k]; });
      SESSION[SESSION_KEY] = box;
    }
    $scope._snapshot = snapshot;

    /** Returns true if a previous render was restored, in which case the
     *  caller must refresh in the BACKGROUND rather than showing a loader. */
    function restore() {
      var box = SESSION[SESSION_KEY];
      if (!box || !box.data || !box.data.tree) return false;
      if (Date.now() - box.at > SESSION_TTL_MS) { delete SESSION[SESSION_KEY]; return false; }
      SNAPSHOT_KEYS.forEach(function (k) {
        if (box.data[k] !== undefined) $scope[k] = box.data[k];
      });
      // A request that was in flight when the tile was destroyed never lands
      // in this instance, so anything mid-flight is reset rather than left
      // showing a spinner that can never resolve.
      $scope.phasePending = {};
      Object.keys($scope.phaseState || {}).forEach(function (k) {
        if ($scope.phaseState[k] === "loading") $scope.phaseState[k] = null;
      });
      Object.keys($scope.stepState || {}).forEach(function (k) {
        if ($scope.stepState[k] === "loading") $scope.stepState[k] = null;
      });
      // The whole point is not to paint a loader over a page we already have.
      // `loading` is initialised true for a genuine cold start, and leaving it
      // set here would show "Loading ZTP fleet data..." on top of a perfectly
      // good restored render -- the flash, preserved exactly.
      $scope.loading = false;
      $scope.error = null;
      return true;
    }
    $scope._restore = restore;
    // Global state deserves a way to clear it: the tests exercise many mounts
    // in one jsdom window, where a leaked snapshot would silently satisfy
    // assertions that are meant to prove a cold mount fetches.
    $scope._clearSession = function () { $window.__ztpRunReportSession = {}; };

    // ---- fetch -----------------------------------------------------------
    // Records are read through POST /api/query/<module> with __selectFields, NOT
    // a plain GET. A step record carries outputJSON, outputHTML, outputText and
    // script blobs, and a device record carries the manager's whole sourceData
    // dump: the unprojected step collection on a modest lab fleet is 14 MB, and
    // parsing that froze the browser tab outright -- no error, just a dead page.
    // The projection below is 4.4 MB for the same 779 records. `$fields` /
    // `$select` on a GET are accepted and silently ignored, so the query
    // endpoint is the only way to ask for less.
    //
    // Relation SUBfields cannot be projected: asking for "ztpfDevices.name"
    // drops the relation entirely rather than narrowing it, so the two relations
    // this widget joins on are requested whole.
    // `recordTags` projects fine and costs almost nothing (a short array of
    // strings), which is why tags are read here rather than through a second
    // query against the tags module.
    var DEVICE_FIELDS = ["name", "managementIP", "platform", "firmware", "adom",
      "status", "connectionStatus", "configStatus", "ztpfRunning", "ztpfArtifacts",
      "ztpfManagers", "recordTags", "uuid"];
    // `status` is the run group's OWN outcome, and it is now what the row's
    // verdict says -- see ztpReport.groupStatusVerdict. `modifyDate` backs the
    // completion stamp for a group the platform reported no duration for.
    // (`totalStepsCompletePercent` is absent on some boxes; nothing reads it
    // directly -- the bar computes its own percentage.)
    var GROUP_FIELDS = ["name", "totalDevices", "totalSteps", "totalStepsComplete",
      "totalStepsCompletePercent", "totalRunningTime", "totalRunningTimeSeconds",
      "status", "ztpfRunning", "recordTags", "createDate", "modifyDate", "uuid"];

    // Without an explicit $limit the platform serves a default page of 30. The
    // graph widget shipped that bug: a device on its second run returned a
    // fraction of its records and the picture looked complete.
    // The step axis is fetched as an AGGREGATE plus a failures-only slice, not
    // as a page of records. See ztpReport.deviceRowsFromAggregate for why -- in
    // short, a groupby on a relation returns a scalar where __selectFields
    // cannot, and the same fleet costs 1.2 KB instead of 5.7 MB.
    //
    // AGG_LIMIT is the platform's documented ceiling. It is not a nicety: an
    // aggregate response is SILENTLY truncated to $limit rows -- no
    // hydra:totalItems, no flag, nothing to tell a short answer from a complete
    // one ($limit=10 on this fleet returns a well-formed 10 rows summing to 34
    // of 955). The ONLY tell is rows === limit, which is why that check below
    // raises the same "Partial data" banner a short record page does.
    var AGG_LIMIT = 5000;

    // ---- the fact cube ---------------------------------------------------
    /** The filter substrate: one row per distinct
     *  (run, device, action, status, exception), with a step count and a time.
     *
     *  Every chip in the filter panel, every number in the summary and every
     *  run-row bar is a fold of THIS, which is why there is one query for the
     *  lot rather than one per axis. It has to be an aggregate and not a
     *  record page: a `groupby` on a relation returns the related record's
     *  name as a scalar, which `__selectFields` flatly cannot do -- projecting
     *  `ztpfDevices` drags the manager's entire sourceData dump along with it
     *  (that is the 14 MB that used to freeze the tab), and `ztpfAutomationActions`
     *  is the same shape.
     *
     *  Date-filtered server-side, for the same reason the run list is: the
     *  facet vocabularies must describe the window on screen, and an action
     *  chip offering something last seen in March is a chip that selects
     *  nothing. */
    var FACT_AGGREGATES = [
      { operator: "groupby", field: "ztpfRunGroups.name", alias: "grp" },
      { operator: "groupby", field: "ztpfDevices.name", alias: "device" },
      { operator: "groupby", field: "ztpfAutomationActions.name", alias: "action" },
      { operator: "groupby", field: "triggerKey", alias: "trigger" },
      // status is the OUTCOME; queueStatus is the worker-queue state, which is
      // routinely left at Running on a finished step. Both are fetched so the
      // outcome can be preferred and the queue state can still answer for a
      // record that has not produced an outcome yet -- see R.resolveStatus.
      { operator: "groupby", field: "status.itemValue", alias: "status" },
      { operator: "groupby", field: "queueStatus.itemValue", alias: "queueStatus" },
      { operator: "groupby", field: "outputStatus.itemValue", alias: "exception" },
      // The record's own finished flag. "Steps in flight" is a sum over THIS
      // and not over the status vocabulary, which reports finished steps as
      // Running whenever their queue row was never reset.
      { operator: "groupby", field: "stepDone", alias: "done" },
      // GROUPED, not summed. A duration bucket is a property of ONE step, and
      // a sum over a group can only say what the group cost in total -- "these
      // nine steps took forty minutes" never says whether that was one long
      // one. Grouping makes every row a set of steps that took the same time,
      // which is exactly what a bucket needs; the total is still recoverable
      // as clock x count, and R.stepFacts does that.
      { operator: "groupby", field: "stepTimeSeconds", alias: "secs" },
      // The step's OWN create time, so the "steps over time" chart can bucket
      // by when each step actually landed instead of when its run group
      // started -- see R.stepTimeSeries. Grouped, not read off a single
      // record: the cube has no per-record read, only this aggregate.
      { operator: "groupby", field: "createDate", alias: "when" },
      { operator: "countdistinct", field: "*", alias: "n" }
    ];

    /** The step list under ONE expanded run: the fact cube with the step's own
     *  name and number added, scoped to that run. Same shape, same reasons,
     *  and small -- a 22-step run is 22 rows of six short strings.
     *
     *  `in`, never `eq`: `eq` on a relation is SILENTLY IGNORED by this
     *  endpoint, and a filter that is ignored does not return nothing, it
     *  returns the whole table. */
    // Grouping by `uuid` makes every row exactly ONE step, which is what the
    // list renders -- and it is the only unique key available: the same device
    // running the same numbered step in two runs collides on every other
    // column, and a colliding `track by` is an ngRepeat:dupes throw.
    //
    // `outputStatusMessage` rides along because it is a short sentence and the
    // exception cell shows it on hover. `outputMarkdown` does NOT: it is a
    // whole rendered report per step, and a run of forty would be most of a
    // megabyte for text nobody has opened. It is fetched per step, on expand.
    //
    // A `max` over a timestamp column returns a FORMATTED UTC STRING, not the
    // epoch the record stores -- R.aggStamp converts it back.
    var GROUP_STEP_AGGREGATES = [
      { operator: "groupby", field: "uuid", alias: "uuid" },
      { operator: "groupby", field: "ztpfDevices.name", alias: "device" },
      { operator: "groupby", field: "stepNumber", alias: "stepNumber" },
      { operator: "groupby", field: "name", alias: "step" },
      { operator: "groupby", field: "ztpfAutomationActions.name", alias: "action" },
      { operator: "groupby", field: "triggerKey", alias: "trigger" },
      { operator: "groupby", field: "status.itemValue", alias: "status" },
      { operator: "groupby", field: "queueStatus.itemValue", alias: "queueStatus" },
      { operator: "groupby", field: "outputStatus.itemValue", alias: "exception" },
      { operator: "groupby", field: "outputStatusMessage", alias: "message" },
      { operator: "groupby", field: "stepDone", alias: "done" },
      { operator: "max", field: "stepStartTimestamp", alias: "startedAt" },
      { operator: "max", field: "stepStopTimestamp", alias: "finishedAt" },
      { operator: "sum", field: "stepTimeSeconds", alias: "secs" }
    ];

    var STEP_AGGREGATES = [
      { operator: "groupby", field: "ztpfDevices.name", alias: "device" },
      { operator: "groupby", field: "ztpfRunGroups.name", alias: "grp" },
      { operator: "groupby", field: "status.itemValue", alias: "status" },
      { operator: "groupby", field: "queueStatus.itemValue", alias: "queueStatus" },
      { operator: "sum", field: "stepTimeSeconds", alias: "secs" },
      { operator: "max", field: "createDate", alias: "newest" },
      { operator: "countdistinct", field: "*", alias: "total" }
    ];
    // Only FAILED steps come back as records -- the one place step detail is
    // read (the callout, the timeline, the CSV, the PDF). 4 of 955 on this fleet.
    var FAIL_FIELDS = ["stepNumber", "name", "triggerKey", "outputStatusMessage",
      "stepStopTimestamp", "modifyDate", "createDate", "uuid",
      "ztpfDevices", "ztpfRunGroups", "ztpfGroup"];

    // The phase list -- which named step passed, which failed, which has not
    // run yet -- is the ONE thing the aggregate cannot answer, so it is fetched
    // per (device, run), on expand, and cached.
    //
    // It is filtered on BOTH relations. The earlier version filtered on the
    // device alone, out of a well-founded fear of relation filters: `eq` on a
    // relation IS silently ignored, and a filter that quietly matches nothing
    // returns the whole table. But `in` is honoured on both, which is
    // measurable rather than a matter of trust -- an `in` against a run group
    // that does not exist returns 0 rows, where a silently-ignored filter
    // would return everything. That check is what licenses this.
    //
    // It matters a lot. A device's steps across EVERY run it has ever been in
    // is 251 rows / 1.5 MB on the lab fleet, of which the UI renders the 11
    // belonging to the run you opened. Scoped to the run, and with the two fat
    // relation objects dropped from the projection (they were only ever read
    // to do this same matching client-side, and at ~6 KB a row they were most
    // of the payload), the same list is 9.7 KB -- 157x smaller.
    //
    // `ztpfGroup` stays: it is a bare string, and some steps carry only that.
    var PHASE_FIELDS = ["stepNumber", "name", "triggerKey", "status", "queueStatus",
      "outputStatusMessage", "stepStartTimestamp", "stepStopTimestamp",
      "stepTimeSeconds", "createDate", "uuid", "ztpfGroup"];

    /** The step list for ONE run, every device in it, as an aggregate.
     *
     *  This replaced a per-DEVICE fetch. The run is the unit the operator
     *  dispatched and the unit they expand, and asking per device meant one
     *  request per row plus a device level they had to click through to reach
     *  the steps -- two clicks to see the thing the run is made of. */
    function fetchGroupSteps(groupName) {
      var url = "/api/query/" + STEP_MODULE + "?$limit=2000";
      var body = {
        logic: "AND",
        filters: [{ field: "ztpfRunGroups.name", operator: "in", value: [groupName] }],
        aggregates: GROUP_STEP_AGGREGATES
      };
      return $http.post(url, body).then(function (resp) {
        var d = (resp && resp.data) || {};
        return d["hydra:member"] || (angular.isArray(d) ? d : []);
      });
    }

    /** Fetch (once) and cache one run's steps. Cached on the run NAME, not on
     *  the row object, because every rebuild produces fresh rows -- a
     *  reference-keyed cache would miss on the first background refresh and
     *  re-query every open run on every tick. */
    function loadGroupSteps(g, opts) {
      var name = g && g.name;
      if (!name) return;
      var force = !!(opts && opts.force);
      if ($scope.stepState[name] === "loading") return;
      if ($scope.stepState[name] === "ok" && !force) return;
      // A forced re-read keeps the CURRENT rows on screen while it runs.
      // Setting "loading" would swap them for a spinner on every refresh tick,
      // which is the page flash again, one level down.
      if (!force) $scope.stepState[name] = "loading";
      $scope.stepError[name] = "";
      fetchGroupSteps(name).then(function (rows) {
        $scope.stepRows[name] = R.groupStepRows(rows || []);
        $scope.stepState[name] = "ok";
        applyFilter({ reopen: false });
        snapshot();
      }).catch(function (err) {
        if (force && $scope.stepRows[name]) return;
        $scope.stepState[name] = "error";
        $scope.stepError[name] = describe(err);
      });
    }
    $scope.loadGroupSteps = loadGroupSteps;
    $scope.retryGroupSteps = function (g) {
      $scope.stepState[g.name] = null;
      loadGroupSteps(g);
    };
    var NO_STEPS = [];
    $scope.stepsFor = function (g) { return (g && g.stepRows) || NO_STEPS; };
    $scope.stepStatusOf = function (g) { return $scope.stepState[g && g.name]; };
    $scope.stepMessage = function (g) { return $scope.stepError[g && g.name]; };

    // ---- one step's rendered report --------------------------------------
    /** `outputMarkdown` is the report a step produced -- the thing an operator
     *  opens a step to read. It is fetched ONE STEP AT A TIME, on expand.
     *
     *  It cannot ride along with the run's step list: it is a full rendered
     *  document per step, so a forty-step run would carry most of a megabyte
     *  of text that nobody has opened. That is the same mistake the
     *  unprojected step fetch made at 14 MB, one field down.
     */
    function fetchStepDoc(uuid) {
      var url = "/api/query/" + STEP_MODULE + "?$limit=1";
      var body = {
        logic: "AND",
        filters: [{ field: "uuid", operator: "eq", value: uuid }],
        __selectFields: ["uuid", "outputMarkdown", "outputStatusMessage"]
      };
      return $http.post(url, body).then(function (resp) {
        var d = (resp && resp.data) || {};
        var m = d["hydra:member"] || (angular.isArray(d) ? d : []);
        return m.length ? m[0] : null;
      });
    }

    function loadStepDoc(step) {
      var id = step && step.uuid;
      if (!id) return;
      if ($scope.stepDocState[id] === "loading") return;
      if ($scope.stepDocState[id] === "ok" || $scope.stepDocState[id] === "empty") return;
      $scope.stepDocState[id] = "loading";
      $scope.stepDocError[id] = "";
      fetchStepDoc(id).then(function (rec) {
        var text = (rec && rec.outputMarkdown) || "";
        $scope.stepDoc[id] = text;
        // Rendered ONCE, here, not per digest. R.renderMarkdown escapes the
        // report before it builds a single tag, so the HTML it returns is made
        // only of markup the widget itself emitted -- which is what makes
        // trusting it honest rather than a shrug.
        $scope.stepDocHtml_[id] = text ? $sce.trustAsHtml(R.renderMarkdown(text)) : null;
        // An empty report is a real answer -- plenty of steps produce none --
        // and it has to read differently from a failed fetch. A spinner that
        // resolves to nothing at all is indistinguishable from a broken one.
        $scope.stepDocState[id] = text ? "ok" : "empty";
        snapshot();
      }).catch(function (err) {
        $scope.stepDocState[id] = "error";
        $scope.stepDocError[id] = describe(err);
      });
    }
    $scope.loadStepDoc = loadStepDoc;

    $scope.isStepOpen = function (s) { return !!(s && $scope.openStep[s.uuid]); };
    /** Expand one step to its report. Steps with no uuid -- a row the
     *  aggregate returned without one -- are not expandable at all rather
     *  than expandable onto a permanent spinner. */
    $scope.toggleStep = function (s, $event) {
      if ($event) $event.stopPropagation();
      if (!s || !s.uuid) return;
      $scope.openStep[s.uuid] = !$scope.openStep[s.uuid];
      if ($scope.openStep[s.uuid]) loadStepDoc(s);
      snapshot();
    };
    $scope.stepDocOf = function (s) { return $scope.stepDoc[s && s.uuid] || ""; };
    /** The rendered report. Returns the CACHED trusted value -- see the note
     *  on stepDocHtml_ for why this must never render in the expression. */
    $scope.stepDocHtml = function (s) { return $scope.stepDocHtml_[s && s.uuid] || null; };
    // Raw markdown stays one click away. A renderer that quietly drops a
    // construct it does not handle is otherwise indistinguishable from a
    // report that never contained it.
    $scope.isStepRaw = function (s) { return !!(s && $scope.stepDocRaw[s.uuid]); };
    $scope.toggleStepRaw = function (s, $event) {
      if ($event) $event.stopPropagation();
      if (!s || !s.uuid) return;
      $scope.stepDocRaw[s.uuid] = !$scope.stepDocRaw[s.uuid];
    };
    /** SHOW EVERY REPORT IN THIS TABLE.
     *
     *  Opening a step's report one row at a time is right when you are
     *  hunting; it is wrong when you are reading the run, because the reports
     *  ARE the run's output and the alternative is thirty clicks and thirty
     *  separate scroll positions. This opens all of them at once, which is
     *  also the shape the PDF export has always had.
     *
     *  It is a TOGGLE, and the title says which way it will go: a control
     *  that only ever opens leaves the reader to shut thirty panels by hand.
     *  Steps with no uuid are skipped rather than opened onto a spinner that
     *  can never resolve, exactly as the per-row caret skips them. */
    $scope.allStepDocsOpen = function (rows) {
      var list = rows || [];
      var any = false;
      for (var i = 0; i < list.length; i++) {
        if (!list[i].uuid) continue;
        any = true;
        if (!$scope.openStep[list[i].uuid]) return false;
      }
      return any;
    };
    $scope.toggleAllStepDocs = function (rows, $event) {
      if ($event) $event.stopPropagation();
      var list = rows || [];
      var open = !$scope.allStepDocsOpen(list);
      list.forEach(function (st) {
        if (!st.uuid) return;
        $scope.openStep[st.uuid] = open;
        // Each report is its own small request, fired only for the rows that
        // have not been read yet -- loadStepDoc is a no-op on a cached one.
        if (open) loadStepDoc(st);
      });
      snapshot();
    };

    $scope.stepDocStatus = function (s) { return $scope.stepDocState[s && s.uuid]; };
    $scope.stepDocMessage = function (s) { return $scope.stepDocError[s && s.uuid]; };
    $scope.retryStepDoc = function (s, $event) {
      if ($event) $event.stopPropagation();
      if (!s || !s.uuid) return;
      $scope.stepDocState[s.uuid] = null;
      loadStepDoc(s);
    };

    function fetchPhases(deviceName, groupName) {
      var url = "/api/query/" + STEP_MODULE + "?$limit=500";
      var filters = [{ field: "ztpfDevices.name", operator: "in", value: [deviceName] }];
      if (groupName) {
        filters.push({ field: "ztpfRunGroups.name", operator: "in", value: [groupName] });
      }
      var body = {
        logic: "AND",
        filters: filters,
        __selectFields: PHASE_FIELDS,
        sort: [{ field: "stepNumber", direction: "ASC" }]
      };
      return $http.post(url, body).then(function (resp) {
        var d = (resp && resp.data) || {};
        return d["hydra:member"] || (angular.isArray(d) ? d : []);
      });
    }

    /** The date filter, server-side, as the query API will actually take it.
     *
     *  ISO-8601 -- NOT epoch. `createDate gte <number>` is a 500
     *  DriverException from this endpoint even though createDate is stored as
     *  an epoch float, so sending the number the record carries takes the
     *  whole widget down. Pinned by a test for exactly that reason. */
    function isoSec(sec) { return new Date(sec * 1000).toISOString().replace(/\.\d{3}Z$/, "Z"); }
    function rangeFilters() {
      if ($scope.range === "custom") {
        var b = customRangeBounds();
        if (!b) return [];
        return [
          { field: "createDate", operator: "gte", value: isoSec(b.startSec) },
          { field: "createDate", operator: "lte", value: isoSec(b.endSec) }
        ];
      }
      var from = R.rangeStartISO($scope.range);
      if (!from) return [];
      return [{ field: "createDate", operator: "gte", value: from }];
    }
    $scope._rangeFilters = rangeFilters;

    function fetchAll() {
      var short = [];
      function query(mod, fields, limit, sort, filters) {
        var url = "/api/query/" + mod + "?$limit=" + encodeURIComponent(limit);
        var body = { logic: "AND", filters: filters || [], __selectFields: fields,
                     sort: sort || [] };
        return $http.post(url, body).then(function (resp) {
          var d = (resp && resp.data) || {};
          var members = d["hydra:member"] || (angular.isArray(d) ? d : []);
          var total = d["hydra:totalItems"];
          if (total > members.length) {
            short.push(mod + " (" + members.length + " of " + total + ")");
          }
          return members;
        });
      }
      function aggregate(mod, aggregates, limit, filters) {
        var url = "/api/query/" + mod + "?$limit=" + encodeURIComponent(limit);
        return $http.post(url, { logic: "AND", filters: filters || [], aggregates: aggregates })
          .then(function (resp) {
            var d = (resp && resp.data) || {};
            var rows = d["hydra:member"] || (angular.isArray(d) ? d : []);
            if (rows.length >= limit) {
              short.push(mod + " aggregate (hit the " + limit + "-row ceiling)");
            }
            return rows;
          });
      }
      function failedSteps(limit) {
        var url = "/api/query/" + STEP_MODULE + "?$limit=" + encodeURIComponent(limit);
        var body = {
          logic: "AND",
          // A failure is an OUTCOME. Filtering the queue state here undercounted
          // the failure list: one lab box had 5 steps at queueStatus=Fail and
          // 16 at status=Fail, so eleven real failures never reached the UI.
          filters: [{ field: "status.itemValue", operator: "eq", value: "Fail" }],
          __selectFields: FAIL_FIELDS, sort: []
        };
        return $http.post(url, body).then(function (resp) {
          var d = (resp && resp.data) || {};
          var members = d["hydra:member"] || (angular.isArray(d) ? d : []);
          var total = d["hydra:totalItems"];
          if (total > members.length) {
            short.push("failed steps (" + members.length + " of " + total + ")");
          }
          return members;
        });
      }
      return $q.all({
        devices: query(DEVICE_MODULE, DEVICE_FIELDS, 500),
        actions: query(ACTION_MODULE, ["name", "uuid"], 500)
          // An action list the box will not serve costs the ARROWS, not the
          // page: every number here comes from the fact cube, so a failure
          // means those links are absent rather than dead.
          .catch(function () { return []; }),
        stepAgg: aggregate(STEP_MODULE, STEP_AGGREGATES, AGG_LIMIT),
        facts: aggregate(STEP_MODULE, FACT_AGGREGATES, AGG_LIMIT, rangeFilters()),
        failures: failedSteps(Number($scope.config.stepPage) || 1000),
        groups: query(GROUP_MODULE, GROUP_FIELDS, Number($scope.config.groupPage) || 500,
                      [{ field: "createDate", direction: "DESC" }], rangeFilters())
      }).then(function (res) {
        res.short = short;
        return res;
      });
    }

    function build(res, opts) {
      var background = !!(opts && opts.background);
      var devRows = R.deviceRowsFromAggregate(res.devices, res.stepAgg, res.failures,
                                              { scope: $scope.config.scope });
      // Steps-per-group and the per-group device list come out of the same
      // aggregate; only the failure count needs the detail slice.
      var groupRows = R.runGroupRowsFromAggregate(res.groups, res.stepAgg, res.failures, 0);

      $scope.allDevices = devRows;
      // The RAW device records, kept because the device grid needs identity
      // columns the fact cube cannot carry -- the device's own status
      // picklist above all.
      $scope.allDeviceRecords = res.devices || [];
      // name -> uuid, for the arrow beside an automation action.
      var actionIds = {};
      (res.actions || []).forEach(function (a) {
        if (a && a.name && a.uuid) actionIds[a.name] = a.uuid;
      });
      $scope.actionIds = actionIds;
      $scope.deviceIds = {};
      (res.devices || []).forEach(function (d) {
        if (d && d.name && d.uuid) $scope.deviceIds[d.name] = d.uuid;
      });
      // EVERY run group in the window, not the first `runGroupLimit` of them.
      // Slicing here made the display limit an ANALYSIS limit: the headline,
      // the charts and every KPI below describe `groups`, so a 2026-08-01 ->
      // today window on a box with 108 runs reported 25 of them and drew an
      // empty August -- the 25 newest all fell in the last week. The limit
      // now caps only the rows the list draws (`runsShown`, applyFilter).
      $scope.groups = groupRows;
      // The hierarchy is a RESHAPE of the same aggregate, not a second fetch --
      // the cube is already grouped by {device, group, status}. See
      // ztpReport.groupDeviceRows.
      $scope.tree = R.groupTree($scope.groups, res.stepAgg, res.failures, res.devices);

      // ---- the run/step model the ZTPF board actually renders ------------
      // Note this hangs off `groups`, the RANGE-FILTERED run list, and the
      // fact cube is range-filtered by the same bound. The two agree by
      // construction, which is the only way the chip counts can be trusted:
      // a vocabulary built from a wider fetch than the list would offer chips
      // that select nothing.
      var groupStatusIndex = {};
      $scope.groups.forEach(function (g) { groupStatusIndex[g.name] = g.status; });
      var deviceStatusIndex = {};
      (res.devices || []).forEach(function (d) {
        // The device record's own `status` field (e.g. "Ok") is the fleet's
        // real health reading -- `connectionStatus` is a raw up/down reachability
        // flag that reported "up" for devices the fleet itself called Ok, which
        // read as two disagreeing answers to the same question on one row.
        if (d && d.name) deviceStatusIndex[d.name] = R.pick(d.status);
      });
      $scope.runs = R.attachFacts($scope.groups,
        R.stepFacts(res.facts, groupStatusIndex, deviceStatusIndex));
      // Name -> uuid, the same trick the device and action arrows use: a step
      // row carries the run group's NAME, never its id.
      $scope.groupIds = {};
      $scope.runs.forEach(function (g) { if (g.uuid) $scope.groupIds[g.name] = g.uuid; });
      $scope.vocab = R.facetVocab($scope.runs);
      // A value can leave the window when the time scale narrows. Dropping it
      // from the live selection too stops the view being silently pinned to an
      // empty result by a chip that is no longer on screen -- which reads as
      // the widget being broken, not as the filter being stale.
      FACET_IDS.forEach(function (id) {
        var live = {};
        ($scope.vocab[id] || []).forEach(function (v) { live[v.name] = true; });
        Object.keys($scope.facet[id]).forEach(function (v) {
          if (!live[v]) delete $scope.facet[id][v];
        });
      });
      // The vocabulary comes from the RUNS on screen, not from a query. A
      // `groupby` on recordTags is a 500 from the aggregate endpoint, and the
      // tags worth offering are the ones present in the range being viewed
      // anyway -- a chip that selects nothing is worse than an absent chip.
      $scope.tagVocab = R.allTags($scope.tree);
      // A tag can leave the vocabulary when the range narrows. Dropping it
      // from the active filter too stops the view from being silently pinned
      // to an empty result by a chip that is no longer on screen.
      var live = {};
      $scope.tagVocab.forEach(function (t) { live[t.name] = true; });
      Object.keys($scope.tagFilter).forEach(function (t) {
        if (!live[t]) delete $scope.tagFilter[t];
      });
      // The full count in the window. The list draws at most
      // config.runGroupLimit rows at a time and says so beside the list.
      $scope.runGroupsTotal = groupRows.length;

      // Everything downstream counts the SCOPED step set -- the steps the device
      // rows actually counted -- not the raw fetch. Feeding the raw fetch to the
      // KPIs while the table counted the latest run made "failed steps" read 2
      // above a table showing one failing device: the extra failure was in a
      // PREVIOUS run that the default scope deliberately excludes. A KPI that
      // disagrees with the table under it is worse than no KPI.
      var scoped = [];
      devRows.forEach(function (r) {
        for (var k in r.counts) {
          for (var i = 0; i < r.counts[k]; i++) scoped.push({ status: k });
        }
      });
      $scope.kpi = R.kpis(devRows, groupRows, scoped);
      // The donut counts DEVICES, not steps. A step-status mix answers "how
      // busy is the fleet"; the question this report exists for is "how many
      // devices actually finished", and those two disagree badly whenever
      // one failure is spread thin across a lot of completed work.
      $scope.verdictSlices = R.verdictTally(devRows);
      $scope.verdictDonut = R.donut($scope.verdictSlices, { cx: 90, cy: 90, r: 78, inner: 52 });
      // Step mix is kept for the drill-down panel, not the headline.
      $scope.statusSlices = R.statusTally(scoped);
      $scope.statusDonut = R.donut($scope.statusSlices, { cx: 60, cy: 60, r: 52, inner: 34 });
      $scope.headline = R.headline(devRows);
      $scope.trend = R.completionTrend(groupRows, { take: 24 });

      $scope.failures = devRows.reduce(function (a, r) { return a.concat(r.failures); }, [])
        .sort(function (a, b) { return (b.when || 0) - (a.when || 0); });

      $scope.truncated = res.short.length
        ? "Partial data: " + res.short.join(", ") + ". Totals below count only what was returned."
        : "";
      $scope.generatedAt = new Date();
      // After the digest that paints the body: the root is not in the DOM to
      // be measured until then, and on a remount it is a brand-new element
      // carrying nothing this instance set.
      $timeout(adoptHostSurface, 0);
      remeasureFacets();
      applyFilter({ reopen: !background });
      selectDefault();
      snapshot();
      // Opening a run is a courtesy on arrival, not something a timer may do
      // to a page someone is reading. A refresh that popped a newly-failed run
      // open under the cursor would be the same defect as the flash.
      if (!background) autoExpand();
      // Prefetch is a FIRST-LOAD courtesy. On a background refresh the cache is
      // already warm, and re-running it would re-issue the same queries every
      // minute for lists nobody has opened.
      if (!background) prefetchPhases();
    }

    /** Warm the phase cache for the devices someone is most likely to open.
     *
     *  Ordering is the whole point: FAILED devices in the runs that are open,
     *  then anything still running, and only then the rest. A drill-down into
     *  a failure is what this view exists for, and making that one instant is
     *  worth a handful of small queries; prefetching a fleet of healthy
     *  devices nobody will click is just load on the box.
     *
     *  Each fetch is the same cached, per-device read `toggleDevice` would
     *  make, so a click on a prefetched device costs nothing and a click on
     *  one we skipped behaves exactly as before. */
    function prefetchPhases() {
      var budget = Number($scope.config.prefetchDevices);
      if (!isFinite(budget) || budget <= 0) return;
      // NEITHER remaining layout has a per-device phase list any more: the run
      // view expands straight to its steps, and the device view reuses those
      // same rows. Warming a list nothing can click would be a handful of
      // queries per load for nothing.
      return;
      var open = [], running = [], rest = [];
      ($scope.treeView || []).forEach(function (g) {
        if (!$scope.openGroup[g.name]) return;   // only what is on screen
        (g.deviceRows || []).forEach(function (d) {
          if (d.verdict === "failed") open.push([g, d]);
          else if (d.verdict === "running") running.push([g, d]);
          else rest.push([g, d]);
        });
      });
      open.concat(running, rest).slice(0, budget).forEach(function (pair) {
        // Quiet: no "loading" state is shown for a list nobody has opened yet.
        loadPhases(pair[0], pair[1], { quiet: true });
      });
    }
    $scope._prefetchPhases = prefetchPhases;

    /** Open the newest run (or every failed one) so the page answers something
     *  before the first click. Only ever opens -- a group the user closed by
     *  hand stays closed across a refresh. */
    function autoExpand() {
      var n = Number($scope.config.autoExpandGroups);
      if (!isFinite(n) || n <= 0) return;
      var opened = 0;
      ($scope.runsShown || []).forEach(function (g) {
        if (opened >= n && g.verdict !== "failed") return;
        if ($scope.openGroup[g.name] === false) return;   // closed on purpose
        $scope.openGroup[g.name] = true;
        loadGroupSteps(g);
        opened += 1;
      });
    }

    function runRowCap() {
      return (Number($scope.config.runGroupLimit) || 25) + ($scope.runRowsExtra || 0);
    }
    /** Draw another page of run rows. Totals never change -- they already
     *  count every run in the window. */
    $scope.showMoreRuns = function () {
      $scope.runRowsExtra = ($scope.runRowsExtra || 0) + (Number($scope.config.runGroupLimit) || 25);
      $scope.runsShown = ($scope.runsView || []).slice(0, runRowCap());
    };

    function applyFilter(opts) {
      $scope.devices = R.filterDevices($scope.allDevices || [], $scope.filter.q, $scope.verdictFilter);
      $scope.bars = R.deviceBars($scope.devices);
      $scope.treeView = R.filterGroups($scope.tree || [], $scope.filter.q,
                                       $scope.verdictFilter, $scope.tagFilter);
      // Recomputed from the FILTERED tree: the numbers above the list always
      // describe the list, including while a chip is narrowing it.
      $scope.runKpi = R.runKpis($scope.treeView, $scope.runGroupsTotal);
      $scope.runHeadline = R.runHeadline($scope.treeView, $scope.runKpi);

      // The ZTPF run list, and the summary that has to agree with it. Both
      // come out of the same call: `runsView` carries only the facts that
      // matched, and `runSummary` is a sum over exactly those. That is what
      // "the summary keeps calculating by what is shown" means mechanically
      // -- there is no second source for it to drift from.
      $scope.runsView = R.filterRunGroups($scope.runs || [], $scope.facet, $scope.filter.q);
      // Only the DRAWN rows are capped; everything computed below still reads
      // the whole filtered `runsView`.
      $scope.runsShown = $scope.runsView.slice(0, runRowCap());
      $scope.summary = R.runSummary($scope.runsView);
      // Precomputed, never called from an ng-repeat expression: summaryLines
      // builds a fresh array, and a fresh array per digest is $rootScope:infdig.
      $scope.summaryLines = R.summaryLines($scope.summary);
      $scope.verdictLine = R.runVerdictLine($scope.runsView, $scope.summary);
      // THE NARRATIVE, computed here and never from a template expression: it
      // picks at random, so an expression would hand the digest a different
      // string every pass and never settle. Recomputing it per filter pass is
      // the point -- the paragraph is about the rows on screen, so it has to
      // be re-read when they change, and a fresh pick each time is what stops
      // it becoming furniture.
      $scope.narrative = R.reportNarrative($scope.runsView, $scope.summary,
                                           { rangeLabel: $scope.rangeLabel() });
      // The words in both sentences that are FILTER VALUES, split out here
      // and only READ by the template. Doing this in an expression would
      // return a fresh array every digest, which is the $rootScope:infdig
      // this widget has already arrived at twice.
      var linkIdx = R.linkIndex($scope.vocab, FACET_IDS);
      $scope.verdictParts = R.linkify($scope.verdictLine && $scope.verdictLine.text, linkIdx);
      $scope.narrativeParts = R.linkify($scope.narrative, linkIdx);

      // The address bar follows the view. Cheap and idempotent: it compares
      // the encoded state and does nothing at all when nothing moved, which
      // is most passes.
      writeUrlState();
      // CHARTS -- the same filtered runsView, two more ways to read it. Both
      // are computed unconditionally, same as verdictDonut/statusDonut above:
      // recomputing off the Charts tab is cheap next to the fetch, and gating
      // it on `isLayout('charts')` would mean the chart flashes empty for one
      // digest every time the tab is switched TO.
      // The chart reads the same facet/text-filtered runs everything else on
      // the page does -- a bucket click now narrows the Time Scale itself
      // (see toggleDateBucket), so there is no separate, wider reading for
      // the chart to keep around any more.
      var chartFacts = [];
      $scope.runsView.forEach(function (g) {
        (g.factsView || g.facts || []).forEach(function (f) { chartFacts.push(f); });
      });
      var customBounds = $scope.range === "custom" ? customRangeBounds() : null;
      $scope.lineChart = R.lineChartData(chartFacts, customBounds ? {
        hourly: (customBounds.endSec - customBounds.startSec) <= 3 * 86400,
        rangeStart: customBounds.startSec, rangeEnd: customBounds.endSec
      } : {
        hourly: R.isHourlyRange($scope.range),
        rangeDays: (R.rangeById($scope.range) || {}).days || 0
      });
      // A pie slice answers "how many STEPS", same unit the filter chips'
      // own vocab (`$scope.vocab`) now counts in too (see facetVocab's
      // docstring). chartFacetVocab is still its own function because it
      // reads the FILTERED `runsView` -- a pie describes the selection on
      // screen, where the chip vocab describes the whole window so a chip
      // that would select nothing never has to disappear.
      var chartVocab = R.chartFacetVocab($scope.runsView);
      var chartFacets = {};
      $scope.FACETS.forEach(function (f) {
        var vocab = chartVocab[f.id] || [];
        if (!vocab.length) return;
        chartFacets[f.id] = R.facetPieData(f.id, vocab);
      });
      $scope.facetDonuts = chartFacets;
      // c3 owns its own DOM once bound to it -- Angular's digest can rebuild
      // the data above every filter click, but the actual <svg> only redraws
      // when something explicitly hands it to c3. $timeout(fn, 0, false)
      // defers past the digest that just wrote lineChart/facetDonuts (and
      // past ng-if adding/removing chart-card DOM for a tab switch or a
      // focus/minimize toggle) so renderCharts() always finds real bind
      // targets, the same race c3charts' own renderChart already guards
      // against (see its view.controller.js and c3-load-race test).
      $timeout(renderCharts, 0, false);
      // An open run's step list is narrowed by the same chips, so the rows
      // under a run are the rows you asked for rather than the whole run with
      // them buried in it.
      $scope.runsView.forEach(function (g) {
        var all = $scope.stepRows[g.name];
        if (!all) return;
        g.stepRows = R.filterStepRows(all, $scope.facet, $scope.filter.q);
        g.stepsHidden = all.length - g.stepRows.length;
      });
      // THE DEVICE VIEW IS A PIVOT OF THE SAME ROWS. Built from runsView, so
      // one filter panel serves both layouts and the two can never disagree
      // about what is in scope -- see ztpReport.deviceGridRows.
      $scope.deviceGrid = R.deviceGridRows($scope.runsView, R.indexDevices($scope.allDeviceRecords || []));
      // PRECOMPUTED, same as the run rows above and for the same reason: a
      // template that calls a filtering function from inside an ng-repeat
      // rebuilds that list on every digest. It settles only because the rows
      // are the same objects each time -- one map() in the wrong place and it
      // is $rootScope:infdig, which presents as a page that renders its text
      // but silently stops applying ng-class.
      //
      // Keyed by device NAME, not hung off the row object. Every rebuild
      // produces fresh rows, so anything a caller holds a reference to goes
      // stale the moment a filter or a refresh runs -- the same rule
      // openGroup, phases and stepRows all already follow.
      //
      // ACROSS EVERY RUN, not just the last one. A device that took part in
      // four dispatches in the window used to show the steps of one of them,
      // with nothing on screen to say the other three existed -- which made
      // the grid a worse answer than the run view for the only question it is
      // the right shape for. The run group each row came from is now its
      // first column, because once the rows span several runs the step number
      // stops saying which sequence it belongs to.
      var stepIndex = {};
      $scope.deviceGrid.forEach(function (d) {
        stepIndex[d.name] = R.deviceStepRowsAcross(
          d.runGroups, $scope.stepRows, d.name,
          function (all) { return R.filterStepRows(all, $scope.facet, $scope.filter.q); });
      });
      $scope.deviceStepIndex = stepIndex;
      snapshot();
      // Searching is itself a drill-down: if the filter narrowed the tree to a
      // handful of runs, open them rather than making the user click again.
      // Gated on `reopen` so a background rebuild, which re-runs this with the
      // same query, cannot re-open a run the user closed after searching.
      if ((!opts || opts.reopen !== false) && $scope.anyFilter() && $scope.treeView.length <= 3) {
        $scope.treeView.forEach(function (g) { $scope.openGroup[g.name] = true; });
      }
      if ($scope.selectedName) resolveSelected();
    }
    $scope.applyFilter = applyFilter;

    // ---- facet filters ---------------------------------------------------
    $scope.facetToggle = function (axis, value) {
      var m = $scope.facet[axis];
      if (!m) return;
      if (m[value]) delete m[value]; else m[value] = true;
      applyFilter();
    };
    $scope.facetOn = function (axis, value) { return !!($scope.facet[axis] || {})[value]; };
    $scope.facetCount = function (axis) {
      return Object.keys($scope.facet[axis] || {}).length;
    };
    $scope.facetClear = function (axis) { $scope.facet[axis] = {}; applyFilter(); };
    /** Only the first FACET_PEEK chips are drawn until an axis is opened or
     *  measured. Eighty run-group chips stacked above the list is the wall
     *  this widget exists to not be -- but an axis with something SELECTED
     *  always draws in full, because a hidden active chip is a filter the
     *  user cannot see or undo.
     *
     *  Once fitFacetRows has MEASURED the row, its answer is the whole
     *  answer -- it is not re-capped at FACET_PEEK here. That second cap used
     *  to fire even when every chip on the line actually fit (a dozen short
     *  device names is one line, comfortably), so "+N more" appeared for
     *  values that never wrapped anything. FACET_PEEK is only the GUESS this
     *  falls back to before a real measurement exists. */
    function facetPeek(axis) {
      var fit = $scope.facetFit[axis];
      return fit > 0 ? fit : $scope.FACET_PEEK;
    }
    $scope.facetShown = function (axis) {
      var all = $scope.vocab[axis] || [];
      if (all.length <= $scope.FACET_MIN_TO_HIDE) return all;
      if ($scope.facetOpen[axis] || $scope.facetCount(axis)) return all;
      // Unmeasured: render the WHOLE vocabulary rather than pre-slicing to
      // FACET_PEEK. `.fc-shut .fc-chips` is `flex-wrap: nowrap; overflow:
      // hidden`, so anything past the tile's actual width is already clipped
      // from view -- but it still has to be IN THE DOM for fitFacetRows to
      // measure, or a vocabulary of, say, 12 short chips can never be
      // discovered to fit on one line: only the first FACET_PEEK of them
      // would ever be there to measure against. Once measured, slice to the
      // real answer so the DOM stops carrying values nobody can reach.
      var fit = $scope.facetFit[axis];
      return fit > 0 ? all.slice(0, fit) : all;
    };
    $scope.facetMore = function (axis) {
      var all = $scope.vocab[axis] || [];
      if (all.length <= $scope.FACET_MIN_TO_HIDE) return 0;
      return Math.max(0, all.length - facetPeek(axis));
    };
    /** "+N more" is offered only while the axis is SHUT.
     *
     *  It used to be offered whenever the axis had hidden values, which is
     *  still true after you open it -- so the button that opened the row
     *  stayed on screen beside the "Show fewer" that closes it, and clicking
     *  it again looked like a control that does nothing. One row, one state,
     *  one button. */
    $scope.facetCollapsible = function (axis) {
      return !$scope.facetOpen[axis] && !$scope.facetCount(axis) &&
             $scope.facetMore(axis) > 0;
    };
    $scope.facetExpand = function (axis) {
      $scope.facetOpen[axis] = !$scope.facetOpen[axis];
    };

    /** The six axes are hidden behind a Filters toggle. They are the widest
     *  thing on the page -- six rows of wrapping chips push the run list a
     *  couple of hundred pixels down the dashboard tile, and most sessions
     *  narrow once and then read the list. So the panel opens on demand.
     *
     *  The toggle carries the number of ACTIVE selections across every axis,
     *  because a closed panel hiding an active filter is the same unseeable
     *  state that facetShown() already refuses to create within an axis. The
     *  count, and the Clear filters button beside it, are how a filtered list
     *  still explains itself while the panel is shut. */
    /** The unmapped status values behind a run's "N unknown" badge, so the
     *  tooltip can name them. A value here means the box speaks a spelling the
     *  synonym table does not, which is a one-line fix once it is visible. */
    $scope.unknownList = function (g) {
      var m = (g && g.steps && g.steps.unknownValues) || {};
      return Object.keys(m).sort().join(", ") || "none";
    };
    // ---- the device view ---------------------------------------------------
    /** A device row expands to the steps of its LAST run -- the same rows the
     *  run view draws, filtered by the same chips, minus the device column
     *  (the row you opened already names the device).
     *
     *  Those rows come from the per-run step cache, so opening a device whose
     *  run is already expanded upstairs costs nothing at all. */
    $scope.isDeviceRowOpen = function (d) { return !!(d && $scope.openDeviceRow[d.name]); };
    /** Fetch the steps of every run this device appears in. Each is cached
     *  per run group and shared with the run view, so a run already expanded
     *  upstairs costs nothing here. */
    function loadDeviceRuns(d) {
      ((d && d.runGroups) || []).forEach(function (name) {
        loadGroupSteps({ name: name });
      });
    }
    $scope.toggleDeviceRow = function (d) {
      if (!d) return;
      $scope.openDeviceRow[d.name] = !$scope.openDeviceRow[d.name];
      if ($scope.openDeviceRow[d.name]) loadDeviceRuns(d);
      snapshot();
    };
    // ONE shared empty array, never a fresh `[]` -- see NO_PHASES below for
    // what a new array per digest costs.
    var NO_DEVICE_STEPS = [];
    /** This run's steps, narrowed by the SAME chips the run view applies and
     *  cut to this device. Computed in applyFilter, not here: see the note
     *  there. Skipping the chip pass would list steps the filter above says
     *  are out of scope. */
    $scope.deviceStepsFor = function (d) {
      return (d && ($scope.deviceStepIndex || {})[d.name]) || NO_DEVICE_STEPS;
    };
    /** One state for a row backed by SEVERAL run fetches.
     *
     *  Anything still loading keeps the row on the spinner -- a partial list
     *  that stops growing is indistinguishable from a complete one. Failure
     *  only wins once nothing is still in flight, and only when it left us
     *  with nothing to draw: a run that errored beside three that returned is
     *  reported through the hidden-steps line, not by blanking the row. */
    $scope.deviceStepState = function (d) {
      var names = (d && d.runGroups) || [];
      if (!names.length) return null;
      var loading = false, error = false, ok = false;
      names.forEach(function (n) {
        var st = $scope.stepState[n];
        if (st === "loading" || !st) loading = true;
        else if (st === "error") error = true;
        else if (st === "ok") ok = true;
      });
      if (loading) return "loading";
      if (ok) return "ok";
      return error ? "error" : null;
    };
    $scope.deviceStepError = function (d) {
      var names = (d && d.runGroups) || [];
      for (var i = 0; i < names.length; i++) {
        if ($scope.stepError[names[i]]) return $scope.stepError[names[i]];
      }
      return "";
    };
    $scope.retryDeviceSteps = function (d) {
      ((d && d.runGroups) || []).forEach(function (name) {
        $scope.stepState[name] = null;
      });
      loadDeviceRuns(d);
    };
    /** Re-read the step lists the OPEN device rows are drawing. Used when the
     *  layout is switched into, and by the background refresh. */
    function loadDeviceGridSteps() {
      ($scope.deviceGrid || []).forEach(function (d) {
        if ($scope.openDeviceRow[d.name]) loadDeviceRuns(d);
      });
    }
    $scope._loadDeviceGridSteps = loadDeviceGridSteps;
    $scope.expandAllDevices = function () {
      var rows = $scope.deviceGrid || [];
      var open = rows.some(function (d) { return !$scope.openDeviceRow[d.name]; });
      rows.forEach(function (d) {
        $scope.openDeviceRow[d.name] = open;
        if (open) loadDeviceRuns(d);
      });
    };

    // ---- the summary tiles are filter controls -----------------------------
    /** Clicking a summary number selects the filter that produces it.
     *
     *  The tile and the chip have to mean the same thing or this lies: the
     *  tile counts steps whose resolved status is Complete, and the chip it
     *  selects is that same value on that same axis, so the list below
     *  narrows to exactly the rows the number counted.
     *
     *  Re-clicking clears the axis, so a tile is a toggle rather than a trap
     *  -- and the panel opens, because a filter the user cannot see is the
     *  unseeable state this widget already refuses to create.
     */
    function selectFacet(axis, value) {
      var m = $scope.facet[axis] || ($scope.facet[axis] = {});
      var only = Object.keys(m).length === 1 && m[value];
      $scope.facet[axis] = {};
      if (!only) { $scope.facet[axis][value] = true; $scope.facetsShown = true; }
      applyFilter();
      snapshot();
    }
    $scope.selectFacet = selectFacet;
    $scope.filterComplete = function () { selectFacet("status", "Complete"); };
    $scope.filterFailed = function () { selectFacet("status", "Fail"); };
    $scope.filterExceptions = function () { selectFacet("exception", "Exceptions Found"); };
    $scope.filterRunning = function () { selectFacet("status", "Running"); };
    // The Queued tile counts every PENDING status (New/Preparing/Input
    // Needed/Ready/Queued -- see R.STATUS), the same bucket the run bar's
    // "queued" tooltip already reads. "Queued" is the one exact value in that
    // bucket the facet vocabulary is likely to carry, so it is the closest
    // single chip a click can select -- an approximation, not a lie: the tile
    // and the chip can drift apart on a box using one of the other pending
    // spellings, same as any other summary tile would with a synonym.
    $scope.filterQueued = function () { selectFacet("status", "Queued"); };

    /** A tile's number as a share of the steps on screen.
     *
     *  Of the STEPS, always -- never of the runs, never of the previous
     *  tile. Five tiles whose percentages are taken against five different
     *  denominators are five numbers that cannot be compared to each other,
     *  which is the only thing a row of tiles is for. */
    $scope.stepPct = function (n) {
      return R.pctOf(n, ($scope.summary && $scope.summary.steps) || 0);
    };

    /** The headline and the narrative are written out of the filter
     *  vocabulary, so the words in them ARE chips. Clicking one toggles it,
     *  exactly as clicking the chip would -- and, like the tiles, it opens
     *  the panel, because a filter the reader cannot see is the unseeable
     *  state this widget refuses to create. */
    $scope.partToggle = function (part) {
      if (!part || !part.axis) return;
      $scope.facetToggle(part.axis, part.value);
      $scope.facetsShown = true;
      snapshot();
    };

    $scope.facetsShown = false;
    $scope.toggleFacets = function () {
      $scope.facetsShown = !$scope.facetsShown;
      // The panel has no width to measure while it is shut, so the fit pass
      // has to wait for the digest that opens it.
      remeasureFacets();
    };
    $scope.facetTotal = function () {
      return FACET_IDS.reduce(function (n, id) { return n + $scope.facetCount(id); }, 0);
    };

    // ---- tag filter ------------------------------------------------------
    $scope.toggleTag = function (t) {
      $scope.tagFilter[t] = !$scope.tagFilter[t];
      if (!$scope.tagFilter[t]) delete $scope.tagFilter[t];
      applyFilter();
    };
    $scope.tagActive = function (t) { return !!$scope.tagFilter[t]; };
    $scope.clearTags = function () { $scope.tagFilter = {}; applyFilter(); };
    $scope.activeTags = function () { return Object.keys($scope.tagFilter); };

    /** Change the window the run list covers. This re-FETCHES, because the
     *  date filter is applied by the server -- narrowing client-side would
     *  still pull every run on the box and then hide most of them. */
    $scope.setRange = function (id) {
      if (!R.rangeById(id) || id === $scope.range) return;
      $scope.range = id;
      // Background, so changing the range never blanks the page.
      $scope.load({ background: true });
    };
    $scope.rangeLabel = function () {
      return $scope.range === "custom" ? $scope.customRangeLabel() : R.rangeLabel($scope.range);
    };

    // ---- selection (console layout) ---------------------------------------
    // Selecting by NAME, not by object reference: every rebuild produces new row
    // objects, and a reference-held selection would silently go stale on the
    // first auto-refresh -- the detail pane would keep rendering a device row
    // that no longer exists in the list beside it.
    $scope.selectedName = null;
    $scope.selected = null;
    function resolveSelected() {
      var rows = $scope.allDevices || [];
      $scope.selected = null;
      for (var i = 0; i < rows.length; i++) {
        if (rows[i].name === $scope.selectedName) { $scope.selected = rows[i]; break; }
      }
    }
    function selectDefault() {
      var rows = $scope.devices && $scope.devices.length ? $scope.devices : ($scope.allDevices || []);
      if (!rows.length) { $scope.selectedName = null; $scope.selected = null; return; }
      resolveSelected();
      if ($scope.selected) return;
      // Default to whatever the headline is about -- the device that needs
      // attention -- falling back to the first row.
      var focus = $scope.headline && $scope.headline.focus;
      $scope.selectedName = (focus && focus.name) || rows[0].name;
      resolveSelected();
    }
    $scope.selectDevice = function (d) {
      $scope.selectedName = d && d.name;
      resolveSelected();
    };
    $scope.isSelected = function (d) { return !!d && d.name === $scope.selectedName; };
    // Re-filter from a $watch rather than the input's ng-change: ng-change fires
    // only on a real user edit, and the watch also covers the value being set
    // any other way.
    $scope.$watch("filter.q", function (now, before) {
      if (now !== before) applyFilter();
    });

    /** `load({background: true})` refreshes IN PLACE: the current page keeps
     *  rendering until the new data is ready, then the rows update through
     *  their `track by` identities. A background load never blanks the body,
     *  never collapses what is open, and never drops the phase lists -- it
     *  re-reads the open ones and swaps each array when its answer lands.
     *
     *  The first load, and only the first, is allowed to show the empty state:
     *  there is genuinely nothing to render yet. */
    $scope.load = function (opts) {
      var background = !!(opts && opts.background) && !!$scope.generatedAt;
      if (background) {
        $scope.refreshing = true;
      } else {
        $scope.loading = true;
        $scope.error = null;
        $scope.phases = {};
        $scope.phaseState = {};
        $scope.phaseError = {};
        $scope.phasePending = {};
        $scope.stepRows = {};
        $scope.stepState = {};
        $scope.stepError = {};
      }
      fetchAll().then(function (res) {
        build(res, { background: background });
        $scope.loading = false;
        $scope.refreshing = false;
        $scope.refreshError = "";
        if (background) refreshOpenPhases();
      }).catch(function (err) {
        $scope.refreshing = false;
        $scope.loading = false;
        // A failed BACKGROUND read must not replace a good page with an error
        // panel. The numbers on screen were true a minute ago and are still
        // the best answer available; say the refresh failed and leave them.
        if (background) $scope.refreshError = "Refresh failed (" + describe(err) + "). Showing the last good read.";
        else $scope.error = describe(err);
      });
    };
    $scope.refresh = function () { $scope.load({ background: true }); };

    /** Re-read the phase lists that are currently OPEN, and only those. Each
     *  swaps its own array when it arrives, so an unchanged run redraws to the
     *  identical DOM (the `track by` on the phase key holds the nodes) and a
     *  changed one updates just the steps that moved. */
    /** Does this run still have a step ON SCREEN that has not finished?
     *
     *  THE BUG THIS FIXES: a run group whose own record has flipped to
     *  Complete is no longer "running", so the loop below used to skip it --
     *  and the step rows under it, fetched while it was still going, stayed
     *  exactly as they were. Two runs finished, both rows said Complete, and
     *  every step under them still read Running until the whole page was
     *  reloaded. The run's verdict is the WRONG question: it describes the
     *  dispatch, while the rows on screen are steps, and the steps are what
     *  went stale.
     *
     *  So the question asked here is about the rows themselves. `done` is the
     *  step record's own finished flag -- the one honest source for it -- and
     *  a step carrying it will never change again, so a list where every row
     *  is done is skipped and costs nothing. That is what keeps this from
     *  undoing the saving the verdict check was there for: a finished run
     *  full of finished steps is still never re-read. */
    function hasUnfinishedSteps(name) {
      var rows = $scope.stepRows[name];
      if (!rows || !rows.length) return false;
      for (var i = 0; i < rows.length; i++) {
        if (!rows[i].done) return true;
      }
      return false;
    }
    $scope._hasUnfinishedSteps = hasUnfinishedSteps;

    function refreshOpenPhases() {
      // Only runs that are STILL MOVING. A completed run's steps are immutable
      // -- re-reading them every minute is a query per open device that can
      // only ever return the same answer. On a board where most runs are
      // finished this is the difference between a refresh costing eight
      // queries and costing four.
      var live = {};
      ($scope.tree || []).forEach(function (g) {
        if (g.verdict === "running" || g.running) live[g.name] = true;
      });
      // Same rule for the run-level step lists: a finished run's steps are
      // immutable, so re-reading them on a timer can only ever return what is
      // already on screen.
      // Iterated over runsVIEW, not `runs`: the verdict is computed in
      // withFacts, on the filtered copies, so `runs` entries do not carry one
      // and every test against it would silently read undefined.
      ($scope.runsView || []).forEach(function (g) {
        if (!$scope.openGroup[g.name]) return;
        if (g.verdict === "running" || g.running || live[g.name] ||
            hasUnfinishedSteps(g.name)) {
          loadGroupSteps(g, { force: true });
        }
      });
      // The device view draws the per-run step lists too, so an open device
      // row on a still-moving run wants the same forced re-read.
      ($scope.deviceGrid || []).forEach(function (d) {
        if (!$scope.openDeviceRow[d.name]) return;
        (d.runGroups || []).forEach(function (name) {
          if (live[name] || hasUnfinishedSteps(name)) {
            loadGroupSteps({ name: name }, { force: true });
          }
        });
      });
      Object.keys($scope.openDevice).forEach(function (k) {
        if (!$scope.openDevice[k]) return;
        var cut = k.indexOf("::");
        if (cut < 0) return;
        var gname = k.slice(0, cut);
        if (!live[gname]) return;
        loadPhases({ name: gname }, { name: k.slice(cut + 2) }, { force: true });
      });
    }

    function describe(err) {
      if (!err) return "Unknown error.";
      if (err.status) return "HTTP " + err.status + ": " + (err.statusText || "request failed");
      return err.message || String(err);
    }

    // ---- filter chips ----------------------------------------------------
    $scope.toggleVerdict = function (v) {
      $scope.verdictFilter[v] = !$scope.verdictFilter[v];
      if (!$scope.verdictFilter[v]) delete $scope.verdictFilter[v];
      applyFilter();
    };
    $scope.verdictActive = function (v) { return !!$scope.verdictFilter[v]; };
    $scope.anyFacet = function () {
      for (var i = 0; i < FACET_IDS.length; i++) {
        if (Object.keys($scope.facet[FACET_IDS[i]] || {}).length) return true;
      }
      return false;
    };
    $scope.anyFilter = function () {
      return !!($scope.filter.q || Object.keys($scope.verdictFilter).length ||
                Object.keys($scope.tagFilter).length || $scope.anyFacet());
    };
    /** Clear everything -- and SHUT the panel.
     *
     *  The panel is the widest thing on the page and it only ever opened
     *  because something needed narrowing. Once nothing is selected it is a
     *  screenful of chips pushing the list below the fold, so clearing the
     *  filters and leaving it standing there finishes the gesture halfway.
     *  Re-opening it is one click, and the badge on that button still says
     *  zero, so nothing is hidden by closing it. */
    $scope.clearFilters = function () {
      $scope.filter.q = ""; $scope.verdictFilter = {}; $scope.tagFilter = {};
      $scope.facet = blankFacets();
      $scope.facetsShown = false;
      applyFilter();
      snapshot();
    };
    $scope.toggleExpand = function (name) { $scope.expanded[name] = !$scope.expanded[name]; };
    $scope.expandAll = function () {
      var open = $scope.devices.some(function (d) { return !$scope.expanded[d.name]; });
      $scope.devices.forEach(function (d) { $scope.expanded[d.name] = open; });
    };

    // ---- groups layout: expand, drill, deep-link --------------------------
    $scope.isGroupOpen = function (g) { return !!(g && $scope.openGroup[g.name]); };
    $scope.toggleGroup = function (g) {
      if (!g) return;
      // Explicit false, not delete: autoExpand() reads it to tell "never
      // touched" from "the user closed this".
      $scope.openGroup[g.name] = !$scope.openGroup[g.name];
      if ($scope.openGroup[g.name]) loadGroupSteps(g);
      snapshot();
    };
    /** Expand or collapse EVERYTHING in whichever view is on screen. One
     *  control, one label, because two buttons that each said "Expand all" and
     *  never said "collapse" made the second click look like a no-op. The verb
     *  follows the state: anything shut means the next click opens. */
    $scope.expandAllOpen = function () {
      if ($scope.isLayout("grid")) {
        return ($scope.deviceGrid || []).some(function (d) {
          return !$scope.openDeviceRow[d.name];
        });
      }
      return ($scope.runsShown || []).some(function (g) { return !$scope.openGroup[g.name]; });
    };
    $scope.expandCollapseAll = function () {
      if ($scope.isLayout("grid")) $scope.expandAllDevices();
      else $scope.expandAllGroups();
    };
    $scope.expandAllGroups = function () {
      var rows = $scope.isLayout("groups") ? ($scope.runsShown || []) : ($scope.treeView || []);
      var open = rows.some(function (g) { return !$scope.openGroup[g.name]; });
      rows.forEach(function (g) {
        $scope.openGroup[g.name] = open;
        if (open) loadGroupSteps(g);
      });
    };

    function phaseKey(g, d) { return (g && g.name ? g.name : g) + "::" + (d && d.name ? d.name : d); }
    $scope.phaseKey = phaseKey;

    $scope.isDeviceOpen = function (g, d) { return !!$scope.openDevice[phaseKey(g, d)]; };
    $scope.toggleDevice = function (g, d) {
      var k = phaseKey(g, d);
      $scope.openDevice[k] = !$scope.openDevice[k];
      if (!$scope.openDevice[k]) return;
      // Already warm from the prefetch: show it, no request, no spinner.
      if ($scope.phaseState[k] === "ok") return;
      // A quiet prefetch is in flight (it left no state behind on purpose).
      // Mark it loading so the row says so, and let the in-flight promise
      // land -- re-issuing the same query would just double the traffic.
      if ($scope.phasePending[k]) { $scope.phaseState[k] = "loading"; return; }
      loadPhases(g, d);
      snapshot();
    };

    /** Fetch (once) and cache the phase list for one device in one run.
     *  Cached on the key, not the row, so it survives a rebuild; a manual
     *  Refresh clears it, because a running device's phases go stale. */
    function loadPhases(g, d, opts) {
      var k = phaseKey(g, d);
      var force = !!(opts && opts.force);
      var quiet = !!(opts && opts.quiet);
      if ($scope.phaseState[k] === "loading") return;
      if ($scope.phaseState[k] === "ok" && !force) return;
      // A forced re-read keeps the CURRENT list rendered while it runs, and a
      // prefetch has nothing rendered to disturb. Setting "loading" in either
      // case would swap the steps for a spinner -- the flash again, one level
      // down -- or draw one under a row nobody has opened.
      if (!force && !quiet) { $scope.phaseState[k] = "loading"; }
      $scope.phasePending[k] = true;
      $scope.phaseError[k] = "";
      // The RUN is now part of the query, so what comes back is already this
      // run's steps and must NOT be re-filtered client-side. That re-filter
      // would reject all of them: it compares against `stepGroup`, which falls
      // back to the bare `ztpfGroup` string once the relation is dropped from
      // the projection -- and `ztpfGroup` holds a different identifier
      // entirely (an `add-...` batch id, not the run group name). Filtering on
      // it here would render "no steps" for every device on the box.
      fetchPhases(d.name, g.name).then(function (steps) {
        $scope.phasePending[k] = false;
        $scope.phases[k] = R.phaseRows(steps || []);
        $scope.phaseState[k] = "ok";
        // Park it: a remount should not have to re-fetch an open run's steps.
        snapshot();
      }).catch(function (err) {
        $scope.phasePending[k] = false;
        // Same rule as the page: a failed refresh leaves the last good list up.
        if (force && $scope.phases[k]) return;
        // A prefetch that fails is silent -- nothing is on screen to fail, and
        // the click that follows will retry it through the normal path.
        if (quiet) { $scope.phaseState[k] = null; return; }
        $scope.phaseState[k] = "error";
        $scope.phaseError[k] = describe(err);
      });
    }
    $scope.loadPhases = loadPhases;
    $scope.retryPhases = function (g, d) {
      var k = phaseKey(g, d);
      $scope.phaseState[k] = null;
      loadPhases(g, d);
    };
    // ONE shared empty array, never a fresh `[]`. An ng-repeat whose expression
    // returns a new array every digest never lets the digest settle
    // ($rootScope:infdig) -- and an aborted digest stops applying ng-class, so
    // the failure turns up as missing colours, not as an error anyone sees.
    var NO_PHASES = [];
    $scope.phasesFor = function (g, d) { return $scope.phases[phaseKey(g, d)] || NO_PHASES; };
    $scope.phaseStatus = function (g, d) { return $scope.phaseState[phaseKey(g, d)]; };
    $scope.phaseMessage = function (g, d) { return $scope.phaseError[phaseKey(g, d)]; };

    // ---- deep links -------------------------------------------------------
    // The view-panel route is the same one ztpAutomationGraph deep-links to.
    // A row with no uuid gets NO link rather than a dead one -- an href that
    // 404s reads as a broken widget, an absent one reads as a record we did
    // not fetch.
    function recordUrl(module, id) {
      return id ? "/modules/view-panel/" + module + "/" + id : "";
    }
    $scope.deviceUrl = function (d) { return recordUrl(DEVICE_MODULE, d && d.uuid); };
    /** The arrows on a STEP row resolve by NAME, because that is all the fact
     *  cube carries: a `groupby` on a relation returns the related record's
     *  name as a scalar and no id at all. The name -> uuid maps are built once
     *  per load from the two small record fetches. A name with no id gets NO
     *  arrow rather than a dead one -- an href that 404s reads as a broken
     *  widget, an absent one reads as a record we did not fetch. */
    $scope.deviceUrlByName = function (name) {
      return recordUrl(DEVICE_MODULE, ($scope.deviceIds || {})[name]);
    };
    $scope.groupUrlByName = function (name) {
      return recordUrl(GROUP_MODULE, ($scope.groupIds || {})[name]);
    };
    $scope.actionUrlByName = function (name) {
      return recordUrl(ACTION_MODULE, ($scope.actionIds || {})[name]);
    };
    $scope.groupUrl = function (g) { return recordUrl(GROUP_MODULE, g && g.uuid); };
    $scope.stepUrl = function (p) { return recordUrl(STEP_MODULE, p && p.uuid); };
    /** Open a record. Takes the click event so the row's own expand handler
     *  does not also fire -- a link that expands the thing you are leaving is
     *  the kind of detail that makes a page feel unfinished. */
    $scope.openRecord = function (url, $event) {
      if ($event) { $event.preventDefault(); $event.stopPropagation(); }
      if (!url) return;
      if ($scope.config.openInNewTab) $window.open(url, "_blank");
      else $window.location.href = url;
    };

    // ---- an opaque surface, in whatever theme the host is wearing --------
    /** The export menu has to be OPAQUE -- a dropdown you can read the table
     *  through is not a dropdown. That is the one colour this widget cannot
     *  get from its own palette: every other surface here is a translucent
     *  grey laid over the host's background, which is precisely why the
     *  palette has never needed to know what that background IS, and why the
     *  same stylesheet survives every FortiSOAR theme.
     *
     *  CSS alone cannot answer it. `Canvas` -- the obvious candidate -- is the
     *  BROWSER's page colour for the OS colour scheme, not the application's
     *  theme, so on a dark theme under a light OS it resolves to white. That
     *  was a white menu on the steel theme, which is the bug this replaced.
     *
     *  So it is read off the rendered page: walk up from the widget root to
     *  the first ancestor that paints a non-transparent background, and
     *  publish it as --rr-pop. That is the colour the menu is actually
     *  sitting on, by construction, whatever the theme is called.
     *
     *  Best-effort throughout. If the walk finds nothing (a themed gradient,
     *  an image, a detached node) the property is never set and the
     *  stylesheet's own fallback -- a heavy scrim plus a backdrop blur --
     *  takes over, which is legible on a light or a dark host without knowing
     *  which one it is. */
    var TRANSPARENT = /^\s*(transparent|rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\))\s*$/i;
    function adoptHostSurface() {
      var doc = $window.document;
      if (!doc || !doc.querySelectorAll || !$window.getComputedStyle) return;
      // querySelectorAll, not a held reference: the controller is created by
      // ng-controller, so there is no $element local to inject, and two tiles
      // of this widget on one board each need their own value.
      var roots = doc.querySelectorAll(".ztp-rr");
      for (var i = 0; i < roots.length; i++) {
        var el = roots[i], found = "";
        for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
          var bg = "";
          try { bg = $window.getComputedStyle(n).backgroundColor; } catch (e) { break; }
          if (bg && !TRANSPARENT.test(bg)) { found = bg; break; }
          if (n === doc.documentElement) break;
        }
        if (found && el.style && el.style.setProperty) {
          el.style.setProperty("--rr-pop", found);
        }
      }
    }
    $scope._adoptHostSurface = adoptHostSurface;

    /* ---- a collapsed facet row is ONE line ------------------------------
     *
     *  FACET_PEEK alone cannot deliver that. Eight chips is two lines of
     *  run-group names and half a line of statuses, so the cap either wraps
     *  the row it was meant to bound or wastes the width it was given -- and
     *  which one depends on the vocabulary, the theme's font and how wide the
     *  operator made the dashboard tile. None of that is knowable from a
     *  constant, so it is MEASURED, the same argument as the menu's surface
     *  colour one function above.
     *
     *  The pass runs against a row rendered at the full PEEK, so the chips it
     *  needs to measure are in the DOM, and it reserves room for the "+N
     *  more" button before deciding what fits -- a row that fits exactly and
     *  then wraps its own affordance is the bug, not the fix. An axis whose
     *  whole vocabulary fits keeps all of it and gets no button.
     *
     *  Nothing here reads a scope value the template also writes, and the fit
     *  is applied inside $apply, so it settles in one extra digest. */
    var CHIP_GAP = 5;          // .fc-chips gap, in px -- keep with the CSS
    var MORE_RESERVE = 84;     // widest "+NN more" the button ever draws

    function fitFacetRows() {
      var doc = $window.document;
      if (!doc || !doc.querySelectorAll) return;
      var rows = doc.querySelectorAll(".ztp-rr .rr-facet[data-axis]");
      var next = {}, changed = false;
      for (var i = 0; i < rows.length; i++) {
        var axis = rows[i].getAttribute("data-axis");
        if (!axis) continue;
        // An open or an active axis draws in full by design, so there is
        // nothing to fit and measuring it would record a bogus width.
        if ($scope.facetOpen[axis] || $scope.facetCount(axis)) continue;
        var box = rows[i].querySelector(".fc-chips");
        if (!box) continue;
        var avail = box.clientWidth;
        if (!avail) continue;                 // not laid out yet
        var chips = box.querySelectorAll(".fc-chip");
        var total = ($scope.vocab[axis] || []).length;
        var full = countFitting(chips, avail);
        // Only pay for the button when there is actually something behind it.
        var fit = (full >= total) ? full : countFitting(chips, avail - MORE_RESERVE);
        fit = Math.max(1, fit);               // one chip, even if it overflows
        next[axis] = fit;
        if ($scope.facetFit[axis] !== fit) changed = true;
      }
      if (!changed) return;
      $scope.facetFit = next;
      if (!$scope.$$phase && !$scope.$root.$$phase) $scope.$apply();
    }

    function countFitting(chips, avail) {
      var used = 0, n = 0;
      for (var j = 0; j < chips.length; j++) {
        var w = chips[j].offsetWidth + (j ? CHIP_GAP : 0);
        if (used + w > avail) break;
        used += w;
        n = j + 1;
      }
      return n;
    }

    /** Re-measure from scratch. The stored fit is cleared FIRST so the pass
     *  runs against a row drawn at the full PEEK -- measuring a row that a
     *  previous fit already shortened can only ever shrink it further, which
     *  is how a widened tile would keep the narrow row it was born with. */
    function remeasureFacets() {
      if (!$scope.facetsShown) return;
      $scope.facetFit = {};
      $timeout(fitFacetRows, 0);
      // A second pass, one frame later: a short axis (Step status, Step
      // exception, Step time) has few enough chips that the FIRST pass can
      // race a webfont swap or a still-settling flex width and measure a
      // narrower box than the tile ends up at, which is what used to draw a
      // "+N more" on a row that fits fine once everything has actually laid
      // out. Re-measuring is free -- fitFacetRows is a no-op when nothing
      // changed.
      $timeout(fitFacetRows, 150);
    }
    $scope._fitFacetRows = fitFacetRows;
    $scope._remeasureFacets = remeasureFacets;
    // A handle for the browser tier, which has to REPAINT the host and then
    // ask the widget to look again -- there is no scope to reach from there.
    try { $window.__rrAdopt = adoptHostSurface; } catch (e) { /* sandboxed */ }

    $scope.verdictClass = function (v) { return "verdict-" + (v || "no-data"); };
    $scope.verdictLabel = function (v) { return R.verdictLabel(v); };
    $scope.verdictColor = function (v) { return R.verdictColor(v); };
    $scope.human = function (s) { return R.humanSeconds(s); };
    $scope.stamp = function (secs) {
      return secs ? new Date(secs * 1000).toLocaleString() : "--";
    };

    // ---- CSV export ------------------------------------------------------
    // A Blob + object URL, not a data: URI -- a data: URI carrying a few hundred
    // failure messages blows past what some browsers accept in an href.
    function download(name, text, mime) {
      var blob = new $window.Blob([text], { type: (mime || "text/csv") + ";charset=utf-8;" });
      var url = $window.URL.createObjectURL(blob);
      var a = $window.document.createElement("a");
      a.href = url; a.download = name;
      $window.document.body.appendChild(a);
      a.click();
      $window.document.body.removeChild(a);
      // Revoke on the next tick: revoking synchronously can cancel the download
      // in flight on some browsers.
      $timeout(function () { $window.URL.revokeObjectURL(url); }, 1000);
    }
    $scope._download = download;

    function stampName(kind, ext) {
      var d = $scope.generatedAt || new Date();
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return "ztp-" + kind + "-" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) +
             "-" + p(d.getHours()) + p(d.getMinutes()) + "." + ext;
    }
    // ---- the export menu -------------------------------------------------
    /** Four sibling CSV buttons plus a PDF was five controls competing with
     *  Refresh and the view switch for the top-right corner, and "CSV: run
     *  steps" next to "CSV: steps" was a distinction nobody could read at a
     *  glance. One Export control, three destinations, stated as what they are
     *  ABOUT rather than as file formats. */
    $scope.exportOpen = false;
    $scope.toggleExport = function ($event) {
      if ($event) $event.stopPropagation();
      $scope.exportOpen = !$scope.exportOpen;
    };
    $scope.closeExport = function () { $scope.exportOpen = false; };
    // A menu that stays open behind the click that dismissed it is the classic
    // half-finished dropdown; the overlay below it catches the outside click.
    $scope.exportBusy = false;
    $scope.exportNote = "";

    // The menu is Run Groups, Devices and Steps, and nothing else reaches
    // download() any more. The four earlier entry points -- the flat device
    // CSV, the failures-only CSV, the run -> device tree CSV, and the
    // on-screen-only step CSV -- are gone rather than left as unreachable
    // methods: three of them exported shapes no view still draws, and an
    // export nothing can invoke is indistinguishable from a broken button the
    // day someone wires it back up. R.csvDevices / R.csvFailures /
    // R.csvGroupDevices / R.csvRunSteps remain in the module, tested, for
    // whoever wants one back.
    /** DEVICES, summarised -- one row per device on screen, no step detail. */
    $scope.exportDeviceGridCsv = function () {
      $scope.closeExport();
      download(stampName("devices", "csv"), R.csvDeviceGrid($scope.deviceGrid));
    };
    /** RUN GROUPS, summarised -- one row per dispatch ON SCREEN.
     *
     *  `runsView`, not `groups`: the filtered rows carry the counts the page is
     *  showing, while `groups` is the unfiltered fetch. An export that
     *  disagrees with the page it was taken from is the same defect as a
     *  summary that does. */
    $scope.exportRunGroupsCsv = function () {
      $scope.closeExport();
      download(stampName("rungroups", "csv"), R.csvRunGroupsView($scope.runsView));
    };

    // ---- the STEP export --------------------------------------------------
    /** One row per step, with the run group and the device as COLUMNS -- the
     *  opposite of the two summaries above, and pivotable on either.
     *
     *  It cannot use what is on screen. Only EXPANDED runs have their steps
     *  fetched, so exporting `runsView` would silently hand back the two runs
     *  someone happened to open. This fetches every step of every run in the
     *  filtered window in ONE aggregate, then applies the same chips the list
     *  applies, so the sheet is exactly what the filters describe.
     *
     *  `outputText` then rides a SECOND pass, chunked by uuid. It is a document
     *  per step -- the same field family that made the unprojected step fetch
     *  14 MB -- so it is never part of the list query, only of an export the
     *  user asked for by name.
     */
    var EXPORT_STEP_AGGREGATES = [{ operator: "groupby", field: "ztpfRunGroups.name", alias: "grp" }]
      .concat(GROUP_STEP_AGGREGATES);
    // Chunked because a uuid list is a URL-sized thing even in a POST body, and
    // a 1200-step window in one filter is how an endpoint starts returning 500s.
    var TEXT_CHUNK = 150;

    function fetchStepsForRuns(names) {
      if (!names.length) return $q.when([]);
      var url = "/api/query/" + STEP_MODULE + "?$limit=5000";
      return $http.post(url, {
        logic: "AND",
        filters: [{ field: "ztpfRunGroups.name", operator: "in", value: names }],
        aggregates: EXPORT_STEP_AGGREGATES
      }).then(function (resp) {
        var d = (resp && resp.data) || {};
        return d["hydra:member"] || (angular.isArray(d) ? d : []);
      });
    }

    function fetchStepText(uuids) {
      var chunks = [];
      for (var i = 0; i < uuids.length; i += TEXT_CHUNK) {
        chunks.push(uuids.slice(i, i + TEXT_CHUNK));
      }
      return $q.all(chunks.map(function (c) {
        return $http.post("/api/query/" + STEP_MODULE + "?$limit=" + c.length, {
          logic: "AND",
          filters: [{ field: "uuid", operator: "in", value: c }],
          __selectFields: ["uuid", "outputText"]
        }).then(function (resp) {
          var d = (resp && resp.data) || {};
          return d["hydra:member"] || (angular.isArray(d) ? d : []);
        // One failed chunk costs that chunk's text column, not the export.
        }).catch(function () { return []; });
      })).then(function (lists) {
        var by = {};
        lists.forEach(function (rows) {
          rows.forEach(function (r) { if (r && r.uuid) by[r.uuid] = r.outputText || ""; });
        });
        return by;
      });
    }

    $scope.exportStepsCsv = function () {
      $scope.closeExport();
      if ($scope.exportBusy) return;
      var names = ($scope.runsView || []).map(function (g) { return g.name; });
      if (!names.length) return;
      $scope.exportBusy = true;
      $scope.exportNote = "Collecting steps...";
      fetchStepsForRuns(names).then(function (raw) {
        // Stamped with their run group, then narrowed by the SAME chips the
        // list applies -- R.filterStepRows is the one the run rows go through.
        var byGroup = {};
        (raw || []).forEach(function (r) {
          var g = (r && r.grp) || "";
          (byGroup[g] = byGroup[g] || []).push(r);
        });
        var rows = [];
        Object.keys(byGroup).forEach(function (g) {
          R.filterStepRows(R.groupStepRows(byGroup[g]), $scope.facet, $scope.filter.q)
            .forEach(function (st) { st.group = g; rows.push(st); });
        });
        if (!rows.length) {
          $scope.exportBusy = false; $scope.exportNote = "";
          return;
        }
        $scope.exportNote = "Reading " + rows.length + " step outputs...";
        var ids = rows.map(function (r) { return r.uuid; })
                      .filter(function (u) { return !!u; });
        return fetchStepText(ids).then(function (text) {
          download(stampName("steps", "csv"), R.csvSteps(rows, text));
          $scope.exportBusy = false; $scope.exportNote = "";
        });
      }).catch(function (err) {
        $scope.exportBusy = false;
        $scope.exportNote = "";
        $scope.refreshError = "Step export failed (" + describe(err) + ").";
      });
    };

    // ---- PDF export ------------------------------------------------------
    // Rendered into a NEW WINDOW rather than print()ing this page. Printing in
    // place would carry the whole FortiSOAR shell -- nav, other widgets, the
    // record header -- into the PDF, and a widget cannot suppress chrome it
    // does not own. Building the document gives us exactly the report, on white,
    // with page breaks where they belong.
    $scope.exportPdf = function () {
      $scope.closeExport();
      var win = $window.open("", "_blank", "width=1100,height=800,menubar=yes");
      if (!win) {
        // Popup blocked. Say so -- a silently dead button is the defect the
        // socreport widget shipped with.
        $scope.error = "The report window was blocked. Allow pop-ups for this " +
                       "site, then click PDF again.";
        return;
      }
      win.document.write(printableHtml());
      win.document.close();
      win.focus();
      // Give the new document a beat to lay out its tables before the print
      // dialog freezes it. onload is unreliable for a document.write'd page.
      $timeout(function () { try { win.print(); } catch (e) { /* user closed it */ } }, 500);
    };

    function esc(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    $scope._esc = esc;

    /** THE PDF IS THE DASHBOARD, ON WHITE.
     *
     *  It used to be a different report altogether -- a device-first roll-up
     *  with a donut, a failures table and a device table, none of which is on
     *  the screen it was printed from. A printed report that disagrees with
     *  the page that produced it is worse than no print button: the numbers
     *  differ (the old KPI strip counted devices in their latest run, while
     *  the page counts device-runs in the filtered window) and there is
     *  nothing on the paper to tell you which one you are holding.
     *
     *  So it follows the page: the same narrative summary, the same three
     *  numbers, the filter state spelled out, and then whichever view is on
     *  screen with the steps under each row -- run groups, or devices. */
    function printableHtml() {
      var s = $scope.summary || {};
      var when = ($scope.generatedAt || new Date()).toLocaleString();
      var groupsView = $scope.isLayout("groups");
      var h = [];
      h.push('<!DOCTYPE html><html><head><meta charset="utf-8">');
      h.push("<title>" + esc($scope.config.title) + "</title><style>");
      h.push(PRINT_CSS);
      h.push("</style></head><body>");
      h.push('<div class="hdr"><h1>' + esc($scope.config.title) + "</h1>");
      h.push('<div class="sub">' + esc(groupsView ? "Run groups" : "Devices") +
             " &middot; last " + esc($scope.rangeLabel()) +
             " &middot; generated " + esc(when) + "</div></div>");
      if ($scope.truncated) h.push('<div class="warn">' + esc($scope.truncated) + "</div>");

      // The filter, in words. A printed sheet has no chips to look at, so a
      // filtered export that does not say what it excluded is a sheet nobody
      // can safely forward.
      var bits = [];
      if ($scope.filter.q) bits.push('search "' + $scope.filter.q + '"');
      FACET_IDS.forEach(function (id) {
        var picked = Object.keys($scope.facet[id] || {});
        if (!picked.length) return;
        var f = $scope.FACETS.filter(function (x) { return x.id === id; })[0];
        bits.push((f ? f.label : id) + ": " + picked.join(", "));
      });
      h.push('<div class="filters">' +
             (bits.length ? "Filtered by " + esc(bits.join(" &middot; ")) : "No filters -- every run in the window") +
             "</div>");

      // The summary band, in the same two halves the screen uses.
      h.push('<div class="top">');
      if ($scope.verdictLine) {
        h.push('<div class="headline lvl-' + esc($scope.verdictLine.level) + '">' +
               '<div class="hero">' + esc(s.runs || 0) + " run group" +
               ((s.runs === 1) ? "" : "s") + "</div>" +
               "<b>" + esc($scope.verdictLine.text) + "</b>");
        if ($scope.narrative) h.push('<p class="narr">' + esc($scope.narrative) + "</p>");
        h.push('<ul class="facts">');
        ($scope.summaryLines || []).forEach(function (l) {
          h.push("<li><span>" + esc(l.label) + "</span><b>" + esc(l.value) + "</b></li>");
        });
        h.push("</ul></div>");
      }
      h.push('<div class="kpis">');
      // The SAME five tiles the screen draws, in the same order and with the
      // same shares. A printed report that counts differently from the page
      // it was printed from is a report someone will quote against it.
      [["Steps queued", s.queued || 0],
       ["Steps running", s.runningNow || 0],
       ["Steps complete", s.complete || 0],
       ["Steps failed", s.failed || 0],
       ["Steps with exceptions", s.exceptions || 0]].forEach(function (p) {
        h.push('<div class="kpi"><div class="n">' + esc(p[1]) +
               '</div><div class="p">(' + esc(R.pctOf(p[1], s.steps || 0)) +
               '%)</div><div class="l">' + esc(p[0]) + "</div></div>");
      });
      h.push("</div></div>");

      function stepTable(rows, lead) {
        if (!rows || !rows.length) return;
        var leadHead = lead === "device" ? "Device" : (lead === "group" ? "Run group" : "");
        h.push("<table><thead><tr>" + (leadHead ? "<th>" + leadHead + "</th>" : "") +
               "<th>Step#</th><th>Step name</th><th>Automation action</th>" +
               "<th>Action type</th><th>Status</th><th>Output status</th>" +
               "<th>Started - stopped</th><th>Time</th></tr></thead><tbody>");
        rows.forEach(function (st) {
          h.push('<tr class="' + (st.bad ? "bad" : (st.flagged ? "warnrow" : "")) + '">' +
                 (leadHead ? "<td>" + esc(lead === "device" ? st.device : (st.group || "")) + "</td>" : "") +
                 "<td>" + esc(st.stepNumber) + "</td><td>" + esc(st.name) +
                 "</td><td>" + esc(st.action) + "</td><td>" + esc(st.trigger) +
                 "</td><td>" + esc(st.status) + "</td><td>" + esc(st.exception) +
                 "</td><td>" + esc(st.when || "--") + "</td><td>" +
                 esc(st.seconds ? R.humanSeconds(st.seconds) : "--") + "</td></tr>");
          // The message the exception status is asking you to read. On screen
          // it is a hover; on paper a hover is nothing at all.
          if (st.message && st.flagged) {
            h.push('<tr class="msg"><td colspan="' + (leadHead ? 9 : 8) +
                   '">' + esc(st.message) + "</td></tr>");
          }
        });
        h.push("</tbody></table>");
      }

      if (groupsView) {
        ($scope.runsView || []).forEach(function (g) {
          h.push('<div class="row"><div class="rowhead ' + esc(g.verdict) + '">');
          h.push("<b>" + esc(g.name) + "</b> <span>" + esc($scope.stamp(g.createDate)) +
                 "</span> <em>" + esc($scope.verdictLabel(g.verdict)) + "</em>");
          h.push("<span>" + (g.progress.complete) + "/" + (g.progress.total) +
                 " steps &middot; " + g.progress.percent + "%" +
                 (g.steps.failed ? " &middot; " + g.steps.failed + " failed" : "") +
                 (g.steps.exceptions ? " &middot; " + g.steps.exceptions + " exc" : "") +
                 "</span></div>");
          stepTable($scope.stepsFor(g), "device");
          h.push("</div>");
        });
        if (!($scope.runsView || []).length) {
          h.push('<div class="panel ok"><p>No run group matches the current filters.</p></div>');
        }
      } else {
        ($scope.deviceGrid || []).forEach(function (d) {
          h.push('<div class="row"><div class="rowhead ' + esc(d.verdict) + '">');
          h.push("<b>" + esc(d.name) + "</b> <span>" + esc(d.managementIP || "--") +
                 (d.platform ? " &middot; " + esc(d.platform) : "") + "</span>" +
                 (d.status ? " <em>" + esc(d.status) + "</em>" : "") +
                 " <em>" + esc($scope.verdictLabel(d.verdict)) + "</em>");
          h.push("<span>" + d.steps + " steps &middot; " + esc(d.lastRun) + " &middot; " +
                 esc($scope.stamp(d.lastRunStartedAt)) + " &rarr; " +
                 esc(d.lastRunFinishedAt ? $scope.stamp(d.lastRunFinishedAt) : "running") +
                 "</span></div>");
          stepTable($scope.deviceStepsFor(d), "group");
          h.push("</div>");
        });
        if (!($scope.deviceGrid || []).length) {
          h.push('<div class="panel ok"><p>No device matches the current filters.</p></div>');
        }
      }

      // Only EXPANDED rows have their steps fetched, so a printed sheet that
      // silently omitted the rest would read as a run with no steps in it.
      h.push('<div class="foot">Steps are listed for the rows that were expanded on screen. ' +
             'Generated by the ZTP Run Report widget &middot; ' + esc(when) + "</div>");
      h.push("</body></html>");
      return h.join("");
    }
    $scope._printableHtml = printableHtml;

    // Light theme only, on purpose: this document exists to become a PDF, and
    // a dark dashboard prints as a wall of toner.
    var PRINT_CSS = [
      "@page{margin:12mm}",
      "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;",
      "color:#1f2430;background:#fff;margin:0;padding:18px;font-size:11px;line-height:1.45}",
      ".hdr{border-bottom:3px solid #0e7490;padding-bottom:8px;margin-bottom:12px}",
      ".hdr h1{margin:0 0 3px;font-size:19px;color:#0e7490}",
      ".hdr .sub{font-size:11px;color:#6b7280}",
      ".warn{background:#fff7ed;border:1px solid #fdba74;color:#9a3412;padding:7px 10px;",
      "border-radius:4px;margin-bottom:10px}",
      ".filters{font-size:10px;color:#6b7280;margin-bottom:12px}",
      ".top{display:flex;gap:12px;margin-bottom:16px;align-items:stretch}",
      ".headline{flex:1;border:1px solid #e5e7eb;border-left:4px solid #9ca3af;",
      "border-radius:6px;padding:10px 12px;background:#f9fafb}",
      ".headline b{font-size:14px}",
      ".headline .narr{margin:6px 0 0;font-size:11px;line-height:1.5}",
      ".headline.lvl-failed{border-left-color:#dc2626}",
      ".headline.lvl-running{border-left-color:#0284c7}",
      ".headline.lvl-exception{border-left-color:#d97706}",
      ".headline.lvl-healthy{border-left-color:#16a34a}",
      ".facts{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:4px 18px}",
      ".facts li{font-size:10px;color:#6b7280}",
      ".facts li b{margin-left:5px;color:#1f2430;font-size:11px}",
      ".kpis{display:flex;gap:8px}",
      ".kpi{min-width:92px;border:1px solid #e5e7eb;border-radius:6px;padding:8px 10px;",
      "background:#f9fafb;text-align:center}",
      ".kpi .n{font-size:20px;font-weight:700;line-height:1}",
      ".kpi .p{font-size:9px;color:#6b7280;margin-top:2px;line-height:1}",
      ".headline .hero{font-size:10px;text-transform:uppercase;letter-spacing:.06em;",
      "color:#6b7280;margin-bottom:4px}",
      ".kpi .l{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;margin-top:3px}",
      ".row{margin-bottom:12px;page-break-inside:avoid}",
      ".rowhead{background:#f3f4f6;border-left:3px solid #9ca3af;padding:5px 9px;",
      "border-radius:3px 3px 0 0;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}",
      ".rowhead b{font-size:12px}",
      ".rowhead span{font-size:10px;color:#6b7280}",
      ".rowhead em{font-style:normal;font-size:9px;text-transform:uppercase;",
      "letter-spacing:.05em;color:#4b5563}",
      ".rowhead.failed{border-left-color:#dc2626;background:#fef2f2}",
      ".rowhead.running{border-left-color:#0284c7}",
      ".rowhead.exception{border-left-color:#d97706;background:#fffbeb}",
      ".rowhead.healthy{border-left-color:#16a34a}",
      ".panel.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px}",
      "table{border-collapse:collapse;width:100%;font-size:10px}",
      "th,td{border:1px solid #e5e7eb;padding:4px 7px;text-align:left;vertical-align:top}",
      "th{background:#f9fafb;font-weight:600;font-size:9px;text-transform:uppercase;",
      "letter-spacing:.04em;color:#4b5563}",
      "tr.bad td{background:#fef2f2}",
      "tr.warnrow td{background:#fffbeb}",
      "tr.msg td{background:#fffbeb;color:#92400e;font-style:italic}",
      ".foot{margin-top:18px;padding-top:7px;border-top:1px solid #e5e7eb;font-size:9px;",
      "color:#9ca3af;text-align:center}",
      "@media print{body{padding:0}.row{page-break-inside:avoid}}"
    ].join("");

    // ---- the reading position is addressable ------------------------------
    /** Mirror the filters, the search box, the time scale and the layout into
     *  ONE query parameter, and read them back on mount.
     *
     *  This is about handover, not convenience. "The firmware pushes that
     *  failed on FG1 in the last fortnight" is six clicks deep and, until
     *  now, impossible to send to anyone: the recipient opened the dashboard
     *  on its default window with a description of where to click. A view
     *  that cannot be cited gets screenshotted instead, and a screenshot
     *  outlives the data in it.
     *
     *  replaceState, never pushState: this widget is a tenant on a page it
     *  does not own, and filling the host's back button with thirty entries
     *  because someone clicked thirty chips would break navigation for every
     *  other tile on the board. For the same reason the whole thing lives
     *  under one namespaced key instead of scattering `device=`/`status=`
     *  across a query string two tiles might both write to.
     *
     *  Everything here is wrapped: a sandboxed frame throws on
     *  history.replaceState, and a report that will not render because it
     *  could not update its own URL would be a spectacular own goal. */
    var URL_KEY = "rr";
    var lastUrlState = null;
    /** ONE tile owns the query string.
     *
     *  Two copies of this widget on one board -- which is a supported thing
     *  to do, and the reason the session snapshot is keyed by title -- would
     *  otherwise both write `?rr=`, each overwriting the other on every
     *  filter click, and on the next reload BOTH would adopt whichever
     *  selection happened to land last. A filter nobody chose, applied to a
     *  tile that never showed it, is the unseeable state again.
     *
     *  So the first instance to mount claims the key and is the only one that
     *  reads or writes it; the rest keep their filters to themselves. It is
     *  released on teardown, so the tile that replaces it after a dashboard
     *  remount claims it straight back. */
    var URL_OWNER = "__ztpRunReportUrlOwner";
    /** What this widget last wrote into the bar, and under which settings.
     *
     *  Needed to tell a HANDOVER from an ECHO. Once the filters are mirrored
     *  into the URL, every remount reads back the state it just wrote -- and
     *  if that counts as "someone sent me a link", the tile takes the cold
     *  path and paints a loader over a page it already had, which is exactly
     *  the flash the session snapshot exists to prevent. An echo is applied
     *  quietly; only a URL this widget did not write is a handover.
     *
     *  The settings key rides along for the same reason the snapshot carries
     *  one: an echo written under the OLD configuration is stale, and letting
     *  it back in would put the old range straight back after someone changed
     *  it in the modal -- a setting that does not appear to take. */
    var URL_WRITTEN = "__ztpRunReportUrlWritten";
    var urlOwned = false;
    function claimUrl() {
      if (!$window[URL_OWNER]) $window[URL_OWNER] = SESSION_KEY;
      urlOwned = $window[URL_OWNER] === SESSION_KEY;
      return urlOwned;
    }
    function releaseUrl() {
      if ($window[URL_OWNER] === SESSION_KEY) $window[URL_OWNER] = null;
    }

    function currentUrlState() {
      var f = {};
      FACET_IDS.forEach(function (id) {
        var vals = R.chosen($scope.facet[id]);
        if (vals.length) f[id] = vals;
      });
      return { range: $scope.range, layout: $scope.layout,
               q: $scope.filter.q, facet: f };
    }

    /** The query string, read through the HOST'S ROUTER rather than off
     *  `location` directly.
     *
     *  This is not a stylistic preference, it is the whole reason the feature
     *  is safe to ship. A raw history.replaceState DOES update the bar --
     *  and then the AngularJS application this widget is a tenant of notices
     *  that the URL no longer matches the one it believes it is on, and
     *  pushes an entry of its own to reconcile. Measured in the harness:
     *  three chip clicks, three extra history entries, and a back button that
     *  no longer leaves the dashboard. Going through $location lets the host
     *  make the change itself, and $location.replace() is how you tell it not
     *  to push.
     *
     *  The raw fallbacks below are for a host that provides no usable
     *  $location at all. A report that will not render because it could not
     *  update its own URL would be a spectacular own goal. */
    function readParam(key) {
      try {
        var q = $location && $location.search && $location.search();
        if (q && typeof q === "object") return q[key];
      } catch (e) { /* fall through to the raw read */ }
      var loc = $window.location || {};
      var m = new RegExp("[?&]" + key + "=([^&]*)").exec(String(loc.search || ""));
      return m ? decodeURIComponent(m[1]) : undefined;
    }

    function writeParam(key, value) {
      try {
        if ($location && $location.search) {
          // null REMOVES the key -- an empty string would leave `?rr=`
          // sitting in the bar of a page with nothing selected.
          $location.search(key, value || null);
          // The whole point: the host replaces rather than pushes.
          if ($location.replace) $location.replace();
          return true;
        }
      } catch (e) { /* fall through */ }
      return false;
    }

    /** Apply a shared link. Returns true if anything was actually requested,
     *  which the caller needs because a state carrying a RANGE has to be in
     *  place before the first fetch -- the date filter is applied server-side,
     *  so arriving on ?rr=r:30d and then fetching 7 days would show the
     *  wrong window under the right chips. */
    function applyUrlState() {
      if (!urlOwned) return false;
      var raw = readParam(URL_KEY);
      if (!raw) return false;
      var enc = String(raw);
      var mine = $window[URL_WRITTEN];
      if (mine && mine.enc === enc) {
        // Our own echo. Under the SAME settings it is simply what the page
        // was already showing, so it is applied and reported as "no link";
        // under different ones it is stale and dropped entirely.
        if (mine.key !== SESSION_KEY) return false;
        lastUrlState = enc;
        applyDecoded(R.decodeState(enc));
        return false;
      }
      var st = R.decodeState(enc);
      return applyDecoded(st);
    }

    function applyDecoded(st) {
      var touched = false;
      if (st.range && R.rangeById(st.range)) { $scope.range = st.range; touched = true; }
      if (st.layout && LAYOUT_IDS.indexOf(st.layout) >= 0) {
        $scope.layout = st.layout; touched = true;
      }
      if (st.q) { $scope.filter.q = st.q; touched = true; }
      Object.keys(st.facet || {}).forEach(function (axis) {
        // An axis this build does not have is ignored rather than stored: a
        // link shared from a newer version must not park a selection no chip
        // can ever show, which would be the unseeable filter again.
        if (FACET_IDS.indexOf(axis) < 0) return;
        var m = {};
        st.facet[axis].forEach(function (v) { m[v] = true; });
        $scope.facet[axis] = m;
        touched = true;
      });
      // A link that arrives carrying chips opens the panel, for the same
      // reason a tile click does: the reader has to be able to SEE what is
      // narrowing the list they were sent.
      if (touched && $scope.anyFacet()) $scope.facetsShown = true;
      return touched;
    }
    $scope._applyUrlState = applyUrlState;

    function writeUrlState() {
      if (!urlOwned) return;
      var enc = R.encodeState(currentUrlState());
      if (enc === lastUrlState) return;      // nothing moved; leave the bar alone
      lastUrlState = enc;
      $window[URL_WRITTEN] = { key: SESSION_KEY, enc: enc };
      if (writeParam(URL_KEY, enc)) return;
      // No usable $location. Fall back to the raw history API, which still
      // beats not being shareable at all.
      try {
        var h = $window.history;
        if (!h || !h.replaceState) return;
        var loc = $window.location || {};
        var qs = enc ? "?" + URL_KEY + "=" + encodeURIComponent(enc) : "";
        h.replaceState(h.state, "", (loc.pathname || "") + qs + (loc.hash || ""));
      } catch (e) { /* sandboxed frame; the widget still works */ }
    }
    $scope._writeUrlState = writeUrlState;

    /** The link to hand someone else -- the address bar as it stands. Offered
     *  as an explicit copy rather than left as "select the URL yourself",
     *  because the URL of a dashboard tile is not where anyone looks. */
    $scope.shareUrl = function () {
      writeUrlState();
      try {
        if ($location && $location.absUrl) return $location.absUrl();
      } catch (e) { /* fall through */ }
      return (($window.location || {}).href) || "";
    };

    // ---- Run Automation --------------------------------------------------
    // Pick devices in the configured status, then fire the configured Manual
    // playbook on them. The playbook asks for everything else (the automation
    // profile, whether to run straight away) through its own prompt -- this
    // panel deliberately does not duplicate that form.
    $scope.auto = { open: false };

    $scope.openAutomation = function () {
      $scope.auto = { open: true, loading: true, error: null, done: null,
                      minimized: false, devices: [], selected: {}, search: "" };
      var status = $scope.config.automationDeviceStatus || "Ok";
      $http.post("/api/query/" + DEVICE_MODULE + "?$limit=1000", R.automationDeviceQuery(status))
        .then(function (resp) {
          $scope.auto.devices = (resp.data && resp.data["hydra:member"]) || [];
        }, function (err) {
          $scope.auto.error = "Could not load " + status + " devices: " + httpMessage(err);
        })
        .finally(function () { $scope.auto.loading = false; });
    };

    $scope.closeAutomation = function () { $scope.auto = { open: false }; };

    $scope.expandAutomation = function () { $scope.auto.minimized = false; };

    $scope.autoVisible = function () {
      return ($scope.auto.devices || []).filter(function (d) {
        return R.automationMatches(d, $scope.auto.search);
      });
    };

    $scope.autoSelected = function () {
      return ($scope.auto.devices || []).filter(function (d) { return $scope.auto.selected[d.uuid]; });
    };

    // Acts on what is VISIBLE: select-all under a search box that ticked the
    // rows the search hid would run devices nobody was looking at.
    $scope.autoSelectAll = function (on) {
      $scope.autoVisible().forEach(function (d) { $scope.auto.selected[d.uuid] = !!on; });
    };

    $scope.runAutomation = function () {
      var picked = $scope.autoSelected();
      var name = $scope.config.automationPlaybook;
      if (!picked.length || $scope.auto.running) return;
      $scope.auto.running = true;
      $scope.auto.error = null;
      var playbookUuid;
      $http.post("/api/query/workflows?$limit=5", {
        logic: "AND",
        filters: [{ field: "name", operator: "eq", value: name },
                  { field: "isActive", operator: "eq", value: true }],
        __selectFields: ["uuid", "name"]
      }).then(function (resp) {
        var pb = ((resp.data && resp.data["hydra:member"]) || [])[0];
        if (!pb) return $q.reject({ message: "Playbook \"" + name + "\" was not found or is not active." });
        playbookUuid = pb.uuid;
        return $http.get("/api/3/workflows/" + pb.uuid + "?$relationships=true&$triggerOnly=true");
      }).then(function (resp) {
        var route = R.automationRoute(resp.data);
        if (!route) return $q.reject({ message: "Playbook \"" + name + "\" has no Manual trigger to run it from." });
        return $http.post("/api/triggers/1/action/" + route, R.automationTriggerBody(playbookUuid, picked));
      }).then(function () {
        $scope.auto.done = { count: picked.length, playbook: name };
        $scope.auto.selected = {};
        // The dispatch succeeded -- minimize the picker (search box, device
        // list, All/None) so the confirmation and the run list underneath,
        // where the new run is about to show up, are what's on screen. The
        // panel itself stays open (the confirmation lives inside it); the
        // header button re-opens it full-size for another batch.
        $scope.auto.minimized = true;
      }, function (err) {
        $scope.auto.error = "Could not start \"" + name + "\": " + httpMessage(err);
      }).finally(function () { $scope.auto.running = false; });
    };

    function httpMessage(err) {
      if (!err) return "unknown error";
      if (err.message) return err.message;
      var d = err.data || {};
      return d["hydra:description"] || d.message || ("HTTP " + (err.status || "error"));
    }

    // ---- init ------------------------------------------------------------
    var timer = null;
    var secs = Number($scope.config.refreshSecs) || 0;
    if (secs > 0) {
      timer = $window.setInterval(function () {
        // BACKGROUND, always. A timer that calls the foreground load blanks the
        // widget on every tick -- the page flashes, every open run collapses,
        // and the phase list you were reading is thrown away, all to redraw
        // numbers that usually did not change.
        $scope.$applyAsync(function () { $scope.load({ background: true }); });
      }, Math.max(15, secs) * 1000);
    }
    // Park the state on the way out, so the instance the dashboard builds a
    // moment later has something to paint. $destroy is the only hook that
    // fires on a tile teardown.
    $scope.$on("$destroy", function () {
      if (timer) $window.clearInterval(timer);
      releaseUrl();
      if ($scope.generatedAt) snapshot();
      Object.keys(charts).forEach(destroyChart);
    });

    // A remount paints the previous page immediately and re-reads behind it;
    // a genuine first load shows the loader, because there is nothing to show.
    // A shared link WINS over the parked session: someone who was handed a
    // URL is asking for that reading, not for whatever this browser happened
    // to be looking at ten minutes ago. It is applied before either load, so
    // the range it names is the range that gets fetched.
    claimUrl();
    var fromLink = applyUrlState();
    var restored = restore();
    // restore() rewrites the filter state wholesale, so a link that arrived
    // with this mount is re-applied on top of it.
    if (restored && fromLink) applyUrlState();
    if (restored && !fromLink) $scope.load({ background: true });
    else $scope.load();
  }
})();

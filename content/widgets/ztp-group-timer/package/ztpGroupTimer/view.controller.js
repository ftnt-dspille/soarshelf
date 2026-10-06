/* Copyright start
   MIT License
   Copyright (c) 2026 Fortinet Inc
   Copyright end */
"use strict";
// VIEW controller. The harness/SOAR resolves the controller name as
// `<name><numericVersion>DevCtrl` -- ztpGroupTimer103DevCtrl for v1.0.0.
// `widget bump` rewrites this suffix on a version change; never hand-edit it.
//
// A count-up clock for ONE ztpfRunGroup record. ztpf_run_groups carries no
// start/stop field of its own (only totalRunningTimeSeconds, which the
// platform only fills in once a run is already over) -- the run's start and
// stop are DERIVED from its own steps' stepStartTimestamp/stepStopTimestamp,
// see R.computeWindow. All of that math lives in widgetAssets/js/ztpGroupTimer.js
// so it can be unit-tested without Angular or a live clock.
(function () {
  angular
    .module("cybersponse")
    .controller("ztpGroupTimer103DevCtrl", ztpGroupTimer103DevCtrl);

  ztpGroupTimer103DevCtrl.$inject =
    ["$scope", "config", "FormEntityService", "$http", "$interval", "$window"];

  function ztpGroupTimer103DevCtrl($scope, config, FormEntityService, $http, $interval, $window) {
    var R = $window.ztpGroupTimer;
    var STEP_MODULE = "ztpf_device_automation_steps";

    $scope.config = angular.extend({}, {
      title: "Run Timer",
      // One of R.THEMES' ids. Kept as a plain string (not validated against
      // the list here) so a theme added later still renders on a widget
      // saved under an older version -- an unknown id just falls through to
      // the CSS default rather than blanking the whole card.
      theme: "digital",
      // How often to re-read the steps while the run might still be going.
      // Once the run is over there is nothing left to change, so polling
      // stops itself -- see poll() below.
      refreshSecs: 5
    }, config || {});
    $scope.THEMES = R.THEMES;

    // ---- record context ---------------------------------------------------
    function getEntity() {
      try { return FormEntityService.get(); } catch (e) { return null; }
    }
    var entity = getEntity();
    $scope.record = (entity && entity.originalData) ? entity.originalData : null;
    $scope.hasRecord = !!$scope.record;
    $scope.groupName = $scope.record && $scope.record.name || null;

    $scope.loading = true;
    $scope.error = null;
    $scope.window = { start: null, stop: null };
    $scope.state = "idle";
    $scope.elapsed = 0;
    $scope.clock = R.formatClock(0);
    $scope.compact = R.formatCompact(0);
    $scope.digits = R.digitParts(0);

    function nowSec() { return Math.floor(Date.now() / 1000); }

    /** Recompute everything the template reads from the current window and
     *  the current clock tick -- one place, called both when fresh steps
     *  land and on every tick, so the two can never render two different
     *  numbers for the same instant. */
    function render() {
      var elapsed = R.elapsedSeconds($scope.window, nowSec());
      $scope.state = R.timerState($scope.window);
      $scope.elapsed = elapsed;
      $scope.clock = R.formatClock(elapsed);
      $scope.compact = R.formatCompact(elapsed);
      $scope.digits = R.digitParts(elapsed);
    }
    $scope._render = render; // test hook

    // ---- ticking (every second, only while running) ------------------------
    var tickPromise = null;
    function ensureTicking() {
      if (tickPromise || $scope.state !== "running") return;
      tickPromise = $interval(render, 1000);
    }
    function stopTicking() {
      if (!tickPromise) return;
      $interval.cancel(tickPromise);
      tickPromise = null;
    }

    // ---- fetch the group's own steps ---------------------------------------
    // Projected to the two timestamps plus `stepDone` -- a step also carries
    // a script blob and rendered output, and nothing here reads either.
    // `stepDone` is what R.computeWindow trusts to call a step over; the
    // timestamps alone are not enough (see that function's comment).
    function fetchSteps() {
      if (!$scope.groupName) return;
      var url = "/api/query/" + STEP_MODULE + "?$limit=2000";
      var body = {
        logic: "AND",
        filters: [{ field: "ztpfRunGroups.name", operator: "in", value: [$scope.groupName] }],
        __selectFields: ["stepStartTimestamp", "stepStopTimestamp", "stepDone"]
      };
      return $http.post(url, body).then(function (resp) {
        var d = (resp && resp.data) || {};
        var rows = d["hydra:member"] || (angular.isArray(d) ? d : []);
        $scope.window = R.computeWindow(rows);
        $scope.loading = false;
        $scope.error = null;
        render();
        if ($scope.state === "running") ensureTicking();
        else stopTicking();
      }).catch(function (err) {
        $scope.loading = false;
        $scope.error = (err && err.status) ? ("HTTP " + err.status) : "Could not read run steps.";
      });
    }
    $scope.retry = fetchSteps;

    // ---- polling for a run still in flight ---------------------------------
    // Stops itself the moment the fetched window comes back stopped -- a
    // finished run's steps do not change again, so there is nothing left to
    // poll for.
    var pollPromise = null;
    function ensurePolling() {
      if (pollPromise) return;
      var secs = Number($scope.config.refreshSecs) || 5;
      pollPromise = $interval(function () {
        if ($scope.state === "stopped") { stopPolling(); return; }
        fetchSteps();
      }, secs * 1000);
    }
    function stopPolling() {
      if (!pollPromise) return;
      $interval.cancel(pollPromise);
      pollPromise = null;
    }

    if ($scope.groupName) {
      fetchSteps().then(function () {
        if ($scope.state !== "stopped") ensurePolling();
      });
    } else {
      $scope.loading = false;
    }

    $scope.$on("$destroy", function () {
      stopTicking();
      stopPolling();
    });
  }
})();

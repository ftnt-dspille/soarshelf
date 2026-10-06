/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
// EDIT controller -- the config editor. The SOAR shell opens it as a $uibModal,
// so save() must close with the config and cancel() must dismiss.
(function () {
  angular
    .module("cybersponse")
    .controller("editZtpRunReport1055DevCtrl", editZtpRunReport1055DevCtrl);

  // `config` is the SAVED config, injected -- not handed over on $scope. Without
  // it the editor shows stale defaults every time it reopens and closes the
  // modal with a fresh object, silently discarding the user's saved choices.
  editZtpRunReport1055DevCtrl.$inject = ["$scope", "$uibModalInstance", "config"];

  function editZtpRunReport1055DevCtrl($scope, $uibModalInstance, config) {
    var defaults = {
      title: "ZTP Run Report",
      scope: "latest",
      layout: "groups",
      runGroupLimit: 25,
      stepPage: 1000,
      groupPage: 500,
      refreshSecs: 0,
      showTrend: true,
      showRunGroups: true,
      openInNewTab: true,
      autoExpandGroups: 1,
      prefetchDevices: 4,
      range: "7d",
      showTags: true,
      showRunAutomation: true,
      automationPlaybook: "Add Steps to Device from Profile",
      automationDeviceStatus: "Ok"
    };
    $scope.config = angular.extend({}, defaults, config || {}, $scope.config || {});
    // Which reading the dashboard OPENS with. All three stay reachable from the
    // widget's own switcher -- this only picks the default.
    $scope.LAYOUT_IDS = ["groups", "answer", "console", "grid"];
    $scope.layoutOptions = [
      { v: "groups",  label: "Runs -- run group, then its devices, then their phases" },
      { v: "answer",  label: "Answer -- lead with what needs attention" },
      { v: "console", label: "Console -- fleet list beside per-device detail" },
      { v: "grid",    label: "Grid -- one card per device" }
    ];
    // Mirrors ztpReport.RANGES. The edit modal must not depend on the view's
    // asset bundle being loaded, so the list is restated rather than imported.
    $scope.rangeOptions = [
      { id: "24h", label: "Last 24 hours" },
      { id: "7d",  label: "Last 7 days" },
      { id: "30d", label: "Last 30 days" },
      { id: "90d", label: "Last 90 days" },
      { id: "all", label: "All time" }
    ];
    $scope.scopeOptions = [
      { v: "latest", label: "Latest run group per device (recommended)" },
      { v: "all", label: "Every run in the fetched history" }
    ];

    // Closing the modal is NOT one contract -- it is four, and which one is
    // live depends on the host. Injected $uibModalInstance is the documented
    // path and the only one the harness provides; the dashboard/template
    // editor instead exposes $close/$dismiss straight on this scope, and some
    // hosts hand down a closeSettings() on a parent. Guarding on only the
    // first (`if ($uibModalInstance) ...`) is why Save and Cancel were both
    // dead in the real shell: the call succeeded, did nothing, and reported
    // nothing. Try every path and tell the caller whether ANY of them fired.
    function closeModal(result, dismiss) {
      if ($uibModalInstance) {
        if (dismiss) { $uibModalInstance.dismiss("cancel"); }
        else { $uibModalInstance.close(result); }
        return true;
      }
      if (typeof $scope.$dismiss === "function" && dismiss) { $scope.$dismiss("cancel"); return true; }
      if (typeof $scope.$close === "function" && !dismiss) { $scope.$close(result); return true; }
      for (var s = $scope; s; s = s.$parent) {
        if (typeof s.closeSettings === "function") { s.closeSettings(result); return true; }
      }
      // Last resort: let the host hear about it even if it gave us no handle.
      $scope.$emit(dismiss ? "widgetSettingsDismissed" : "widgetSettingsSaved", result);
      return false;
    }

    $scope.save = function () {
      // Coerce the numeric fields: an <input type=number> hands back a string
      // when the user types, and the view does arithmetic on these.
      ["runGroupLimit", "stepPage", "groupPage", "refreshSecs",
       "autoExpandGroups", "prefetchDevices"].forEach(function (k) {
          // `|| defaults[k]` would turn a deliberate 0 back into the default,
        // and 0 is a real answer on two of these fields -- "manual refresh
        // only", "open no runs". A BLANK field still means "use the default",
        // so empty string and NaN fall back while an explicit 0 survives.
        var raw = $scope.config[k];
        var n = (raw === "" || raw == null) ? NaN : Number(raw);
        $scope.config[k] = isFinite(n) && n >= 0 ? n : defaults[k];
      });
      if (["latest", "all"].indexOf($scope.config.scope) === -1) $scope.config.scope = "latest";
      if ($scope.LAYOUT_IDS.indexOf($scope.config.layout) === -1) $scope.config.layout = "groups";
      return closeModal($scope.config, false);
    };
    $scope.cancel = function () {
      return closeModal(null, true);
    };
  }
})();

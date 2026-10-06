/* Copyright start
   MIT License
   Copyright (c) 2026 Fortinet Inc
   Copyright end */
"use strict";
// EDIT controller -- the config editor. It loads only when the host opens
// "Edit Config". The SOAR shell opens it as a $uibModal, so wire the modal
// close/dismiss contract: save() must close with the config; cancel() dismisses.
(function () {
  angular
    .module("cybersponse")
    .controller("editZtpGroupTimer103DevCtrl", editZtpGroupTimer103DevCtrl);

  // `config` is the SAVED config, injected -- not handed over on $scope.
  // Without it the editor shows stale defaults every time it reopens and
  // closes the modal with a fresh object, silently discarding saved choices.
  editZtpGroupTimer103DevCtrl.$inject = ["$scope", "$uibModalInstance", "config"];

  // Mirrors widgetAssets/js/ztpGroupTimer.js's R.THEMES -- kept as a plain
  // literal here rather than read off `window.ztpGroupTimer`, because the
  // editor can open before the VIEW template (which is what loads that
  // script) has ever mounted, e.g. when a widget is added to a dashboard for
  // the first time. Both lists are ids + labels only; add a theme in one
  // place and mirror the id/label pair in the other.
  var THEMES = [
    { id: "digital", label: "Digital (LCD)" },
    { id: "flip", label: "Flip digits" },
    { id: "minimal", label: "Minimal text" },
    { id: "ring", label: "Spinner ring" },
    { id: "badge", label: "Compact badge" }
  ];

  function editZtpGroupTimer103DevCtrl($scope, $uibModalInstance, config) {
    $scope.THEMES = THEMES;

    $scope.config = angular.extend({
      title: "Run Timer",
      theme: "digital",
      refreshSecs: 5
    }, config || {});

    // Modal contract -- without these, Save/Cancel won't close the SOAR modal.
    $scope.save = function () {
      if ($uibModalInstance) $uibModalInstance.close($scope.config);
    };
    $scope.cancel = function () {
      if ($uibModalInstance) $uibModalInstance.dismiss("cancel");
    };
  }
})();

/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
// EDIT controller -- the config editor. Loads only when the host opens
// "Edit Config". The SOAR shell opens it as a $uibModal, so wire the modal
// close/dismiss contract: save() must close with the config; cancel() dismisses.
(function () {
  angular
    .module("cybersponse")
    .controller("editZtpAutomationGraph1040DevCtrl", editZtpAutomationGraph1040DevCtrl);

  // MUST inject `config` -- the host passes the SAVED widget config in as this
  // dependency, NOT via $scope inheritance. Reading `$scope.config` here instead
  // (a) shows stale defaults every time the editor reopens and (b) closes the
  // modal with a fresh object, so the user's saved choices never round-trip.
  // Bind the injected object with angular.extend(defaults, config) so defaults
  // fill only the gaps and existing values survive. (lint: edit-config-inject)
  editZtpAutomationGraph1040DevCtrl.$inject = ["$scope", "$uibModalInstance", "config"];

  function editZtpAutomationGraph1040DevCtrl($scope, $uibModalInstance, config) {
    // Defaults fill only missing keys; saved values (incl. orientation/graphHeight) win.
    $scope.config = angular.extend(
      {}, { title: "ZTP Automation Step Graph", pollSeconds: 6, openInNewTab: true,
            orientation: "LR", graphHeight: 380, graphWidth: 0, align: "center",
            blinkCurrent: true, nodeStyle: "chip" },
      config || {});

    // Modal contract -- without these, Save/Cancel won't close the SOAR modal.
    $scope.save = function () {
      if ($uibModalInstance) $uibModalInstance.close($scope.config);
    };
    $scope.cancel = function () {
      if ($uibModalInstance) $uibModalInstance.dismiss("cancel");
    };
  }
})();

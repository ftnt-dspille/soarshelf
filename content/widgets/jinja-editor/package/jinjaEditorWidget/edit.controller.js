/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
(function () {
  angular
    .module("cybersponse")
    .controller("editJinjaEditorWidget122DevCtrl", editJinjaEditorWidget122DevCtrl);

  editJinjaEditorWidget122DevCtrl.$inject = [
    "$scope",
    "$state",
    "$uibModalInstance",
    "config",
    "Entity",
  ];

  function editJinjaEditorWidget122DevCtrl(
    $scope,
    $state,
    $uibModalInstance,
    config,
    Entity
  ) {
    $scope.config = angular.extend(
      {
        title: "Jinja Editor",
        defaultTemplate: "",
        jsonSourceField: "sourcedata",
        templateSourceField: "",
      },
      config || {}
    );

    $scope.isViewPanel =
      $state &&
      $state.current &&
      typeof $state.current.name === "string" &&
      $state.current.name.indexOf("viewPanel") !== -1;

    $scope.currentModule = $state && $state.params && $state.params.module;
    $scope.fieldsArray = [];
    $scope.fieldsLoading = false;
    $scope.fieldsError = null;

    if ($scope.isViewPanel && $scope.currentModule) {
      $scope.fieldsLoading = true;
      const entity = new Entity($scope.currentModule);
      entity.loadFields().then(
        function () {
          const all = entity.getFormFieldsArray() || [];
          // Sort alphabetically by display title for the dropdown.
          $scope.fieldsArray = all.slice().sort(function (a, b) {
            return (a.title || a.name).localeCompare(b.title || b.name);
          });
          // Ensure sourcedata is selectable even if it isn't in the form-field list
          // (it often isn't surfaced as an editable form field).
          const hasSourceData = $scope.fieldsArray.some(function (f) {
            return f.name === "sourcedata";
          });
          if (!hasSourceData) {
            $scope.fieldsArray.unshift({
              name: "sourcedata",
              title: "sourcedata (raw payload)",
            });
          }
          $scope.fieldsLoading = false;
        },
        function (err) {
          $scope.fieldsLoading = false;
          $scope.fieldsError =
            (err && (err.statusText || err.message)) || "Failed to load fields";
        }
      );
    }

    $scope.save = function () {
      $uibModalInstance.close($scope.config);
    };

    $scope.cancel = function () {
      $uibModalInstance.dismiss("cancel");
    };
  }
})();

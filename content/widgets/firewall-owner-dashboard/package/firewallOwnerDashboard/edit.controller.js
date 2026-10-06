/* Copyright start 
  MIT License
  Copyright (c) 2025 Fortinet Inc
  Copyright end */
'use strict';

/* jshint camelcase: false */

(function () {
    angular
        .module('cybersponse')
        .controller('editFirewallOwnerDashboard100Ctrl', editFirewallOwnerDashboard100Ctrl);

    editFirewallOwnerDashboard100Ctrl.$inject = [
        '$scope',
        '$uibModalInstance',
        'config',
        'toaster',
        'Entity'
    ];

    function editFirewallOwnerDashboard100Ctrl(
        $scope,
        $uibModalInstance,
        config,
        toaster,
        Entity
    ) {
        $scope.cancel = cancel;
        $scope.save = save;
        $scope.config = config || {};

        // Initialize arrays
        $scope.fieldsArray = [];
        $scope.fields = {};

        /**
         * Load fields for firewall_devices module
         */
        function loadAttributes() {
            var entity = new Entity('firewall_devices');
            entity.loadFields().then(function () {
                $scope.fieldsArray = entity.getFormFieldsArray();
                $scope.fields = entity.getFormFields();

                // Include relationship fields
                angular.extend($scope.fields, entity.getRelationshipFields());

                console.log('Loaded firewall_devices fields:', $scope.fieldsArray.length);
            }).catch(function (error) {
                console.error('Error loading firewall_devices fields:', error);
                toaster.error('Failed to load firewall_devices module fields');
            });
        }

        /**
         * Initialize the edit form with default values
         */
        function init() {
            // Set default title if not present
            if (!$scope.config.title) {
                $scope.config.title = 'Firewall Owner Dashboard';
            }

            // Hardcode resource to firewall_devices
            $scope.config.resource = 'firewall_devices';

            // Set default boolean values
            if ($scope.config.showAnnouncements === undefined) {
                $scope.config.showAnnouncements = true;
            }

            if ($scope.config.autoRefresh === undefined) {
                $scope.config.autoRefresh = false;
            }

            // Default to using live data
            if ($scope.config.useLiveData === undefined) {
                $scope.config.useLiveData = true;
            }

            // Set default numeric values
            if (!$scope.config.refreshInterval) {
                $scope.config.refreshInterval = 300; // 5 minutes default
            }

            if (!$scope.config.queryLookbackDays) {
                $scope.config.queryLookbackDays = 30;
            }

            if (!$scope.config.queryLimit) {
                $scope.config.queryLimit = 100;
            }

            if (!$scope.config.defaultAdom) {
                $scope.config.defaultAdom = 'All';
            }

            if (!$scope.config.defaultRole) {
                $scope.config.defaultRole = 'Owner';
            }

            if (!$scope.config.maxPoliciesDisplay) {
                $scope.config.maxPoliciesDisplay = 10;
            }

            if ($scope.config.showMetrics === undefined) {
                $scope.config.showMetrics = true;
            }

            if ($scope.config.showTopPolicies === undefined) {
                $scope.config.showTopPolicies = true;
            }

            // Load fields for filter UI
            loadAttributes();
        }

        /**
         * Cancel and close the modal
         */
        function cancel() {
            $uibModalInstance.dismiss('cancel');
        }

        /**
         * Validate and save the configuration
         */
        function save() {
            // Validate form
            if ($scope.firewallDashboardForm.$invalid) {
                $scope.firewallDashboardForm.$setTouched();
                $scope.firewallDashboardForm.$focusOnFirstError();
                toaster.error('Please fix the validation errors before saving.');
                return;
            }

            // Validate refresh interval if auto-refresh is enabled
            if ($scope.config.autoRefresh) {
                if ($scope.config.refreshInterval < 30 || $scope.config.refreshInterval > 3600) {
                    toaster.error('Refresh interval must be between 30 and 3600 seconds.');
                    return;
                }
            }

            // Validate max policies display
            if ($scope.config.maxPoliciesDisplay < 1 || $scope.config.maxPoliciesDisplay > 50) {
                toaster.error('Maximum policies to display must be between 1 and 50.');
                return;
            }

            // Validate query settings
            if ($scope.config.useLiveData) {
                if ($scope.config.queryLookbackDays < 1 || $scope.config.queryLookbackDays > 365) {
                    toaster.error('Query lookback period must be between 1 and 365 days.');
                    return;
                }

                if ($scope.config.queryLimit < 1 || $scope.config.queryLimit > 1000) {
                    toaster.error('Query limit must be between 1 and 1000.');
                    return;
                }
            }

            // Ensure resource is set to firewall_devices
            $scope.config.resource = 'firewall_devices';

            // Save the configuration
            $uibModalInstance.close($scope.config);
        }

        // Initialize the controller
        init();
    }
})();
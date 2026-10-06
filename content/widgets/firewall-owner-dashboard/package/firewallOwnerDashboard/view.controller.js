/* Copyright start
  MIT License
  Copyright (c) 2025 Fortinet Inc
  Copyright end */
'use strict';

/* jshint camelcase: false */

(function () {
    angular.module('cybersponse')
        .controller('firewallOwnerDashboard100Ctrl', firewallOwnerDashboard100Ctrl);

    firewallOwnerDashboard100Ctrl.$inject = ['$scope', 'config', '$rootScope', '$filter', '$http', 'usersService', 'Query', 'API', 'mockDataService'];

    function firewallOwnerDashboard100Ctrl($scope, config, $rootScope, $filter, $http, usersService, Query, API, mockDataService) {
        var DEFAULT_LOOKBACK_DAYS = 30;
        var DEFAULT_QUERY_LIMIT = 500;
        var CURRENT_USER_EMAIL_KEY = 'firewallOwnerDashboard.currentUserEmail';
        $scope.announcements = mockDataService.getAnnouncements();

        $scope.config = config || {};
        $scope.processing = false;
        $scope.collapsed = false;
        $scope.searchQuery = '';
        $scope.activeTab = 'policies';
        $scope.filters = {
            adom: 'All',
            role: 'Owner'
        };
        $scope.currentUserName = '';
        $scope.currentUserEmail = '';

        /**
         * Helper function to safely get a nested field value
         */
        function _getFieldValue(obj, fieldPath, defaultValue) {
            if (!fieldPath) return defaultValue;

            var value = obj;
            var parts = fieldPath.split('.');

            for (var i = 0; i < parts.length; i++) {
                if (value == null) return defaultValue;
                value = value[parts[i]];
            }

            return value != null ? value : defaultValue;
        }

        /**
         * Format time from minutes to days, hours, minutes format
         */
        function _formatTimeFromMinutes(minutes) {
            if (!minutes || minutes === 0) return '0m';

            var days = Math.floor(minutes / (60 * 24));
            var hours = Math.floor((minutes % (60 * 24)) / 60);
            var mins = Math.floor(minutes % 60);

            var parts = [];
            if (days > 0) parts.push(days + 'd');
            if (hours > 0) parts.push(hours + 'h');
            if (mins > 0) parts.push(mins + 'm');

            return parts.length > 0 ? parts.join(' ') : '0m';
        }

        /**
         * Map a device record from the API to the widget's expected format
         * Hardcoded for firewall_devices module
         */
        function _mapFirewallDevice(device) {
            var nowSeconds = Math.floor(Date.now() / 1000);

            // Hardcoded field mappings for firewall_devices module
            var hostname = _getFieldValue(device, 'hostname', null) ||
                _getFieldValue(device, 'deviceID', 'Unknown');

            var deviceID = _getFieldValue(device, 'deviceID', '');
            var adom = _getFieldValue(device, 'aDOM', 'Unknown');
            var mgmtIP = _getFieldValue(device, 'mGMTIP', '');
            var haRole = _getFieldValue(device, 'hARole', null) ||
                _getFieldValue(device, 'hAStatus', null) ||
                _getFieldValue(device, 'connectionStatus', 'Unknown');

            var cpuUsage = Number(_getFieldValue(device, 'cPUUsage', 0)) || 0;
            var memoryUsage = Number(_getFieldValue(device, 'memoryUsage', 0)) || 0;

            var uptimeSince = _getFieldValue(device, 'uptimeSince', null);
            var uptimeSeconds = 0;
            if (uptimeSince) {
                var uptimeTimestamp = typeof uptimeSince === 'number' ? uptimeSince :
                    new Date(uptimeSince).getTime() / 1000;
                uptimeSeconds = Math.max(0, nowSeconds - uptimeTimestamp);
            }

            var lastSync = _getFieldValue(device, 'lastSync', null);
            var lastSyncMin = 0;
            var lastSyncText = '0m';
            if (lastSync) {
                var lastSyncTimestamp = typeof lastSync === 'number' ? lastSync :
                    new Date(lastSync).getTime() / 1000;
                lastSyncMin = Math.max(0, Math.floor((nowSeconds - lastSyncTimestamp) / 60));
                lastSyncText = _formatTimeFromMinutes(lastSyncMin);
            }

            var firewallRules = _getFieldValue(device, 'firewallRules', null) || [];

            return {
                id: device.uuid || device['@id'] || device.deviceID || hostname,
                name: hostname,
                adom: adom,
                primary: haRole ? haRole.toLowerCase() === 'master' || haRole.toLowerCase() === 'primary' : false,
                serial: deviceID,
                mgmt_ip: mgmtIP,
                uptime: uptimeSeconds,
                nextChange: null,
                status: {
                    ha: haRole,
                    cpu: cpuUsage,
                    mem: memoryUsage
                },
                lastSyncMin: lastSyncMin,
                lastSyncText: lastSyncText,
                selectedPolicies: [],
                contacts: {
                    owner: {name: 'Unknown'},
                    delegate: {name: 'Unknown'},
                    cx: {name: 'Unknown'}
                },
                _raw: device // Keep raw data for reference
            };
        }

        /**
         * Map firewall rules/policies from raw data
         */
        function _mapFirewallRules(rules) {
            if (!Array.isArray(rules)) return [];

            return rules.map(function (rule) {
                return {
                    policy: rule.policyID || rule.id || 0,
                    name: rule.ruleName || rule.name || rule.comments || 'Policy',
                    hits: Number(rule.hitCount) || Number(rule.hits) || 0,
                    bytes: rule.bytes ? Number(rule.bytes) : 0,
                    action: rule.action || 'allow',
                    enabled: rule.status ? rule.status.toLowerCase() === 'enable' : true,
                    section: rule.sourceZone || rule.section || 'N/A'
                };
            });
        }

        /**
         * Build policies by firewall from the raw data
         */
        function _buildPoliciesByFw(firewalls, members) {
            var policiesByFw = {};

            members.forEach(function (member, index) {
                var firewall = firewalls[index];
                if (!firewall) return;

                var rawRules = firewall._raw.firewallRules ||
                    firewall._raw.policies ||
                    firewall._raw.rules ||
                    [];

                var rules = _mapFirewallRules(rawRules);
                policiesByFw[firewall.id] = rules;

                // Set top policies
                firewall.topPolicies = rules.slice(0, 3).map(function (rule) {
                    return {id: rule.policy, name: rule.name, hits: rule.hits};
                });
            });

            return policiesByFw;
        }

        function rebuildAdomOptions() {
            var seen = {};
            var adoms = [];

            ($scope.firewalls || []).forEach(function (fw) {
                var a = (fw && fw.adom) ? String(fw.adom).trim() : '';
                if (a && !seen[a]) {
                    seen[a] = true;
                    adoms.push(a);
                }
            });

            adoms.sort();
            $scope.adomOptions = [{value: 'All', label: 'All ADOMs'}]
                .concat(adoms.map(function (a) {
                    return {value: a, label: a};
                }));
        }

        /**
         * Apply firewalls and policies to scope
         */
        function _applyFirewalls(firewalls, policiesByFw) {
            $scope.firewalls = firewalls;
            rebuildAdomOptions();
            $scope.policiesByFw = policiesByFw || {};
            $scope.filteredFirewalls = angular.copy($scope.firewalls);
            $scope.selectedFirewall = $scope.filteredFirewalls[0];
            $scope.selectedPolicies = $scope.selectedFirewall
                ? ($scope.policiesByFw[$scope.selectedFirewall.id] || [])
                : [];
            calculateMaxPolicyHits();
        }

        /**
         * Use mock data for demonstration
         */
        function _useMockData() {
            var mockFirewalls = mockDataService.getFirewalls();
            var mockPoliciesByFw = mockDataService.getPoliciesByFirewall();
            _applyFirewalls(mockFirewalls, mockPoliciesByFw);
        }

        /**
         * Fetch live firewalls from FortiSOAR using configured query
         * Hardcoded for firewall_devices module
         */
        function _fetchLiveFirewalls() {
            var lookbackDays = $scope.config.queryLookbackDays || DEFAULT_LOOKBACK_DAYS;
            var lookbackMs = lookbackDays * 24 * 60 * 60 * 1000;
            var sinceIso = new Date(Date.now() - lookbackMs).toISOString();
            var limit = $scope.config.queryLimit || DEFAULT_QUERY_LIMIT;

            // Build query object
            var queryObject = {
                limit: limit,
                logic: 'AND',
                filters: [],
                aggregates: [],
                sort: []
            };

            // Add date filter for modified records
            queryObject.filters.push({
                field: 'modifyDate',
                operator: 'gte',
                value: $scope.config.querySince || sinceIso
            });

            // Add user-configured filters if present
            if ($scope.config.query && $scope.config.query.filters) {
                queryObject.filters = queryObject.filters.concat($scope.config.query.filters);
            }

            // Apply sorting if configured
            if ($scope.config.query && $scope.config.query.sort) {
                queryObject.sort = $scope.config.query.sort;
            }

            $scope.processing = true;

            // Use Query service to construct the query for firewall_devices
            var queryObj = new Query(queryObject);
            var endpoint = API.QUERY + 'firewall_devices?$relationships=true';

            $http.post(endpoint, queryObj.getQuery(true)).then(function (response) {
                var members = response && response.data && response.data['hydra:member']
                    ? response.data['hydra:member']
                    : [];

                if (!members.length) {
                    console.warn('No firewall_devices records returned from query, using mock data');
                    _useMockData();
                    return;
                }

                var firewalls = members.map(_mapFirewallDevice);
                var policiesByFw = _buildPoliciesByFw(firewalls, members);
                _applyFirewalls(firewalls, policiesByFw);
            }).catch(function (error) {
                console.error('Error fetching firewall_devices:', error);
                _useMockData();
            }).finally(function () {
                $scope.processing = false;
            });
        }

        /**
         * Apply default configuration values
         */
        function _applyConfigDefaults() {
            if ($scope.config.showAnnouncements === undefined) $scope.config.showAnnouncements = true;
            if ($scope.config.autoRefresh === undefined) $scope.config.autoRefresh = false;

            // Default to using live data from firewall_devices
            if ($scope.config.useLiveData === undefined) $scope.config.useLiveData = true;

            // Hardcode resource to firewall_devices
            $scope.config.resource = 'firewall_devices';

            if (!$scope.config.refreshInterval) $scope.config.refreshInterval = 300;
            if (!$scope.config.defaultAdom) $scope.config.defaultAdom = 'All';
            if (!$scope.config.defaultRole) $scope.config.defaultRole = 'Owner';
        }

        /**
         * Apply current user information
         */
        function _applyCurrentUser(user) {
            if (!user) return;

            var nameParts = [];
            if (user.firstname) nameParts.push(user.firstname);
            if (user.lastname) nameParts.push(user.lastname);
            $scope.currentUserName = nameParts.join(' ');
            $scope.currentUserEmail = user.email || '';

            if ($scope.currentUserEmail) {
                window.localStorage.setItem(CURRENT_USER_EMAIL_KEY, $scope.currentUserEmail);
            }
            const mockData = require('./WidgetAssets/js/mockData');
        }

        /**
         * Load current user information
         */
        function _loadCurrentUser() {
            var cachedEmail = window.localStorage.getItem(CURRENT_USER_EMAIL_KEY);
            if (cachedEmail) {
                $scope.currentUserEmail = cachedEmail;
            }

            try {
                var userResult = usersService.getCurrentUser();
                if (userResult && typeof userResult.then === 'function') {
                    userResult.then(_applyCurrentUser).catch(function () {
                        // Ignore errors and keep cached email if available.
                    });
                } else {
                    _applyCurrentUser(userResult);
                }
            } catch (error) {
                // Ignore errors and keep cached email if available.
            }
        }

        /**
         * Initialize the widget
         */
        function _init() {
            _applyConfigDefaults();
            $scope.currentTheme = $rootScope.theme ? $rootScope.theme.id : 'light';
            $scope.filters.adom = $scope.config.defaultAdom;
            $scope.filters.role = $scope.config.defaultRole;
            _loadCurrentUser();

            // Always use firewall_devices module
            if ($scope.config.useLiveData) {
                _fetchLiveFirewalls();
            } else {
                _useMockData();
            }
        }

        // Helper function to format uptime
        $scope.formatUptime = function (seconds) {
            if (!seconds) return '0d 00:00';
            var days = Math.floor(seconds / 86400);
            var hours = Math.floor((seconds % 86400) / 3600);
            var minutes = Math.floor((seconds % 3600) / 60);
            return days + 'd ' +
                String(hours).padStart(2, '0') + ':' +
                String(minutes).padStart(2, '0');
        };

        // Filter firewalls based on search query and ADOM
        $scope.filterFirewalls = function () {
            $scope.filteredFirewalls = $scope.firewalls.filter(function (fw) {
                var matchesAdom = $scope.filters.adom === 'All' || fw.adom === $scope.filters.adom;
                var matchesSearch = !$scope.searchQuery ||
                    fw.name.toLowerCase().indexOf($scope.searchQuery.toLowerCase()) !== -1 ||
                    fw.serial.toLowerCase().indexOf($scope.searchQuery.toLowerCase()) !== -1;
                return matchesAdom && matchesSearch;
            });

            // If current selection is not in filtered list, select first available
            if ($scope.selectedFirewall) {
                var stillVisible = $scope.filteredFirewalls.some(function (fw) {
                    return fw.id === $scope.selectedFirewall.id;
                });

                if (!stillVisible && $scope.filteredFirewalls.length > 0) {
                    $scope.selectFirewall($scope.filteredFirewalls[0]);
                }
            }
        };

        // Select a firewall
        $scope.selectFirewall = function (firewall) {
            $scope.selectedFirewall = firewall;
            $scope.selectedPolicies = $scope.policiesByFw[firewall.id] || [];
            $scope.activeTab = 'policies';
            calculateMaxPolicyHits();
        };

        // Calculate max policy hits for chart scaling
        function calculateMaxPolicyHits() {
            $scope.maxPolicyHits = 0;
            if ($scope.selectedPolicies.length > 0) {
                $scope.maxPolicyHits = Math.max.apply(Math, $scope.selectedPolicies.map(function (p) {
                    return p.hits;
                }));
            }
        }

        // Watch for config changes
        $scope.$watch('config', function (newConfig) {
            if (newConfig) {
                $scope.config = newConfig;
            }
        }, true);

        _init();
    }
})();
/* Copyright start
  MIT License
  Copyright (c) 2024 Fortinet Inc
  Copyright end */
'use strict';
(function () {
    angular
        .module('cybersponse')
        .controller('socreport100Ctrl', socreport100Ctrl);

    socreport100Ctrl.$inject = ['$scope', '$state', 'Entity', '$q', 'toaster', '$http', 'API', 'Query', 'Modules'];

    function socreport100Ctrl($scope, $state, Entity, $q, toaster, $http, API, Query, Modules) {
        $scope.loading = true;
        $scope.error = null;
        $scope.deviceSummary = [];
        $scope.matchingRecords = [];
        $scope.totalDevices = 0;
        $scope.totalRevisions = 0;
        $scope.totalMatches = 0;
        $scope.changeNumber = '';
        $scope.recordInfo = {};

        // Get module and record ID from state params
        $scope.module = $state.params.module;
        $scope.recordId = $state.params.id;

        // Determine widget context
        $scope.isViewPanel = $state.current && $state.current.name.indexOf('viewPanel') !== -1;
        $scope.isDashboard = $state.current && $state.current.name.indexOf('dashboard') !== -1;
        $scope.isReporting = $state.current && $state.current.name.indexOf('reporting') !== -1;

        function loadRecordData() {
            // Determine usage mode
            var usageMode = $scope.config.usageMode || 'auto';
            if (usageMode === 'auto') {
                usageMode = $scope.isViewPanel ? 'detail' : 'query';
            }

            console.log('Loading record data with usage mode:', usageMode);
            console.log('Widget context - isViewPanel:', $scope.isViewPanel, 'isDashboard:', $scope.isDashboard, 'isReporting:', $scope.isReporting);

            if (usageMode === 'detail') {
                loadRecordFromDetailPage();
            } else {
                loadRecordFromQuery();
            }
        }

        function loadRecordFromDetailPage() {
            if (!$scope.module || !$scope.recordId) {
                $scope.error = 'This widget can only be used on record detail pages when in detail mode.';
                $scope.loading = false;
                return;
            }

            if (!$scope.config.selectedField) {
                $scope.error = 'No field selected in widget configuration.';
                $scope.loading = false;
                return;
            }

            console.log('Loading record from detail page - Module:', $scope.module, 'ID:', $scope.recordId);

            var entity = new Entity($scope.module);
            entity.get($scope.recordId, { $relationships: true }).then(function() {
                $scope.entity = entity;
                $scope.recordInfo = {
                    module: $scope.module,
                    id: $scope.recordId,
                    loadMethod: 'Detail Page'
                };

                extractDataFromEntity();
            }).catch(function(error) {
                $scope.error = 'Failed to load record data: ' + (error.message || 'Unknown error');
                $scope.loading = false;
            });
        }

        function loadRecordFromQuery() {
            var moduleToQuery = $scope.config.module;

            if (!moduleToQuery) {
                $scope.error = 'No module specified in widget configuration for dashboard/report usage.';
                $scope.loading = false;
                return;
            }

            if (!$scope.config.selectedField) {
                $scope.error = 'No field selected in widget configuration.';
                $scope.loading = false;
                return;
            }

            if (!$scope.config.query || !$scope.config.query.filters || $scope.config.query.filters.length === 0) {
                $scope.error = 'No query filters configured to identify the record.';
                $scope.loading = false;
                return;
            }

            console.log('Loading record from query - Module:', moduleToQuery);
            console.log('Query config:', $scope.config.query);

            // Build query object
            var queryObject = {
                sort: [],
                limit: 1, // We only need the first matching record
                logic: $scope.config.query.logic || 'AND',
                filters: $scope.config.query.filters || [],
                $relationships: true
            };

            // Add fields we need to select
            var fieldsToSelect = [$scope.config.selectedField];
            if ($scope.config.changeNumberField) {
                fieldsToSelect.push($scope.config.changeNumberField);
            }
            queryObject.__selectFields = fieldsToSelect.join(',');

            var query = new Query(queryObject);

            // Make API call to find the record
            $http.post(API.QUERY + moduleToQuery, query.getQuery(true)).then(function(response) {
                if (response.data && response.data['hydra:member'] && response.data['hydra:member'].length > 0) {
                    var record = response.data['hydra:member'][0];
                    console.log('Found record via query:', record);

                    // Create a mock entity-like object for consistency
                    $scope.entity = {
                        fields: {}
                    };

                    // Map the record data to the entity structure
                    fieldsToSelect.forEach(function(fieldName) {
                        if (record[fieldName] !== undefined) {
                            $scope.entity.fields[fieldName] = {
                                value: record[fieldName]
                            };
                        }
                    });

                    $scope.recordInfo = {
                        module: moduleToQuery,
                        id: record['@id'] || record.uuid || record.id || 'Unknown',
                        loadMethod: 'Query',
                        queryFilters: $scope.config.query.filters.length
                    };

                    extractDataFromEntity();
                } else {
                    $scope.error = 'No records found matching the specified query filters.';
                    $scope.loading = false;
                }
            }).catch(function(error) {
                console.error('Error querying for record:', error);
                $scope.error = 'Failed to query for record: ' + (error.message || 'Unknown error');
                $scope.loading = false;
            });
        }

        function extractDataFromEntity() {
            // Get the change number from the configured field
            if ($scope.config.changeNumberField) {
                var changeNumberValue = $scope.entity.fields[$scope.config.changeNumberField];
                if (changeNumberValue && changeNumberValue.value) {
                    $scope.changeNumber = changeNumberValue.value;
                }
            }

            processReportData();
        }

        function processReportData() {
            try {
                var fieldValue = $scope.entity.fields[$scope.config.selectedField];

                if (!fieldValue || !fieldValue.value) {
                    $scope.error = 'No data found in the selected field.';
                    $scope.loading = false;
                    return;
                }

                var rawValue = fieldValue.value;
                var jsonData;

                // Parse JSON data
                if (typeof rawValue === 'string') {
                    try {
                        jsonData = JSON.parse(rawValue);
                    } catch (parseError) {
                        $scope.error = 'Invalid JSON data in the selected field: ' + parseError.message;
                        $scope.loading = false;
                        return;
                    }
                } else {
                    jsonData = rawValue;
                }

                // Apply JSON path extraction if configured
                if ($scope.config.showJsonPath && $scope.config.jsonPath) {
                    try {
                        jsonData = extractFromJsonPath(jsonData, $scope.config.jsonPath);
                        if (jsonData === undefined || jsonData === null) {
                            $scope.error = 'No data found at the specified JSON path: ' + $scope.config.jsonPath;
                            $scope.loading = false;
                            return;
                        }
                    } catch (pathError) {
                        $scope.error = 'Error extracting data from JSON path: ' + pathError.message;
                        $scope.loading = false;
                        return;
                    }
                }

                // Process the data structure
                processDeviceSummary(jsonData);
                processMatchingRecords(jsonData);

                $scope.loading = false;

            } catch (error) {
                console.error('Error processing report data:', error);
                $scope.error = 'Error processing report data: ' + error.message;
                $scope.loading = false;
            }
        }

        function extractFromJsonPath(data, path) {
            // Simple JSON path implementation using dot notation
            var parts = path.split('.');
            var current = data;

            for (var i = 0; i < parts.length; i++) {
                var part = parts[i];

                // Handle array notation like "items[0]"
                var arrayMatch = part.match(/^([^[]+)\[(\d+)\]$/);
                if (arrayMatch) {
                    var arrayName = arrayMatch[1];
                    var arrayIndex = parseInt(arrayMatch[2]);

                    if (current[arrayName] && Array.isArray(current[arrayName]) && current[arrayName][arrayIndex] !== undefined) {
                        current = current[arrayName][arrayIndex];
                    } else {
                        return undefined;
                    }
                } else {
                    if (current && typeof current === 'object' && current[part] !== undefined) {
                        current = current[part];
                    } else {
                        return undefined;
                    }
                }
            }

            return current;
        }

        function processDeviceSummary(jsonData) {
            // Handle records_by_device data
            if (jsonData.records_by_device && Array.isArray(jsonData.records_by_device)) {
                $scope.deviceSummary = jsonData.records_by_device.map(function(device) {
                    return {
                        device: device.device,
                        total: device.total,
                        matches: 0 // Will be calculated from matching records
                    };
                });

                // Calculate total devices and revisions
                $scope.totalDevices = $scope.deviceSummary.length;
                $scope.totalRevisions = $scope.deviceSummary.reduce(function(sum, device) {
                    return sum + device.total;
                }, 0);
            }
        }

        function processMatchingRecords(jsonData) {
            // Handle records_matching_query data
            if (jsonData.records_matching_query && Array.isArray(jsonData.records_matching_query)) {
                $scope.matchingRecords = jsonData.records_matching_query.map(function(record) {
                    return {
                        id: record.id,
                        uuid: record.uuid,
                        device: record.device,
                        revisionID: record.revisionID,
                        comments: record.comments,
                        status: record.status ? record.status.itemValue : 'Unknown',
                        statusColor: getStatusColor(record.status ? record.status.itemValue : 'Unknown'),
                        extraInfo: record.extraInfo,
                        modifiedDate: formatDateTime(record.modifiedDate),
                        modifyingUser: record.modifyingUser,
                        installingUser: record.installingUser,
                        installTime: formatDateTime(record.installTime),
                        // Since records are pre-filtered, we know they contain the CHG
                        hasCHG: true,
                        // Extract CHG numbers from comments
                        chgNumbers: extractCHGNumbers(record.comments)
                    };
                });

                $scope.totalMatches = $scope.matchingRecords.length;

                // Update device summary with match counts
                updateDeviceMatchCounts();
            }
        }

        function updateDeviceMatchCounts() {
            // Count matches per device
            var matchCounts = {};
            $scope.matchingRecords.forEach(function(record) {
                if (!matchCounts[record.device]) {
                    matchCounts[record.device] = 0;
                }
                matchCounts[record.device]++;
            });

            // Update device summary with match counts
            $scope.deviceSummary.forEach(function(device) {
                device.matches = matchCounts[device.device] || 0;
            });
        }

        function extractCHGNumbers(text) {
            if (!text) return [];
            var matches = text.match(/CHG\d+/gi);
            return matches || [];
        }

        function formatDateTime(timestamp) {
            if (!timestamp) return 'N/A';

            try {
                // Handle both Unix timestamp and regular timestamp
                var date = new Date(timestamp * 1000); // Assume Unix timestamp
                if (isNaN(date.getTime())) {
                    date = new Date(timestamp); // Try regular timestamp
                }
                if (isNaN(date.getTime())) {
                    return timestamp.toString();
                }
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
            } catch (e) {
                return timestamp.toString();
            }
        }

        function getStatusColor(status) {
            switch (status.toLowerCase()) {
                case 'installed': return 'success';
                case 'pending': return 'warning';
                case 'failed': return 'danger';
                case 'cancelled': return 'secondary';
                case 'active': return 'info';
                default: return 'info';
            }
        }

        // Get devices sorted by revision count
        $scope.getDevicesWithCounts = function() {
            return $scope.deviceSummary.sort(function(a, b) {
                return b.total - a.total; // Sort by revision count descending
            });
        };

        // Get matching records by device
        $scope.getMatchingRecordsByDevice = function(deviceName) {
            return $scope.matchingRecords.filter(function(record) {
                return record.device === deviceName;
            }).sort(function(a, b) {
                return b.revisionID - a.revisionID; // Sort by revision ID descending
            });
        };

        // Get all matching records sorted
        $scope.getAllMatchingRecords = function() {
            return $scope.matchingRecords.sort(function(a, b) {
                // First sort by device, then by revision ID
                if (a.device === b.device) {
                    return b.revisionID - a.revisionID;
                }
                return a.device.localeCompare(b.device);
            });
        };

        // Get unique CHG numbers from all matching records
        $scope.getAllCHGNumbers = function() {
            var allCHGs = [];
            $scope.matchingRecords.forEach(function(record) {
                allCHGs = allCHGs.concat(record.chgNumbers);
            });
            // Return unique CHG numbers
            return allCHGs.filter(function(chg, index, self) {
                return self.indexOf(chg) === index;
            });
        };


        // Refresh data
        $scope.refreshData = function() {
            $scope.loading = true;
            $scope.error = null;
            $scope.deviceSummary = [];
            $scope.matchingRecords = [];
            $scope.totalDevices = 0;
            $scope.totalRevisions = 0;
            $scope.totalMatches = 0;
            $scope.changeNumber = '';
            loadRecordData();
        };

        // Check if there's data to display
        $scope.hasData = function() {
            return $scope.deviceSummary.length > 0 || $scope.matchingRecords.length > 0;
        };

        // Get usage mode display text
        $scope.getUsageModeText = function() {
            if ($scope.isViewPanel) {
                return 'Record Detail View';
            } else if ($scope.isDashboard) {
                return 'Dashboard';
            } else if ($scope.isReporting) {
                return 'Reporting';
            } else {
                return 'Unknown Context';
            }
        };

        function _init() {
            if (!$scope.config) {
                $scope.error = 'Widget configuration not found.';
                $scope.loading = false;
                return;
            }

            console.log('SOC Report Widget initializing...');
            console.log('Config:', $scope.config);
            console.log('State params:', $state.params);
            console.log('Current state:', $state.current);

            loadRecordData();
        }

        _init();
    }
})();
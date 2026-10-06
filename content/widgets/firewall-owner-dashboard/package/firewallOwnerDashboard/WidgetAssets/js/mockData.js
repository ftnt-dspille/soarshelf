/* Copyright start
  MIT License
  Copyright (c) 2025 Fortinet Inc
  Copyright end */
'use strict';

(function () {
    angular
        .module('cybersponse')
        .factory('mockDataService', mockDataService);

    function mockDataService() {
        const announcements = [
            {
                id: 'a1',
                title: 'FAZ maintenance window',
                body: 'Analyzer search will be read-only during the window.',
                severity: 'warn',
                scope: 'ADOM:Prod',
                start: new Date('2025-10-25T01:00:00Z'),
                end: new Date('2025-10-25T02:00:00Z')
            },
            {
                id: 'a2',
                title: 'Policy naming standard updated',
                body: 'Use SEC-<Section>-<Purpose> format.',
                severity: 'info',
                scope: 'Global',
                start: new Date('2025-10-20T00:00:00Z'),
                end: new Date('2025-11-30T00:00:00Z')
            }
        ];

        const firewalls = [
            {
                id: 'fw-0001',
                name: 'fw-0001',
                adom: 'ADOM1',
                primary: true,
                serial: 'FGT60FTK00000001',
                mgmt_ip: '192.0.2.10',
                uptime: 18 * 24 * 3600 + 4 * 3600 + 12 * 60,
                nextChange: {
                    number: 'CRQ0001234',
                    start: new Date('2025-10-24T18:00:00Z'),
                    end: new Date('2025-10-24T19:00:00Z'),
                    risk: 'Moderate'
                },
                status: {
                    ha: 'OK',
                    cpu: 22,
                    mem: 48
                },
                lastSyncMin: 5,
                topPolicies: [
                    {id: 12, name: 'Allow-App', hits: 14233},
                    {id: 20, name: 'Web', hits: 8912},
                    {id: 5, name: 'DNAT', hits: 3110}
                ],
                contacts: {
                    owner: {name: 'NetSec Team'},
                    delegate: {name: 'Jane Doe'},
                    cx: {name: 'ACME, Inc.'}
                }
            },
            {
                id: 'fw-0002',
                name: 'fw-0002',
                adom: 'ADOM1',
                primary: false,
                serial: 'FGT81FTK00000002',
                mgmt_ip: '192.0.2.20',
                uptime: 3 * 24 * 3600 + 22 * 3600 + 41 * 60,
                nextChange: null,
                status: {
                    ha: 'WARN: role mismatch',
                    cpu: 31,
                    mem: 61
                },
                lastSyncMin: 12,
                topPolicies: [
                    {id: 5, name: 'DNAT', hits: 3110},
                    {id: 7, name: 'VPN', hits: 2002}
                ],
                contacts: {
                    owner: {name: 'NetSec Team'},
                    delegate: {name: 'John Smith'},
                    cx: {name: 'ACME, Inc.'}
                }
            },
            {
                id: 'fw-0003',
                name: 'fw-0003',
                adom: 'ADOM2',
                primary: true,
                serial: 'FGT60FTK00000003',
                mgmt_ip: '192.0.2.30',
                uptime: 45 * 24 * 3600 + 8 * 3600 + 23 * 60,
                nextChange: {
                    number: 'CRQ0001235',
                    start: new Date('2025-10-26T20:00:00Z'),
                    end: new Date('2025-10-26T21:30:00Z'),
                    risk: 'Low'
                },
                status: {
                    ha: 'OK',
                    cpu: 18,
                    mem: 42
                },
                lastSyncMin: 3,
                topPolicies: [
                    {id: 15, name: 'DMZ-Access', hits: 11500},
                    {id: 22, name: 'Internal', hits: 9200}
                ],
                contacts: {
                    owner: {name: 'NetSec Team'},
                    delegate: {name: 'Bob Johnson'},
                    cx: {name: 'TechCorp'}
                }
            }
        ];

        const policiesByFw = {
            'fw-0001': [
                {
                    policy: 12,
                    name: 'Allow-App',
                    hits: 14233,
                    bytes: 18.2,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-APP'
                },
                {
                    policy: 20,
                    name: 'Web',
                    hits: 8912,
                    bytes: 9.1,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-WEB'
                },
                {
                    policy: 5,
                    name: 'DNAT',
                    hits: 3110,
                    bytes: 2.6,
                    action: 'nat',
                    enabled: true,
                    section: 'SEC-NAT'
                },
                {
                    policy: 8,
                    name: 'Block-Malicious',
                    hits: 1205,
                    bytes: 0.8,
                    action: 'deny',
                    enabled: true,
                    section: 'SEC-SECURITY'
                }
            ],
            'fw-0002': [
                {
                    policy: 5,
                    name: 'DNAT',
                    hits: 3110,
                    bytes: 2.6,
                    action: 'nat',
                    enabled: true,
                    section: 'SEC-NAT'
                },
                {
                    policy: 7,
                    name: 'VPN',
                    hits: 2002,
                    bytes: 1.9,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-VPN'
                }
            ],
            'fw-0003': [
                {
                    policy: 15,
                    name: 'DMZ-Access',
                    hits: 11500,
                    bytes: 15.3,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-DMZ'
                },
                {
                    policy: 22,
                    name: 'Internal',
                    hits: 9200,
                    bytes: 12.1,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-INTERNAL'
                },
                {
                    policy: 10,
                    name: 'Guest-WiFi',
                    hits: 4500,
                    bytes: 5.2,
                    action: 'allow',
                    enabled: true,
                    section: 'SEC-GUEST'
                }
            ]
        };
        var service;

        service = {
            getAnnouncements: function () {
                return announcements;
            },
            getFirewalls: function () {
                return firewalls;
            },
            getPoliciesByFirewall: function () {
                return policiesByFw;
            }
        }

        return service;
    }
})();

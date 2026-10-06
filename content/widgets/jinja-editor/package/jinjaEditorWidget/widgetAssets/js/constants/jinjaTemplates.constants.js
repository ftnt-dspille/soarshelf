/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
(function () {
    const ns = (window.JinjaEditorWidget = window.JinjaEditorWidget || {});

    // Each entry is a ready-to-run example that pairs a Jinja template with a
    // matching input JSON. Selecting an entry from the picker replaces both the
    // template and input panes so the user can hit Render immediately.
    ns.templateExamples = [
        // ── Original examples (preserved verbatim) ────────────────────────────────
        {
            id: "greeting",
            label: "Greeting — simple variable",
            description: "Interpolate a single field with a fallback.",
            template: "Hello, {{ vars.input.records[0].name | default('stranger') }}!",
            input: {
                vars: { input: { records: [{ name: "Ada" }] } },
            },
        },
        {
            id: "record-summary",
            label: "Record summary — multi-line",
            description: "Print several fields from the current record.",
            template:
                "Name:    {{ vars.input.records[0].name }}\n" +
                "Email:   {{ vars.input.records[0].email | default('n/a') }}\n" +
                "Status:  {{ vars.input.records[0].status | upper }}",
            input: {
                vars: {
                    input: {
                        records: [
                            { name: "Ada Lovelace", email: "ada@example.com", status: "active" },
                        ],
                    },
                },
            },
        },
        {
            id: "loop-table",
            label: "Loop — render a table of alerts",
            description: "Iterate over records with loop.index and conditional rows.",
            template:
                "{% for alert in vars.input.records %}\n" +
                "{{ loop.index }}. [{{ alert.severity | upper }}] {{ alert.name }}" +
                "{% if alert.assigned_to %} → {{ alert.assigned_to }}{% endif %}\n" +
                "{% else %}\n" +
                "No alerts to show.\n" +
                "{% endfor %}",
            input: {
                vars: {
                    input: {
                        records: [
                            { name: "Suspicious login", severity: "high", assigned_to: "soc" },
                            { name: "Port scan", severity: "medium" },
                        ],
                    },
                },
            },
        },
        {
            id: "conditional",
            label: "Conditional — if / elif / else",
            description: "Branch on a numeric score.",
            template:
                "{% set score = vars.input.records[0].risk_score %}\n" +
                "{% if score >= 80 %}\n" +
                "CRITICAL — immediate response required ({{ score }}).\n" +
                "{% elif score >= 50 %}\n" +
                "Elevated — review within the hour ({{ score }}).\n" +
                "{% else %}\n" +
                "Low — routine handling ({{ score }}).\n" +
                "{% endif %}",
            input: {
                vars: { input: { records: [{ risk_score: 72 }] } },
            },
        },
        {
            id: "macro",
            label: "Macro — reusable row renderer",
            description: "Define a macro and call it inside a loop.",
            template:
                "{% macro row(item) %}" +
                "- {{ item.name }} ({{ item.count | default(0) }})" +
                "{% endmacro %}\n" +
                "{% for item in vars.input.records %}\n" +
                "{{ row(item) }}\n" +
                "{% endfor %}",
            input: {
                vars: {
                    input: {
                        records: [
                            { name: "phishing", count: 12 },
                            { name: "malware", count: 3 },
                            { name: "policy" },
                        ],
                    },
                },
            },
        },
        {
            id: "filter-chain",
            label: "Filter chain — normalize strings",
            description: "Demonstrates trim, lower, replace, title filters.",
            template:
                "{{ vars.input.records[0].title " +
                "| default('untitled') " +
                "| trim " +
                "| lower " +
                "| replace('_', ' ') " +
                "| title }}",
            input: {
                vars: {
                    input: { records: [{ title: "  incident_response_runbook  " }] },
                },
            },
        },
        {
            id: "json-extract",
            label: "Extract — unique list join",
            description: "Collect one field across records and join the unique values.",
            template:
                "Affected hosts: " +
                "{{ vars.input.records | map(attribute='host') | unique | list | join(', ') }}",
            input: {
                vars: {
                    input: {
                        records: [
                            { host: "web-01" },
                            { host: "web-02" },
                            { host: "web-01" },
                            { host: "db-07" },
                        ],
                    },
                },
            },
        },
        {
            id: "api-response",
            label: "API response — summarize a result block",
            description: "Typical vars.steps.<step>.data shape from FortiSOAR.",
            template:
                "Fetched {{ vars.steps.getUsers.data.hydra_totalItems }} user(s):\n" +
                "{% for user in vars.steps.getUsers.data['hydra_member'] %}\n" +
                "- {{ user.userName }} <{{ user.email | default('no-email') }}>\n" +
                "{% endfor %}",
            input: {
                vars: {
                    steps: {
                        getUsers: {
                            data: {
                                hydra_totalItems: 2,
                                hydra_member: [
                                    { userName: "alice", email: "alice@example.com" },
                                    { userName: "bob" },
                                ],
                            },
                        },
                    },
                },
            },
        },

        // ── New FortiSOAR scenario templates ─────────────────────────────────────

        {
            id: "alert-summary-table",
            label: "Alert summary — HTML table via json2html",
            description:
                "Renders open alerts as a styled HTML table using the FortiSOAR json2html filter. Select specific columns via row_fields. The result can be pasted directly into a rich-text field or email body.",
            template:
                "{% set open_alerts = vars.input.records | selectattr('status', 'equalto', 'Open') | list %}\n" +
                "{% if open_alerts %}\n" +
                "<p><strong>Open alerts: {{ open_alerts | length }}</strong></p>\n" +
                "{{ open_alerts | json2html(row_fields=['id', 'name', 'severity', 'assignedTo', 'createDate']) }}\n" +
                "{% else %}\n" +
                "<p>No open alerts at this time.</p>\n" +
                "{% endif %}",
            input: {
                vars: {
                    input: {
                        records: [
                            {
                                id: "ALT-1001",
                                name: "Suspicious outbound traffic",
                                severity: "High",
                                status: "Open",
                                assignedTo: "SOC Tier 1",
                                createDate: "2026-04-25T08:12:00Z",
                            },
                            {
                                id: "ALT-1002",
                                name: "Repeated failed logins",
                                severity: "Medium",
                                status: "Open",
                                assignedTo: "SOC Tier 1",
                                createDate: "2026-04-25T09:44:00Z",
                            },
                            {
                                id: "ALT-1003",
                                name: "Legacy SSL negotiation",
                                severity: "Low",
                                status: "Closed",
                                assignedTo: "Auto-resolved",
                                createDate: "2026-04-24T22:00:00Z",
                            },
                        ],
                    },
                },
            },
        },

        {
            id: "incident-timeline",
            label: "Incident timeline — chronological event list",
            description:
                "Builds a numbered, chronological timeline from a list of incident events. Demonstrates sort by attribute, conditional severity colouring via label words, and multi-field formatting.",
            template:
                "# Incident Timeline — {{ vars.input.records[0].incidentId }}\n\n" +
                "{% set events = vars.input.records[0].events | sort(attribute='timestamp') %}\n" +
                "{% for evt in events %}\n" +
                "{{ loop.index }}. [{{ evt.timestamp | default('?') }}] " +
                "{% if evt.severity == 'Critical' %}[CRITICAL] " +
                "{% elif evt.severity == 'High' %}[HIGH] " +
                "{% elif evt.severity == 'Medium' %}[MEDIUM] " +
                "{% else %}[INFO] {% endif %}" +
                "{{ evt.summary | default('No description') }}" +
                "{% if evt.actor %} — actor: {{ evt.actor }}{% endif %}\n" +
                "{% else %}\n" +
                "No events recorded.\n" +
                "{% endfor %}\n\n" +
                "Total events: {{ events | length }}",
            input: {
                vars: {
                    input: {
                        records: [
                            {
                                incidentId: "INC-2026-0042",
                                events: [
                                    {
                                        timestamp: "2026-04-25T14:00:00Z",
                                        severity: "Critical",
                                        summary: "Ransomware executable detected on WORKSTATION-07",
                                        actor: "AV scanner",
                                    },
                                    {
                                        timestamp: "2026-04-25T13:45:00Z",
                                        severity: "High",
                                        summary: "Lateral movement detected — SMB traffic anomaly",
                                        actor: "NDR",
                                    },
                                    {
                                        timestamp: "2026-04-25T13:30:00Z",
                                        severity: "Medium",
                                        summary: "User credentials used from unusual geo-location",
                                        actor: "Identity provider",
                                    },
                                    {
                                        timestamp: "2026-04-25T13:00:00Z",
                                        severity: "Info",
                                        summary: "Phishing email received and clicked by user",
                                    },
                                ],
                            },
                        ],
                    },
                },
            },
        },
        {
            id: "csv-export",
            label: "CSV export — comma-separated records",
            description:
                "Generates a plain-text CSV file from a list of records. Values are double-quoted and inner quotes are escaped. The header row is derived from a fixed field list so the column order is always predictable. Save the output to a .csv attachment using a Write File connector step.",
            template:
                '"Alert ID","Name","Severity","Status","Source IP","Assigned To","Created"\n' +
                "{% for r in vars.input.records %}\n" +
                '"{{ r.id | default(\'\') }}",' +
                '"{{ (r.name | default(\'\')) | replace(\'\"\', \'\\\\\"\') }}",' +
                '"{{ r.severity | default(\'\') }}",' +
                '"{{ r.status | default(\'\') }}",' +
                '"{{ r.sourceIp | default(\'\') }}",' +
                '"{{ (r.assignedTo | default(\'\')) | replace(\'\"\', \'\\\\\"\') }}",' +
                '"{{ r.createDate | default(\'\') }}"\n' +
                "{% endfor %}",
            input: {
                vars: {
                    input: {
                        records: [
                            {
                                id: "ALT-1001",
                                name: 'Suspicious "admin" login',
                                severity: "High",
                                status: "Open",
                                sourceIp: "203.0.113.42",
                                assignedTo: "SOC Tier 1",
                                createDate: "2026-04-25T08:12:00Z",
                            },
                            {
                                id: "ALT-1002",
                                name: "Port scan from external host",
                                severity: "Medium",
                                status: "In Progress",
                                sourceIp: "198.51.100.7",
                                assignedTo: "SOC Tier 2",
                                createDate: "2026-04-25T09:44:00Z",
                            },
                        ],
                    },
                },
            },
        },
        {
            id: "conditional-fields",
            label: "Conditional fields — adaptive record card",
            description:
                "Renders a record summary that adapts its output based on which fields are present. Uses `is defined` and `is not none` guards before each block. Demonstrates the pattern for building human-readable notifications from incomplete data.",
            template:
                "=== Record: {{ vars.input.records[0].id | default('Unknown ID') }} ===\n\n" +
                "{% if vars.input.records[0].name is defined and vars.input.records[0].name %}\n" +
                "Name:       {{ vars.input.records[0].name }}\n" +
                "{% endif %}\n" +
                "{% if vars.input.records[0].severity is defined %}\n" +
                "Severity:   {{ vars.input.records[0].severity | upper }}\n" +
                "{% endif %}\n" +
                "{% if vars.input.records[0].description is defined and vars.input.records[0].description %}\n" +
                "Description:\n{{ vars.input.records[0].description | trim | indent(4) }}\n" +
                "{% endif %}\n" +
                "{% if vars.input.records[0].indicators is defined and vars.input.records[0].indicators | length > 0 %}\n" +
                "Indicators ({{ vars.input.records[0].indicators | length }}):\n" +
                "{% for ioc in vars.input.records[0].indicators %}\n" +
                "  - {{ ioc.type | default('unknown') }}: {{ ioc.value }}\n" +
                "{% endfor %}\n" +
                "{% endif %}\n" +
                "{% if vars.input.records[0].assignedTo is defined and vars.input.records[0].assignedTo %}\n" +
                "Assigned:   {{ vars.input.records[0].assignedTo }}\n" +
                "{% else %}\n" +
                "Assigned:   (unassigned)\n" +
                "{% endif %}",
            input: {
                vars: {
                    input: {
                        records: [
                            {
                                id: "ALT-1005",
                                name: "Credential stuffing detected",
                                severity: "high",
                                description:
                                    "Multiple failed authentication attempts using a known leaked credential list.\nSource CIDR: 192.0.2.0/24",
                                indicators: [
                                    { type: "IP", value: "192.0.2.17" },
                                    { type: "IP", value: "192.0.2.88" },
                                    { type: "URL", value: "https://login.example.com/api/v1/auth" },
                                ],
                            },
                        ],
                    },
                },
            },
        },
        {
            id: "severity-grouped-summary",
            label: "Severity grouping — counts and per-group table",
            description:
                "Groups records by severity using the groupby filter, then renders a count summary followed by a per-group json2html table. Useful for SOC daily digest emails.",
            template:
                "Alert Digest — {{ vars.input.records | length }} total alert(s)\n\n" +
                "{% for severity, group in vars.input.records | groupby('severity') %}\n" +
                "{{ severity | upper }}: {{ group | length }} alert(s)\n" +
                "{% endfor %}\n\n" +
                "--- Details by severity ---\n\n" +
                "{% for severity, group in vars.input.records | sort(attribute='severity') | groupby('severity') %}\n" +
                "<h3>{{ severity | upper }} ({{ group | length }})</h3>\n" +
                "{{ group | list | json2html(row_fields=['id', 'name', 'status', 'assignedTo']) }}\n" +
                "{% endfor %}",
            input: {
                vars: {
                    input: {
                        records: [
                            { id: "ALT-001", name: "RDP brute force",       severity: "High",     status: "Open",        assignedTo: "Tier 1" },
                            { id: "ALT-002", name: "DNS tunnelling",         severity: "High",     status: "In Progress", assignedTo: "Tier 2" },
                            { id: "ALT-003", name: "Stale account login",    severity: "Medium",   status: "Open",        assignedTo: "Tier 1" },
                            { id: "ALT-004", name: "USB storage detected",   severity: "Low",      status: "Closed",      assignedTo: "Auto"   },
                            { id: "ALT-005", name: "Unusual GeoIP login",    severity: "Medium",   status: "Open",        assignedTo: "Tier 1" },
                        ],
                    },
                },
            },
        },
];
})();
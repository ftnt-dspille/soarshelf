/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
(function () {
    const ns = (window.JinjaEditorWidget = window.JinjaEditorWidget || {});

    ns.snippets = [
        // ── Control flow ─────────────────────────────────────────────────────────
        {
            label: "if",
            detail: "Conditional block",
            insertText: "{% if ${1:condition} %}\n\t$0\n{% endif %}",
            asSnippet: true,
        },
        {
            label: "if-else",
            detail: "Conditional with else branch",
            insertText:
                "{% if ${1:condition} %}\n\t${2}\n{% else %}\n\t${0}\n{% endif %}",
            asSnippet: true,
        },
        {
            label: "if-elif-else",
            detail: "Conditional chain",
            insertText:
                "{% if ${1:condition} %}\n\t${2}\n{% elif ${3:other_condition} %}\n\t${4}\n{% else %}\n\t${0}\n{% endif %}",
            asSnippet: true,
        },
        {
            label: "for",
            detail: "Iterate over a collection",
            insertText: "{% for ${1:item} in ${2:collection} %}\n\t$0\n{% endfor %}",
            asSnippet: true,
        },
        {
            label: "for-else",
            detail: "Iterate with fallback when empty",
            insertText:
                "{% for ${1:item} in ${2:collection} %}\n\t${3}\n{% else %}\n\t${0:No items}\n{% endfor %}",
            asSnippet: true,
        },
        {
            label: "for-index",
            detail: "Iterate with loop.index",
            insertText:
                "{% for ${1:item} in ${2:collection} %}\n\t{{ loop.index }}. {{ ${1:item} }}$0\n{% endfor %}",
            asSnippet: true,
        },
        {
            label: "set",
            detail: "Assign a variable",
            insertText: "{% set ${1:name} = ${2:value} %}$0",
            asSnippet: true,
        },
        {
            label: "set-block",
            detail: "Capture block output into a variable",
            insertText: "{% set ${1:name} %}\n\t$0\n{% endset %}",
            asSnippet: true,
        },
        {
            label: "macro",
            detail: "Define a reusable macro",
            insertText: "{% macro ${1:name}(${2:args}) %}\n\t$0\n{% endmacro %}",
            asSnippet: true,
        },
        {
            label: "block",
            detail: "Define an overridable block",
            insertText: "{% block ${1:name} %}\n\t$0\n{% endblock %}",
            asSnippet: true,
        },
        {
            label: "filter",
            detail: "Apply a filter to a block of text",
            insertText: "{% filter ${1:upper} %}\n\t$0\n{% endfilter %}",
            asSnippet: true,
        },
        {
            label: "raw",
            detail: "Literal text, ignore Jinja syntax inside",
            insertText: "{% raw %}\n\t$0\n{% endraw %}",
            asSnippet: true,
        },
        {
            label: "include",
            detail: "Include another template",
            insertText: '{% include "${1:template}" %}$0',
            asSnippet: true,
        },
        {
            label: "extends",
            detail: "Extend a parent template",
            insertText: '{% extends "${1:base.html}" %}$0',
            asSnippet: true,
        },

        // ── Expression helpers ────────────────────────────────────────────────────
        {
            label: "expression",
            detail: "Print an expression — {{ … }}",
            insertText: "{{ $0 }}",
            asSnippet: true,
        },
        {
            label: "comment",
            detail: "Jinja comment — {# … #}",
            insertText: "{# $0 #}",
            asSnippet: true,
        },
        {
            label: "ternary",
            detail: "Inline conditional expression",
            insertText: "{{ ${1:value_if_true} if ${2:condition} else ${3:value_if_false} }}$0",
            asSnippet: true,
        },
        {
            label: "default",
            detail: "Value or fallback via default filter",
            insertText: "{{ ${1:value} | default(${2:'-'}) }}$0",
            asSnippet: true,
        },

        // ── FortiSOAR record helpers ──────────────────────────────────────────────
        {
            label: "records-loop",
            detail: "Loop over vars.input.records",
            insertText:
                "{% for record in vars.input.records %}\n\t{{ record.${1:name} }}$0\n{% endfor %}",
            asSnippet: true,
        },
        {
            label: "records-loop-indexed",
            detail: "Loop over records with index and null guard",
            insertText:
                "{% for record in vars.input.records %}\n" +
                "{{ loop.index }}. {{ record.${1:name} | default('N/A') }}$0\n" +
                "{% else %}\n" +
                "No records found.\n" +
                "{% endfor %}",
            asSnippet: true,
        },
        {
            label: "null-guard",
            detail: "Defensive null/undefined check before accessing a field",
            insertText:
                "{% if ${1:vars.input.records[0].field} is defined and ${1:vars.input.records[0].field} is not none %}\n" +
                "\t{{ ${1:vars.input.records[0].field} }}\n" +
                "{% else %}\n" +
                "\t${2:N/A}\n" +
                "{% endif %}$0",
            asSnippet: true,
        },
        {
            label: "null-guard-chain",
            detail: "Safe access through a potentially-null parent object",
            insertText:
                "{{ (${1:vars.input.records[0].parent} or {})|attr('${2:name}') | default('${3:N/A}') }}$0",
            asSnippet: true,
        },

        // ── json2html snippets ────────────────────────────────────────────────────
        {
            label: "json2html-basic",
            detail: "Render all records as an HTML table (all fields)",
            insertText:
                "{{ vars.input.records | json2html }}$0",
            asSnippet: true,
        },
        {
            label: "json2html-fields",
            detail: "Render selected fields of records as an HTML table",
            insertText:
                "{{ vars.input.records | json2html(row_fields=['${1:id}', '${2:name}', '${3:status}']) }}$0",
            asSnippet: true,
        },
        {
            label: "json2html-single",
            detail: "Render a single record as an HTML table",
            insertText:
                "{{ [vars.input.records[0]] | json2html(row_fields=['${1:id}', '${2:name}', '${3:status}']) }}$0",
            asSnippet: true,
        },
        {
            label: "json2html-loop",
            detail: "Render each record as its own HTML table in a loop",
            insertText:
                "{% for record in vars.input.records %}\n" +
                "<h3>{{ record.${1:name} | default('Record ' ~ loop.index) }}</h3>\n" +
                "{{ [record] | json2html(row_fields=['${2:id}', '${3:name}', '${4:status}']) }}\n" +
                "{% endfor %}$0",
            asSnippet: true,
        },

        // ── Dict construction ─────────────────────────────────────────────────────
        {
            label: "dict-from-fields",
            detail: "Build a dict from record fields, skipping nulls",
            insertText:
                "{% set summary = {} %}\n" +
                "{% if vars.input.records[0].${1:name} is defined %}\n" +
                "  {% set _ = summary.update({'${1:name}': vars.input.records[0].${1:name}}) %}\n" +
                "{% endif %}\n" +
                "{% if vars.input.records[0].${2:status} is defined %}\n" +
                "  {% set _ = summary.update({'${2:status}': vars.input.records[0].${2:status}}) %}\n" +
                "{% endif %}\n" +
                "{{ summary | toJSON }}$0",
            asSnippet: true,
        },

        // ── Date / time snippets ──────────────────────────────────────────────────
        {
            label: "date-format-iso",
            detail: "Format a datetime string as ISO 8601 (YYYY-MM-DD HH:MM:SS)",
            insertText:
                "{{ vars.input.records[0].${1:createDate} | default('') | replace('T', ' ') | truncate(19, true, '') }}$0",
            asSnippet: true,
        },
        {
            label: "date-display",
            detail: "Display a FortiSOAR epoch timestamp as a readable UTC date",
            insertText:
                "{% set ts = vars.input.records[0].${1:createDate} %}\n" +
                "{{ ts | default('Unknown date') }}$0",
            asSnippet: true,
        },

        // ── Formatting helpers ────────────────────────────────────────────────────
        {
            label: "csv-row",
            detail: "Render one record as a CSV row (comma-separated values)",
            insertText:
                '"{{ vars.input.records[0].${1:id} }}",' +
                '"{{ vars.input.records[0].${2:name} | replace(\'"\', \'\\\\"\') }}",' +
                '"{{ vars.input.records[0].${3:status} }}"$0',
            asSnippet: true,
        },
        {
            label: "csv-table",
            detail: "Render all records as CSV (header + rows)",
            insertText:
                '"${1:id}","${2:name}","${3:status}"\n' +
                "{% for r in vars.input.records %}\n" +
                '"{{ r.${1:id} }}","{{ (r.${2:name} | default(\'\')) | replace(\'\"\', \'\\\\\"\') }}","{{ r.${3:status} | default(\'\') }}"\n' +
                "{% endfor %}$0",
            asSnippet: true,
        },

        // ── fromIRI helper ────────────────────────────────────────────────────────
        {
            label: "fromIRI-field",
            detail: "Resolve a FortiSOAR IRI field and access a nested property",
            insertText:
                "{{ (vars.input.records[0].${1:ownerIri} | fromIRI).${2:name} | default('Unassigned') }}$0",
            asSnippet: true,
        },
        {
            label: "fromIRI-recursive",
            detail: "Resolve two levels of FortiSOAR IRI references",
            insertText:
                "{{ ((vars.input.records[0].${1:alertIri} | fromIRI).${2:owner} | fromIRI).${3:name} | default('Unknown') }}$0",
            asSnippet: true,
        },
    ];
})();

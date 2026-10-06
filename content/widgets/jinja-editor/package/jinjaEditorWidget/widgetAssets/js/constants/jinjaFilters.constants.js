/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
(function () {
    const ns = (window.JinjaEditorWidget = window.JinjaEditorWidget || {});

    // Each entry describes one Jinja filter so it can drive three features:
    //   * inline completion after `|`
    //   * hover + signature-help popups
    //   * the Filter Library palette (search by name / description, grouped by
    //     category, click to insert at the cursor).
    // Categories are used purely for presentation in the palette.

    // ─── String filters ──────────────────────────────────────────────────────
    const stringFilters = {
        capitalize: {
            category: "String",
            documentation:
                "Capitalizes the first character and lowercases the rest of the string.",
            example: "{{ vars.input.records[0].description | capitalize }}",
            parameters: [],
            returnValue: {type: "string", description: "The capitalized string."},
        },
        center: {
            category: "String",
            documentation: "Centers a value within a given width, padding with spaces.",
            example: "{{ vars.input.records[0].name | center(40) }}",
            parameters: [
                {name: "width", type: "integer", description: "Total output width."},
            ],
            returnValue: {type: "string", description: "The centered string."},
        },
        format: {
            category: "String",
            documentation: "Applies printf-style string formatting.",
            example: "{{ 'Hello, %s!' | format(vars.input.records[0].name) }}",
            parameters: [
                {name: "args", type: "any", description: "Positional arguments substituted into the format string."},
            ],
            returnValue: {type: "string", description: "The formatted string."},
        },
        indent: {
            category: "String",
            documentation: "Indents each line of a string with a number of spaces.",
            example: "{{ vars.input.records[0].body | indent(4) }}",
            parameters: [
                {name: "width", type: "integer", description: "Number of spaces per indent."},
                {name: "first", type: "boolean", description: "Indent the first line too. Optional.", optional: true},
                {name: "blank", type: "boolean", description: "Indent blank lines too. Optional.", optional: true},
            ],
            returnValue: {type: "string", description: "The indented string."},
        },
        lower: {
            category: "String",
            documentation: "Converts a string to lowercase.",
            example: "{{ vars.input.records[0].name | lower }}",
            parameters: [],
            returnValue: {type: "string", description: "The lowercase string."},
        },
        replace: {
            category: "String",
            documentation:
                "Replaces occurrences of a substring within a given string.",
            example: "{{ vars.input.records[0].status | replace('open', 'active') }}",
            parameters: [
                {name: "old", type: "string", description: "The substring to be replaced."},
                {name: "new", type: "string", description: "The substring to replace with."},
                {
                    name: "count",
                    type: "integer",
                    description: "Maximum number of occurrences to replace.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "The string with replacements made."},
        },
        split: {
            category: "String",
            documentation: "Splits a string into a list on a specified separator.",
            example: "{{ vars.input.records[0].tags | split(',') | join(', ') }}",
            parameters: [
                {name: "separator", type: "string", description: "The delimiter to use for splitting."},
                {name: "limit", type: "integer", description: "Maximum number of splits to perform.", optional: true},
            ],
            returnValue: {type: "list", description: "A list of substrings."},
        },
        striptags: {
            category: "String",
            documentation: "Strips SGML/XML tags and collapses whitespace.",
            example: "{{ vars.input.records[0].htmlBody | striptags }}",
            parameters: [],
            returnValue: {type: "string", description: "The stripped string."},
        },
        title: {
            category: "String",
            documentation:
                "Capitalizes the first character of each word in the string.",
            example: "{{ vars.input.records[0].name | title }}",
            parameters: [],
            returnValue: {type: "string", description: "The title-cased string."},
        },
        trim: {
            category: "String",
            documentation: "Removes leading and trailing whitespace from a string.",
            example: "{{ vars.input.records[0].name | trim }}",
            parameters: [
                {
                    name: "chars",
                    type: "string",
                    description: "Characters to strip. Defaults to whitespace.",
                    optional: true,
                },
            ],
            returnValue: {type: "string", description: "The trimmed string."},
        },
        truncate: {
            category: "String",
            documentation:
                "Truncates a string to a maximum length, appending a suffix.",
            example: "{{ vars.input.records[0].description | truncate(80) }}",
            parameters: [
                {name: "length", type: "integer", description: "Maximum length of the output."},
                {name: "killwords", type: "boolean", description: "If true, cut mid-word.", optional: true},
                {
                    name: "end",
                    type: "string",
                    description: "Suffix to append when truncated. Defaults to '...'.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "The truncated string."},
        },
        upper: {
            category: "String",
            documentation: "Converts a string to uppercase.",
            example: "{{ vars.input.records[0].name | upper }}",
            parameters: [],
            returnValue: {type: "string", description: "The uppercase string."},
        },
        wordcount: {
            category: "String",
            documentation: "Counts the words in a string.",
            example: "{{ vars.input.records[0].description | wordcount }} words",
            parameters: [],
            returnValue: {type: "integer", description: "Number of words."},
        },
        wordwrap: {
            category: "String",
            documentation:
                "Wraps a string so that each line is at most `width` characters long.",
            example: "{{ vars.input.records[0].description | wordwrap(72) }}",
            parameters: [
                {name: "width", type: "integer", description: "Maximum line length."},
                {
                    name: "break_long_words",
                    type: "boolean",
                    description: "Break words longer than width.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "The wrapped string."},
        },
    };

    // ─── Collection filters ───────────────────────────────────────────────────
    const collectionFilters = {
        batch: {
            category: "Collection",
            documentation: "Batches items into chunks of a fixed size.",
            example: "{% for chunk in vars.input.records | batch(3) %}{{ chunk | map(attribute='name') | join(', ') }}\n{% endfor %}",
            parameters: [
                {name: "linecount", type: "integer", description: "Items per batch."},
                {name: "fill_with", type: "any", description: "Value used to pad the last batch.", optional: true},
            ],
            returnValue: {type: "list", description: "A list of batches."},
        },
        first: {
            category: "Collection",
            documentation: "Returns the first item of a sequence.",
            example: "{{ vars.input.records | first }}",
            parameters: [],
            returnValue: {type: "any", description: "The first element."},
        },
        groupby: {
            category: "Collection",
            documentation:
                "Groups a sequence of objects by a shared attribute value.",
            example: "{% for status, records in vars.input.records | groupby('status') %}{{ status }}: {{ records | length }}\n{% endfor %}",
            parameters: [
                {name: "attribute", type: "string", description: "The attribute to group by."},
            ],
            returnValue: {type: "list", description: "List of (grouper, list) pairs."},
        },
        join: {
            category: "Collection",
            documentation:
                "Concatenates a list of strings with a specified separator.",
            example: "{{ vars.input.records | map(attribute='name') | join(', ') }}",
            parameters: [
                {name: "separator", type: "string", description: "The string to use as a separator."},
                {
                    name: "attribute",
                    type: "string",
                    description: "Optional attribute to use when joining a list of objects.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "The joined string."},
        },
        last: {
            category: "Collection",
            documentation: "Returns the last item of a sequence.",
            example: "{{ vars.input.records | last }}",
            parameters: [],
            returnValue: {type: "any", description: "The last element."},
        },
        length: {
            category: "Collection",
            documentation:
                "Returns the length of a string, list, or dictionary. Alias: count.",
            example: "{{ vars.input.records | length }} records",
            parameters: [],
            returnValue: {type: "integer", description: "The length of the object."},
        },
        list: {
            category: "Collection",
            documentation:
                "Converts a value to a list (useful after map/select/unique).",
            example: "{{ vars.input.records | map(attribute='name') | list }}",
            parameters: [],
            returnValue: {type: "list", description: "A materialised list."},
        },
        map: {
            category: "Collection",
            documentation:
                "Applies a filter or extracts an attribute from each item in a sequence.",
            example: "{{ vars.input.records | map(attribute='name') | join(', ') }}",
            parameters: [
                {name: "filter_or_attribute", type: "string", description: "Filter name or 'attribute=NAME' selector."},
            ],
            returnValue: {type: "list", description: "A list of mapped values."},
        },
        max: {
            category: "Collection",
            documentation: "Returns the largest item of a sequence.",
            example: "{{ vars.input.records | map(attribute='severity') | max }}",
            parameters: [
                {name: "case_sensitive", type: "boolean", description: "Case-sensitive comparison.", optional: true},
                {name: "attribute", type: "string", description: "Compare by this attribute.", optional: true},
            ],
            returnValue: {type: "any", description: "The largest item."},
        },
        min: {
            category: "Collection",
            documentation: "Returns the smallest item of a sequence.",
            example: "{{ vars.input.records | map(attribute='severity') | min }}",
            parameters: [
                {name: "case_sensitive", type: "boolean", description: "Case-sensitive comparison.", optional: true},
                {name: "attribute", type: "string", description: "Compare by this attribute.", optional: true},
            ],
            returnValue: {type: "any", description: "The smallest item."},
        },
        random: {
            category: "Collection",
            documentation: "Picks a random element from a sequence.",
            example: "{{ vars.input.records | random }}",
            parameters: [],
            returnValue: {type: "any", description: "A random element."},
        },
        reject: {
            category: "Collection",
            documentation:
                "Filters a sequence, dropping items where the test passes.",
            example: "{{ [1, 2, 3, 4] | reject('odd') | list }}",
            parameters: [
                {name: "test", type: "string", description: "Name of the test to apply."},
            ],
            returnValue: {type: "list", description: "Items that failed the test."},
        },
        rejectattr: {
            category: "Collection",
            documentation:
                "Filters a sequence of objects, dropping ones whose attribute passes the test.",
            example: "{% for r in vars.input.records | rejectattr('status', 'equalto', 'closed') %}{{ r.name }}\n{% endfor %}",
            parameters: [
                {name: "attribute", type: "string", description: "Attribute to inspect."},
                {name: "test", type: "string", description: "Test name.", optional: true},
                {name: "value", type: "any", description: "Value passed to the test.", optional: true},
            ],
            returnValue: {type: "list", description: "Objects that failed the test."},
        },
        reverse: {
            category: "Collection",
            documentation: "Reverses the order of items in a sequence or string.",
            example: "{% for r in vars.input.records | reverse %}{{ r.name }}\n{% endfor %}",
            parameters: [],
            returnValue: {type: "any", description: "The reversed sequence."},
        },
        select: {
            category: "Collection",
            documentation:
                "Filters a sequence, keeping items where the test passes.",
            example: "{{ [1, 2, 3, 4] | select('odd') | list }}",
            parameters: [
                {name: "test", type: "string", description: "Name of the test to apply (e.g. 'even')."},
            ],
            returnValue: {type: "list", description: "Items that pass the test."},
        },
        selectattr: {
            category: "Collection",
            documentation:
                "Filters a sequence of objects by applying a test to one of their attributes.",
            example: "{% for r in vars.input.records | selectattr('status', 'equalto', 'open') %}{{ r.name }}\n{% endfor %}",
            parameters: [
                {name: "attribute", type: "string", description: "Attribute to inspect."},
                {name: "test", type: "string", description: "Test name (e.g. 'equalto').", optional: true},
                {name: "value", type: "any", description: "Value passed to the test.", optional: true},
            ],
            returnValue: {type: "list", description: "Matching objects."},
        },
        slice: {
            category: "Collection",
            documentation: "Splits a sequence into a fixed number of slices.",
            example: "{% for col in vars.input.records | slice(2) %}{{ col | map(attribute='name') | join(', ') }}\n{% endfor %}",
            parameters: [
                {name: "slices", type: "integer", description: "Number of slices to produce."},
                {name: "fill_with", type: "any", description: "Value used to pad short slices.", optional: true},
            ],
            returnValue: {type: "list", description: "A list of slices."},
        },
        sort: {
            category: "Collection",
            documentation:
                "Sorts a sequence. Use `attribute` to sort a list of objects.",
            example: "{% for r in vars.input.records | sort(attribute='name') %}{{ r.name }}\n{% endfor %}",
            parameters: [
                {name: "reverse", type: "boolean", description: "Sort descending.", optional: true},
                {name: "case_sensitive", type: "boolean", description: "Case-sensitive comparison.", optional: true},
                {name: "attribute", type: "string", description: "Sort by this attribute.", optional: true},
            ],
            returnValue: {type: "list", description: "A sorted list."},
        },
        sum: {
            category: "Collection",
            documentation: "Sums a sequence of numbers.",
            example: "Total: {{ vars.input.records | sum(attribute='count') }}",
            parameters: [
                {
                    name: "attribute",
                    type: "string",
                    description: "Sum this attribute when operating on objects.",
                    optional: true
                },
                {name: "start", type: "number", description: "Initial value. Defaults to 0.", optional: true},
            ],
            returnValue: {type: "number", description: "The sum of the values."},
        },
        unique: {
            category: "Collection",
            documentation: "Removes duplicates from a sequence, preserving order.",
            example: "{{ vars.input.records | map(attribute='status') | unique | join(', ') }}",
            parameters: [
                {name: "case_sensitive", type: "boolean", description: "Case-sensitive comparison.", optional: true},
                {name: "attribute", type: "string", description: "Deduplicate by this attribute.", optional: true},
            ],
            returnValue: {type: "list", description: "A list of unique items."},
        },
    };

    // ─── Number filters ───────────────────────────────────────────────────────
    const numberFilters = {
        abs: {
            category: "Number",
            documentation: "Returns the absolute value of a number.",
            example: "{{ vars.input.records[0].delta | abs }}",
            parameters: [],
            returnValue: {type: "number", description: "The absolute value."},
        },
        filesizeformat: {
            category: "Number",
            documentation:
                "Formats a byte count as a human-readable file size (e.g. '1.2 MB'). Accepts an optional `binary` flag to use powers of 1024 instead of 1000.",
            example: "{{ vars.input.records[0].file_size_bytes | filesizeformat }}",
            parameters: [
                {
                    name: "binary",
                    type: "boolean",
                    description: "Use IEC binary prefixes (KiB, MiB…) instead of SI prefixes (KB, MB…). Defaults to false.",
                    optional: true,
                    default: false
                },
            ],
            returnValue: {type: "string", description: "Human-readable file size string."},
        },
        float: {
            category: "Number",
            documentation: "Converts a value to a float, with a fallback default.",
            example: "{{ vars.input.records[0].ratio | float(0.0) }}",
            parameters: [
                {name: "default", type: "number", description: "Value returned when conversion fails.", optional: true},
            ],
            returnValue: {type: "number", description: "The float value."},
        },
        int: {
            category: "Number",
            documentation: "Converts a value to an integer, with a fallback default.",
            example: "{{ vars.input.records[0].count | int(0) }}",
            parameters: [
                {
                    name: "default",
                    type: "integer",
                    description: "Value returned when conversion fails.",
                    optional: true
                },
                {name: "base", type: "integer", description: "Numeric base for string inputs.", optional: true},
            ],
            returnValue: {type: "integer", description: "The integer value."},
        },
        round: {
            category: "Number",
            documentation: "Rounds a number to a given precision.",
            example: "{{ vars.input.records[0].score | round(2) }}",
            parameters: [
                {name: "precision", type: "integer", description: "Number of decimal places.", optional: true},
                {name: "method", type: "string", description: "'common', 'ceil', or 'floor'.", optional: true},
            ],
            returnValue: {type: "number", description: "The rounded number."},
        },
    };

    // ─── Value / misc filters ─────────────────────────────────────────────────
    const valueFilters = {
        attr: {
            category: "Value",
            documentation:
                "Returns the named attribute of an object (like obj.name but dynamic).",
            example: "{{ vars.input.records[0] | attr('name') }}",
            parameters: [
                {name: "name", type: "string", description: "The attribute name."},
            ],
            returnValue: {type: "any", description: "The attribute value."},
        },
        default: {
            category: "Value",
            documentation:
                "Returns a default value if the variable is undefined or empty. Alias: d.",
            example: "{{ vars.input.records[0].name | default('Unknown') }}",
            parameters: [
                {name: "default_value", type: "any", description: "Value returned when the input is missing."},
                {
                    name: "boolean",
                    type: "boolean",
                    description: "If true, falsy values also use the default.",
                    optional: true
                },
            ],
            returnValue: {type: "any", description: "The variable value or the default."},
        },
        dictsort: {
            category: "Value",
            documentation:
                "Sorts a dictionary and yields (key, value) pairs.",
            example: "{% for key, val in vars.input.records[0] | dictsort %}{{ key }}: {{ val }}\n{% endfor %}",
            parameters: [
                {name: "case_sensitive", type: "boolean", description: "Case-sensitive comparison.", optional: true},
                {name: "by", type: "string", description: "Sort by 'key' or 'value'.", optional: true},
            ],
            returnValue: {type: "list", description: "A list of [key, value] pairs in order."},
        },
        items: {
            category: "Value",
            documentation:
                "Yields (key, value) pairs of a dictionary for use in loops.",
            example: "{% for key, val in vars.input.records[0] | items %}{{ key }}: {{ val }}\n{% endfor %}",
            parameters: [],
            returnValue: {type: "list", description: "A list of [key, value] pairs."},
        },
        pprint: {
            category: "Encoding",
            documentation: "Pretty-prints a value for debugging.",
            example: "{{ vars.input.records[0] | pprint }}",
            parameters: [],
            returnValue: {type: "string", description: "A human-readable representation."},
        },
        tojson: {
            category: "Encoding",
            documentation: "Serialises a value to a JSON string (standard Jinja2 built-in).",
            example: "{{ vars.input.records[0] | tojson(indent=2) }}",
            parameters: [
                {name: "indent", type: "integer", description: "Indent level for pretty-printing.", optional: true},
            ],
            returnValue: {type: "string", description: "A JSON string."},
        },
    };

    // ─── Encoding / conversion filters ───────────────────────────────────────
    const encodingFilters = {
        escape: {
            category: "Encoding",
            documentation:
                "Replaces the characters &, <, >, ' and \" with HTML-safe sequences. Alias: e.",
            example: "{{ vars.input.records[0].userInput | escape }}",
            parameters: [],
            returnValue: {type: "string", description: "The HTML-escaped string."},
        },
        forceescape: {
            category: "Encoding",
            documentation:
                "Forcefully HTML-escapes a string even if it has already been marked safe. Unlike `escape`, this always escapes regardless of the Markup state.",
            example: "{{ vars.input.records[0].rawHtml | forceescape }}",
            parameters: [],
            returnValue: {type: "string", description: "The forcefully escaped string."},
        },
        safe: {
            category: "Encoding",
            documentation:
                "Marks a string as safe so it won't be escaped by autoescape.",
            example: "{{ vars.input.records[0].htmlContent | safe }}",
            parameters: [],
            returnValue: {type: "string", description: "A Markup-wrapped string."},
        },
        string: {
            category: "Encoding",
            documentation: "Converts a value to a string.",
            example: "{{ vars.input.records[0].count | string }}",
            parameters: [],
            returnValue: {type: "string", description: "The string representation."},
        },
        urlencode: {
            category: "Encoding",
            documentation:
                "Percent-encodes a string so it's safe for use in a URL query.",
            example: "https://example.com/search?q={{ vars.input.records[0].query | urlencode }}",
            parameters: [],
            returnValue: {type: "string", description: "The URL-encoded string."},
        },
        urlize: {
            category: "Encoding",
            documentation:
                "Converts URLs in plain text into clickable `<a>` links.",
            example: "{{ vars.input.records[0].notes | urlize }}",
            parameters: [
                {name: "trim_url_limit", type: "integer", description: "Maximum displayed URL length.", optional: true},
                {name: "nofollow", type: "boolean", description: "Add rel=nofollow.", optional: true},
            ],
            returnValue: {type: "string", description: "HTML with linked URLs."},
        },
        xmlattr: {
            category: "Encoding",
            documentation:
                "Converts a dictionary into an XML/HTML attribute string. Keys become attribute names, values become quoted attribute values. Useful for injecting dynamic attributes into HTML tags.",
            example: "{{ {'class': 'alert alert-danger', 'data-id': vars.input.records[0].id} | xmlattr }}",
            parameters: [
                {
                    name: "autospace",
                    type: "boolean",
                    description: "Prepend a leading space automatically. Defaults to true.",
                    optional: true,
                    default: true
                },
            ],
            returnValue: {type: "string", description: "A string of HTML attribute key=value pairs."},
        },
    };

    // ─── FortiSOAR custom filters ─────────────────────────────────────────────
    // Sources: FortiSOAR 7.6.x Playbooks Guide — Jinja Filters and Functions
    // https://docs.fortinet.com/document/fortisoar/7.6.2/playbooks-guide/767891/jinja-filters-and-functions
    const fortisoarFilters = {
        extract_artifacts: {
            category: "FortiSOAR",
            documentation:
                "Parses a plain-text string and extracts a list of Indicators of Compromise (IOCs). The returned list contains identified values such as IP addresses, domain names, URLs, email addresses, and file hashes. Useful for auto-populating indicator fields from unstructured log or alert text.",
            example: "{{ vars.input.records[0].description | extract_artifacts }}",
            parameters: [],
            returnValue: {type: "list", description: "A list of extracted IOC strings."},
        },
        fromIRI: {
            category: "FortiSOAR",
            documentation:
                "Resolves a FortiSOAR IRI (Internationalized Resource Identifier — the string path like '/api/3/alerts/abc-123') and returns the full object that lives at that path. Supports dot-access on the result and can be chained for recursive lookups. Use this filter whenever a field stores an IRI rather than a full object.",
            example: "{{ vars.input.records[0].alert_iri | fromIRI }}",
            parameters: [],
            returnValue: {type: "object", description: "The FortiSOAR record object at the given IRI."},
        },
        html2text: {
            category: "FortiSOAR",
            documentation:
                "Converts an HTML string into plain text by stripping all HTML tags and collapsing whitespace. Useful for extracting readable content from rich-text or email-body fields before further processing or display.",
            example: "{{ vars.input.records[0].emailBody | html2text }}",
            parameters: [],
            returnValue: {type: "string", description: "Plain text with HTML tags removed."},
        },
        json2html: {
            category: "FortiSOAR",
            documentation:
                "Converts a JSON value (list of dicts, or a single dict) into a styled HTML table using FortiSOAR's built-in rendering templates. The output is a self-contained HTML snippet ready to be saved into a rich-text field or included in an email notification. By default every key in the data becomes a column; pass `row_fields` to restrict which keys are rendered. The `row_fields` parameter is the only argument officially documented in the FortiSOAR 7.x Playbooks Guide; additional keyword arguments seen in widget source code (table_style, styling, template, display) are not yet verified against a live instance — see research-notes.md.",
            example: "{{ vars.input.records | json2html(row_fields=['id', 'name', 'severity', 'status']) }}",
            parameters: [
                {
                    name: "row_fields",
                    type: "list",
                    description: "An ordered list of key names to render as columns. If omitted, all keys present in the first record are used.",
                    optional: true,
                },
            ],
            returnValue: {type: "string", description: "An HTML string containing a styled table."},
        },
        parse_cef: {
            category: "FortiSOAR",
            documentation:
                "Parses a CEF (Common Event Format) log string and returns a dictionary of key-value pairs. CEF is a standard format used by many security devices. After parsing, individual fields such as `src`, `dst`, `deviceEventClassId`, etc. are accessible by key.",
            example: "{{ vars.input.records[0].rawLog | parse_cef }}",
            parameters: [],
            returnValue: {type: "object", description: "A dictionary of CEF field names and their values."},
        },
        readfile: {
            category: "FortiSOAR",
            documentation:
                "Fetches the contents of a file that has been downloaded to the FortiSOAR system during the current playbook run. The value piped into this filter should be the file path or attachment IRI returned by a previous connector step.",
            example: "{{ vars.steps.downloadAttachment.data.file | readfile }}",
            parameters: [],
            returnValue: {type: "string", description: "The raw text contents of the file."},
        },
        toDict: {
            category: "FortiSOAR",
            documentation:
                "Attempts to coerce a string value into a Python dictionary by parsing it as JSON. Useful when a FortiSOAR field stores a serialized JSON object as a string and you need to access individual keys from it using dot notation.",
            example: "{{ (vars.input.records[0].incidentJson | toDict).id }}",
            parameters: [],
            returnValue: {type: "object", description: "A dictionary parsed from the input string."},
        },
        toJSON: {
            category: "FortiSOAR",
            documentation:
                "Converts a JSON-serialisable object to a JSON string. Intended specifically for storing structured data in FortiSOAR text area fields (e.g. 'Source Data') so the content renders correctly in the UI. This is FortiSOAR's custom variant; the standard Jinja2 equivalent is `tojson`.",
            example: "{{ vars.input.records[0] | toJSON }}",
            parameters: [],
            returnValue: {type: "string", description: "A JSON-formatted string."},
        },
        xml_to_dict: {
            category: "FortiSOAR",
            documentation:
                "Converts an XML string into a Python dictionary, making it easy to access individual elements with standard dict/dot notation. Useful for processing XML payloads returned by connectors or present in raw log fields.",
            example: "{{ vars.input.records[0].xmlPayload | xml_to_dict }}",
            parameters: [],
            returnValue: {type: "object", description: "A dictionary representation of the XML document."},
        },
    };

    // ─── Regex filters (Ansible / FortiSOAR) ──────────────────────────────────
    // Source: FortiSOAR 7.6.x Playbooks Guide — documented under Ansible filters
    // https://docs.fortinet.com/document/fortisoar/7.6.5/playbooks-guide/767891/jinja-filters-functions-expressions-and-extensions
    const regexFilters = {
        regex_escape: {
            category: "Regex",
            documentation:
                "Escapes all special regular-expression metacharacters in a string so it can be safely embedded inside a regex pattern. For example, the string `^f.*o(.*)$` becomes `\\^f\\.\\*o\\(\\.\\*\\)\\$`.",
            example: "{{ vars.input.records[0].rawPattern | regex_escape() }}",
            parameters: [],
            returnValue: {type: "string", description: "The input string with all regex special characters escaped."},
        },
        regex_findall: {
            category: "Regex",
            documentation:
                "Searches a string for all non-overlapping matches of a regular expression and returns them as a list. Capturing groups in the pattern cause the group values (not the full match) to be returned. Useful for extracting multiple IP addresses, hash values, or other repeated patterns from a block of text.",
            example: "{{ vars.input.records[0].description | regex_findall('\\\\d{1,3}\\\\.\\\\d{1,3}\\\\.\\\\d{1,3}\\\\.\\\\d{1,3}') }}",
            parameters: [
                {name: "pattern", type: "string", description: "A regular expression pattern to search for."},
                {
                    name: "ignorecase",
                    type: "boolean",
                    description: "Perform case-insensitive matching.",
                    optional: true,
                    default: false
                },
                {
                    name: "multiline",
                    type: "boolean",
                    description: "Allow ^ and $ to match at line boundaries.",
                    optional: true,
                    default: false
                },
            ],
            returnValue: {type: "list", description: "A list of all matched strings (or captured groups)."},
        },
        regex_replace: {
            category: "Regex",
            documentation:
                "Replaces all substrings of the input that match a regular expression with a replacement string. Backreferences such as `\\1` can be used in the replacement to refer to captured groups.",
            example: "{{ vars.input.records[0].message | regex_replace('(\\\\d+\\\\.\\\\d+\\\\.\\\\d+\\\\.\\\\d+)', '[REDACTED]') }}",
            parameters: [
                {name: "pattern", type: "string", description: "A regular expression pattern to match."},
                {
                    name: "replacement",
                    type: "string",
                    description: "The replacement string. Backreferences like \\\\1 refer to captured groups."
                },
                {
                    name: "ignorecase",
                    type: "boolean",
                    description: "Perform case-insensitive matching.",
                    optional: true,
                    default: false
                },
                {
                    name: "multiline",
                    type: "boolean",
                    description: "Allow ^ and $ to match at line boundaries.",
                    optional: true,
                    default: false
                },
            ],
            returnValue: {type: "string", description: "The input string with all regex matches replaced."},
        },
        regex_search: {
            category: "Regex",
            documentation:
                "Searches a string for the first occurrence of a regular expression pattern and returns the match (or a captured group). Returns an empty string if no match is found. Commonly used to test whether a string contains a specific pattern before acting on it.",
            example: "{{ vars.input.records[0].logLine | regex_search('([0-9]+\\\\.[0-9]+\\\\.[0-9]+\\\\.[0-9]+)', '\\\\1') }}",
            parameters: [
                {name: "pattern", type: "string", description: "A regular expression pattern to search for."},
                {
                    name: "groups",
                    type: "string",
                    description: "Backreference (e.g. '\\\\1') to return a captured group instead of the full match.",
                    optional: true
                },
                {
                    name: "ignorecase",
                    type: "boolean",
                    description: "Perform case-insensitive matching.",
                    optional: true,
                    default: false
                },
                {
                    name: "multiline",
                    type: "boolean",
                    description: "Allow ^ and $ to match at line boundaries.",
                    optional: true,
                    default: false
                },
            ],
            returnValue: {
                type: "string",
                description: "The matched string or captured group, or an empty string if no match."
            },
        },
    };

    // ─── Date / time filters (Ansible / FortiSOAR) ────────────────────────────
    // Source: FortiSOAR 7.6.x Playbooks Guide
    // https://docs.fortinet.com/document/fortisoar/7.6.5/playbooks-guide/767891/jinja-filters-functions-expressions-and-extensions
    const dateFilters = {
        strftime: {
            category: "Date",
            documentation:
                "Formats the current date and time (or an arbitrary epoch timestamp) as a string using Python's `strftime` format codes. The format string is piped into the filter; an optional epoch integer can be passed as an argument to format a specific point in time instead of now.",
            example: "{{ '%Y-%m-%d %H:%M:%S' | strftime }}",
            parameters: [
                {
                    name: "epoch",
                    type: "integer",
                    description: "A Unix epoch timestamp to format. Defaults to the current time.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "The formatted date/time string."},
        },
        to_datetime: {
            category: "Date",
            documentation:
                "Parses a date/time string into a Python `datetime` object. Once converted, you can perform date arithmetic such as computing the difference in seconds or days between two dates. The default format is `%Y-%m-%d %H:%M:%S`, but any valid `strptime` format string can be supplied.",
            example: "{{ (('2026-04-25 14:00:00' | to_datetime) - ('2026-04-24 08:00:00' | to_datetime)).seconds }}",
            parameters: [
                {
                    name: "format",
                    type: "string",
                    description: "A strptime format string. Defaults to '%Y-%m-%d %H:%M:%S'.",
                    optional: true,
                    default: "%Y-%m-%d %H:%M:%S"
                },
            ],
            returnValue: {
                type: "datetime",
                description: "A Python datetime object. Supports arithmetic and .total_seconds() / .days / .seconds properties on timedelta results."
            },
        },
    };

    // ─── List / set operation filters (Ansible / FortiSOAR) ───────────────────
    // Source: FortiSOAR 7.6.x Playbooks Guide (Ansible filter set)
    // https://docs.fortinet.com/document/fortisoar/7.6.5/playbooks-guide/767891/jinja-filters-functions-expressions-and-extensions
    const setFilters = {
        b64decode: {
            category: "Encoding",
            documentation:
                "Decodes a Base64-encoded string and returns the original plain-text value. Commonly used when a connector returns Base64-encoded file contents or credential fields that need to be decoded before processing.",
            example: "{{ vars.input.records[0].encodedPayload | b64decode }}",
            parameters: [],
            returnValue: {type: "string", description: "The Base64-decoded string."},
        },
        b64encode: {
            category: "Encoding",
            documentation:
                "Encodes a string as Base64. Use this when a downstream connector or API expects Base64-encoded input, or when storing binary-safe content in a text field.",
            example: "{{ vars.input.records[0].rawContent | b64encode }}",
            parameters: [],
            returnValue: {type: "string", description: "The Base64-encoded string."},
        },
        difference: {
            category: "Collection",
            documentation:
                "Returns the set difference of two lists — items that are in the first list but NOT in the second list. Duplicate values in the result are removed. Useful for finding records not yet processed or IPs not in an allowlist.",
            example: "{{ vars.input.records | map(attribute='ip') | list | difference(['10.0.0.1', '10.0.0.2']) }}",
            parameters: [
                {name: "other", type: "list", description: "The list of items to subtract from the input list."},
            ],
            returnValue: {type: "list", description: "Items in the first list that are not in the second list."},
        },
        flatten: {
            category: "Collection",
            documentation:
                "Flattens a nested list into a single-level list. By default all nesting is removed; pass a `levels` argument to only flatten a given number of levels deep. Null values are removed unless `skip_nulls=false` is set.",
            example: "{{ vars.input.records | map(attribute='tags') | list | flatten }}",
            parameters: [
                {
                    name: "levels",
                    type: "integer",
                    description: "Number of nesting levels to flatten. Omit to flatten all levels.",
                    optional: true
                },
            ],
            returnValue: {type: "list", description: "A flattened list."},
        },
        intersect: {
            category: "Collection",
            documentation:
                "Returns the set intersection of two lists — items that appear in BOTH lists. Duplicate values in the result are removed. Useful for finding common IPs, tags, or users between two datasets.",
            example: "{{ vars.input.records | map(attribute='tag') | list | intersect(['malware', 'phishing', 'ransomware']) }}",
            parameters: [
                {name: "other", type: "list", description: "The second list to intersect with."},
            ],
            returnValue: {type: "list", description: "Items present in both lists."},
        },
        shuffle: {
            category: "Collection",
            documentation:
                "Returns a copy of the input list in a random order. Each call produces a different ordering. Pass a `seed` string to make the shuffle deterministic (idempotent) — the same seed always produces the same ordering, which is useful for reproducible test data.",
            example: "{{ vars.input.records | shuffle }}",
            parameters: [
                {
                    name: "seed",
                    type: "string",
                    description: "A seed string to make the shuffle repeatable.",
                    optional: true
                },
            ],
            returnValue: {type: "list", description: "The list items in a randomised order."},
        },
        symmetric_difference: {
            category: "Collection",
            documentation:
                "Returns the symmetric difference of two lists — items that are in exactly one of the two lists but NOT in both. Duplicate values in the result are removed.",
            example: "{{ ['ALT-001', 'ALT-002', 'ALT-003'] | symmetric_difference(['ALT-002', 'ALT-004']) }}",
            parameters: [
                {name: "other", type: "list", description: "The second list to compare against."},
            ],
            returnValue: {type: "list", description: "Items exclusive to each list."},
        },
        to_uuid: {
            category: "Encoding",
            documentation:
                "Generates a deterministic (name-based) UUID v5 from the input string. The same input string always produces the same UUID, making this useful for creating stable synthetic identifiers from record field values.",
            example: "{{ vars.input.records[0].name | to_uuid }}",
            parameters: [],
            returnValue: {type: "string", description: "A UUID string derived from the input."},
        },
        to_yaml: {
            category: "Encoding",
            documentation:
                "Serialises a value to a YAML-formatted string. Useful for debugging complex nested structures or for writing configuration data into a text field in a human-readable format.",
            example: "{{ vars.input.records[0] | to_yaml }}",
            parameters: [
                {
                    name: "indent",
                    type: "integer",
                    description: "Number of spaces per indentation level.",
                    optional: true
                },
            ],
            returnValue: {type: "string", description: "A YAML string."},
        },
        type_debug: {
            category: "Value",
            documentation:
                "Returns the Python type name of the input value as a string (e.g. `'str'`, `'int'`, `'list'`, `'dict'`, `'NoneType'`). Intended purely for debugging when you need to confirm what type a variable holds at runtime.",
            example: "{{ vars.input.records[0].severity | type_debug }}",
            parameters: [],
            returnValue: {type: "string", description: "The Python type name of the value."},
        },
        union: {
            category: "Collection",
            documentation:
                "Returns the set union of two lists — all items from both lists, with duplicates removed. Order is not guaranteed. Useful for merging indicator lists or tag sets without creating duplicates.",
            example: "{{ vars.input.records | map(attribute='ip') | list | union(['192.168.1.100']) }}",
            parameters: [
                {name: "other", type: "list", description: "The second list to merge into the first."},
            ],
            returnValue: {type: "list", description: "All unique items from both lists combined."},
        },
    };

    // ─── FortiSOAR custom date/time functions ─────────────────────────────────
    // These are used as Jinja functions (called without a leading value), not as
    // pipe filters, but they appear in the same docs section and are commonly
    // expected in autocomplete. They are listed here so the palette surfaces them.
    // Source: FortiSOAR 7.0+ Playbooks Guide custom functions section
    // https://docs.fortinet.com/document/fortisoar/7.0.0/playbooks-guide/767891/jinja-filters-and-functions
    const fortisoarDateFunctions = {
        currentDateMinus: {
            category: "FortiSOAR",
            documentation:
                "Returns a Unix epoch timestamp (integer) representing the current date/time minus a specified number of days. Use this to compute look-back windows for queries, e.g., 'alerts created in the last 7 days'. Called as a function rather than a pipe filter: `{{ currentDateMinus(7) }}`.",
            example: "{{ currentDateMinus(7) }}",
            parameters: [
                {name: "days", type: "integer", description: "Number of days to subtract from the current date."},
            ],
            returnValue: {type: "integer", description: "A Unix epoch timestamp N days before now."},
        },
        get_current_date: {
            category: "FortiSOAR",
            documentation:
                "Returns the current date as a string. Called as a function: `{{ get_current_date() }}`. The exact format (typically `YYYY-MM-DD`) depends on the FortiSOAR instance timezone settings.",
            example: "{{ get_current_date() }}",
            parameters: [],
            returnValue: {type: "string", description: "The current date as a formatted string."},
        },
        get_current_datetime: {
            category: "FortiSOAR",
            documentation:
                "Returns the current date and time as a string. Called as a function: `{{ get_current_datetime() }}`. Useful for stamping records, email subjects, or log entries with a human-readable timestamp.",
            example: "{{ get_current_datetime() }}",
            parameters: [],
            returnValue: {type: "string", description: "The current date and time as a formatted string."},
        },
    };

    ns.filterSignatures = Object.assign(
        {},
        stringFilters,
        collectionFilters,
        numberFilters,
        valueFilters,
        encodingFilters,
        fortisoarFilters,
        regexFilters,
        dateFilters,
        setFilters,
        fortisoarDateFunctions
    );

    // Ordered list of categories for the palette's headings. Anything new that
    // doesn't match a category here will still render in an "Other" section.
    ns.filterCategoryOrder = [
        "String",
        "Collection",
        "Number",
        "Value",
        "Encoding",
        "Regex",
        "Date",
        "FortiSOAR",
        "Other",
    ];
})();
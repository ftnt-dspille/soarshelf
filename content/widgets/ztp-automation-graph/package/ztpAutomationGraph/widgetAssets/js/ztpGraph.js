/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
/* ztpGraph.ts ��� typed pure logic for the ZTP Automation Step Graph widget.
 *
 * Source of truth for the graph's data model + mapping rules (plan §3/§4).
 * Compiled with `tsc -p tsconfig.json` (module: none) to ztpGraph.js, which is
 * loaded via <script> in view.html (exposes a global `ztpGraph` namespace) and
 * is also require()-able by the jest unit tests. Pure + side-effect-free so the
 * tests run headless with no DOM/cytoscape.
 *
 * Field names + picklist values confirmed live against an 8.0 box -- see the
 * memory note `ztp-device-automation-steps-schema`. Do NOT trust the stale
 * `ztpf_devices.ztpfArtifact.steps[].ztpf_status` summary; read canonical
 * `queueStatus` from the fetched step records.
 */
"use strict";
var ztpGraph;
(function (ztpGraph) {
    /* ---------- model types ---------- */
    /* ---------- constants (official queueStatus picklist, live-confirmed) ---------- */
    /** The ztpfDeviceStepStatus picklist, in picklist order, with the colours the
     *  box actually ships. Used only as a FALLBACK -- a step's own queueStatus
     *  object carries its colour and orderIndex, and that always wins.
     *
     *  The previous table modelled five states, two of which do not exist:
     *  "Added" is in no picklist, and the failure value is "Fail", not "Failed".
     *  Four real states were missing entirely (New, Preparing, Input Needed,
     *  Ready), as was Cancelled -- together 80 of the 300 step records on the lab
     *  box. The spelling miss was not cosmetic: isTerminal tested for "Failed",
     *  so a failed step never counted as finished, currentStep() pinned the pulse
     *  to it forever and the run never left "running". */
    ztpGraph.QUEUE_STATUS = {
        "New": { color: "#b6a6b4", order: 0 },
        "Preparing": { color: "#e91784", order: 1 },
        "Input Needed": { color: "#b1ae06", order: 2 },
        "Ready": { color: "#0e12f6", order: 3 },
        "Queued": { color: "#b517ef", order: 4 },
        "Running": { color: "#07b7f6", order: 5 },
        "Complete": { color: "#34ca46", order: 6 },
        "Fail": { color: "#ff0000", order: 7 },
        "Cancelled": { color: "#808080", order: 8 },
    };
    /** States a step can be in before it has started. */
    var PENDING_STATES = {
        "New": true, "Preparing": true, "Input Needed": true, "Ready": true, "Queued": true,
    };
    /** States a step can be in once nothing more will happen to it. */
    var TERMINAL_STATES = {
        "Complete": true, "Fail": true, "Cancelled": true,
    };
    var DEFAULT_COLOR = "#9aa0a6"; // unknown status -- neutral grey
    var DEFAULT_ORDER = 99;
    /* ---------- helpers ---------- */
    /** Unwrap a picklist object (or pass through a bare string) to its itemValue. */
    function pickItemValue(p) {
        if (!p)
            return "";
        if (typeof p === "string")
            return p;
        return p.itemValue || "";
    }
    ztpGraph.pickItemValue = pickItemValue;
    /** The run-group name on a step (ztpfRunGroups may be expanded object or IRI). */
    function runGroupName(step) {
        var rg = step.ztpfRunGroups;
        if (!rg)
            return "";
        if (typeof rg === "string")
            return rg;
        return rg.name || "";
    }
    ztpGraph.runGroupName = runGroupName;
    /** Coerce a step's stepNumber to a number (0 if missing/invalid). */
    function stepNum(step) {
        var n = step.stepNumber;
        return typeof n === "number" && isFinite(n) ? n : 0;
    }
    ztpGraph.stepNum = stepNum;
    /** Resolve status value + color + order + flags. Color prefers the picklist's
     *  own color, falling back to QUEUE_STATUS, then grey. */
    function statusInfo(step) {
        var q = step.queueStatus;
        var value = pickItemValue(q);
        var color = (q && typeof q === "object" && q.color) ? q.color : "";
        var order = (q && typeof q === "object" && typeof q.orderIndex === "number") ? q.orderIndex : undefined;
        if (!color || !order && order !== 0) {
            var known = ztpGraph.QUEUE_STATUS[value];
            if (known) {
                if (!color)
                    color = known.color;
                if (order === undefined)
                    order = known.order;
            }
        }
        if (!color)
            color = DEFAULT_COLOR;
        if (order === undefined)
            order = DEFAULT_ORDER;
        var blocked = value === "Input Needed";
        var failed = value === "Fail";
        return {
            value: value,
            color: color,
            order: order,
            isTerminal: TERMINAL_STATES[value] === true,
            isRunning: value === "Running",
            isQueued: PENDING_STATES[value] === true,
            isBlocked: blocked,
            isFailed: failed,
            badge: blocked ? "attention" : failed ? "fail" : value === "Cancelled" ? "cancelled" : "",
        };
    }
    ztpGraph.statusInfo = statusInfo;
    /** Parse triggerKey into {category,type}. e.g. "FortiManager DeviceDB". */
    function parseTriggerKey(step) {
        var tk = (step.triggerKey || "").trim();
        var sp = tk.indexOf(" ");
        if (sp < 0)
            return { category: tk, type: "" };
        return { category: tk.slice(0, sp), type: tk.slice(sp + 1) };
    }
    ztpGraph.parseTriggerKey = parseTriggerKey;
    /** Map a step to its graph icon. Playbook type wins; else category drives. */
    /** ztpfActionType -> icon family. Grouped rather than one glyph per type:
     *  20 glyphs would not stay distinguishable at 26px, and the types within a
     *  family do the same KIND of work, which is what the icon is for. Types with
     *  no entry fall through to the category default below. */
    var ICON_FAMILY = {
        "Remote CLI": "cli",
        "Remote TCL": "cli",
        "Proxy API": "api",
        "JSON RPC": "api",
        "DeviceDB": "configdb",
        "PolicyDB": "configdb",
        "Install Device Config": "configdb",
        "Install Policy Package": "configdb",
        "Reinstall Policy Package": "configdb",
        "Refresh Device": "configdb",
        "Authorize Device": "configdb",
        "Provisioning CLI Teamplate": "configdb", // sic -- the shipped picklist spelling
        "Provisioning Jinja Teamplate": "configdb", // sic
        "Upgrade Device Firmware": "firmware",
        "Upgrade Preflight": "firmware",
        "Diff Step Output": "analysis",
        "Validate Step Output": "analysis",
        "Report": "analysis",
        "Wait for Condition": "control",
        "Playbook": "control",
    };
    function stepIcon(step) {
        var parsed = parseTriggerKey(step);
        var byType = ICON_FAMILY[parsed.type];
        if (byType)
            return byType;
        // Unknown/absent action type: fall back to something category-shaped rather
        // than a bare dot, so a newly-added type still reads as roughly the right kind.
        if (parsed.category === "FortiManager")
            return "configdb";
        if (parsed.category === "ZTPF")
            return "analysis";
        if (parsed.category === "FortiSOAR")
            return "control";
        return "generic";
    }
    ztpGraph.stepIcon = stepIcon;
    /** Which badge, if any, this step's status should overlay on its icon. */
    function stepBadge(step) {
        return statusInfo(step).badge;
    }
    ztpGraph.stepBadge = stepBadge;
    /** Sort a copy ascending by stepNumber (stable; missing stepNumber sorts last). */
    function sortByStepNumber(steps) {
        var key = function (s) {
            return (s.stepNumber == null) ? Infinity : s.stepNumber;
        };
        return steps.slice().sort(function (a, b) {
            var d = key(a) - key(b);
            return d !== 0 ? d : 0;
        });
    }
    ztpGraph.sortByStepNumber = sortByStepNumber;
    /** Extract the run-group name of the latest run from the device artifact. */
    function latestRunGroupName(artifact) {
        return (artifact && artifact.ztfGroup) ? artifact.ztfGroup : "";
    }
    ztpGraph.latestRunGroupName = latestRunGroupName;
    /** Filter step records to the latest run-group.
     *  - Target = the newest run-group by name epoch present in `steps`, or
     *    `artifact.ztfGroup` when that is newer/the steps carry no name.
     *  Always sorts the result ascending by stepNumber. */
    function filterLatestRunGroup(steps, artifact) {
        if (!steps || !steps.length)
            return [];
        // The newest group PRESENT IN THE STEPS wins over the artifact's ztfGroup.
        // The artifact is read once from FormEntityService when the panel loads, so
        // on a page that has been open across two runs it names the PREVIOUS group
        // -- which is why a finished run stayed on screen while the new one queued
        // its steps behind it. Names are ztpf-<epoch>-<id>, so lexical = chronological.
        var newest = "";
        for (var i = 0; i < steps.length; i++) {
            var nm = runGroupName(steps[i]);
            if (nm && nm > newest)
                newest = nm;
        }
        var target = latestRunGroupName(artifact);
        if (!target || (newest && newest > target))
            target = newest;
        var filtered = target
            ? steps.filter(function (s) { return runGroupName(s) === target; })
            : steps.slice();
        // An artifact naming a group with no step records (stale or mid-write) must
        // not blank the graph -- fall back to whatever the newest real group is.
        if (!filtered.length && newest && target !== newest) {
            filtered = steps.filter(function (s) { return runGroupName(s) === newest; });
        }
        return sortByStepNumber(filtered);
    }
    ztpGraph.filterLatestRunGroup = filterLatestRunGroup;
    /** Derive the graph mode from the (run-group-filtered) steps + device flag.
     *  running > queued > completed > empty. */
    function deriveGraphMode(steps, ztpfRunning) {
        if (!steps || !steps.length)
            return "empty";
        var hasRunning = false, hasBlocked = false, hasFailed = false;
        var allPending = true, allTerminal = true;
        for (var i = 0; i < steps.length; i++) {
            var si = statusInfo(steps[i]);
            if (si.isRunning)
                hasRunning = true;
            if (si.isBlocked)
                hasBlocked = true;
            if (si.isFailed)
                hasFailed = true;
            if (!si.isQueued)
                allPending = false;
            if (!si.isTerminal)
                allTerminal = false;
        }
        // A run whose every step reached an end state is FINISHED, whatever the
        // device flag says. ztpfRunning is a device-level latch that outlives the
        // run: it stayed true on a box where all 22 steps read Complete, and ORing
        // it in unconditionally made the badge contradict the graph under it. The
        // flag still speaks for a dispatched run whose steps have not started yet
        // (allPending, below) -- that is the case it exists for.
        if (hasRunning || (ztpfRunning && !allTerminal))
            return "running";
        // Parked on Input Needed. Previously this fell through to "queued", because
        // Input Needed counts as not-yet-started -- so a run waiting on a human was
        // indistinguishable from one merely sitting in the queue.
        if (hasBlocked)
            return "blocked";
        if (allPending)
            return "queued";
        // "failed"/"completed" require EVERY step to have reached an end state.
        // A run with a failed step but others still pending is not finished: ZTPf2's
        // on-failure behaviour is to carry on (guide 7b, "NO decision -- always
        // continues"), so calling it failed here would stop the widget polling a run
        // that is still advancing.
        if (allTerminal)
            return hasFailed ? "failed" : "completed";
        return "running";
    }
    ztpGraph.deriveGraphMode = deriveGraphMode;
    /** The "current" step = the Running one; else the first non-terminal by order;
     *  else null. */
    function currentStep(steps) {
        if (!steps || !steps.length)
            return null;
        var ordered = sortByStepNumber(steps);
        for (var i = 0; i < ordered.length; i++) {
            if (statusInfo(ordered[i]).isRunning)
                return ordered[i];
        }
        for (var j = 0; j < ordered.length; j++) {
            if (!statusInfo(ordered[j]).isTerminal)
                return ordered[j];
        }
        return null;
    }
    ztpGraph.currentStep = currentStep;
    /** Best-effort error message for a failed step (for tooltip). */
    function errorMessage(step) {
        var out = step.outputSourceData && step.outputSourceData.output;
        if (out && out.error && out.msg)
            return out.msg;
        return "";
    }
    ztpGraph.errorMessage = errorMessage;
    /** Build a short tooltip string for a node. */
    function nodeTooltip(step) {
        var si = statusInfo(step);
        var parts = [];
        parts.push("Step " + stepNum(step) + ": " + (step.name || ""));
        parts.push("Status: " + (si.value || "unknown"));
        var rg = runGroupName(step);
        if (rg)
            parts.push("Run group: " + rg);
        var err = errorMessage(step);
        if (err)
            parts.push("Error: " + err);
        return parts.join("\n");
    }
    ztpGraph.nodeTooltip = nodeTooltip;
    /** The step's record id for deep-linking (uuid preferred, else @id tail). */
    function stepRecordId(step) {
        if (step.uuid)
            return step.uuid;
        if (step["@id"]) {
            var parts = step["@id"].split("/");
            return parts[parts.length - 1];
        }
        return step.id != null ? String(step.id) : "";
    }
    ztpGraph.stepRecordId = stepRecordId;
    /** Deep-link URL to a step's record in FortiSOAR. */
    function deepLinkUrl(step, stepModule) {
        var mod = stepModule || "ztpf_device_automation_steps";
        return "/modules/view-panel/" + mod + "/" + stepRecordId(step);
    }
    ztpGraph.deepLinkUrl = deepLinkUrl;
    /** Build cytoscape element defs (nodes + edges) from run-group steps.
     *  Nodes carry status color/icon; the current step is flagged for glow/blink;
     *  queued mode makes nodes grabbable (reorderable). Edges chain step[n]->[n+1]. */
    function toElements(steps, opts) {
        var mode = opts.mode;
        var grabbable = mode === "queued";
        var curId = opts.currentId || null;
        if (curId === null && steps.length) {
            var cur = currentStep(steps);
            curId = cur ? stepRecordId(cur) : null;
        }
        var nodes = [];
        var edges = [];
        for (var i = 0; i < steps.length; i++) {
            var s = steps[i];
            var si = statusInfo(s);
            var id = stepRecordId(s) || ("step-" + stepNum(s));
            var isCur = curId !== null && id === curId;
            var labelNum = (s.stepNumber == null) ? "?" : String(s.stepNumber);
            // Show the step NAME on the node, prefixed by the step number. Fall back to
            // "Step N" when a step has no name. Long names wrap (text-wrap in the node
            // style) so they don't overflow the canvas.
            var stepName = (s.name == null ? "" : String(s.name)).trim();
            var label = stepName ? (labelNum + ". " + stepName) : ("Step " + labelNum);
            // Slugify: "Input Needed" would otherwise emit the class "status-input
            // needed", and a space inside a cytoscape class string silently splits it
            // into two bogus classes.
            var statusSlug = si.value ? si.value.toLowerCase().replace(/[^a-z0-9]+/g, "-") : "unknown";
            var classes = ["status-" + statusSlug, "icon-" + stepIcon(s), mode];
            if (isCur)
                classes.push("current");
            if (si.isBlocked)
                classes.push("blocked");
            if (si.badge)
                classes.push("badged");
            nodes.push({
                data: {
                    id: id,
                    stepNumber: stepNum(s),
                    label: label,
                    status: si.value || "unknown",
                    color: si.color,
                    icon: stepIcon(s),
                    badge: si.badge,
                    isCurrent: isCur,
                    isTerminal: si.isTerminal,
                    isBlocked: si.isBlocked,
                    recordId: id,
                    tooltip: nodeTooltip(s),
                    name: stepName,
                    runGroup: runGroupName(s),
                    error: errorMessage(s),
                },
                classes: classes.join(" "),
                grabbable: grabbable,
            });
        }
        for (var k = 1; k < steps.length; k++) {
            var prev = stepRecordId(steps[k - 1]) || ("step-" + stepNum(steps[k - 1]));
            var curr = stepRecordId(steps[k]) || ("step-" + stepNum(steps[k]));
            edges.push({ data: { id: "e-" + k + "-" + prev + "-" + curr, source: prev, target: curr } });
        }
        return { nodes: nodes, edges: edges };
    }
    ztpGraph.toElements = toElements;
})(ztpGraph || (ztpGraph = {}));
if (typeof module !== "undefined" && module && module.exports) {
    module.exports = ztpGraph;
}

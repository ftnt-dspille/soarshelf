declare namespace ztpGraph {
    /** FortiSOAR picklist object as returned on a record field. */
    interface Picklist {
        "@id"?: string;
        itemValue: string;
        color?: string | null;
        orderIndex?: number;
        icon?: string | null;
    }
    /** A canonical ztpf_device_automation_steps record (subset the widget uses). */
    interface AutomationStep {
        "@id"?: string;
        uuid?: string;
        id?: number;
        stepNumber: number | null | undefined;
        name?: string | null;
        /** Flat "<category> <type>" e.g. "FortiManager DeviceDB". Icon driver. */
        triggerKey?: string | null;
        /** Picklist object {itemValue,color,orderIndex}. THE status field. */
        queueStatus?: Picklist | string | null | undefined;
        stepDone?: boolean | null;
        stepStartTimestamp?: number | null;
        stepStopTimestamp?: number | null;
        ztpfRunGroups?: {
            name?: string | null;
            uuid?: string | null;
        } | string | null;
        outputSourceData?: {
            output?: {
                error?: boolean | null;
                msg?: string | null;
            } | null;
        } | null;
    }
    /** The ztpf_devices.ztpfArtifact summary (latest run-group, STALE -- id only). */
    interface ZtpfArtifact {
        steps?: Array<{
            id?: number;
            fqid?: string;
            name?: string;
            stepNumber?: number | null;
            action_category?: string;
            action_type?: string;
            ztpf_status?: string;
            ztpf_start_time?: number | null;
            ztpf_stop_time?: number | null;
        }> | null;
        /** Note the typo: `ztfGroup`, not `ztpfGroup`. */
        ztfGroup?: string | null;
        total_steps?: number | null;
    }
    type GraphMode = "empty" | "queued" | "blocked" | "running" | "failed" | "completed";
    /** Icon families. One glyph per family of ztpfActionType, NOT per category:
     *  keying on category drew the same document icon for all seven FortiManager
     *  action types actually in use (Remote CLI, Proxy API, DeviceDB, JSON RPC,
     *  Install Device Config, Upgrade Device Firmware, Upgrade Preflight). */
    type StepIcon = "cli" | "api" | "configdb" | "firmware" | "analysis" | "control" | "generic";
    /** Attention badge overlaid on the step icon, for the states a run can sit in
     *  that a colour alone does not communicate. "" = no badge. */
    type StepBadge = "" | "attention" | "fail" | "cancelled";
    interface StatusInfo {
        value: string;
        color: string;
        order: number;
        /** Reached an end state -- nothing more will happen to this step. */
        isTerminal: boolean;
        isRunning: boolean;
        /** Not started yet: everything from New through Queued. */
        isQueued: boolean;
        /** Waiting on a human (Input Needed) -- the run cannot proceed unattended. */
        isBlocked: boolean;
        /** Ended badly (Fail) as opposed to Complete/Cancelled. */
        isFailed: boolean;
        badge: StepBadge;
    }
    interface NodeData {
        id: string;
        stepNumber: number;
        label: string;
        status: string;
        color: string;
        icon: StepIcon;
        badge: StepBadge;
        isCurrent: boolean;
        isTerminal: boolean;
        isBlocked: boolean;
        recordId: string;
        tooltip: string;
        name: string;
        runGroup: string;
        error: string;
    }
    interface NodeDef {
        data: NodeData;
        classes: string;
        grabbable: boolean;
    }
    interface EdgeDef {
        data: {
            id: string;
            source: string;
            target: string;
        };
    }
    interface GraphElements {
        nodes: NodeDef[];
        edges: EdgeDef[];
    }
    interface ToElementsOptions {
        mode: GraphMode;
        currentId?: string | null;
        stepModule?: string;
    }
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
    const QUEUE_STATUS: {
        [value: string]: {
            color: string;
            order: number;
        };
    };
    /** Unwrap a picklist object (or pass through a bare string) to its itemValue. */
    function pickItemValue(p: Picklist | string | null | undefined): string;
    /** The run-group name on a step (ztpfRunGroups may be expanded object or IRI). */
    function runGroupName(step: AutomationStep): string;
    /** Coerce a step's stepNumber to a number (0 if missing/invalid). */
    function stepNum(step: AutomationStep): number;
    /** Resolve status value + color + order + flags. Color prefers the picklist's
     *  own color, falling back to QUEUE_STATUS, then grey. */
    function statusInfo(step: AutomationStep): StatusInfo;
    /** Parse triggerKey into {category,type}. e.g. "FortiManager DeviceDB". */
    function parseTriggerKey(step: AutomationStep): {
        category: string;
        type: string;
    };
    function stepIcon(step: AutomationStep): StepIcon;
    /** Which badge, if any, this step's status should overlay on its icon. */
    function stepBadge(step: AutomationStep): StepBadge;
    /** Sort a copy ascending by stepNumber (stable; missing stepNumber sorts last). */
    function sortByStepNumber(steps: AutomationStep[]): AutomationStep[];
    /** Extract the run-group name of the latest run from the device artifact. */
    function latestRunGroupName(artifact: ZtpfArtifact | null | undefined): string;
    /** Filter step records to the latest run-group.
     *  - If `artifact.ztfGroup` is set, keep steps whose ztpfRunGroups.name matches.
     *  - Else fall back to the newest run-group by name epoch (ztpf-<epoch>).
     *  Always sorts the result ascending by stepNumber. */
    function filterLatestRunGroup(steps: AutomationStep[], artifact: ZtpfArtifact | null | undefined): AutomationStep[];
    /** Derive the graph mode from the (run-group-filtered) steps + device flag.
     *  running > queued > completed > empty. */
    function deriveGraphMode(steps: AutomationStep[], ztpfRunning: boolean | null | undefined): GraphMode;
    /** The "current" step = the Running one; else the first non-terminal by order;
     *  else null. */
    function currentStep(steps: AutomationStep[]): AutomationStep | null;
    /** Best-effort error message for a failed step (for tooltip). */
    function errorMessage(step: AutomationStep): string;
    /** Build a short tooltip string for a node. */
    function nodeTooltip(step: AutomationStep): string;
    /** The step's record id for deep-linking (uuid preferred, else @id tail). */
    function stepRecordId(step: AutomationStep): string;
    /** Deep-link URL to a step's record in FortiSOAR. */
    function deepLinkUrl(step: AutomationStep, stepModule?: string): string;
    /** Build cytoscape element defs (nodes + edges) from run-group steps.
     *  Nodes carry status color/icon; the current step is flagged for glow/blink;
     *  queued mode makes nodes grabbable (reorderable). Edges chain step[n]->[n+1]. */
    function toElements(steps: AutomationStep[], opts: ToElementsOptions): GraphElements;
}
declare var module: {
    exports: any;
} | undefined;

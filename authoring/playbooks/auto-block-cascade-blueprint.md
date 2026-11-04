# Auto-Block Cascade -- the layered use case blueprint

One detection anywhere in the stack becomes one indicator, one FortiGuard
verdict, and -- when the verdict says malicious -- one automated block at
every layer that can carry it, at any hour, with no human in the loop. The
SOC plane (Splunk + ServiceNow) is kept exactly as it is today: the SOC
keeps working in the tools they already run, and their phones keep buzzing
through the channels they already carry.

This blueprint describes the `auto-block-cascade.yaml` collection in this
directory: five playbooks, compiled with zero warnings and machine-verified
offline (16 execution lanes walked under mock outputs), grounded in the
real Content Hub connector operations of every product named below. Where a
product's blocking API does not exist, this document says so instead of
pretending. The shelf item's page text is the condensed
`auto-block-cascade-description.md` in this directory (the shelf caps
descriptions below this document's length); this file stays the full
design and verification record.

## The stack and what each piece does here

| Product | Role in the cascade | Enforcement it can take from FortiSOAR |
|---|---|---|
| FortiGate (+ FortiSASE) | The gate. Primary, broadest layer | FortiGate: `block_url` (web filter blocklist), `block_ip_new` (Policy Based into an IPv4/IPv6 block policy + named group, or Quarantine Based via `ip_addresses` + `time_to_live`), and `quarantine_host` for endpoint-host cut-off via the `fortigate-firewall` connector. FortiSASE: today its hub connector (v1.0.0) manages hosts/services/to/from-hub policies and a generic API call -- indicator blocklisting there is a policy-side follow-up this blueprint documents as such, not something the compiled playbooks claim |
| Microsoft Defender for Endpoint | The endpoint EDR: block the thing even if the gate never saw it (SSL inspection blind spots, off-network endpoints) | `submit_indicator` with action "Alert and block" (the connector's enum label for Microsoft's AlertAndBlock) -- domain, IP, URL or file hash |
| ThreatLocker | The app allowlist sitting at the lowest layer: the deny is the resting state | There is no policy-write or known-threats-write endpoint in ThreatLocker's public PortalAPI -- so "blocking" in ThreatLocker means: the default-deny posture already blocks the file, and FortiSOAR closes the crack a user could open through it -- any pending approval request for that exact file hash is auto-rejected with the FortiGuard verdict as the reason (the requestor sees why, in the toast follow-up and their email) |
| CrowdStrike Falcon Identity Protection | A detection source: identity alerts (impossible travel, MFA fatigue, kerberoasting) flow in like any other signal | Automated identity containment is NOT wired in v1: the hub connector (v1.0.0) exposes alert/incident reads and status updates, not a contain-user operation. Containment stays a documented manual step (documented verdict and target inside the SIR) |
| Darktrace | A detection source -- and the SOC's existing phone channel for network-side events (the Darktrace mobile app pushes breaches in real time) | No enforcement from this flow (Antigena owns its own response); the compiled Darktrace Breach Sweep feeds detections INTO the cascade |
| Splunk | The SOC's SIEM -- stays the SOC's operational pane | `add_record_to_collection` writes every cascade outcome into a KVStore collection the SOC already has or creates once |
| ServiceNow | The SOC's ticket queue (SIR module) | `create_SIR` -- a security-incident record with the full story and every enforcement receipt |
| FortiGuard | The verdict authority: one reputation answer (risk score, level, category, tags) decides if this runs autonomously or waits for a human | `ioc_search` on the fortinet-fortiguard-ioc connector |

## The cascade -- why in this order

1. **Gate first** (`block_url` / `block_ip_new`): the broadest, cheapest cut --
   every user behind the gate stops reaching the indicator immediately,
   regardless of which endpoint they use.
2. **Endpoint EDR second** (Defender `submit_indicator`, action "Alert and block"): for
   the paths the gate cannot see -- remote/off-VPN endpoints, encrypted
   traffic, an infection already resident.
3. **ThreatLocker third** -- it is already denying the file by default; the
   cascade's job there is to keep it that way: auto-reject any approval
   request whose file hash matches, quoting the verdict, so a user cannot
   allow-list a known-bad binary out from under the SOC at 3am.

A file hash enforces at layers 2-3 only (a firewall does not carry file
hashes); a domain/IP enforces at the gate and layer 2. Every layer acts on
the same verdict, independently -- that is the point of a cascade, not a
chain of dependencies: "if not blocked at the gate" (the user's own line)
is covered by design, not by fallback logic.

The **verdict gates the autonomy, not the action**:

| FortiGuard verdict | What happens, without anyone awake |
|---|---|
| malicious (risk >= 80) | the full cascade, silently, then the SIR and the Splunk record |
| suspicious (risk 50-79) | a Manual Input approval pauses the run: configure the step's email notification for the on-call address (deployment config) and the analyst approves or declines from mail or the FortiSOAR app; approving cascades, declining or skipping records-only |
| clean / unknown | record-only: SIR + Splunk, human triage |

## The five playbooks in auto-block-cascade.yaml

| Playbook | Trigger | What it does |
|---|---|---|
| `>> Auto-Block Cascade > Resolve Indicator Verdict` | referenced helper (the `>>` prefix keeps helpers out of the browse list) | Classifies the indicator (domain / IPv4 / IPv6 / URL / SHA-256 / SHA-1 / MD5, with the Defender indicator type derived) and asks FortiGuard (`ioc_search`) for the verdict bundle: risk score, level, confidence, category, tags, and the verdict at thresholds 80/50 |
| `>> Auto-Block Cascade > Enforce Indicator` | referenced helper | The cascade: gate block -> Defender IOC -> ThreatLocker pending-request auto-reject, each layer independently `when:`-guarded by indicator type (IPv4 and IPv6 gate blocks are separate steps so each operation's parameter set is statically verified); always ends in a ServiceNow SIR + a Splunk record carrying every receipt |
| `Auto-Block Cascade > Block Indicator (API)` | HTTP `POST /api/triggers/1/block-indicator` | The generic front door: ANY detector (or a human) POSTs a JSON body `{indicator, hostname?, computer_id?, username?, source?, notes?}`. The endpoint materializes the raw body (there are no per-field trigger inputs on this trigger type); the playbook parses it once and reads every field defensively, so the cheapest detector integration is a one-field POST. Verdict decides autonomous cascade vs human approval vs record-only |
| `Auto-Block Cascade > ThreatLocker Request Autotriage` | Run button / schedule | The end-user loop: a user double-clicks a blocked file, gets the ThreatLocker toast, requests permission (that is the "ticket"); this picks the next pending request with a file hash, verdicts it via FortiGuard, and -- only on a malicious verdict -- auto-rejects it with the reason and cascades the hash. Anything less than malicious becomes a task for a human (the natural handoff is the connector's own Decide Elevation Request playbook) |
| `Auto-Block Cascade > Darktrace Breach Sweep` | Run button / schedule | The detection-side example: pulls recent model breaches (`get_model_breaches` -> `get_breach_details`), extracts the destination candidates and sweeps the first usable one through the cascade with source Darktrace -- the full candidate list rides in the SIR/task so nothing is lost, and widening to every candidate is a loop change, not a redesign. The Darktrace app has already pushed the breach to phones -- this is the machine response to what the phones saw |

CrowdStrike Identity / Defender / anything else with an API: point them at
the `block-indicator` route with a webhook or their own schedules -- the
route body is the whole contract (below).

## The end-user loop (the ThreatLocker toast story)

1. A user double-clicks something ThreatLocker does not know. ThreatLocker
   denies it and shows its toast: the option to request the app.
2. The user types their reason; the request lands in the approval queue
   (what this blueprint calls "a ticket in ThreatLocker").
3. The Autotriage run verdicts the file's hash with FortiGuard.
   - malicious: the request is rejected automatically, the requestor gets
     the verdict as the denial reason, and the hash cascades to Defender
     (and the SIR/Splunk record exists for the SOC).
   - suspicious/unknown/clean: a task for the human decide-loop, and the
     human can still permit it into the allowlist when they judge it
     safe -- nothing in this flow removes their agency.

## How the SOC is notified (the research ask, answered)

- **Splunk Mobile** (iOS/Android): native push notifications triggered by
  Splunk data -- the cascade writes its record into the SOC's Splunk
  collection, so the SOC's existing alerting (saved searches over that
  collection, or alert actions) becomes the phone notification. This is the
  recommended primary channel because it rides the SOC's existing SIEM
  workflow.
- **Darktrace Mobile App**: pushes its model breaches in real time today --
  unchanged by this flow; the sweep is the automated response to those
  pushes.
- **ServiceNow**: the SIR record notifies its assignee/group (existing
  ServiceNow notification rules).
- **Edge case coverage**: if the customer's Splunk collection is the chosen
  phone path but gets redesigned, the fallback is one added
  `send_email` step after Record In Splunk (a deliberate non-stub: shipping
  an email step with no recipient would look like wiring and fire blanks;
  the integration point is documented here instead) -- any SMTP relay the
  customer already runs works.

## Demo script (the simple-scripts.de walkthrough)

1. (Optional primer) Show a ThreatLocker deny toast on a test endpoint --
   the user's view of the lowest layer.
2. `POST /api/triggers/1/block-indicator` with
   `{"indicator": "simple-scripts.de", "source": "demo", "hostname": "lab-endpoint-01"}`
   -- on screen, not hidden: the point is that any detector could have sent
   it.
3. Walk the run tree live: classification -> FortiGuard verdict (the LIVE
   lookup decides the demo's color -- do not pre-claim the verdict for this
   domain;) -> cascade steps with their receipts.
4. Show the FortiGate blocklist entry (or its mock), the Defender indicator,
   and -- the signature move -- a pending ThreatLocker request for the
   matching hash disappearing into auto-rejected with the verdict reason.
5. Open ServiceNow: the SIR with category, risk, and each enforcement
   receipt. Open Splunk: the record, then the saved-search alert that pushed
   the analyst's phone.
6. The close: run the ThreatLocker Request Autotriage once more and show
   it fall through to "nothing malicious pending" -- the system is quiet
   exactly when it should be.

## Prerequisites (deployment config the playbooks assume)

- **FortiGate connector**: an IPv4/IPv6 Block Policy and the named IP group
  configured (the `block_ip_new` policy/group names are deployment-config
  values -- set them in the playbook's Configuration step); web filter
  blocklist enabled for `block_url`.
- **Splunk**: a KVStore collection (e.g. `fortisoar_autoblock`) in an app
  the SOC owns; the playbooks set `app_name`/`collection` in their
  Configuration step.
- **ServiceNow**: the SIR module enabled (it is a plugin); the playbooks set
  the table name (`sn_si_incident`) in Configuration.
- **Defender**: an AAD app with Defender ATP permissions to submit
  indicators; indicator limits per license honored.
- **ThreatLocker (our connector)**: API user with "View Approvals" (minimum)
  and enough org scope to see child-organization requests. The connector
  itself is not on the Content Hub: its source is the separate repo
  `github.com/ftnt-dspille/connector-threatlocker`, published separately
  from this collection.
- **Darktrace**: API key with read on model breaches (public API).
- **FortiGuard**: the fortinet-fortiguard-ioc connector works against the
  public FortiGuard API -- thresholds (80/50) live at the top of Resolve
  Indicator Verdict.

## Offline verification (what ran, what did not)

Nothing here has run against a live tenant of any product. What did run:

- `fsrpb compile` writes the collection JSON with zero warnings: every
  connector, operation and parameter name is checked against the catalog,
  including the per-`ip_type` parameter sets on `block_ip_new` (the reason
  the IPv4 and IPv6 gate blocks are separate steps) and the Defender
  action enum.
- `fsrpb validate` passes clean.
- 16 execution lanes walked offline with the live Jinja engine and authored
  mock outputs: both workflow_reference helper recursions (synchronous),
  every decision branch and when-guard, the suspicious-lane human approval
  in both directions, the empty-request refusal, the nothing-pending
  autotriage, and the Darktrace quiet-window and unusable-candidate
  terminals.

The YAML ships `mock_result` blocks on the connector steps, the five code
snippets and the API trigger seed (the demo POST body). They model the
canonical demo scenario -- simple-scripts.de at risk 100, the pending
ThreatLocker request, the Darktrace breach -- and on a live box they take
effect only where Use-Mock-Output is toggled for that step, so a deployed
copy is unaffected. The shelf's publish step strips these blocks from the
downloadable copy ("authoring sample data removed"), so the installed
playbook starts with zero sample data; the blocks live in the authoring
source in this directory, which is also where the walks ran. The alternate
lanes are walked by patching these mocks at walk time, never by editing
the file:

| Walk-time override | Lane it exercises |
|---|---|
| Score Verdict mock -> risk 60 / suspicious | human-approval loop (both outcomes) on the API front door, autotriage and sweep task lanes |
| Score Verdict mock -> risk 30 / clean | clean record-only lane |
| Start mock body -> `{}` | empty-request refusal |
| queue row gets an actionDate | nothing-pending autotriage terminal |
| breach list -> `[]` / extracted picked -> '' | quiet-window and unusable-candidate terminals |

The walk harness itself is maintainers' tooling kept out of the shelf
content; the table above plus the mock blocks is enough to rebuild it.

## Lab runnability (our side)

Fabric Studio gives a real FortiGate and a real FortiSOAR for the demo, and
the FortiGate/SIR/Splunk steps run against live boxes the moment those
integrations are configured. ThreatLocker, CrowdStrike, Darktrace, Splunk
and ServiceNow need the customer's own instances/credentials -- until those
are wired, the compiled set carries the offline verification above, the
same wire-then-verify bar the threatlocker connector's own samples carry.
The cascade's steps are all connector-call steps, so a live lab demo can
subset: FortiGuard verdict + FortiGate block + SIR creation is a complete
kill in three products on the first day.

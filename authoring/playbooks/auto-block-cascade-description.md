# Auto-Block Cascade (shelf description)

One detection, one FortiGuard verdict, one automatic block at every layer
that can carry it -- with no human awake. The SOC plane (ServiceNow +
Splunk) keeps working exactly as it does today.

The FortiGuard risk score gates the autonomy, not the action: malicious
(risk 80 and up) cascades silently across every layer; suspicious (50-79)
pauses at a Manual Input approval the on-call can answer from mail or the
FortiSOAR app; clean or unknown records only. The thresholds live in one
step, so tuning the autonomy is a one-place edit.

The layers, in cascade order:

- **FortiGate** -- the gate, the broadest cut: `block_url` into the web
  filter blocklist, `block_ip_new` Policy Based into the named IPv4/IPv6
  block policy and group (both are configuration values in one step);
  quarantine-based blocking and `quarantine_host` are the connector's
  other options.
- **Microsoft Defender for Endpoint** -- `submit_indicator` with action
  "Alert and block" carries hashes and network indicators along the paths
  the gate never sees (remote endpoints, encrypted traffic).
- **ThreatLocker** -- an application allowlist's resting state is deny,
  and ThreatLocker's public API has no policy-write endpoint, so the
  cascade holds the default-deny closed instead: any pending approval
  request whose file hash matches the verdict is auto-rejected, with the
  FortiGuard verdict as the reason the requestor sees. A hash cannot be
  allow-listed out from under the SOC at 3am. The ThreatLocker connector
  is not on the Content Hub; its source is
  `github.com/ftnt-dspille/connector-threatlocker`.

Every outcome ends in a ServiceNow SIR and a Splunk KVStore record, so the
SOC's existing notification surface needs no new wiring: Splunk Mobile and
saved searches trigger off the record, the SIR notifies its assignee.

**Playbooks**

- `Resolve Indicator Verdict` (helper) -- classifies the indicator
  (domain / IP / URL / sha256 / sha1 / md5, Defender type derived) and asks
  FortiGuard `ioc_search` for the verdict bundle.
- `Enforce Indicator` (helper) -- the cascade itself, each layer
  independently guarded by what the indicator type can carry, and the SIR +
  Splunk receipts either way.
- `Block Indicator (API)` -- `POST /api/triggers/1/block-indicator` with a
  JSON body, `{"indicator": "..."}` and optional hostname, computer_id,
  username, source, notes: the whole wiring story for ANY detector.
- `ThreatLocker Request Autotriage` -- the end-user loop: a blocked user
  requests the app from the ThreatLocker toast (their "ticket"); this
  verdicts the pending request's file hash, auto-rejects on malicious, and
  queues everything else for a human.
- `Darktrace Breach Sweep` -- pulls model breaches and sweeps the first
  usable destination indicator through the cascade: the machine response
  to what the Darktrace mobile app already pushed.

**Status: machine-verified offline, not live-tested.** The collection
compiles with zero warnings and all 16 execution lanes (every decision
branch, both human-approval outcomes, every terminal path) walked clean
under mock outputs. No live tenant of any product named above has been
touched yet. The playbooks install inactive; activate them after review,
wire the connector configurations, and try the demo POST
(`{"indicator": "simple-scripts.de", "source": "demo"}`) to watch a first
verdict run end to end.

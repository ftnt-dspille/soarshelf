# FortiSOAR Ansible Automation Connector

Executes Ansible playbooks, ad-hoc modules, and roles directly from FortiSOAR
playbooks using [`ansible-runner`](https://ansible.readthedocs.io/projects/runner/),
returning structured per-host and per-task results. Ansible is agentless, so the
connector drives remote hosts over SSH/WinRM without a separate Ansible
Automation Platform deployment.

Verified end-to-end on a live FortiSOAR 8.0.0 appliance — including a real
FortiGate driven via `fortinet.fortios` — see
[`../tests/LIVE_RESULTS.md`](../tests/LIVE_RESULTS.md).

## Why a connector

FortiSOAR bundles Ansible inside the **workflow** engine venv (nginx-owned) only
to source Jinja filter plugins; the **integrations** venv where connectors run
has no Ansible, and no playbook step type executes modules. This connector adds
its own `ansible-core` + `ansible-runner` (declared in `requirements.txt`,
installed into the integrations venv at connector-install time) and exposes
Ansible execution as connector operations.

## Operations

| Operation | Purpose |
|---|---|
| `run_playbook` | Execute a playbook from inline YAML, an absolute path on the node, or a git repo. |
| `run_module` | Ad-hoc single module against a host pattern (the `ansible -m` equivalent). |
| `run_role` | Execute a single role against a host pattern. |
| `get_run_status` | Poll an asynchronously started run (returned `ident`). |
| `get_run_artifacts` | Full event stream, stdout, and fact cache of a retained run. |
| `cancel_run` | Terminate a running job. |
| `validate_playbook` | `--syntax-check` without executing. |
| `list_collections` | Collections installed in the connector's collections path. |
| `install_collection` | `ansible-galaxy collection install` into the collections path. |
| `list_modules` | Modules resolvable in the environment, optionally filtered. |

Shared execute params: `inventory`, `extra_vars`, `limit`, `tags`, `skip_tags`,
`check_mode`, `diff`, `verbosity`, `timeout`, `wait`, `keep_artifacts`.

## Result contract

Every execute operation returns a uniform object — `ident`, `status`, `rc`,
`ok`/`changed`/`failed`/`unreachable`/`skipped` counts, per-host `hosts{}`,
per-task `tasks[]`, and `stdout_tail`. **A failed Ansible task is a result, not
an exception**: the op returns `status: "failed"` so playbooks branch on it.
`ConnectorError` is reserved for connector-level failures (bad config,
unwritable runtime root, missing playbook, git absent, timeout).

## Security

- SSH private key and passwords live in connector-configuration password fields
  (encrypted at rest). The key is written `0600` to a run-scoped file and
  removed when the run completes; passwords go through ansible-runner's prompt
  channel or a run-scoped inventory file, never the command line.
- Runtime state is under `/opt/cyops-integrations/data/ansible/` (`0700`),
  owned by the integrations user. Runs are reaped after `run_retention_hours`.
- Host-key verification is on by default against the connector's `known_hosts`.

## Driving a FortiGate (fortinet.fortios)

1. `install_collection` → `fortinet.fortios`.
2. `run_playbook` with `connection: httpapi` and an inventory host whose vars are
   `ansible_host`, `ansible_httpapi_port`, `ansible_httpapi_use_ssl`,
   `ansible_network_os: fortinet.fortios.fortios`, `ansible_user`,
   `ansible_password`.
3. Pass the FortiGate credentials as **literal** inventory values, not Jinja
   `{{ }}` — FortiSOAR pre-renders Jinja in connector params, which would consume
   Ansible-side templating.

## Known constraints on a stock appliance

- **git source** requires `git`, which is not installed by default — use
  `inline` or `path`, or install git.
- **become / SSH password**: provision the configuration through the product UI
  so password-type fields are delivered to the connector.
- After iterating on connector **code**, `systemctl restart uwsgi` to reload the
  module; a reinstall alone leaves workers on the previous bytecode.

## Build

`info.json` is generated (avoids hand-maintaining repetitive field JSON):

```bash
python3 ../build_info_json.py
tar --exclude='._*' --exclude='__pycache__' -czf ../ansible-automation.tgz ansible-automation/
```

Install the `.tgz` via the product UI or pyfsr
(`client.connectors.install_from_file(..., replace=True, wait=True)`).

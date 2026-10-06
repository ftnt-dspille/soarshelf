"""Static configuration for the Ansible Automation connector."""

CONNECTOR_NAME = "ansible-automation"
LOGGER_NAME = "connectors.ansible-automation"

# Runtime root. Owned by the integrations service user; the workflow venv's
# ansible install is nginx-owned and deliberately not used.
ANSIBLE_ROOT = "/opt/cyops-integrations/data/ansible"

RUNS_DIRNAME = "runs"
COLLECTIONS_DIRNAME = "collections"
KEYS_DIRNAME = "keys"
KNOWN_HOSTS_FILENAME = "known_hosts"

DEFAULT_TIMEOUT = 300
DEFAULT_FORKS = 5
DEFAULT_RETENTION_HOURS = 24
MIN_CORE_VERSION = (2, 16)

# Terminal states reported by ansible-runner.
TERMINAL_STATUSES = {"successful", "failed", "timeout", "canceled"}

STDOUT_TAIL_BYTES = 20000

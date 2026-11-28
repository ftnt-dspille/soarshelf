"""Constants for the Microsoft Office 365 feed connector (v2)."""

# Public, anonymous endpoints feed. Tests point this at a loopback fake.
FEED_BASE = "https://endpoints.office.com"

REGIONS = ["China", "Germany", "USGovDoD", "USGovGCCHigh", "Worldwide"]
SERVICES = ["Common", "Exchange", "Sharepoint", "Skype", "All"]
INDICATOR_TYPES = {"ips": "IPs", "urls": "URLs", "both": "Both"}

# Only these path prefixes are reachable through execute_api_request.
ALLOWED_PATH_PREFIXES = ("/version/", "/endpoints/")

REQUEST_TIMEOUT = 60

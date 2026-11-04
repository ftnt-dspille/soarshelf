"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""

THREADS = 4
alerts_filter_map = {
    "vendor": "vendorInformation/vendor",
    "provider": "vendorInformation/provider",
    "severity": "severity",
    "search_from": "eventDateTime",
    "assigned_to": "assignedTo",
    "classification": "classification",
    "determination": "determination",
    "status": "status",
    "createdDateTime": "createdDateTime",
    "lastUpdateDateTime": "lastUpdateDateTime",
    "serviceSource": "serviceSource"
}
FEEDBACK = {
    "Unknown": "unknown",
    "True Positive": "truePositive",
    "False Positive": "falsePositive",
    "Benign Positive": "benignPositive"
}

SEVERITY = {
    "Unknown": "unknown",
    "Informational": "informational",
    "low": "low",
    "Medium": "medium",
    "High": "high",
    "Unknown Future Value": "unknownFutureValue"

}
STATUS = {
    "Unknown": "unknown",
    "Unknown Future Value": "unknownFutureValue",
    "New Alert": "newAlert",
    "In Progress": "inProgress",
    "Resolved": "resolved"
}
CLASSIFICATION = {
    "Unknown": "unknown",
    "False Positive": "falsePositive",
    "True Positive": "truePositive",
    "Informational Expected Activity": "informationalExpectedActivity",
    "Unknown Future Value": "unknownFutureValue"
}
DETERMINATION = {
    "Unknown": "unknown",
    "ATP": "apt",
    "Malware": "malware",
    "Security Personnel": "securityPersonnel",
    "Security Testing": "securityTesting",
    "Unwanted Software": "unwantedSoftware",
    "Other": "other",
    "MultiStaged Attack": "multiStagedAttack",
    "Compromised User": "compromisedUser",
    "Phishing": "phishing",
    "Malicious User Activity": "maliciousUserActivity",
    "Clean": "clean",
    "Insufficient Data": "insufficientData",
    "Confirmed User Activity": "confirmedUserActivity",
    "Line Of Business Application": "lineOfBusinessApplication",
    "Unknown Future Value": "unknownFutureValue"
}
IPv4 = "#microsoft.graph.iPv4CidrRange"
IPv6 = "#microsoft.graph.iPv6CidrRange"
FIELDS = {
    "ID": "id",
    "Created Date Time": "createdDateTime",
    "Display Name": "displayName",
    "Modified Date Time": "modifiedDateTime"
}

RESOURCE = "https://graph.microsoft.com"
SCOPE = 'https://graph.microsoft.com/.default'
API_VERSION = 'v1.0'
AUTH_USING_APP = "Without a User - Application Permission"
AUTH_BEHALF_OF_USER = "On behalf of User - Delegate Permission"
REFRESH_TOKEN_FLAG = False
DEFAULT_REDIRECT_URL = 'https://localhost/myapp'
AUTH_URL = 'https://login.microsoftonline.com'
# grant types
CLIENT_CREDENTIALS = 'client_credentials'
AUTHORIZATION_CODE = 'authorization_code'
REFRESH_TOKEN = 'refresh_token'
CERTIFICATE_BASED_AUTH_TYPE = "Certificate Based Authentication"

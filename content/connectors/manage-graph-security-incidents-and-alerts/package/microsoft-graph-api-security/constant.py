""" Copyright start
  Copyright (C) 2008 - 2024 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

STATUS = {
    'Active': 'active',
    'InProgress': 'inProgress',
    'Resolved': 'resolved'
}

GRAPH_SCOPE = "https://graph.microsoft.com/.default offline_access"
GRAPH_RESOURCE = "https://graph.microsoft.com"
GRAPH_API_VERSION = "v1.0"
AUTH_BEHALF_OF_USER = "On behalf of User - Delegated Permission"
AUTH_USING_APP = "Without a User - Application Permission"
DEFAULT_REDIRECT_URL = "https://localhost/myapp"
CLIENT_CREDENTIALS = "client_credentials"
AUTHORIZATION_CODE = "authorization_code"
REFRESH_TOKEN = "refresh_token"
ALERT = "/v1.0/security/alerts_v2"
INCIDENT = "/v1.0/security/incidents"
ADVANCED_HUNTING = "/beta/security/runHuntingQuery"

CLASSIFICATION = {
    'Unknown': 'unknown',
    'True Positive': 'truePositive',
    'Informational Expected Activity': 'informationalExpectedActivity',
    'False Positive': 'falsePositive',
    'Unknown Future Value': 'unknownFutureValue'
}

DETERMINATION = {
    'Multistage attack': 'multiStagedAttack',
    'Malicious user activity': 'maliciousUserActivity',
    'Compromised account': 'compromisedAccount',
    'Malware': 'malware',
    'Phishing': 'phishing',
    'Unwanted software': 'unwantedSoftware',
    'Other': 'other',
    'Security test': 'securityTesting',
    'Line-of-business application': 'lineOfBusinessApplication',
    'Confirmed user activity': 'confirmedActivity',
    'Not malicious': 'notMalicious',
    'Not enough data to validate': 'notEnoughDataToValidate',
    'Unknown future value': 'unknownFutureValue',
    'Apt': 'apt',
    'Unknown': 'unknown',
    'Security personnel': 'securityPersonnel'
}

TIMESPAN = {
    'Last 1 Hour': 'PT1H',
    'Last 6 Hours':	'PT6H',
    'Last 12 Hours': 'PT12H',
    'Last 24 Hours': 'P1D',
    'Last 7 Days': 'P7D',
    'Last 30 Days':	'P30D',
    'Last 90 Days;': 'P90D' 
}

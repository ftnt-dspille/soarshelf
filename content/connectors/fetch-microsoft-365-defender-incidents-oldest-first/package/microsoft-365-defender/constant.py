""" Copyright start
  Copyright (C) 2008 - 2024 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

STATUS = {
    'Active': 'Active',
    'Resolved': 'Resolved',
    'In Progress': 'InProgress',
    'Redirected': 'Redirected'
}

INCIDENT = "/api/incidents/"
ADVANCE_HUNTING = "/api/advancedhunting/run"

CLASSIFICATION = {
    'TruePositive': 'TruePositive',
    'Informational, expected activity': 'InformationalExpectedActivity',
    'FalsePositive': 'FalsePositive'
}

DETERMINATION = {
    'Multistage attack': 'MultiStagedAttack',
    'Malicious user activity': 'MaliciousUserActivity',
    'Compromised account': 'CompromisedAccount',
    'Malware': 'Malware',
    'Phishing': 'Phishing',
    'Unwanted software': 'UnwantedSoftware',
    'Other': 'Other',
    'Security test': 'SecurityTesting',
    'Line-of-business application': 'LineOfBusinessApplication',
    'Confirmed activity': 'ConfirmedActivity',
    'Not malicious': 'NotMalicious',
    'Not enough data to validate': '120'
}

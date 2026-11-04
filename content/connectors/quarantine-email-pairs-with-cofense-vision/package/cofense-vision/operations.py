"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""

import requests
import base64
from urllib.parse import urlencode
from requests.auth import HTTPBasicAuth
from connectors.core.connector import get_logger, ConnectorError
from .constants import *

logger = get_logger(LOGGER_NAME)


class CofenseVision:

    def __init__(self, config):
        self.config = config
        self.base_url = config.get('hostname', '').strip('/')
        if not self.base_url.startswith(('http://', 'https://')):
            self.base_url = f'https://{self.base_url}'
        self.verify_ssl = config.get('verify_ssl', True)
        self.timeout = 30
        self.auth_token = None

    # def encode_credentials(self, username, password):
    #     try:
    #         credentials = f"{username}:{password}"
    #         base64_string = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    #         logger.info('Credentials encoded successfully.')
    #         return base64_string
    #     except Exception as err:
    #         logger.error(f"Failed to encode credentials: {str(err)}")
    #         raise ConnectorError(str(err))

    def get_access_token(self):
        try:
            if self.auth_token:
                return self.auth_token

            url = f"{self.base_url}/uaa/oauth/token"

            client_id = self.config.get('username').strip()
            client_secret = self.config.get('password').strip()

            payload = urlencode({
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            })

            response = requests.post(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                verify=self.verify_ssl,
                timeout=self.timeout
            )

            if response.status_code in [200, 201]:
                self.auth_token = response.json().get('access_token')
                return self.auth_token

            raise ConnectorError(f"Failed: {response.text}")

        except Exception as err:
            raise ConnectorError(str(err))

    def get_search_results(self, search_id):
        try:
            access_token = self.get_access_token()
            url = f"{self.base_url}/api/v5/searches/{search_id}/results"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            response = requests.get(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)

            if response.status_code in [200, 201]:
                logger.info("Search results retrieved successfully.")
                results = response.json()
                filtered_results = []

                for item in results.get('messages', []):
                    sender_email = None
                    from_list = item.get('from')
                    if isinstance(from_list, list) and len(from_list) > 0:
                        sender_email = from_list[0].get('address')
                    recipients = [
                        r.get('address') for r in item.get('recipients', [])
                        if isinstance(r, dict) and r.get('address')
                    ]

                    filtered_results.append({
                        "Subject": item.get('subject'),
                        "InternetMessageID": item.get('internetMessageId'),
                        "SenderEmailAddress": sender_email,
                        "RecipientEmailAddresses": recipients
                    })

                return filtered_results
            else:
                logger.error(f"Failed to get search results: {response.text}")
                raise ConnectorError(f"Failed to get search results: {response.text}")
        except Exception as err:
            logger.error(f"Error in get_search_results: {str(err)}")
            raise ConnectorError(str(err))


def search_email(config, params):
    try:
        obj = CofenseVision(config)
        access_token = obj.get_access_token()
        url = f"{obj.base_url}/api/v5/searches"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        if not params.get('emailSubject') and not params.get('senderEmailAddress'):
            raise ConnectorError('Either "subjects" or "senders" must be provided.')

        payload = {

            'subjects': [s.strip() for s in params.get('emailSubject', '').split(',') if s.strip()],
            'senders': [s.strip() for s in params.get('senderEmailAddress', '').split(',') if s.strip()]
        }

        response = requests.post(url, headers=headers, json=payload, timeout=obj.timeout, verify=obj.verify_ssl)

        if response.status_code in [200, 201]:
            logger.info("Email search executed successfully.")
            search_id = response.json().get('id')
            return obj.get_search_results(search_id)
        else:
            logger.error(f"Failed to search email: {response.text}")
            raise ConnectorError(f"Failed to search email: {response.text}")

    except Exception as err:
        logger.error(f"Error in search_email: {str(err)}")
        raise ConnectorError(str(err))


def check_health(config):
    try:
        obj = CofenseVision(config)
        if obj.get_access_token():
            logger.info("Health check successful.")
            return True
        logger.error("Health check failed: No access token.")
        return False
    except Exception as err:
        logger.error(f"Health check failed: {str(err)}")
        raise ConnectorError(str(err))


def quarantine_email(config, params):
    try:
        obj = CofenseVision(config)
        access_token = obj.get_access_token()
        url = f"{obj.base_url}/api/v5/quarantineJobs"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        recipients = [s.strip() for s in params.get('recipientAddress', '').split(',') if s.strip()]
        message_id = params.get('internetMessageId')

        if not recipients or not message_id:
            raise ConnectorError('Both "recipientAddress" and "internetMessageId" are required parameters.')

        payload = {
            "quarantineEmails": [
                {"recipientAddress": r, "internetMessageId": message_id} for r in recipients
            ]
        }

        response = requests.post(url, headers=headers, json=payload, timeout=obj.timeout, verify=obj.verify_ssl)

        if response.status_code in [200, 201]:
            logger.info("Emails quarantined successfully.")
            return response.json()
        else:
            logger.error(f"Failed to quarantine emails: {response.text}")
            raise ConnectorError(f"Failed to quarantine emails: {response.text}")

    except Exception as err:
        logger.error(f"Error in quarantine_email: {str(err)}")
        raise ConnectorError(str(err))


def normalize_email_pairs(raw_input):
    # If already a list → return directly
    if isinstance(raw_input, list):
        return [item.strip() for item in raw_input if item]
    # Otherwise treat as string
    entries = []
    for item in raw_input.replace(',', '\n').split('\n'):
        item = item.strip()
        if item:
            entries.append(item)
    return entries


def quarantine_email_pairs(config, params):
    try:
        obj = CofenseVision(config)
        access_token = obj.get_access_token()
        url = f"{obj.base_url}/api/v5/quarantineJobs"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        raw_input = params.get("emailPairs")
        if not raw_input:
            raise ConnectorError('Parameter "emailPairs" is required.')
        entries = normalize_email_pairs(raw_input)
        quarantine_list = []
        for entry in entries:
            parts = entry.split(':', 1)
            if len(parts) != 2:
                raise ConnectorError(f'Invalid format: "{entry}"')
            quarantine_list.append({
                "internetMessageId": parts[0].strip(),
                "recipientAddress": parts[1].strip()
            })
        payload = {
            "quarantineEmails": quarantine_list
        }
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=obj.timeout,
            verify=obj.verify_ssl
        )
        if response.status_code in [200, 201]:
            logger.info("Emails quarantined successfully.")
            return response.json()
        else:
            logger.error(f"Failed to quarantine emails: {response.text}")
            raise ConnectorError(f"Failed to quarantine emails: {response.text}")
    except Exception as err:
        logger.error(f"Error in quarantine_email_pairs: {str(err)}")
        raise ConnectorError(str(err))


operations = {
    'search_email': search_email,
    'quarantine_email': quarantine_email,
    'quarantine_email_pairs': quarantine_email_pairs
}

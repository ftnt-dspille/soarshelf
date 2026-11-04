""" Copyright start
  Copyright (C) 2008 - 2026 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import requests
import json
from connectors.core.connector import get_logger, ConnectorError

logger = get_logger('proofpoint-email-gateway')

errors = {
    400: 'Invalid Argument/Invalid Time Range',
    401: 'Unauthorized - Invalid API key, secret, or missing authentication',
    402: 'Payment Required - Billing/Quota issue (rare)',
    403: 'Forbidden - Authentication succeeded but permission denied',
    404: 'Not Found - The resource or endpoint does not exist',
    405: 'Method Not Allowed - Incorrect HTTP method for this endpoint',
    429: 'Operation Lockout Error',
    500: 'Internal Server Error - Unexpected server issue',
    503: 'Maximum Requests Exceeded'
}

mapping = {
    "Release Message": {'action': "release"},
    "Resubmit Message": {'action': "resubmit"},
    "Forward Message": {'action': "forward"},
    "Move Message": {'action': "move"},
    "Delete Message": {'action': "delete"},
    "Number of Smart Identifiers": {'dlpviolation': "t"},
    "Actual Smart Identifiers": {'dlpviolation': "details"}
}


class ProofpointEmailGateway:
    def __init__(self, config, *args, **kwargs):
        self.api_key = config.get('api_key')
        self.secret = config.get('secret')
        server = config.get('server_url').strip('/')

        # Ensure URL format is correct
        if not server.startswith('http://') and not server.startswith('https://'):
            self.url = f"https://{server}/"
        else:
            server = server.rstrip('/')
            self.url = f"{server}/"

        # Get Bearer token
        token_response = get_token(self.api_key, self.secret, config.get('verify_ssl'))
        self.token = f"Bearer {token_response['access_token']}"
        self.ssl_verify = config.get('verify_ssl')

    def make_rest_call(self, endpoint, method, data=None, params=None, header=None):
        try:
            url = self.url + endpoint
            logger.debug(f"Endpoint URL: {url}")
            token_response = get_token(self.api_key, self.secret, self.ssl_verify)

            headers = {'Content-Type': 'application/json', "Authorization": f"Bearer {token_response['access_token']}"}

            response = requests.request(
                method,
                url,
                headers=headers,
                verify=self.ssl_verify,
                data=data,
                params=params
            )

            # This line is purely for testing to see what the response is
            # return f"{response}: {response.text} ---|---  {url} ---|--- {params} ---|--- {data}"

            if response.ok: 
                logger.info(f"Successful response for {url}")

                if not response.content:
                    return {
                        "status": "success",
                        "message": "Operation completed successfully."
                    }
                if "application/json" in response.headers.get("Content-Type", ""):
                    return response.json()

                return {
                    "response": response.text
                }

            error_msg = errors.get(response.status_code, response.text)
            logger.error(f"Error response from {url}: {error_msg}")
            raise ConnectorError(error_msg)

        except requests.exceptions.SSLError:
            raise ConnectorError('SSL certificate validation failed')
        except requests.exceptions.ConnectTimeout:
            raise ConnectorError(
                'Connection timed out while trying to reach the server')
        except requests.exceptions.ReadTimeout:
            raise ConnectorError(
                'The server did not send data in the allotted time')
        except requests.exceptions.ConnectionError:
            raise ConnectorError('Invalid endpoint or credentials')
        except Exception as err:
            raise ConnectorError(str(err))

    def build_payload(self, params):
        payload = {k: v for k, v in params.items() if v not in [None, '']}
        logger.debug(f"Query Parameters: {payload}")
        return payload


def get_token(api_key, secret, verify):
    token_url = "https://auth.proofpoint.com/v1/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret
    }
    response = requests.post(token_url, headers=headers, data=data, verify=verify)
    return response.json()


def search_quarantine_messages(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        params = params.copy()

        # Format dates
        if params.get('start_date'):
            params['start_date'] = params['start_date'][-1].replace('T', ' ')
        if params.get('end_date'):
            params['end_date'] = params['end_date'][-1].replace('T', ' ')

        # DLP mapping
        dlpviolation = params.get('dlpviolation')
        if dlpviolation and dlpviolation in mapping:
            params.update(mapping[dlpviolation])

        if params.get('messagestatus'):
            params['messagestatus'] = 't'

        endpoint = 'rest/v1/quarantine'
        payload = eg.build_payload(params)
        return eg.make_rest_call(endpoint, 'GET', params=payload)

    except Exception as err:
        logger.exception(f"Error searching quarantine messages: {err}")
        raise ConnectorError(f"Error searching quarantine messages: {err}")


def login(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        endpoint = 'rest/v1/quarantine'
        payload = eg.build_payload(params)
        return eg.make_rest_call(endpoint, 'GET', params=payload)
    except Exception as err:
        logger.exception(str(err))
        raise ConnectorError(str(err))


def quarantine_message_actions(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        params = params.copy()

        # Handle scan flag
        if params.get('scan'):
            params['scan'] = 't'
        else:
            params.pop('scan', None)

        # Map message action
        message = params.get('message')
        if message in mapping:
            params.update(mapping[message])
        params.pop('message', None)

        endpoint = 'rest/v1/quarantine'
        payload = eg.build_payload(params)
        return eg.make_rest_call(endpoint, 'POST', data=json.dumps(payload))

    except Exception as err:
        logger.exception(f"Error executing quarantine action: {err}")
        raise ConnectorError(f"Error executing quarantine action: {err}")


def get_organizational_block_list(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        endpoint = 'api/v1/emailProtection/modules/spam/orgBlockList'
        payload = eg.build_payload(params)
        return eg.make_rest_call(endpoint, 'GET', params=payload)
    except Exception as err:
        logger.exception(f"Error fetching organizational block list: {err}")
        raise ConnectorError(
            f"Error fetching organizational block list: {err}")


def add_remove_organizational_block_list(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        params = params.copy()

        cluster_id = params.pop('clusterId', None)
        endpoint = 'api/v1/emailProtection/modules/spam/orgBlockList'
        query_params = {'clusterId': cluster_id} if cluster_id else {}
        params['action'] = params.get('action').lower()
        payload = eg.build_payload(params)

        return eg.make_rest_call(endpoint, 'POST', params=query_params, data=json.dumps(payload))

    except Exception as err:
        logger.exception(f"Error modifying organizational block list: {err}")
        raise ConnectorError(
            f"Error modifying organizational block list: {err}")


def _check_health(config):
    try:
        get_token(config.get("api_key"), config.get("secret"), config.get("verify_ssl"))
        return True
    except Exception as err:
        logger.exception(f"Health check failed: {err}")
        raise ConnectorError(f"Health check failed: {err}")


def edit_custom_list(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        params = params.copy()
        # Required params
        cluster_id = params.pop('clusterID', None)
        list_id = params.pop('listID', None)
        if not list_id:
            raise ConnectorError("listId is required")
        if not cluster_id:
            raise ConnectorError("clusterId is required")
        # Endpoint (NO query string here)
        endpoint = f'api/v1/lists/{list_id}/entries'
        # Query params
        query_params = {
            "clusterId": cluster_id
        }
        add = params.get("add")
        delete = params.get("delete")

        if isinstance(add, str):
            add = [x.strip() for x in add.split(",") if x.strip()]
        elif add is None:
            add = []
        if isinstance(delete, str):
            delete = [x.strip() for x in delete.split(",") if x.strip()]
        elif delete is None:
            delete = []

        # Build payload EXACTLY as API expects
        payload = {
            "add": add,
            "delete": delete
        }
        return eg.make_rest_call(
            endpoint,
            'POST',
            params=query_params,
            data=json.dumps(payload)
        )
    except Exception as err:
        logger.exception(f"Error modifying custom list: {err}")
        raise ConnectorError(f"Error modifying custom list: {err}")


def get_custom_list_entries(config, params):
    try:
        eg = ProofpointEmailGateway(config)
        params = params.copy()
        # Required params
        list_id = params.get("listID")
        cluster_id = params.get("clusterID")
        if not list_id:
            raise ConnectorError("listId is required")
        if not cluster_id:
            raise ConnectorError("clusterId is required") 
        # Endpoint (no query string here)
        endpoint = f'api/v1/lists/{list_id}'
        # Query params
        query_params = {
            "clusterId": cluster_id
        }
        response = eg.make_rest_call(
            endpoint,
            'GET',
            params=query_params
        )
        # Optional: normalize output
        return {
            "entries": response.get("entries", [])
        }
    except Exception as err:
        logger.exception(f"Error fetching custom list entries: {err}")
        raise ConnectorError(f"Error fetching custom list entries: {err}")


operations = {
    'search_quarantine_messages': search_quarantine_messages,
    'quarantine_message_actions': quarantine_message_actions,
    'get_organizational_block_list': get_organizational_block_list,
    'add_remove_organizational_block_list': add_remove_organizational_block_list,
    'edit_custom_list': edit_custom_list,
    'get_custom_list_entries': get_custom_list_entries
}

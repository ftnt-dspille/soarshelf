""" Copyright start
  Copyright (C) 2008 - 2024 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import get_logger, ConnectorError
from requests import exceptions as req_exceptions
from time import sleep
from .microsoft_api_auth import *
from .constant import *
import json

logger = get_logger('microsoft-365-defender')


def api_request(method, endpoint, connector_info, config, params=None, data=None, json=None, headers={}, link=None):
    try:
        ms = MicrosoftAuth(config)
        if not link:
            endpoint = ms.host + endpoint
        token = ms.validate_token(config, connector_info)
        headers['Authorization'] = token
        headers['Content-Type'] = 'application/json'
        headers['consistencylevel'] = 'eventual'

        retries = 0
        max_retries = 10
        retry_delay = 10

        while retries < max_retries:
            try:
                response = request(method, endpoint, headers=headers, params=params, data=data, json=json,
                                   verify=ms.verify_ssl)
                if response.status_code == 429:
                    retries += 1
                    logger.warn(f'Failed to connect URL: {endpoint} with status code 429. Retrying in {retry_delay} seconds.')
                    sleep(retry_delay)
                    logger.debug(f'Retry count: {retries}')
                    continue
                if response.status_code in [200, 201, 204]:
                    if response.text != "":
                        return response.json()
                    else:
                        return True
                elif response.status_code == 404:
                    return response
                else:
                    if response.text != "":
                        err_resp = response.json()
                        failure_msg = err_resp['error']['message']
                        error_msg = 'Response [{0}:{1} Details: {2}]'.format(response.status_code, response.reason,
                                                                             failure_msg if failure_msg else '')
                    else:
                        error_msg = 'Response [{0}:{1}]'.format(response.status_code, response.reason)
                    logger.error(error_msg)
                    raise ConnectorError(error_msg)
            except req_exceptions.SSLError:
                logger.error('An SSL error occurred')
                raise ConnectorError('An SSL error occurred')
            except req_exceptions.ConnectionError:
                logger.error('A connection error occurred')
                raise ConnectorError('A connection error occurred')
            except req_exceptions.Timeout:
                logger.error('The request timed out')
                raise ConnectorError('The request timed out')
            except req_exceptions.RequestException as e:
                logger.error(f'Request exception occurred: {e}')
                raise ConnectorError('There was an error while handling the request')
            except Exception as err:
                raise ConnectorError(str(err))
        logger.error(f'Failed after {retries} retries to connect to endpoint {endpoint}')
        raise ConnectorError(f'Failed after {retries} retries to connect to endpoint {endpoint}')
    except Exception as err:
        raise ConnectorError(str(err))


def check_payload(payload):
    updated_payload = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = check_payload(value)
            if len(nested.keys()) > 0:
                updated_payload[key] = nested
        elif value:
            updated_payload[key] = value
    return updated_payload


def convert_date_time(ts):
    try:
        ts = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%dT%H:%M:%SZ')
        return ts
    except Exception as err:
        logger.error("Convert Date {0}".format(str(err)))
        raise ConnectorError(str(err))


def list_incidents(config, params, connector_info):
    get_all_records = params.pop('get_all_records', None)
    filter_params = {
        'lastUpdateTime': convert_date_time(params.get('lastUpdateTime')) if params.get('lastUpdateTime') else '',
        'createdTime': convert_date_time(params.get('createdTime')) if params.get('createdTime') else '',
        'assignedTo': params.get('assignedTo')
    }

    status_values = params.get('status', []) if params.get('status') else []
    if isinstance(status_values, list):
        status_filter = ' or '.join([f"status eq '{STATUS.get(status)}'" for status in status_values])
    else:
        status_filter = f"status eq '{STATUS.get(status_values)}'"

    filter_params = {k: v for k, v in filter_params.items() if v is not None and v != ''}
    filter_str = [f"{key} ge {value}" if key.endswith('Time') else f"{key} eq '{value}'" for key, value in
                  filter_params.items()]

    if status_filter:
        filter_str.append(f"({status_filter})")

    if params.get('query'):
        filter_str.append(params.get('query'))

    filter_str = ' and '.join(filter_str)

    logger.debug("Checking the Query String: {0}".format(filter_str))

    if get_all_records:
        params['skip'] = ''
        params['top'] = ''

    payload = {
        '$filter': filter_str,
        '$skip': params.get('skip'),
        '$top': params.get('top')
    }

    payload = check_payload(payload)
    logger.debug("Checking the Payload: {0}".format(payload))

    response = api_request("GET", INCIDENT, connector_info, config, params=payload)

    if get_all_records:
        return fetch_all_records(response, connector_info, config)

    return response


def fetch_all_records(response, connector_info, config):
    result = response
    while '@odata.nextLink' in response:
        response = api_request("GET", response.get('@odata.nextLink'), connector_info, config, link=True)
        result['value'].extend(response['value'])
    return result


def advanced_hunting(config, params, connector_info):
    payload = {
        'Query': params.get('Query')
    }
    payload = check_payload(payload)
    logger.debug("Checking the Payload:{0}".format(payload))
    response = api_request("POST", ADVANCE_HUNTING, connector_info, config, data=json.dumps(payload))
    return response


def get_incident(config, params, connector_info):
    url = "{0}{1}".format(INCIDENT, params.get('id'))
    response = api_request("GET", url, connector_info, config)
    return response


def update_incident(config, params, connector_info):
    url = "{0}{1}".format(INCIDENT, params.get('id'))
    tags = params.get('tags')
    if tags:
        tags = tags.split(",")
    payload = {
        'status': STATUS.get(params.get('status')) if params.get(
            'status') else '',
        'assignedTo': params.get('assignedTo'),
        'classification': CLASSIFICATION.get(params.get('classification')) if params.get(
            'classification') else '',
        'tags': tags,
        'determination': DETERMINATION.get(params.get('determination')) if params.get(
            'determination') else '',
        'comment': params.get('comment')
    }
    payload = check_payload(payload)
    logger.debug("Checking the Payload:{0}".format(payload))
    response = api_request("PATCH", url, connector_info, config, data=json.dumps(payload))
    return response


def _check_health(config, connector_info):
    if check(config, connector_info) and list_incidents(config, params={}, connector_info=connector_info):
        return True


operations = {
    'list_incidents': list_incidents,
    'get_incident': get_incident,
    'update_incident': update_incident,
    'advanced_hunting': advanced_hunting
}

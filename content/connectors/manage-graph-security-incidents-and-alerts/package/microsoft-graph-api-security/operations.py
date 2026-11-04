""" Copyright start
  Copyright (C) 2008 - 2024 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from connectors.core.connector import get_logger, ConnectorError
from requests import exceptions as req_exceptions
from time import sleep
from .microsoft_api_auth import MicrosoftAuth, check
from .constant import (
    INCIDENT,
    STATUS,
    CLASSIFICATION,
    DETERMINATION,
    ADVANCED_HUNTING,
    TIMESPAN,
    ALERT
    )
import json

logger = get_logger('microsoft-graph-api-security')


def api_request(method, endpoint, connector_info, config, params=None, data=None, json=None, headers={}, link=None):
    try:
        ms = MicrosoftAuth(config) 
        session = ms.get_session(
            config,
            connector_info
        )

        if not link:
            endpoint = ms.host + endpoint
        if params:
            if "$count" in params or "$search" in params:
                session.headers["ConsistencyLevel"] = "eventual"

        if data is not None or json is not None:
            session.headers["Content-Type"] = "application/json"

        retries = 0
        max_retries = 10
        retry_delay = 10

        while retries < max_retries:
            try:
                response = session.request(
                    method,
                    endpoint,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    verify=ms.verify_ssl
                )
                if response.status_code == 429:
                    retries += 1
                    logger.warning(f'Failed to connect URL: {endpoint} with status code 429. Retrying in {retry_delay} seconds.')
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
                    logger.error(
                        "Microsoft Graph request failed | "
                        "Method=%s | URL=%s | Params=%s | Status=%s | Response=%s",
                        method,
                        response.url,
                        params,
                        response.status_code,
                        response.text
                    )
                    try:
                        err_resp = response.json()
                        graph_error = err_resp.get("error", {})
                        failure_msg = graph_error.get("message", response.text)
                        error_code = graph_error.get("code", "Unknown")
                    except ValueError:
                        failure_msg = response.text
                        error_code = "NonJSONResponse"

                    error_msg = (
                        "Microsoft Graph Error | "
                        "Status={0} | Code={1} | Message={2}"
                    ).format(
                        response.status_code,
                        error_code,
                        failure_msg
                    )

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


def get_security_incidents(config, params, connector_info):
    """
    Get Microsoft Graph Security Incidents
    """

    requested_top = params.get("top")
    get_all_records = params.get("getAllRecords", False)

    query_params = {
        "$skip": params.get("skip"),
        "$filter": params.get("filter"),
        "$orderby": params.get("orderBy")
    }

    # Only use $top when GET ALL RECORDS is NOT selected.
    if requested_top:
        query_params["$top"] = min(int(requested_top), 50)

    # Only include count if explicitly requested.
    if params.get("includeCount"):
        query_params["$count"] = "true"

    if params.get("expandAlerts"):
        query_params["$expand"] = "alerts"

    query_params = check_payload(query_params)

    logger.error(
        "Get Security Incidents | params=%s | query_params=%s",
        params,
        query_params
    )
    logger.debug(
        "Get Security Incidents Query Parameters: {}".format(query_params)
    )
    response = api_request(
        "GET",
        INCIDENT,
        connector_info,
        config,
        params=query_params
    )
    if get_all_records:
        return fetch_all_records(
            response,
            connector_info,
            config
        )

    return response


def fetch_all_records(response, connector_info, config):
    """
    Fetch all Microsoft Graph Security Incidents
    by following @odata.nextLink.
    """

    result = dict(response)
    result["value"] = list(response.get("value", []))

    next_link = response.get("@odata.nextLink")
    seen_links = set()

    while next_link:
        if next_link in seen_links:
            logger.error("Pagination loop detected. Repeated nectLink: %s", next_link)

            break

        seen_links.add(next_link)

        logger.info("Fetching next page: %s", len(seen_links) + 1)

        response = api_request(
            "GET",
            next_link,
            connector_info,
            config,
            link=True
        )

        records = response.get("value", [])

        logger.debug(
            "Fetched {} records".format(len(records))
        )
        result["value"].extend(records)
        next_link = response.get("@odata.nextLink")

    logger.debug(
        "Total records fetched: {}".format(
            len(result["value"])
        )
    )

    result.pop("@odata.nextLink", None)

    return result


def get_security_alerts(config, params, connector_info):
    """
    Get Microsoft Graph Security Alerts (alerts_v2)
    """
    get_all_records = params.get("getAllRecords", False)
    query_params = {
        "$top": params.get("top"),
        "$skip": params.get("skip"),
        "$filter": params.get("filter")
    }

    if params.get("includeCount"):
        query_params["$count"] = "true"

    query_params = check_payload(query_params)
    logger.debug(
        "Get Security Alerts Query Parameters: {}".format(query_params)
    )
    response = api_request(
        "GET",
        ALERT,
        connector_info,
        config,
        params=query_params
    )

    if get_all_records:
        return fetch_all_records(response, connector_info, config)
    return response


def get_security_alert(config, params, connector_info):
    """
    Get Microsoft Graph Security Alert (alerts_v2)
    """
    endpoint = "{}/{}".format(
        ALERT,
        params.get("alertID")
    )

    response = api_request(
        "GET",
        endpoint,
        connector_info,
        config
    )

    return response


def run_advanced_hunting(config, params, connector_info):
    """
    Execute Microsoft Graph Advanced Hunting Query
    """
    payload = {
        "Query": params.get("query"),
        "Timespan": TIMESPAN.get(params.get("timespan"))
    }

    payload = check_payload(payload)

    logger.debug(
        "Advanced Hunting Payload: {}".format(payload)
    )
    response = api_request(
        "POST",
        ADVANCED_HUNTING,
        connector_info,
        config,
        data=json.dumps(payload)
    )

    return response


def update_security_incident(config, params, connector_info):
    """
    Update Microsoft Graph Security Incident
    """
    endpoint = "{}/{}".format(
        INCIDENT,
        params.get("incidentID")
    )
    custom_tags = None
    if params.get("customTags"):
        custom_tags = [
            tag.strip()
            for tag in params.get("customTags").split(",")
            if tag.strip()
        ]
    payload = {
        "status": STATUS.get(params.get("status")),
        "assignedTo": params.get("assignedTo"),
        "classification": CLASSIFICATION.get(params.get("classification")),
        "determination": DETERMINATION.get(params.get("determination")),
        "resolvingComment": params.get("resolvingComment"),
        "customTags": custom_tags
    }
    payload = check_payload(payload)
    logger.debug(
        "Update Security Incident Payload: {}".format(payload)
    )
    response = api_request(
        "PATCH",
        endpoint,
        connector_info,
        config,
        data=json.dumps(payload)
    )
    return response


def update_security_alert(config, params, connector_info):
    """
    Update Microsoft Graph Security Alert (alerts_v2)
    """
    endpoint = "{}/{}".format(
        ALERT,
        params.get("alertID")
    )

    payload = {
        "assignedTo": params.get("assignedTo"),
        "classification": CLASSIFICATION.get(params.get("classification")),
        "determination": DETERMINATION.get(params.get("determination")),
        "status": STATUS.get(params.get("status"))
    }

    payload = check_payload(payload)

    logger.debug(
        "Update Security Alert Payload: {}".format(payload)
    )

    response = api_request(
        "PATCH",
        endpoint,
        connector_info,
        config,
        data=json.dumps(payload)
    )

    return response


def _check_health(config, connector_info):
    if check(config, connector_info):
        response = get_security_incidents(
            config,
            {"top": 1},
            connector_info=connector_info
        )

        if response:
            return True
    return False


operations = {
    "get_security_incidents": get_security_incidents,
    "get_security_alert": get_security_alert,
    "get_security_alerts": get_security_alerts,
    "update_security_incident": update_security_incident,
    "run_advanced_hunting": run_advanced_hunting
}

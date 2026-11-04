""" Copyright start
  Copyright (C) 2008 - 2022 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from .cofense_api_auth import *
from connectors.core.connector import get_logger, ConnectorError
from connectors.cyops_utilities.builtins import upload_file_to_cyops
import requests, json, os
from django.conf import settings

logger = get_logger('cofense-triage')

errors = {
    401: 'Unauthorized',
    404: 'Invalid Path or Method',
    422: 'Invalid Parameter'
}


def make_rest_call(endpoint, method, connector_info, config, data=None, params=None):
    try:
        co = CofenseAuth(config)
        url = co.host + endpoint
        token = co.validate_token(config, connector_info)
        logger.debug("Token: {0}".format(token))
        logger.debug("Endpoint URL: {0}".format(url))
        headers = {'Content-Type': 'application/json', 'Authorization': token}
        logger.debug("Headers: {0}".format(headers))
        response = requests.request(method, url, headers=headers, verify=co.verify_ssl, data=data, params=params)
        logger.debug("Response: {0}".format(response))
        if response.ok or response.status_code == 204:
            logger.info('Successfully got response for url {0}'.format(url))
            if 'json' in str(response.headers):
                return response.json()
            else:
                return response.content
        else:
            raise ConnectorError("{}".format(errors.get(response.status_code)))
    except requests.exceptions.SSLError:
        raise ConnectorError('SSL certificate validation failed')
    except requests.exceptions.ConnectTimeout:
        raise ConnectorError('The request timed out while trying to connect to the server')
    except requests.exceptions.ReadTimeout:
        raise ConnectorError(
            'The server did not send any data in the allotted amount of time')
    except requests.exceptions.ConnectionError:
        raise ConnectorError('Invalid endpoint or credentials')
    except Exception as err:
        raise ConnectorError(str(err))


def build_payload(params):
    payload = {k: v for k, v in params.items() if v is not None and v != ''}
    logger.debug("Query Parameters: {0}".format(payload))
    return payload


def _check_health(config, connector_info):
    try:
        return check(config, connector_info)
    except Exception as err:
        raise ConnectorError('Invalid URL or Credentials')


def retrieve_fields(fields):
    fields = ",".join([x.strip() for x in fields.split(",") if x.strip()])
    return fields


def filter_fields(filter_by, payload):
    for key, value in filter_by.items():
        if key and value:
            payload.update({'filter[{0}]'.format(key): value})
    return payload


def get_clusters(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/clusters"
        sort = params.get('sort_by')
        if sort:
            sort = retrieve_fields(sort)
        tags = params.get('tags')
        if tags:
            tags = retrieve_fields(tags)
        fields_to_retrieve = params.get('fields_to_retrieve')
        if fields_to_retrieve:
            fields_to_retrieve = retrieve_fields(fields_to_retrieve)
        payload = {
            'page[size]': params.get('page_size'),
            'page[number]': params.get('page_number'),
            'sort': sort,
            'fields[clusters]': fields_to_retrieve,
            'filter[created_at_gteq]': params.get('created_at'),
            'filter[updated_at_gteq]': params.get('updated_at'),
            'filter[match_priority]': params.get('match_priority'),
            'filter[total_reports_count]': params.get('total_reports_count'),
            'filter[tags_any]': tags
        }
        filter_by = params.get('filter_by')
        if filter_by:
            payload = filter_fields(filter_by, payload)
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_cluster_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/clusters/{0}".format(params.get("cluster_id"))
        response = make_rest_call(endpoint, 'GET', connector_info, config)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_reports(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/reports"
        sort = params.get('sort_by')
        if sort:
            sort = retrieve_fields(sort)
        tags = params.get('tags')
        if tags:
            tags = retrieve_fields(tags)
        categorization_tags = params.get('categorization_tags')
        if categorization_tags:
            categorization_tags = retrieve_fields(categorization_tags)
        location = params.get('report_location')
        if location:
            location = retrieve_fields(location)
        fields_to_retrieve = params.get('fields_to_retrieve')
        if fields_to_retrieve:
            fields_to_retrieve = retrieve_fields(fields_to_retrieve)
        payload = {
            'page[size]': params.get('page_size'),
            'page[number]': params.get('page_number'),
            'sort': sort,
            'fields[reports]': fields_to_retrieve,
            'filter[created_at_gteq]': params.get('created_at'),
            'filter[updated_at_gteq]': params.get('updated_at'),
            'filter[match_priority]': params.get('match_priority'),
            'filter[location]': location,
            'filter[categorization_tags_any]': categorization_tags,
            'filter[tags_any]': tags
        }
        filter_by = params.get('filter_by')
        if filter_by:
            payload = filter_fields(filter_by, payload)
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_reports_by_category_id(config, params, connector_info):
    try:
        categoryID = int(params.get('categoryID') or 7)
        endpoint = "/api/public/v2/categories/{0}/reports".format(categoryID)
        limit = int(params.get('limit') or 10)
        payload = {
            'page[size]': limit,
            'filter[updated_at_gteq]': params.get('updatedAt'),
            'filter[location]': 'processed'
        }
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug(f"type(make_rest_call): {type(make_rest_call)}")
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_report_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/reports/{0}".format(params.get("report_id"))
        response = make_rest_call(endpoint, 'GET', connector_info, config)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_inbox_reports(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/reports"
        sort = params.get('sort_by')
        if sort:
            sort = retrieve_fields(sort)
        tags = params.get('tags')
        if tags:
            tags = retrieve_fields(tags)
        categorization_tags = params.get('categorization_tags')
        if categorization_tags:
            categorization_tags = retrieve_fields(categorization_tags)
        fields_to_retrieve = params.get('fields_to_retrieve')
        if fields_to_retrieve:
            fields_to_retrieve = retrieve_fields(fields_to_retrieve)
        payload = {
            'page[size]': params.get('page_size'),
            'page[number]': params.get('page_number'),
            'sort': sort,
            'fields[reports]': fields_to_retrieve,
            'filter[created_at_gteq]': params.get('created_at'),
            'filter[updated_at_gteq]': params.get('updated_at'),
            'filter[match_priority]': params.get('match_priority'),
            'filter[location]': 'inbox',
            'filter[categorization_tags_any]': categorization_tags,
            'filter[tags_any]': tags
        }
        filter_by = params.get('filter_by')
        if filter_by:
            payload = filter_fields(filter_by, payload)
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_report_reporters_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/reporters"
        sort = params.get('sort_by')
        if sort:
            sort = retrieve_fields(sort)
        fields_to_retrieve = params.get('fields_to_retrieve')
        if fields_to_retrieve:
            fields_to_retrieve = retrieve_fields(fields_to_retrieve)
        payload = {
            'page[size]': params.get('page_size'),
            'page[number]': params.get('page_number'),
            'sort': sort,
            'fields[reporters]': fields_to_retrieve,
            'filter[created_at_gteq]': params.get('created_at'),
            'filter[updated_at_gteq]': params.get('updated_at'),
            'filter[reputation_score]': params.get('reputation_score'),
            'filter[vip]': params.get('vip'),
            'filter[email]': params.get('email')
        }
        filter_by = params.get('filter_by')
        if filter_by:
            payload = filter_fields(filter_by, payload)
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_attachment_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/attachments/{0}".format(params.get("attachment_id"))
        response = make_rest_call(endpoint, 'GET', connector_info, config)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_triage_threat_indicators(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/threat_indicators"
        sort = params.get('sort_by')
        if sort:
            sort = retrieve_fields(sort)
        fields_to_retrieve = params.get('fields_to_retrieve')
        if fields_to_retrieve:
            fields_to_retrieve = retrieve_fields(fields_to_retrieve)
        payload = {
            'page[size]': params.get('page_size'),
            'page[number]': params.get('page_number'),
            'sort': sort,
            'fields[threat_indicators]': fields_to_retrieve,
            'filter[created_at_gteq]': params.get('created_at'),
            'filter[updated_at_gteq]': params.get('updated_at'),
            'filter[threat_level]': params.get('threat_level'),
            'filter[threat_type]': params.get('threat_type'),
            'filter[threat_value]': params.get('threat_value'),
            'filter[threat_source]': params.get('threat_source')
        }
        filter_by = params.get('filter_by')
        if filter_by:
            payload = filter_fields(filter_by, payload)
        payload = build_payload(payload)
        logger.debug("Payload: {0}".format(payload))
        response = make_rest_call(endpoint, 'GET', connector_info, config, params=payload)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_url_details(config, params, connector_info):
    try:
        value = '/api/public/v2/'
        url = params.get('endpoint').split(value)
        endpoint = value + url[-1]
        method = params.get('method')
        body = params.get('body')
        if method == 'GET':
            response = make_rest_call(endpoint, 'GET', connector_info, config, params=body)
        if method == 'POST':
            response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(body))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def download_report(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/reports/{0}/download".format(params.get('id'))
        response, file_name = make_rest_call(endpoint, 'POST', connector_info, config)
        logger.debug("API response: {0}".format(response))
        if response:
            path = os.path.join(settings.TMP_FILE_ROOT, file_name)
            logger.debug("Path: {0}".format(path))
            with open(path, 'wb') as fp:
                fp.write(response)
            attach_response = upload_file_to_cyops(file_path=file_name, filename=file_name,
                                                   name=file_name, create_attachment=True)
            return attach_response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def download_attachment(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/attachments/{0}/download".format(params.get('id'))
        response, file_name = make_rest_call(endpoint, 'POST', connector_info, config)
        logger.debug("API response: {0}".format(response))
        if response:
            path = os.path.join(settings.TMP_FILE_ROOT, file_name)
            logger.debug("Path: {0}".format(path))
            with open(path, 'wb') as fp:
                fp.write(response)
            attach_response = upload_file_to_cyops(file_path=file_name, filename=file_name,
                                                   name=file_name, create_attachment=True)
            return attach_response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_domain_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/domains/{0}".format(params.get("domain_id"))
        response = make_rest_call(endpoint, 'GET', connector_info, config)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_hostname_details(config, params, connector_info):
    try:
        endpoint = "/api/public/v2/hostnames/{0}".format(params.get("hostname_id"))
        response = make_rest_call(endpoint, 'GET', connector_info, config)
        logger.debug("Response: {0}".format(response))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


operations = {
    'get_clusters': get_clusters,
    'get_cluster_details': get_cluster_details,
    'get_reports': get_reports,
    'get_report_details': get_report_details,
    'get_inbox_reports': get_inbox_reports,
    'get_report_reporters_details': get_report_reporters_details,
    'get_attachment_details': get_attachment_details,
    'get_triage_threat_indicators': get_triage_threat_indicators,
    'get_url_details': get_url_details,
    'download_report': download_report,
    'download_attachment': download_attachment,
    'get_domain_details': get_domain_details,
    'get_hostname_details': get_hostname_details,
    'get_reports_by_category_id': get_reports_by_category_id
}

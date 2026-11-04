""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import requests
import json
from elasticsearch import Elasticsearch, ElasticsearchException
from connectors.core.connector import get_logger, ConnectorError
from .utils import MyConnection
from elasticsearch_dsl import Search, Q

logger = get_logger('elasticsearch_cs')


def get_config(config):
    try:
        if config is not None:
            hostname = config.get('server_url')
            protocol = config.get('protocol')
            username = config.get('username')
            password = config.get('password')
            api_key = config.get('api_key')
            port = config.get('port')
            max_retries = config.get('max_retries') if config.get('max_retries') else 0
            verify_ssl = config.get('verify_ssl')
            return hostname, protocol, username, password, api_key, port, max_retries, verify_ssl
    except Exception as Err:
        logger.warn('Error occured while extracting conf :[{0}] '.format(Err))
        raise ConnectorError(Err)


def make_api_call(config, port, method, endpoint=None, json=None, params=None, data=None, files=None):
    hostname, protocol, username, password, api_key, config_port, max_retries, verify_ssl = get_config(config)
    headers = {}
    if method.upper() != "GET":
        headers = {'Content-Type': 'application/json'}
    if "http://" in hostname or "https://" in hostname:
        hostname = hostname.split("://")[1]
    # port = "5601"
    if ":" in hostname:
        hostname_split = hostname.split(":")
        hostname = hostname_split[0]
        port = hostname_split[1]
    if config.get('authentication_type') == "Basic Authentication":
        headers['kbn-xsrf'] = 'true'
        auth = (username, password)
        if endpoint:
            url = '{0}://{1}:{2}/{3}'.format(protocol, hostname, port, endpoint)
        else:
            url = '{0}://{1}:{2}'.format(protocol, hostname, port)
    elif config.get('authentication_type') == "API Key Authentication":
        headers['Authorization'] = api_key
        auth = None
        if endpoint:
            url = '{0}://{1}/{2}'.format(protocol, hostname, endpoint)
        else:
            url = '{0}://{1}'.format(protocol, hostname)

    logger.info('Request URL {}'.format(url))
    try:
        response = requests.request(method=method, url=url, auth=auth, headers=headers, json=json,
                                        params=params, data=data, verify=verify_ssl)

        if response.ok:
            return response.json()
        elif response.status_code == 401:
            logger.info('Unauthorized: Invalid credentials')
            raise ConnectorError('Unauthorized: Invalid credentials')
        else:
            logger.info(
                'Fail To request API {0} response is : {1} with reason: {2}'.format(str(url), str(response.content),
                                                                                    str(response.reason)))
            raise ConnectorError(
                'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                                   str(response.reason)))
    except requests.exceptions.SSLError as Err:
        logger.exception('{}'.format(Err))
        raise ConnectorError('{}'.format('SSL certificate validation failed'))
    except requests.exceptions.ConnectionError as Err:
        logger.exception('{}'.format(Err))
        raise ConnectorError('{}'.format('The request timed out while trying to connect to the remote server'))
    except Exception as Err:
        logger.exception('{}'.format(Err))
        raise ConnectorError('{}'.format(Err))


def build_payload(params):
    result = {k: v for k, v in params.items() if v is not None and v != ''}
    return result


def elasticsearch_object(config, extra_headers):
    hostname, protocol, username, password, api_key, port, max_retries, verify_ssl = get_config(config)
    if "http://" in hostname or "https://" in hostname:
        hostname = hostname.split("://")[1]
    # port = "9200"
    use_ssl = False
    if protocol == 'https':
        use_ssl = True
    if ":" in hostname:
        hostname_split = hostname.split(":")
        hostname = hostname_split[0]
        port = hostname_split[1]
    if not port or port == '':
        port = 9200
    try:
        es = Elasticsearch(["{0}://{1}:{2}".format(protocol, hostname, port)], connection_class=MyConnection,
                           http_auth=(username, password), extra_headers=extra_headers, timeout=30,
                           max_retries=max_retries, retry_on_timeout=True,
                           use_ssl=use_ssl, verify_certs=verify_ssl)
        return es
    except Exception as Err:
        logger.exception('Exception occurred {}'.format(Err))
        raise ConnectorError('Exception occurred {}'.format(Err))


def execute_query(config, params, **kwargs):
    try:
        query = params.get('query', '')
        index = params.get('index', '')
        size = int(params.get('size') or 10)
        doc_type = params.get('doc_type', None)
        routing = params.get('routing', None)
        run_as_user = params.get('run_as_user', None)
        if run_as_user:
            extra_headers = {"es-security-runas-user": run_as_user}
        else:
            extra_headers = {}
        es = elasticsearch_object(config, extra_headers=extra_headers)
        search_kwargs = {'index': index, 'size': size}
        if params.get('lucene'):
            search_kwargs['q'] = query
        else:
            search_kwargs['body'] = query
        logger.info("Connected to ElasticSearch:\n{0}".format(es.info()))

        if doc_type:
            search_kwargs.update({"doc_type": doc_type})
        if routing:
            search_kwargs.update({"routing": routing})
        search_results = es.search(**search_kwargs, ignore_unavailable=True)
        return search_results
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def execute_lucene_query(config, params, **kwargs):
    try:
        query = params.get('query')
        index = params.get('index', '')
        size = int(params.get('size') or 10)
        run_as_user = params.get('run_as_user', None)
        params = {"query": query, "index": index, "run_as_user": run_as_user, "lucene": True, 'size': size}
        return execute_query(config, params)
    except ConnectorError as e:
        error_details = {"error": {"query": query,
                                   "error_details": {"error": e.error, "info": e.info, "status_code": e.status_code}}}
        logger.error("Error executing lucene search query\n{0}".format(error_details))
        raise ConnectorError(str(error_details))


def fetch_incidents(config, params, **kwargs):
    try:
        es = elasticsearch_object(config, extra_headers={})
        INDEX = params.get('index')
        FETCH_QUERY = params.get('fetchQuery')
        FETCH_SIZE = params.get('fetchSize', 50)
        TIME_FIELD = '@timestamp'
        PULL_TIME = params.get('pullTime')

        search = Search(using=es, index=INDEX)

        # Only fetch records newer than the last pull time
        if PULL_TIME:
            search = search.filter(
                "range",
                **{TIME_FIELD: {"gt": PULL_TIME}}
            )
        # Ignore documents that don't have the timestamp field
        search = search.filter(
            "exists",
            field=TIME_FIELD
        )
        # Apply the user's query only if one was provided
        if FETCH_QUERY:
            search = search.query(
                "query_string",
                query=FETCH_QUERY
            )
        # Sort oldest to newest and limit the number of results
        search = search.sort(
            {TIME_FIELD: {"order": "asc"}}
        )[:FETCH_SIZE]
        logger.debug("SEARCH: {}".format(search.to_dict()))

        try:
            search_results = search.execute().to_dict()
            logger.debug("SEARCH RESULTS: {}".format(search_results))
        except ElasticsearchException:
            search_results = es.search(
                index=search._index,
                body=search.to_dict(),
                **search._params
            )

        return search_results

    except ElasticsearchException as err:
        logger.error(f"Exception occurred: {err}")
        raise ConnectorError(err)


def get_mapping(config, params, **kwargs):
    try:
        index = params.get('index', "_all")
        doc_type = params.get('doc_type', "_all")
        run_as_user = params.get('run_as_user', None)
        if run_as_user:
            extra_headers = {"es-security-runas-user": run_as_user}
        else:
            extra_headers = {}
        es = elasticsearch_object(config, extra_headers=extra_headers)
        request_params = {"index": index, "doc_type": doc_type}
        results = es.indices.get_mapping(**request_params)
        return {"mapping": results}
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def get_cluster_details(config, params, **kwargs):
    try:
        index = params.get('index', "_all")
        run_as_user = params.get('run_as_user', None)
        if run_as_user:
            extra_headers = {"es-security-runas-user": run_as_user}
        else:
            extra_headers = {}
        es = elasticsearch_object(config, extra_headers=extra_headers)

        request_params = {"index": index}
        es.search(ignore_unavailable=True)
        results = es.cluster.state(**request_params)
        return {"cluster_details": results}
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def get_saved_search(config, params, **kwargs):
    try:
        return make_api_call(config, port=params.pop('port') if params.get('port') else 5601, method='get',
                             endpoint='api/saved_objects/search/{}'.format(params.get('object_id')))
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def get_alerts_list(config, params, **kwargs):
    try:
        params = build_payload(params)
        aggregate = {"aggs": {"latest": {"max": {"field": "@timestamp"}},"oldest": {"min": {"field": "@timestamp"}}}}
        if params.get('start') and params.get('end'):
            aggregate['aggs']['latest']['max']['field'] = params.get('end')
            aggregate['aggs']['oldest']['min']['field'] = params.get('start')
        if params.get('size'):
            params.update({'size': params.get('size')})
        return make_api_call(config, port=params.pop('port') if params.get('port') else 5601, method='post',
                             endpoint='api/detection_engine/signals/search', data=json.dumps(params))
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def set_alert_status(config, params, **kwargs):
    try:
        params = build_payload(params)
        if params.get('signal_ids'):
            if not isinstance(params.get('signal_ids'), list):
               alerts_ids = [x.strip() for x in params.get('signal_ids').split(',')]
               params.update({"signal_ids": alerts_ids})
            else:
               params.update({"signal_ids": params.get('signal_ids')})
        return make_api_call(config, port=params.pop('port') if params.get('port') else 5601, method='post',
                             endpoint='api/detection_engine/signals/status', data=json.dumps(params))
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def apply_alert_tags(config, params, **kwargs):
    try:
        params = build_payload(params)
        tags = {"tags": {}}
        if not isinstance(params.get('ids'), list):
            alerts_ids = [x.strip() for x in params.get('ids').split(',')]
            params.update({"ids": alerts_ids})
        else:
            params.update({"ids": params.get('ids')})
        if params.get("tags_to_add") or params.get("tags_to_remove"):
            tags.get('tags').update({"tags_to_add": [params.get("tags_to_add")] if params.get("tags_to_add") else [],
                                       "tags_to_remove": [params.get("tags_to_remove")] if params.get("tags_to_remove") else []})
            params.update(tags)
            if params.get('tags_to_add'):
               params.pop('tags_to_add')
            if params.get('tags_to_remove'):
               params.pop('tags_to_remove')
        return make_api_call(config, port=params.pop('port') if params.get('port') else 5601, method='post',
                             endpoint='api/detection_engine/signals/tags', data=json.dumps(params))
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def assign_unassign_users_from_alert(config, params, **kwargs):
    try:
        params = build_payload(params)
        assignees = {"assignees": {}}
        if not isinstance(params.get('ids'), list):
            alerts_ids = [x.strip() for x in params.get('ids').split(',')]
            params.update({"ids": alerts_ids})
        else:
            params.update({"ids": params.get('ids')})
        if params.get("add") or params.get("remove"):
            assignees.get('assignees').update({"add": [params.get("add")] if params.get("add") else [],
                                            "remove": [params.get("remove")] if params.get("remove") else []})
            params.update(assignees)
            if params.get('add'):
               params.pop('add')
            if params.get('remove'):
               params.pop('remove')
        return make_api_call(config, port=params.pop('port') if params.get('port') else 5601, method='post',
                             endpoint='api/detection_engine/signals/assignees', data=json.dumps(params))
    except ElasticsearchException as Err:
        logger.error('Exception occurred: {}'.format(Err))
        raise ConnectorError(Err)


def check_health(config):
    try:
        if config.get('authentication_type') == "Basic Authentication":
            if get_cluster_details(config, params={"index":"_all", "run_as_user":None}):
                return True
        elif config.get('authentication_type') == "API Key Authentication":
            if make_api_call(config, port=config.get('port'), method='get', endpoint='api/alerting/_health'):
                return True
    except Exception as e:
        logger.error("Error establishing connection:\n{0}".format(str(e)))
        raise ConnectorError("Error establishing connection:\n{0}".format(str(e)))


operations = {
    'execute_query': execute_query,
    'execute_lucene_query': execute_lucene_query,
    'get_mapping': get_mapping,
    'get_cluster_details': get_cluster_details,
    'get_saved_search': get_saved_search,
    'get_alerts_list': get_alerts_list,
    'set_alert_status': set_alert_status,
    'apply_alert_tags': apply_alert_tags,
    'fetch_incidents': fetch_incidents,
    'assign_unassign_users_from_alert': assign_unassign_users_from_alert 
}

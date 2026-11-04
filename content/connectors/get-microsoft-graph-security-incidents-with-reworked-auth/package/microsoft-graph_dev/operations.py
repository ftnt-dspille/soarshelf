""""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""
import threading
from queue import Queue
from threading import Thread

import requests
from connectors.core.connector import get_logger, ConnectorError

from .microsoft_api_auth import *
from .utils import _list

logger = get_logger('microsoft-graph')


class SetupSession(object):
    def __init__(self, config):
        self.connector_info = config.get('connector_info')
        self.ms = MicrosoftAuth(config)
        self.verify_ssl = self.ms.verify_ssl
        self.token = self.ms.validate_token(config, self.connector_info)
        self.__setupSession()

    def __setupSession(self):
        try:
            self.session = requests.session()
            self.session.headers.update({
                'User-Agent': 'fortiSOAR/1.0',
                'Authorization': self.token,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            })
            self.session.verify = self.verify_ssl
            logger.info("session set up successfully")
        except Exception as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(e))


class ThreadCreate(object):
    def __init__(self, config):
        self.start_time = time()
        self.threadpool = []
        self.microsoft_graph = SetupSession(config)
        self.queue = Queue()

    def thread_run(self):
        logger.info(threading.active_count())
        for x in range(THREADS):
            worker = ThreadRunner(self.queue, self.microsoft_graph)
            worker.daemon = True
            worker.start()
            self.threadpool.append(worker)

    def api_result(self):
        message_found_list = []
        message_notfound_list = []
        error_list = []
        message_deleted_list = []
        for thread in self.threadpool:
            message_found_list = message_found_list + thread.matched
            message_notfound_list = message_notfound_list + thread.unmatched
            error_list = error_list + thread.error_msg
            message_deleted_list = message_deleted_list + thread.msg_deleted
        api_end_time = time()
        runtime = api_end_time - self.start_time
        result = {}
        if message_found_list:
            result['Message_Found_List'] = message_found_list
        if message_notfound_list:
            result['Message_Not_Found_List'] = message_notfound_list
        if error_list:
            result['Error_List'] = error_list
        if message_deleted_list:
            result['Message_Deleted_List'] = message_deleted_list
        result['Run_Time'] = runtime
        return result


class ThreadRunner(Thread):
    def __init__(self, queue, microsoft_graph):
        Thread.__init__(self)
        self.queue = queue
        self.microsoft_graph = microsoft_graph
        self.matched = []
        self.unmatched = []
        self.error_msg = []
        self.msg_deleted = []

    def api_call(self, queue_payload):
        try:
            headers = {'Connection': 'keep-alive',
                       'Authorization': self.microsoft_graph.token}
            self.microsoft_graph.session.headers = headers
            response = self.microsoft_graph.session.request(method=queue_payload['operation'], url=queue_payload['url'],
                                                            params=queue_payload['param'])
            if queue_payload['operation'] == 'Get':
                if response.status_code == 200:
                    if 'error' not in response.json():
                        if len(response.json()['value']) != 0:
                            tmp = response.json()
                            tmp['user_id'] = queue_payload['user_id']
                            self.matched.append(tmp)
                            tmp = None
                        else:
                            tmp = response.json()
                            tmp['user_id'] = queue_payload['user_id']
                            self.unmatched.append(tmp)
                            tmp = None
                    else:
                        tmp = response.json()
                        tmp['user_id'] = queue_payload['user_id']
                        self.unmatched.append(tmp)
                        tmp = None
                elif response.status_code == 403:
                    tmp = {
                        'error_msg': response.json(),
                        'user_id': queue_payload['user_id']
                    }
                    self.error_msg.append(tmp)
                    tmp = None
                elif response.status_code == 400:
                    tmp = response.json()
                    tmp['user_id'] = queue_payload['user_id']
                    self.unmatched.append(tmp)
                    tmp = None
                else:
                    tmp = {
                        'error_msg': response.status_code,
                        'user_id': queue_payload['user_id']
                    }
                    self.error_msg.append(tmp)

            elif queue_payload['operation'] == 'Delete':
                if response.status_code == 204:
                    tmp = {
                        'msg_deleted': 'Yes',
                        'user_id': queue_payload['user_id']
                    }
                    self.msg_deleted.append(tmp)
                else:
                    tmp = {
                        'error_msg': response.status_code,
                        'user_id': queue_payload['user_id']
                    }
                    self.error_msg.append(tmp)
        except:
            pass

    def run(self):
        while True:
            queue_payload = self.queue.get()
            try:
                self.api_call(queue_payload)
            except:
                pass
            finally:
                self.queue.task_done()


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


def get_risky_users_list(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    risk_id = params.get('risk_id')
    if risk_id:
        url = graph_api_endpoint + '/identityProtection/riskyUsers/{0}'.format(risk_id)
    else:
        url = graph_api_endpoint + '/identityProtection/riskyUsers'
    response = microsoft_graph.session.get(url=url)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def get_risky_user_details(config, params):
    return get_risky_users_list(config, params)


def get_groups(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    group_id = params.get('group_id')
    if group_id:
        url = graph_api_endpoint + '/groups/{0}/members'.format(group_id)
    else:
        url = graph_api_endpoint + '/groups'
    response = microsoft_graph.session.get(url=url)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def get_group_users(config, params):
    return get_groups(config, params)


def get_security_alert(config, params):
    microsoft_graph = SetupSession(config)
    api_version = params.pop('api_version', 'V1')
    alert_endpoint = get_alert_endpoint(microsoft_graph, config, api_version)
    url = alert_endpoint + '/{0}'.format(params.get('alert_id'))
    logger.info("THIS IS THE URL: " + url)
    response = microsoft_graph.session.get(url=url)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def get_alert_endpoint(microsoft_graph, config, api_version):
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    if api_version.lower() == 'v2':
        alert_endpoint = graph_api_endpoint + '/security/alerts_v2'
    else:
        alert_endpoint = graph_api_endpoint + '/security/alerts'
    return alert_endpoint


def get_filter_query_string(params):
    all_filters = []
    params['classification'] = CLASSIFICATION.get(params.get('classification'))
    params['status'] = STATUS.get(params.get('status'))
    params['determination'] = STATUS.get(params.get('determination'))
    params['severity'] = STATUS.get(params.get('severity'))
    for key, parameter in params.items():
        if not parameter:
            continue
        parameter_key = alerts_filter_map.get(key)
        if key in ['search_from', 'lastUpdateDateTime', 'createdDateTime']:
            param_filter = f"{parameter_key} gt {parameter}"
        else:
            param_filter = f"{parameter_key} eq '{parameter}'"
        all_filters.append(param_filter)
    if all_filters:
        all_filters = ['(' + filter_str + ')' for filter_str in all_filters]
        all_filters = ' and '.join(all_filters)
    return all_filters


def get_all_security_alerts(config, params):
    microsoft_graph = SetupSession(config)
    api_version = params.pop('api_version', 'V1')
    url = get_alert_endpoint(microsoft_graph, config, api_version)
    top = params.pop('top', '')
    skip = params.pop('skip', '')
    query_string = get_filter_query_string(params)
    params = {
        '$top': top,
        '$skip': skip
    }
    if query_string:
        params['$filter'] = query_string
    params = {k: v for k, v in params.items() if v is not None and v != ''}
    response = microsoft_graph.session.get(url=url, params=params)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def get_alert_payload(params):
    alert_tags = str(params.get('tags', ''))
    if alert_tags:
        alert_tags = list(alert_tags.split(","))
    api_version = params.get('api_version', 'V1')
    payload = {
        'assignedTo': params.get('assigned_to'),
        'status': STATUS.get(params.get('status'), ''),
    }
    if api_version.lower() == 'v2':
        payload.update({
            "classification": CLASSIFICATION.get(params.get('classification')),
            "determination": DETERMINATION.get(params.get('determination'))
        })
    else:
        payload.update({
            'comments': params.get('comments'),
            'feedback': FEEDBACK.get(params.get('feedback'), ''),
            'tags': alert_tags,
            'vendorInformation': {
                'provider': params.get('provider'),
                'vendor': params.get('vendor'),
                'subProvider': params.get('subProvider'),
                'providerVersion': params.get('providerVersion')
            }
        })
    payload = check_payload(payload)
    return payload


def update_security_alert(config, params):
    microsoft_graph = SetupSession(config)
    api_version = params.get('api_version', 'V1')
    url = get_alert_endpoint(microsoft_graph, config, api_version)
    alert_id = params.get('alert_id')
    alert_endpoint = f'{url}/{alert_id}'
    payload = get_alert_payload(params)
    response = microsoft_graph.session.patch(url=alert_endpoint, json=payload)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def add_comment_on_security_alert(config, params):
    microsoft_graph = SetupSession(config)
    alert_id = params.get('alert_id')
    endpoint = '{0}/{1}/security/alerts_v2/{2}/comments'.format(microsoft_graph.ms.host, config.get('api_version'),
                                                                alert_id)
    payload = {
        "@odata.type": "microsoft.graph.security.alertComment",
        "comment": params.get('comment')
    }
    response = microsoft_graph.session.post(url=endpoint, json=payload)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(endpoint), str(response.content),
                                                                               str(response.reason)))


def search_message(config, params):
    thread_create = ThreadCreate(config)
    graph_api_endpoint = '{0}/{1}'.format(RESOURCE, config.get('api_version'))
    subject = "subject eq " + "'" + params.get('subject') + "'"
    param = {"$filter": subject}
    if params.get("size", ''):
        param['$top'] = params.get('size')
    if params.get("skip", ''):
        param['$skip'] = params.get('skip')
    for user in _list(params.get('user_list', '')):
        url = graph_api_endpoint + '/users/{0}/messages'.format(user)
        queue_payload = {
            "operation": "Get",
            "param": param,
            "url": url,
            "user_id": user
        }
        thread_create.queue.put(queue_payload)
    thread_create.thread_run()
    thread_create.queue.join()
    thread_create.microsoft_graph.session.close()
    result = thread_create.api_result()
    result['Total_Users_Processed'] = len(params.get('user_list'))
    return result


def del_message_bulk(config, params):
    thread_create = ThreadCreate(config)
    graph_api_endpoint = '{0}/{1}'.format(RESOURCE, config.get('api_version'))
    param = None
    for user in _list(params.get('user_list', '')):
        url = graph_api_endpoint + '/users/{0}/messages/{1}'.format(user['user_id'], user['message_id'])
        queue_payload = {
            "operation": "Delete",
            "param": param,
            "url": url,
            "user_id": user
        }
        thread_create.queue.put(queue_payload)
    thread_create.thread_run()
    thread_create.queue.join()
    thread_create.microsoft_graph.session.close()
    result = thread_create.api_result()
    result['Total_Users_Processed'] = len(params.get('user_list'))
    return result


def del_message(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    url = graph_api_endpoint + '/users/{0}/messages/{1}'.format(params.get('user_id'), params.get('message_id'))
    microsoft_graph.session.headers.pop('Prefer', '')
    response = microsoft_graph.session.delete(url=url)
    microsoft_graph.session.close()
    if response.ok:
        return {"status_code": response.status_code}
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def revoke_user_sessions(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    url = graph_api_endpoint + '/users/{0}/revokeSignInSessions'.format(params.get('user'))
    response = microsoft_graph.session.post(url=url)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def block_or_unblock_new_ips(config, params, operation='block_new_ips'):
    microsoft_graph = SetupSession(config)
    try:
        graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
        named_location_uuid = params.get('namedLocationUuid')
        url = graph_api_endpoint + '/identity/conditionalAccess/namedLocations/' + named_location_uuid
        response = microsoft_graph.session.get(url=url)
        if not response.ok:
            if response.status_code == 404:
                logger.error(response.json().get('error').get('message') if 'error' in response.json() else
                             'Named location with id {0} does not exist in the directory'.format(named_location_uuid))
            raise ConnectorError(
                'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                                   str(response.reason)))
        response = response.json()
        if 'ipRanges' in response:
            ipranges_graph_content = response['ipRanges']
        else:
            raise ConnectorError("Specified named location is not of type IP ranges.")
        if response['isTrusted']:
            raise ConnectorError("Specified named location is trusted. Cannot be used to block/unblock IP addresses.")
        ipv4_ips = _list(params.get('ipv4_ips', ''))
        ipv6_ips = _list(params.get('ipv6_ips', ''))
        if not (ipv4_ips or ipv6_ips):
            raise ConnectorError("At least IPv4 or IPv6 address is required.")
        if operation == 'block_new_ips':
            if ipv4_ips:
                for ip in ipv4_ips:
                    NewIPAddress = {
                        "@odata.type": IPv4,
                        "cidrAddress": ip.strip()
                    }
                    ipranges_graph_content.append(NewIPAddress)
            if ipv6_ips:
                for ip in ipv6_ips:
                    NewIPAddress = {
                        "@odata.type": IPv6,
                        "cidrAddress": ip.strip()
                    }
                    ipranges_graph_content.append(NewIPAddress)
        else:
            ips_to_unblock = ipv4_ips + ipv6_ips
            ipranges_graph_content[:] = [entry for entry in ipranges_graph_content if
                                         entry.get('cidrAddress') not in ips_to_unblock]
        newData = {
            "@odata.type": "#microsoft.graph.ipNamedLocation",
            "ipRanges": ipranges_graph_content
        }
        response = microsoft_graph.session.patch(url=url, json=newData)
        if response.ok:
            return response.json()
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))
    finally:
        microsoft_graph.session.close()


def block_new_ips(config, params):
    return block_or_unblock_new_ips(config, params)


def unblock_new_ips(config, params):
    return block_or_unblock_new_ips(config, params, 'unblock_new_ips')


def get_all_named_locations(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    url = graph_api_endpoint + '/identity/conditionalAccess/namedLocations'
    order_by = FIELDS.get(params.get('order_by'))
    if params.get('order') == 'Descending':
        order_by += ' desc'
    select = []
    for field in params.get('select', []):
        select.append(FIELDS.get(field))
    payload = {
        '$top': params.get('size'),
        '$skip': params.get('skip'),
        '$orderby': order_by,
        '$select': ','.join(select)
    }
    payload = check_payload(payload)
    payload['$count'] = 'true' if params.get('count') else 'false'
    display_name = params.get('name')
    if display_name:
        payload['$filter'] = "displayName eq '{0}'".format(display_name)
    response = microsoft_graph.session.get(url=url, params=payload)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def create_ip_range_location(config, params):
    microsoft_graph = SetupSession(config)
    name = params.get('name')
    is_trusted = params.get('is_trusted', False)
    graph_api_endpoint = '{0}/{1}'.format(microsoft_graph.ms.host, config.get('api_version'))
    url = graph_api_endpoint + '/identity/conditionalAccess/namedLocations'
    payload = {
        "@odata.type": "#microsoft.graph.ipNamedLocation",
        "displayName": name,
        "isTrusted": is_trusted
    }
    ipranges_graph_content = []
    ipv4_ips = _list(params.get('ipv4_ips', ''))
    ipv6_ips = _list(params.get('ipv6_ips', ''))
    if ipv4_ips:
        for ip in ipv4_ips:
            NewIPAddress = {
                "@odata.type": IPv4,
                "cidrAddress": ip.strip()
            }
            ipranges_graph_content.append(NewIPAddress)
    if ipv6_ips:
        for ip in ipv6_ips:
            NewIPAddress = {
                "@odata.type": IPv6,
                "cidrAddress": ip.strip()
            }
            ipranges_graph_content.append(NewIPAddress)
    payload['ipRanges'] = ipranges_graph_content
    response = microsoft_graph.session.post(url=url, json=payload)
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    else:
        raise ConnectorError(
            'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url), str(response.content),
                                                                               str(response.reason)))


def get_security_incidents(config, params):
    microsoft_graph = SetupSession(config)
    graph_api_endpoint = "{0}/{1}".format(
        microsoft_graph.ms.host,
        config.get("api_version")
    )
    endpoint = graph_api_endpoint + "/security/incidents"
    payload = {
        "$top": params.get("top"),
        "$skip": params.get("skip"),
        "$filter": params.get("filter"),
        "$orderby": params.get("orderBy"),
        "$count": "true" if params.get("count") else None
    }
    # Expand incident alerts if requested
    if params.get("fetchAlerts"):
        payload["$expand"] = "alerts"

    payload = check_payload(payload)
    response = microsoft_graph.session.get(
        url=endpoint,
        params=payload
    )
    microsoft_graph.session.close()
    if response.ok:
        return response.json()
    raise ConnectorError(
        "Fail To request API {0} response is :{1} with reason: {2}".format(
            str(endpoint),
            str(response.content),
            str(response.reason)
        )
    )


def _check_health(config):
    if check(config, config.get('connector_info')):
        return True


operations = {
    'get_risky_users_list': get_risky_users_list,
    'get_risky_user_details': get_risky_user_details,
    'get_groups': get_groups,
    'get_security_alert': get_security_alert,
    'get_all_security_alerts': get_all_security_alerts,
    'update_security_alert': update_security_alert,
    'add_comment_on_security_alert': add_comment_on_security_alert,
    'get_group_users': get_group_users,
    'search_message': search_message,
    'del_message_bulk': del_message_bulk,
    'del_message': del_message,
    'revoke_user_sessions': revoke_user_sessions,
    'create_ip_range_location': create_ip_range_location,
    'block_new_ips': block_new_ips,
    'unblock_new_ips': unblock_new_ips,
    'get_all_named_locations': get_all_named_locations,
    'check_health': _check_health,
    'get_security_incidents': get_security_incidents
}

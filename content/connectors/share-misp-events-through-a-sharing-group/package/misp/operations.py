"""
Copyright start
MIT License
Copyright (c) 2024 Fortinet Inc
Copyright end
"""

import json
import requests
import arrow
from .constants import *
from connectors.core.connector import get_logger, ConnectorError
from requests_toolbelt.utils import dump

logger = get_logger('misp')

error_msgs = {
    400: 'Bad/Invalid Request',
    401: 'Unauthorized: Invalid credentials provided failed to authorize',
    404: 'Not Found',
    429: 'Too Many Requests',
    500: 'Internal Server Error'
}


class MISP(object):
    def __init__(self, config, *args, **kwargs):
        self.server_url = config.get('hostname')
        self.api_key = config.get('api_key')
        self.verify = config.get('verify_ssl')
        url = config.get('hostname').strip('/')
        if not url.startswith('https://') and not url.startswith('http://'):
            self.url = 'https://{0}/'.format(url)
        else:
            self.url = url + '/'

    def make_rest_call(self, url, method, data=None, params=None):
        try:
            url = self.url + url
            logger.debug("Endpoint URL: {0}".format(url))
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': self.api_key}
            response = requests.request(method, url, headers=headers, data=data, params=params, verify=self.verify)
            logger.debug('\n{}\n'.format(dump.dump_all(response).decode('utf-8')))
            if response.ok:
                logger.info('Successfully got response for url {0}'.format(url))
                if 'json' in str(response.headers):
                    try:
                        return response.json()
                    except:
                        result = json.loads(response.text)
                        return result
                else:
                    result = json.loads(response.text)
                    return result
            else:
                logger.error("{0}".format(error_msgs.get(response.status_code, '')))
                raise ConnectorError("{0}".format(error_msgs.get(response.status_code, response.json())))
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

    def build_payload(self, payload):
        data = {}
        for k, v in payload.items():
            if v and ((k == 'page' and v < 0) or (k == 'limit' and v <= 0)):
                raise ConnectorError('Value {0} of {1} parameter is invalid.'.format(v, k))
            elif type(v) is bool:
                data[k] = v
            elif v or (v == 0 and isinstance(v, int)):
                data[k] = v
        logger.debug("Query Parameters: {0}".format(payload))
        return data


def create_event(config, params):
    try:
        mp = MISP(config)
        url = 'events'
        date = params.get("date")
        if date:
            if isinstance(date, str):
                date = date.split("T")[0]
            elif isinstance(date, (int, float)):
                date = arrow.get(date).format("YYYY-MM-DD")
            else:         # datetime object or Arrow object
                date = arrow.get(date).format("YYYY-MM-DD")
        payload = {
            'Event': {
                'date': date,
                'threat_level_id': threat_level_mapping.get(params.get('threat_level')),
                'info': params.get('event_info'),
                'analysis': analysis_mapping.get(params.get('analysis')),
                'distribution': distrib_mapping.get(params.get('distribution')),
                'published': params.get('published')
            }
        }
        extends_uuid = params.get('extends_uuid')
        if extends_uuid:
            payload.get('Event', {}).update({'extends_uuid': extends_uuid})
        additional_attributes = params.get('additional_attributes')
        if additional_attributes:
            payload.get('Event', {}).update(additional_attributes)
        payload = mp.build_payload(payload['Event'])
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        return response
    except Exception as err:
        logger.exception("Error while creating event in MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while creating event in MISP. Error as follows: {0}".format(str(err)))


def get_events(config, params):
  try:
    mp = MISP(config)
    url = 'events/index'
    data = params.get('searchJSONBody')
    response = mp.make_rest_call(method='POST', url=url, data=json.dumps(data))
    return response
  except Exception as err:
    logger.exception("Error while getting event from MISP. Error as follows: {0}".format(str(err)))
    raise ConnectorError("Error while getting event from MISP. Error as follows: {0}".format(str(err)))


def get_event(config, params):
    try:
        mp = MISP(config)
        url = 'events/{0}'.format(params.get('event_id'))
        response = mp.make_rest_call(method='GET', url=url)
        return response
    except Exception as err:
        logger.exception("Error while getting event from MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while getting event from MISP. Error as follows: {0}".format(str(err)))


def add_attributes_to_event(config, params):
    try:
        mp = MISP(config)
        url = 'attributes/add/{0}'.format(params.get('event_id'))
        category = params.get('category')
        payload = {
            'value': params.get('value'),
            'type': params.get('type'),
            'category': category,
            'distribution': distrib_mapping.get(params.get('distribution')),
            'to_ids': params.get('to_ids'),
            'comment': params.get('comment')
        }
        payload = mp.build_payload(payload)
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        if response:
            return response
    except Exception as err:
        logger.exception("Error while adding attribute to event in MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while adding attribute to event in MISP. Error as follows: {0}".format(str(err)))


def login(config, params):
    mp = MISP(config)
    endpoint = "events"
    response = mp.make_rest_call(endpoint, 'GET')
    return response


def delete_attribute(config, params):
    try:
        mp = MISP(config)
        url = 'attributes/delete/{0}'.format(params.get('attribute_id'))
        response = mp.make_rest_call(method='POST', url=url)
        return response
    except Exception as err:
        logger.exception("Error while deleting attribute in MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while deleting attribute in MISP. Error as follows: {0}".format(str(err)))


def delete_event(config, params):
    try:
        mp = MISP(config)
        url = 'events/delete/{0}'.format(params.get('event_id'))
        response = mp.make_rest_call(method='DELETE', url=url)
        return response
    except Exception as err:
        logger.exception("Error while deleting event in MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while deleting event in MISP. Error as follows: {0}".format(str(err)))


def add_tag_to_event(config, params):
    try:
        mp = MISP(config)
        url = 'events/addTag'
        tags = params.get('tag')

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        payload = {
            'request': {
                'Event': {
                    'id': params.get('event_id'),
                    'tag': tags
                }
            }
        }
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        if response.get('saved'):
            return response
        else:
            error_msg = response.get('errors')
            logger.error(error_msg)
            raise ConnectorError("{0}".format(error_msg))
    except Exception as err:
        logger.exception("Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error as follows: {0}".format(str(err)))


def remove_tag_from_event(config, params):
    try:
        mp = MISP(config)
        url = 'events/removeTag'
        payload = {
            'request': {
                'Event': {
                    'id': params.get('event_id'),
                    'tag': params.get('tag')
                }
            }
        }
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        if response.get('saved'):
            return response
        else:
            error_msg = response.get('errors')
            logger.error(error_msg)
            raise ConnectorError("{0}".format(error_msg))
    except Exception as err:
        logger.exception("Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error as follows: {0}".format(str(err)))


def get_tags(config, params):
    try:
        mp = MISP(config)
        url = 'tags'
        response = mp.make_rest_call(method='GET', url=url)
        return response
    except Exception as err:
        logger.exception("Error while getting tags from MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while getting tags from MISP. Error as follows: {0}".format(str(err)))


def add_tag(config, params):
    try:
        mp = MISP(config)
        payload = {
            'name': params.get('name'),
            'exportable': params.get('exportable'),
            'hide_tag': params.get('hide_tag'),
            'org_id': params.get('org_id'),
            'user_id': params.get('user_id'),
            'colour': params.get('colour')
        }
        payload = mp.build_payload(payload)
        url = 'tags/add'
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        if response:
            return response
    except Exception as err:
        logger.exception("Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error as follows: {0}".format(str(err)))


def run_search(config, params):
    try:
        mp = MISP(config)
        payload = {}
        search_type = params.get('search_type')
        if search_type == 'Advanced':
            payload = params.get('search_filter')
        elif search_type == 'Basic':
            searchDatefrom = params.get('from')
            searchDateuntil = params.get('to')
            payload = {
                "page": params.get('page', 1),
                "limit": params.get('limit', 10),
                "from": arrow.get(searchDatefrom).format('YYYY-MM-DD') if searchDatefrom else None,
                "to": arrow.get(searchDateuntil).format('YYYY-MM-DD') if searchDateuntil else None,
                "type": params.get('type', '')
            }
        payload = mp.build_payload(payload)
        search = params.get('controller')
        url = 'events/restSearch' if search == 'Events' else 'attributes/restSearch'
        response = mp.make_rest_call(method='POST', url=url, data=json.dumps(payload))
        return response
    except Exception as err:
        logger.exception("Error while searching Events/Attributes in MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error while searching Events/Attributes in MISP. Error as follows: {0}".format(str(err)))


def get_organisations(config, params):
    mp = MISP(config)
    return mp.make_rest_call(method='GET', url='organisations')


def get_users(config, params):
    mp = MISP(config)
    return mp.make_rest_call(method='GET', url='admin/users')


def get_attribute_type(config, params):
    category = params.get('category')
    if category:
        type = attribute_type.get(category)
        return type


def generic_rest_api_call(config, params):
    mp = MISP(config)
    endpoint = params.get('endpoint','')
    query_params = params.get('query_params', {})
    method = params.get('method', '')
    payload = params.get('payload')
    return mp.make_rest_call(method=method, url=endpoint, params=query_params, data=json.dumps(payload))
    

def _check_health(config):
    try:
        response = login(config, params="")
        if response:
            return True
        else:
            logger.error("Error in Check Health:{0}".format(response))
            raise ConnectorError('Error in Check Health:{0}'.format(error_msgs[response.status_code]))
    except Exception as err:
        logger.error("Error connecting to MISP. Error as follows: {0}".format(str(err)))
        raise ConnectorError("Error connecting to MISP. Error as follows: {0}".format(str(err)))


operations = {
    'create_event': create_event,
    'get_events': get_events,
    'get_event': get_event,
    'add_attributes_to_event': add_attributes_to_event,
    'delete_attribute': delete_attribute,
    'delete_event': delete_event,
    'add_tag': add_tag,
    'add_tag_to_event': add_tag_to_event,
    'remove_tag_from_event': remove_tag_from_event,
    'get_tags': get_tags,
    'run_search': run_search,
    'get_attribute_type': get_attribute_type,
    'get_organisations': get_organisations,
    'get_users': get_users,
    'generic_rest_api_call': generic_rest_api_call
}

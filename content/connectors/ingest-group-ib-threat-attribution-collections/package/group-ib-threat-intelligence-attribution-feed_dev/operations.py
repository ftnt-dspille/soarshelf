"""
Copyright start
MIT License
Copyright (c) 2025    Fortinet Inc
Copyright end
"""

import requests
import logging
import json
from requests_toolbelt.utils import dump
from integrations.crudhub import maybe_json_or_raise
from connectors.core.connector import get_logger, ConnectorError
from .constants import *
from dateutil.parser import parse

logger = get_logger('group-ib-threat-intelligence-attribution-feed')

DATE_FIELD_MAPPING = {
    "compromised/account_group": "dateFirstSeen",
    "compromised/bank_card_group": "dateFirstCompromised",
    "compromised/masked_card": "dateDetected",
    "compromised/mule": "dateAdd",
    "compromised/spd": "createdAt",
    "attacks/ddos": "dateReg",
    "attacks/deface": "date",
    "attacks/phishing_group": "detected",
    "attacks/phishing_kit": "detected",
    "osi/git_repository": "dateDetected",
    "osi/public_leak": "created",
    "osi/vulnerability": "datePublished",
    "malware/cnc": "dateDetected",
    "malware/malware": "dateDetected"
}


class GroupIB():
    def __init__(self, config):
        self.server_url = config.get('server_url')
        if self.server_url.startswith('https://') or self.server_url.startswith('http://'):
            self.server_url = self.server_url.strip('/') + '/api/v2/'
        else:
            self.server_url = 'https://{0}'.format(self.server_url.strip('/')) + '/api/v2/'
        self.username = config.get('username')
        self.api_key = config.get('api_key')
        self.verify_ssl = config.get('verify_ssl')

    def make_api_call(self, method='GET', endpoint=None, params=None, data=None,
                      json=None, flag=False, url= None):
        if not url:
            if endpoint:
                url = '{0}{1}'.format(self.server_url, endpoint)
            else:
                url = '{0}'.format(self.server_url)
        logger.info('Request URL {0}'.format(url))
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        try:
            response = requests.request(method=method, url=url, auth=(self.username, self.api_key), params=params,
                                        data=data, json=json,
                                        headers=headers,
                                        verify=self.verify_ssl)
            logger.debug("\n{}\n".format(dump.dump_all(response).decode('utf-8')))
            if response.ok:
                result = maybe_json_or_raise(response)
                if 'error' in result:
                    raise ConnectorError('{}'.format(result.get('error').get('message')))
                if response.status_code == 204:
                    return {"Status": "Success", "Message": "Executed successfully"}
                return result
            elif messages_codes[response.status_code]:
                logger.error('{0}'.format(messages_codes[response.status_code]))
                raise ConnectorError('{0}'.format(messages_codes[response.status_code]))
            else:
                logger.error(
                    'Fail To request API {0} response is : {1} with reason: {2}'.format(str(url),
                                                                                        str(response.content),
                                                                                        str(response.reason)))
                raise ConnectorError(
                    'Fail To request API {0} response is :{1} with reason: {2}'.format(str(url),
                                                                                       str(response.content),
                                                                                       str(response.reason)))

        except requests.exceptions.SSLError as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(messages_codes['ssl_error']))
        except requests.exceptions.ConnectionError as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(messages_codes['timeout_error']))
        except Exception as e:
            logger.exception('{0}'.format(e))
            raise ConnectorError('{0}'.format(e))


def build_payload(params, input_params_list):
    result = {k: v for k, v in params.items() if v is not None and v != '' and k in input_params_list}
    return result


def check_health(config):
    try:
        logger.info("Invoking check_health")
        obj = GroupIB(config)
        response = obj.make_api_call(method='GET', endpoint='compromised/mule', params={'limit': 10})
        if response:
            return True
    except Exception as err:
        logger.exception('{0}'.format(err))
        raise ConnectorError('{0}'.format(err))


def get_indicators(config, params):
    try:
        collection = params.get('collection')
        obj = GroupIB(config)

        if params.get('id') and params.get('limit'):
            response = obj.make_api_call(method='GET', endpoint=collection + '/' + params.get('id'), params={'limit': params.get('limit')})
            return response
        if params.get('id'):
            response = obj.make_api_call(method='GET', endpoint=collection + '/' + params.get('id'))
            return response
        if params.get('limit'):
            response = obj.make_api_call(method='GET', endpoint=collection, params={'limit': params.get('limit')})
            return response

        response = obj.make_api_call(method='GET', endpoint=collection)
        return response
    except Exception as err:
        logger.exception('{0}'.format(err))
        raise ConnectorError('{0}'.format(err))


def search_indicator(config, params):
    try:
        results = []
        limit = params.get('limit')
        obj = GroupIB(config)
        result = obj.make_api_call(method='GET', endpoint='search', params=params)
        if len(result) > 0:
            result = result[:limit] if len(result) > limit else result
            for entry in result:
                events = obj.make_api_call(method='GET', url="{0}&limit={1}".format(entry['link'], limit))
                entry.update({'events': events})
                results.append(entry)
        return results
    except Exception as err:
        logger.exception('{0}'.format(err))
        raise ConnectorError('{0}'.format(err))    


def ingest_collection(config, params):

    """
    Group-IB ingestion action.
    Parameters:
        collection (str): Group-IB collection name
        limit (int): Number of records to fetch
        offset (int): Pagination offset
        seqUpdate (int): Incremental fetch cursor
    Returns:
        dict
    """
    try:
        client = GroupIB(config)
        collection = params.get("collection")
        if not collection:
            raise ConnectorError("Collection parameter is required")

        query_params = {
            "limit": int(params.get("limit", 10))
        }

        if params.get("offset"):
            query_params["offset"] = params.get("offset")

        if params.get("seqUpdate"):
            query_params["seqUpdate"] = int(params.get("seqUpdate"))

        response = client.make_api_call(
            endpoint=collection,
            method="GET",
            params=query_params
        )

        data = response.get("items", [])

        startTime = parse(params.get("startTime")) if params.get("startTime") else None
        endTime = parse(params.get("endTime")) if params.get("endTime") else None
        dateField = DATE_FIELD_MAPPING.get(collection)

        filteredData = []

        if dateField and (startTime or endTime):
            for item in data:
                eventTime = item.get(dateField)
                if not eventTime:
                    continue

                try:
                    eventTime = parse(eventTime)
                except Exception:
                    continue

                if eventTime < startTime:
                    continue
                if eventTime > endTime:
                    continue

                filteredData.append(item)
            data = filteredData

        return {
            "success": True,
            "collection": collection,
            "count": len(data),
            "data": data
        }

    except Exception as err:
        logger.exception(str(err))
        raise ConnectorError(str(err))


operations = {
    'get_indicators': get_indicators,
    'search_indicator': search_indicator,
    'ingest_collection': ingest_collection
}
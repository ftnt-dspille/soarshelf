"""
Copyright start
MIT License
Copyright (c) 2023 Fortinet Inc
Copyright end
"""

from .fortiflex_api_auth import *
from .constants import *
from connectors.core.connector import get_logger, ConnectorError
import requests, json
from urllib.parse import unquote, urlparse

logger = get_logger('fortinet-fortiflex')

errors = {
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    500: 'Internal Server Error',
    502: 'Gateway Error',
    504: 'Gateway Error'
}


def make_rest_call(endpoint, method, connector_info, config, data=None, params=None):
    try:
        co = FortiFlex(config)
        url = co.host + endpoint
        token = co.validate_token(config, connector_info)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': token
        }
        response = requests.request(method, url, headers=headers, verify=co.verify_ssl, data=data, params=params)
        if response.status_code in [200, 201, 204]:
            if response.text != "":
                return response.json()
            else:
                return {}
        elif response.status_code == 404:
            return {'Not Found'}
        else:
            raise ConnectorError("{0}: {1}".format(errors.get(response.status_code), response.content))
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


def build_payload(payload):
    payload = {k: v for k, v in payload.items() if v is not None and v != ''}
    return payload


def get_programs(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/programs/list"
        response = make_rest_call(endpoint, 'POST', connector_info, config)
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def create_configuration_parameters(params):
    parameters = []
    pid = params.get('productTypeId')
    if pid == 'FortiGate Virtual Machine - Service Bundle':
        parameters.append({'id': 1, 'value': CPU_SIZE.get(params.get('FGTVMSBCpuSize'))})
        parameters.append({'id': 2, 'value': SERVICE_PACKAGE.get(params.get('FGTVMSBServicePackage'))})
        if params.get('FGTVMSBVDOMs'):
            parameters.append({'id': 10, 'value': params.get('FGTVMSBVDOMs')})
        return parameters
    elif pid == 'FortiGate Virtual Machine - A La Carte Services':
        parameters.append({'id': 6, 'value': params.get('FGTVMALCSCpuSize')})
        if params.get('FGTVMALCSFortiGuardServices'):
            for fortiguard_service in params.get('FGTVMALCSFortiGuardServices'):
                parameters.append({'id': 7, 'value': FORTIGUARD_SERVICE.get(fortiguard_service)})
        parameters.append({'id': 8, 'value': SUPPORT_SERVICES_FG.get(params.get('FGTVMALCSSupportServices'))})
        if params.get('FGTVMALCSVDOMs'):
            parameters.append({'id': 11, 'value': params.get('FGTVMALCSVDOMs')})
        if params.get('FGTVMALCSCloudServices'):
            for cloud_service in params.get('FGTVMALCSCloudServices'):
                parameters.append({'id': 12, 'value': CLOUD_SERVICE.get(cloud_service)})
        return parameters
    elif pid == 'FortiWeb Virtual Machine - Service Bundle':
        parameters.append({'id': 4, 'value': CPU_SIZE.get(params.get('FWBVMSBCpuSize'))})
        parameters.append({'id': 5, 'value': SERVICE_PACKAGE.get(params.get('FWBVMSBServicePackage'))})
        return parameters
    elif pid == 'FortiClient EMS On-Prem':
        parameters.append({'id': 13, 'value': params.get('FCLTZtna')})
        parameters.append({'id': 14, 'value': params.get('FCLTEpp')})
        parameters.append({'id': 15, 'value': params.get('FCLTChromebook')})
        parameters.append({'id': 16, 'value': SUPPORT_SERVICES_FOR_FC_EMS.get(params.get('FCLTSupportServices'))})
        if params.get('FCLTAddons'):
            parameters.append({'id': 36, 'value': ADDONS.get(params.get('FCLTAddons'))})
        return parameters
    elif pid == 'FortiManager Virtual Machine':
        parameters.append({'id': 30, 'value': params.get('FMGVMManagedDevices')})
        parameters.append({'id': 9, 'value': params.get('FMGVMAdoms')})
        return parameters
    elif pid == 'FortiAnalyzer Virtual Machine':
        parameters.append({'id': 21, 'value': params.get('FAZVMDailyStorage')})
        parameters.append({'id': 22, 'value': params.get('FAZVMAdoms')})
        parameters.append({'id': 23, 'value': SUPPORT_SERVICES_FOR_FAZ.get(params.get('FAZSupportServices'))})
        return parameters
    elif pid == 'FortiPortal Virtual Machine':
        parameters.append({'id': 24, 'value': params.get('FPTLManagedDevices')})
        return parameters
    elif pid == 'FortiADC Virtual Machine':
        parameters.append({'id': 25, 'value': CPU_SIZE.get(params.get('FADCVMCpuSize'))})
        parameters.append({'id': 26, 'value': SUPPORT_SERVICES_FOR_ADC.get(params.get('FADCVMServicePackage'))})
        return parameters
    elif pid == 'FortiGate Hardware':
        parameters.append({'id': 27, 'value': DEVICE_MODEL.get(params.get('FGTHDeviceModel'))})
        parameters.append({'id': 28, 'value': SERVICE_PACKAGE_FOR_FG_HD.get(params.get('FCLTServicePackage'))})
        if params.get('FCLTAddons'):
            for addons in params.get('FCLTAddons'):
                parameters.append({'id': 29, 'value': ADDONS_FOR_FG_HD.get(addons)})
        return parameters
    elif pid == 'FortiWeb Cloud - Private':
        parameters.append({'id': 32, 'value': params.get('FWBCPVTAvgThroughput')[:-5]})
        parameters.append({'id': 33, 'value': params.get('FWBCPVTWebApp')})
        return parameters
    elif pid == 'FortiWeb Cloud - Public':
        parameters.append({'id': 34, 'value': params.get('FWBCPUBAvgThroughput')[:-5]})
        parameters.append({'id': 35, 'value': params.get('FWBCPUBWebApp')})
        return parameters


def create_configuration(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/configs/create"
        payload = {
            'programSerialNumber': params.get('programSerialNumber'),
            'accountId': params.get('accountId'),
            'name': params.get('name'),
            'productTypeId': PRODUCT_ID.get(params.get('productTypeId'))
        }
        parameters = create_configuration_parameters(params)
        payload.update({'parameters': parameters})
        payload = build_payload(payload)
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(payload))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_configurations(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/configs/list"
        params = build_payload(params)
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def enable_configuration(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/configs/enable"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def disable_configuration(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/configs/disable"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def update_configuration(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/configs/update"
        payload = {
            'id': params.get('id'),
            'name': params.get('name'),
        }
        parameters = create_configuration_parameters(params)
        payload.update({'parameters': parameters})
        payload = build_payload(payload)
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(payload))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def create_vm_entitlements(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/vm/create"
        end_date = params.get('endDate')
        if end_date:
            end_date_time = end_date.split("T")[0] + ' ' + end_date.split("T")[1].split(".")[0]
            params.update({'endDate': end_date_time})
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def create_hardware_entitlements(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/hardware/create"
        end_date = params.get('endDate')
        if end_date:
            end_date_time = end_date.split("T")[0] + ' ' + end_date.split("T")[1].split(".")[0]
            params.update({'endDate': end_date_time})
        params.update({'serialNumbers': params.get('serialNumbers').split(",")})
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_entitlements(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/list"
        params = build_payload(params)
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def update_entitlements(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/update"
        end_date = params.get('endDate')
        if end_date:
            params.update({'endDate': end_date.split("T")[0]})
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def stop_entitlement(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/stop"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def reactivate_entitlement(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/reactivate"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def transfer_entitlement(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/transfer"
        params.update({'serialNumbers': params.get('serialNumbers').split(",")})
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def regenerate_token_for_vm(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/vm/token"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_point_usage_for_vm(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/entitlements/points"
        end_date = params.get('endDate')
        if end_date:
            params.update({'endDate': end_date.split("T")[0]})
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_groups(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/groups/list"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def get_group_next_token(config, params, connector_info):
    try:
        endpoint = "/ES/api/fortiflex/v2/groups/nexttoken"
        response = make_rest_call(endpoint, 'POST', connector_info, config, data=json.dumps(params))
        return response
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


def safe_endpoint(endpoint):
    """A path on the configured server, or an error.

    A full URL, a `//host` start, a `..` segment (also percent-encoded, up to
    three layers) or a backslash is refused, so the access token can never be
    sent to another host.
    """
    endpoint = str(endpoint or '').strip()
    if not endpoint:
        raise ConnectorError('Endpoint is required')
    path = endpoint.split('?')[0]
    for _ in range(3):
        path = unquote(path)
    parsed = urlparse(endpoint)
    if (parsed.scheme or parsed.netloc or path.startswith('//') or '..' in path.split('/')
            or '\\' in path):
        raise ConnectorError('Endpoint must be a path on the configured server, '
                             'for example /ES/api/fortiflex/v2/programs/list - not a full URL')
    return endpoint if endpoint.startswith('/') else '/' + endpoint


def json_object(value, name):
    """A JSON object from a dict or a JSON string; blank means none."""
    if value is None or value == '' or value == {}:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ConnectorError('{0} must be valid JSON'.format(name))
    if not isinstance(value, dict):
        raise ConnectorError('{0} must be a JSON object'.format(name))
    return value


def execute_api_request(config, params, connector_info):
    """Call any FortiFlex API endpoint with the configured credentials."""
    method = (params.get('method') or 'GET').upper()
    if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
        raise ConnectorError('Method must be GET, POST, PUT, PATCH or DELETE')
    endpoint = safe_endpoint(params.get('endpoint'))
    query = json_object(params.get('query_params'), 'Query Parameters')
    body = json_object(params.get('request_body'), 'Request Body')
    try:
        co = FortiFlex(config)
        token = co.validate_token(config, connector_info)
        headers = {'Content-Type': 'application/json', 'Authorization': token}
        data = json.dumps(body) if body is not None and method in ('POST', 'PUT', 'PATCH') else None
        response = requests.request(method, co.host + endpoint, headers=headers, verify=co.verify_ssl,
                                    data=data, params=query, timeout=60)
    except ConnectorError:
        raise
    except requests.exceptions.SSLError:
        raise ConnectorError('SSL certificate validation failed')
    except requests.exceptions.RequestException as err:
        raise ConnectorError('Request error: {0}'.format(err))
    if response.status_code >= 400:
        raise ConnectorError('HTTP {0} {1}: {2}'.format(response.status_code, response.reason, response.text))
    if not response.text:
        return {}
    try:
        return response.json()
    except ValueError:
        return {'response': response.text}


def _check_health(config, connector_info):
    try:
        return check(config, connector_info)
    except Exception as err:
        logger.exception("{0}".format(str(err)))
        raise ConnectorError("{0}".format(str(err)))


operations = {
    'get_programs': get_programs,
    'create_configuration': create_configuration,
    'get_configurations': get_configurations,
    'enable_configuration': enable_configuration,
    'disable_configuration': disable_configuration,
    'update_configuration': update_configuration,
    'create_vm_entitlements': create_vm_entitlements,
    'create_hardware_entitlements': create_hardware_entitlements,
    'get_entitlements': get_entitlements,
    'update_entitlements': update_entitlements,
    'stop_entitlement': stop_entitlement,
    'reactivate_entitlement': reactivate_entitlement,
    'transfer_entitlement': transfer_entitlement,
    'regenerate_token_for_vm': regenerate_token_for_vm,
    'get_point_usage_for_vm': get_point_usage_for_vm,
    'get_groups': get_groups,
    'get_group_next_token': get_group_next_token,
    'execute_api_request': execute_api_request
}

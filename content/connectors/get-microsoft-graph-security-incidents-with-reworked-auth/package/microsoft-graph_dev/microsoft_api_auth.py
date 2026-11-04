"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end
"""
import msal, base64
from urllib.parse import urljoin
from requests import request
from time import time, ctime
from datetime import datetime
from connectors.core.connector import get_logger, ConnectorError
from connectors.core.utils import update_connnector_config
from .constants import *
from integrations.crudhub import make_request

logger = get_logger('microsoft-graph')


class MicrosoftAuth:

    def __init__(self, config):
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.verify_ssl = config.get('verify_ssl')
        self.host = config.get("resource").strip("/")
        if self.host[:7] == "http://":
            self.host = self.host.replace('http://', 'https://')
        elif self.host[:8] == "https://":
            self.host = "{0}".format(self.host)
        else:
            self.host = "https://{0}".format(self.host)
        self.scope = "{0}/.default offline_access".format(self.host)
        tenant_id = config.get('tenant')
        self.auth_url = '{0}/{1}'.format(AUTH_URL, tenant_id)
        self.auth_type = config.get("auth_type")
        logger.debug("Auth Type: {}".format(self.auth_type))
        self.token_url = "{0}/{1}/oauth2/v2.0/token".format(AUTH_URL, tenant_id)
        if self.auth_type == AUTH_BEHALF_OF_USER:
            self.refresh_token = ""
            self.code = config.get("code")
            if not config.get("redirect_url"):
                self.redirect_url = DEFAULT_REDIRECT_URL
            else:
                self.redirect_url = config.get("redirect_url")
        if self.auth_type == CERTIFICATE_BASED_AUTH_TYPE:
            self.thumbprint = config.get('thumbprint')
            self.authority = urljoin(AUTH_URL, tenant_id)
            if isinstance(config.get('private_key', {}), dict) and config.get('private_key', {}).get('@type') == "File":
                private_key_file_iri = config.get('private_key', {}).get('@id')
                logger.debug('certificate file iri: {}'.format(private_key_file_iri))
                self.private_key = self.private_key = make_request(private_key_file_iri, 'GET')
                try:
                    # agent machine make_rest call to retrieve file data in encoded format
                    self.private_key = base64.b64decode(self.private_key, validate=True)
                except Exception as e:
                    pass

    def convert_ts_epoch(self, ts):
        datetime_object = datetime.strptime(ctime(ts), "%a %b %d %H:%M:%S %Y")
        return datetime_object.timestamp()

    def generate_token(self, REFRESH_TOKEN_FLAG):
        try:
            if self.auth_type == AUTH_USING_APP:
                resp = self.acquire_token_with_client_credentials()
            elif self.auth_type == CERTIFICATE_BASED_AUTH_TYPE:
                resp = self.generate_token_using_certificate()
            else:
                resp = self.acquire_token_on_behalf_of_user(REFRESH_TOKEN_FLAG)
            ts_now = time()
            resp['expiresOn'] = (ts_now + resp['expires_in']) if resp.get("expires_in") else None
            resp['accessToken'] = resp.get("access_token")
            resp.pop("access_token")
            return resp

        except Exception as err:
            logger.error("{0}".format(err))
            raise ConnectorError("{0}".format(err))

    def validate_token(self, connector_config, connector_info):
        ts_now = time()
        if not connector_config.get('accessToken'):
            logger.error('Error occurred while connecting server: Unauthorized')
            raise ConnectorError('Error occurred while connecting server: Unauthorized')
        expires = connector_config['expiresOn']
        expires_ts = self.convert_ts_epoch(expires)
        if ts_now > float(expires_ts):
            REFRESH_TOKEN_FLAG = True
            logger.info("Token expired at {0}".format(expires))
            self.refresh_token = connector_config["refresh_token"]
            token_resp = self.generate_token(REFRESH_TOKEN_FLAG)
            connector_config['accessToken'] = token_resp['accessToken']
            connector_config['expiresOn'] = token_resp['expiresOn']
            connector_config['refresh_token'] = token_resp.get('refresh_token')
            update_connnector_config(connector_info['connector_name'], connector_info['connector_version'],
                                     connector_config,
                                     connector_config['config_id'])

            return "Bearer {0}".format(connector_config.get('accessToken'))
        else:
            logger.info("Token is valid till {0}".format(expires))
            return "Bearer {0}".format(connector_config.get('accessToken'))

    def generate_token_using_certificate(self):
        try:
            app = msal.ConfidentialClientApplication(self.client_id, authority=self.authority,
                                                     client_credential={"thumbprint": self.thumbprint,
                                                                        "private_key": self.private_key})

            token_resp = app.acquire_token_for_client(scopes=[SCOPE])
            error_code = token_resp.get('error')
            if error_code:
                error_description = token_resp.get('error_description')
                raise ConnectorError(error_description)
            return token_resp

        except Exception as err:
            logger.exception("{0}".format(err))
            raise ConnectorError("{0}".format(err))

    def acquire_token_with_client_credentials(self):
        try:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": self.scope
            }
            res = request("POST", self.token_url, data=data, verify=self.verify_ssl)
            if res.status_code in [200, 204, 201]:
                return res.json()
            else:
                if res.text != "":
                    error_msg = ''
                    err_resp = res.json()
                    if err_resp and 'error' in err_resp:
                        failure_msg = err_resp.get('error_description')
                        error_msg = 'Response {0}: {1} \n Error Message: {2}'.format(res.status_code,
                                                                                     res.reason,
                                                                                     failure_msg if failure_msg else '')
                    else:
                        err_resp = res.text
                else:
                    error_msg = '{0}:{1}'.format(res.status_code, res.reason)
                raise ConnectorError(error_msg)
        except Exception as err:
            logger.error("{0}".format(err))
            raise ConnectorError("{0}".format(err))

    def acquire_token_on_behalf_of_user(self, REFRESH_TOKEN_FLAG):
        try:
            data = {
                "client_id": self.client_id,
                "scope": self.scope,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_url
            }

            if not REFRESH_TOKEN_FLAG:
                data["grant_type"] = AUTHORIZATION_CODE,
                data["code"] = self.code
            else:
                data['grant_type'] = REFRESH_TOKEN,
                data['refresh_token'] = self.refresh_token

            response = request("POST", self.token_url, data=data, verify=self.verify_ssl)
            if response.status_code in [200, 204, 201]:
                return response.json()

            else:
                if response.text != "":
                    error_msg = ''
                    err_resp = response.json()
                    if err_resp and 'error' in err_resp:
                        failure_msg = err_resp.get('error_description')
                        error_msg = 'Response {0}: {1} \n Error Message: {2}'.format(response.status_code,
                                                                                     response.reason,
                                                                                     failure_msg if failure_msg else '')
                    else:
                        err_resp = response.text
                else:
                    error_msg = '{0}:{1}'.format(response.status_code, response.reason)
                raise ConnectorError(error_msg)

        except Exception as err:
            logger.error("{0}".format(err))
            raise ConnectorError("{0}".format(err))


def check(config, connector_info):
    try:
        ms = MicrosoftAuth(config)
        if not 'accessToken' in config:
            token_resp = ms.generate_token(REFRESH_TOKEN_FLAG)
            config['accessToken'] = token_resp.get('accessToken')
            config['expiresOn'] = token_resp.get('expiresOn')
            config['refresh_token'] = token_resp.get('refresh_token')
            update_connnector_config(connector_info['connector_name'], connector_info['connector_version'], config,
                                     config['config_id'])
            return True
        else:
            token_resp = ms.validate_token(config, connector_info)
            return True
    except Exception as err:
        raise ConnectorError(str(err))

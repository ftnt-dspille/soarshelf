"""
Copyright start
MIT License
Copyright (c) 2023 Fortinet Inc
Copyright end
"""

from datetime import datetime
from time import time, ctime

import json
import requests
from connectors.core.connector import get_logger, ConnectorError
from connectors.core.utils import update_connnector_config

logger = get_logger('fortinet-fortiflex')


class FortiFlex:
    def __init__(self, config):
        self.username = config.get("username")
        self.password = config.get("password")
        self.client_id = config.get("client_id")
        self.verify_ssl = config.get('verify_ssl')
        self.host = config.get("server")
        self.refresh_token = config.get("refreshToken")

        # Normalize host URL
        if self.host[:7] == "http://":
            self.host = "https://{0}".format(self.host[7:])
        elif self.host[:8] == "https://":
            self.host = "{0}".format(self.host)
        else:
            self.host = "https://{0}".format(self.host)

    def convert_ts_epoch(self, ts):
        datetime_object = datetime.strptime(ctime(ts), "%a %b %d %H:%M:%S %Y")
        return datetime_object.timestamp()

    def get_new_token(self):
        """Generate a completely new token using username/password"""
        try:
            logger.info("Generating new token using username/password")
            token_resp = self._request_token(use_refresh_token=False)
            return self._process_token_response(token_resp)
        except Exception as err:
            logger.error("Error generating new token: {0}".format(err))
            raise ConnectorError("Error generating new token: {0}".format(err))

    def refresh_existing_token(self):
        """Try to refresh an existing token"""
        try:
            if not self.refresh_token:
                logger.warning("No refresh token available, falling back to new token")
                return self.get_new_token()

            logger.info("Attempting to refresh token")
            token_resp = self._request_token(use_refresh_token=True)
            return self._process_token_response(token_resp)
        except Exception as err:
            logger.warning("Token refresh failed: {0}. Falling back to new token.".format(err))
            return self.get_new_token()

    def _process_token_response(self, token_resp):
        """Process and normalize token response"""
        ts_now = time()
        result = {
            'expiresOn': (ts_now + token_resp['expires_in']) if token_resp.get("expires_in") else None,
            'accessToken': token_resp.get("access_token"),
            'refreshToken': token_resp.get("refresh_token")
        }

        # Update instance refresh token
        if token_resp.get("refresh_token"):
            self.refresh_token = token_resp.get("refresh_token")

        return result

    def _request_token(self, use_refresh_token=False):
        """Make the actual token request"""
        headers = {
            'Content-Type': 'application/json'
        }

        if use_refresh_token:
            if not self.refresh_token:
                raise ConnectorError("No refresh token available")

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id
            }
        else:
            data = {
                "username": self.username,
                "password": self.password,
                "client_id": self.client_id,
                "grant_type": "password"
            }

        # Log payload with sensitive data masked
        logger.debug("Payload: {0}".format(
            {k: '***' if k in ['password', 'refresh_token'] else v for k, v in data.items()}
        ))

        endpoint = 'https://customerapiauth.fortinet.com/api/v1/oauth/token/'
        logger.debug("Endpoint: {0}".format(endpoint))

        try:
            response = requests.post(endpoint, data=json.dumps(data), headers=headers, verify=self.verify_ssl, timeout=60)
            logger.debug("Response Status: {0}".format(response.status_code))

            if response.status_code in [200, 204, 201]:
                return response.json()
            else:
                self._handle_error_response(response)
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise ConnectorError(error_msg)

    def _handle_error_response(self, response):
        """Handle error responses from the API"""
        error_msg = ''
        if response.text:
            try:
                err_resp = response.json()
                if err_resp and 'error' in err_resp:
                    failure_msg = err_resp.get('error_description', '')
                    error_msg = 'Response {0}: {1} \nError Message: {2}'.format(
                        response.status_code, response.reason, failure_msg
                    )
                else:
                    error_msg = 'Response {0}: {1} \nError Message: {2}'.format(
                        response.status_code, response.reason, response.text
                    )
            except ValueError:
                error_msg = 'Response {0}: {1} \nError Message: {2}'.format(
                    response.status_code, response.reason, response.text
                )
        else:
            error_msg = 'Response {0}: {1}'.format(response.status_code, response.reason)

        logger.error(error_msg)
        raise ConnectorError(error_msg)

    def validate_token(self, connector_config, connector_info):
        """Validate and refresh token if needed"""
        try:
            ts_now = time()

            # Check if token exists
            if not connector_config.get('accessToken'):
                logger.error('Error occurred while connecting server: Unauthorized')
                raise ConnectorError('Error occurred while connecting server: Unauthorized')

            # Extract expiration time
            expires = connector_config['expiresOn']
            expires_ts = self.convert_ts_epoch(expires)

            # If token is expired, refresh it
            if ts_now > float(expires_ts):
                logger.info("Token expired at {0}".format(expires))

                # Update instance refresh token from config if needed
                if not self.refresh_token and connector_config.get('refreshToken'):
                    self.refresh_token = connector_config['refreshToken']

                # Try to refresh token first, fall back to new token if refresh fails
                try:
                    token_resp = self.refresh_existing_token()
                except Exception as err:
                    logger.warning(f"Token refresh failed: {str(err)}. Getting new token.")
                    token_resp = self.get_new_token()

                # Update config with new token info
                connector_config['accessToken'] = token_resp['accessToken']
                connector_config['expiresOn'] = token_resp['expiresOn']

                if token_resp.get('refreshToken'):
                    connector_config['refreshToken'] = token_resp['refreshToken']

                # Save updated config
                update_connnector_config(
                    connector_info['connector_name'],
                    connector_info['connector_version'],
                    connector_config,
                    connector_config['config_id']
                )

                return "Bearer {0}".format(connector_config.get('accessToken'))
            else:
                logger.info("Token is valid till {0}".format(expires))
                return "Bearer {0}".format(connector_config.get('accessToken'))
        except Exception as err:
            logger.error("Token validation error: {0}".format(str(err)))
            raise ConnectorError("Token validation error: {0}".format(str(err)))


def check(config, connector_info):
    """Health check function"""
    try:
        co = FortiFlex(config)

        # If no access token in config, generate a new one
        if 'accessToken' not in config:
            logger.info("No existing token found. Generating new token.")
            token_resp = co.get_new_token()
            config['accessToken'] = token_resp.get('accessToken')
            config['expiresOn'] = token_resp.get('expiresOn')
            config['refreshToken'] = token_resp.get('refreshToken')

            update_connnector_config(
                connector_info['connector_name'],
                connector_info['connector_version'],
                config,
                config['config_id']
            )
            return True
        else:
            # Validate existing token
            co.validate_token(config, connector_info)
            return True
    except Exception as err:
        logger.error(f"Health check failed: {str(err)}")
        raise ConnectorError(str(err))
import requests
from connectors.core.connector import get_logger, ConnectorError

logger = get_logger('horizon-ai')


class HorizonAPI:
    def __init__(self, config):
        self.api_key = config.get('api_token')
        self.verify_ssl = config.get('verify_ssl', True)
        self.base_url = config.get('server_url', 'https://api.horizon3ai.com').rstrip('/')
        self._jwt_token = None

    def _get_jwt_token(self):
        """Get JWT token using API key"""
        try:
            url = f"{self.base_url}/v1/auth"
            headers = {
                'Content-Type': 'application/json'
            }
            payload = {
                "key": self.api_key
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('token')  # Assuming token is in response
            else:
                raise ConnectorError(f"Authentication failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error getting JWT token: {str(e)}")
            raise ConnectorError(f"Authentication failed: {str(e)}")

    def _get_auth_token(self):
        """Get or refresh JWT token"""
        if not self._jwt_token:
            self._jwt_token = self._get_jwt_token()
        return self._jwt_token

    def make_request(self, query, variables=None):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._get_auth_token()}'
            }

            payload = {
                'query': query
            }
            if variables:
                payload['variables'] = variables

            response = requests.post(
                f"{self.base_url}/v1/graphql",
                headers=headers,
                json=payload,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    if any('authentication' in str(error).lower() for error in data['errors']):
                        # Token might be expired, try refreshing
                        self._jwt_token = None
                        # Retry request once with new token
                        return self.make_request(query, variables)
                    raise ConnectorError(f"GraphQL Error: {data['errors']}")
                # unpack data key if present
                if 'data' in data:
                    return data['data']
                else:
                    return data
            elif response.status_code == 401:
                # Token expired, try refreshing
                self._jwt_token = None
                # Retry request once with new token
                return self.make_request(query, variables)
            else:
                raise ConnectorError(f"HTTP Error: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
            raise ConnectorError(str(e))

    def check_health(self):
        """Check API health using hello query"""
        query = """
        query hello {
            hello
        }
        """
        try:
            result = self.make_request(query)
            if result.get('hello') == 'world!':
                return True
            else:
                logger.error(f"Unexpected hello query response: {result}")
                return False
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            raise ConnectorError(str(e))

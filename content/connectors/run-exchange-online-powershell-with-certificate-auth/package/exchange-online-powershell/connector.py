from connectors.core.connector import Connector
from connectors.core.connector import get_logger, ConnectorError
from .execute_powershell_command import execute_powershell_command
from .constants import LOGGER_NAME

logger = get_logger(LOGGER_NAME)

# Mapping the Action Name from the UI to the Python Function
supported_operations = {
    'execute_powershell_command': execute_powershell_command
}

class Exchange_online_powershell(Connector):

    def execute(self, config, operation, params, *args, **kwargs):
        logger.info('In execute() | Operation: {}'.format(operation))
        try:
            # Look up the function in our mapping
            operation_func = supported_operations.get(operation)
            if not operation_func:
                raise ConnectorError('Unsupported operation: {}'.format(operation))
            return operation_func(config, params)
        except Exception as err:
            logger.exception(err)
            raise ConnectorError(err)

    def check_health(self, config, *args, **kwargs):
        """
        Validates the connection to Exchange Online.
        We run a simple 'GGet-TenantAllowBlockListItems' to verify auth and module.
        """
        logger.info('In check_health()')
        try:
            # We reuse the existing logic but pass a benign command to verify auth
            health_check_params = {'powerShellCommand': 'Get-TenantAllowBlockListItems -ListType Sender | Where-Object { $_.Value -eq "test123@test.com" }'}
            execute_powershell_command(config, health_check_params)
            return True
        except Exception as err:
            logger.error('Health Check Failed: {}'.format(err))
            raise ConnectorError('Health Check Failed: {}'.format(err))
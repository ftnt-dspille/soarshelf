""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import time
from io import StringIO
from os.path import join

import paramiko
from connectors.core.connector import ConnectorError, get_logger
from connectors.cyops_utilities.builtins import download_file_from_cyops

from .constants import BUFFER_SIZE, INTERACTIVE_COMMAND_WAIT_TIME
from .utils import *
from .utils import _get_list_from_str_or_list

logger = get_logger('fortigatev2')


def read_file_data(params):
    try:
        file_meta = params.get('private_key')
        file_path = join('/tmp', download_file_from_cyops(file_meta.get('@id'))['cyops_file_path'])
        with open(file_path, 'rb') as attachment:
            file_content = attachment.read()
        return file_path, file_content
    except Exception as e:
        error_message = "Error While fetching {0} file data:\n{1}".format(params.get('private_key'), str(e))
        logger.exception(error_message)
        raise ConnectorError(error_message)


def _prepare_ssh_client(config, params):
    try:
        # extract host info
        host = config.get('address').strip('/')
        host = host.split('//')
        if len(host) == 2:
            host = host[1]
        else:
            host = host[0]
        port = params.get('port')
        username = params.get('username')
        password = params.get('password')

        rsa_key = None
        if params.get('private_key') and params.get('private_key').get('filename'):
            private_key_data = StringIO()
            file_path, file_data = read_file_data(params)
            private_key_data.write(str(file_data.decode('utf-8')))
            private_key_data.seek(0)
            rsa_key = paramiko.RSAKey.from_private_key(
                file_obj=private_key_data,
                password=password
            )
            logger.info('successfully created rsa key-pair')
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        client.load_system_host_keys()
        client.connect(host, port=port, username=username, password=password, pkey=rsa_key,
                       allow_agent=False, look_for_keys=False)
        return client
    except Exception as Err:
        raise ConnectorError(str(Err))


def execute_command(config, params):
    def execute_single_command(command):
        """Helper function to execute a single command and handle errors"""
        logger.debug(f"Executing cmd: {command}")
        streams = client.exec_command(cmd, timeout=params.get('timeout'), get_pty=True)
        stdin, stdout, stderr = streams
        error_str = stderr.read().decode('utf-8')
        if error_str:
            logger.error(f"Failed '{command}' command execution with error [{error_str}]. "
                         f"Commands executed successfully [{cmd_output}]")
            raise ConnectorError(
                f"Failed command execution with error [{error_str}]. Refer log file for more details")
        _result = stdout.read().decode('utf-8').strip()
        return _result

    client = _prepare_ssh_client(config, params)
    try:
        cmd_list = _get_list_from_str_or_list(params, 'cmd_list')
        if not cmd_list:
            return []
        cmd_output = []
        is_interactive = params.get('interactive', False)

        if is_interactive:
            # Interactive mode using invoke_shell
            channel = client.invoke_shell()
            try:
                for cmd in cmd_list:
                    channel.send(cmd + '\n')
                    time.sleep(INTERACTIVE_COMMAND_WAIT_TIME)
                    output = ''
                    while channel.recv_ready():
                        output += channel.recv(BUFFER_SIZE).decode('utf-8')
                    output_lines = [line.strip() for line in output.splitlines() if line.strip()]
                    cmd_output.append({"command": cmd, "output": output_lines})
            finally:
                channel.close()
        else:
            # Non-interactive command execution
            for cmd in cmd_list:
                result = execute_single_command(cmd)
                cmd_output.append({"command": cmd, "output": result.split("\r\n")})
                if "Command fail." in result:
                    logger.error(f"Command failed to execute: {cmd}")
                    raise ConnectorError(f"Command failed to execute: {cmd}")
        return cmd_output

    except Exception as Err:
        logger.error(str(Err))
        raise ConnectorError(str(Err))

    finally:
        client.close()

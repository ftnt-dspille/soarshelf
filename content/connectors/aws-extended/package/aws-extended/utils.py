""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import datetime
import boto3
import json, requests
from connectors.core.connector import get_logger, ConnectorError

logger = get_logger('aws')
TEMP_CRED_ENDPOINT = 'http://169.254.169.254/latest/meta-data/iam/security-credentials/{}'

def _change_date_format(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj

def _get_temp_credentials(config):
    try:
        aws_iam_role = config.get('aws_iam_role')
        url = TEMP_CRED_ENDPOINT.format(aws_iam_role)
        resp = requests.get(url=url, verify=False)
        if resp.ok:
            data = json.loads(resp.text)
            return data
        else:
            logger.error(str(resp.text))
            raise ConnectorError("Unable to validate the credentials")
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)

def _assume_a_role(data, params, aws_region):
    try:
        client = boto3.client('sts', region_name=aws_region, aws_access_key_id=data.get('AccessKeyId'),
                              aws_secret_access_key=data.get('SecretAccessKey'),
                              aws_session_token=data.get('Token'))
        role_arn = params.get('role_arn')
        session_name = params.get('session_name')
        response = client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        aws_region2 = params.get('aws_region')
        aws_session = boto3.session.Session(region_name=aws_region2,
                                            aws_access_key_id=response['Credentials']['AccessKeyId'],
                                            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                                            aws_session_token=response['Credentials']['SessionToken'])
        return aws_session
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def _get_session(config, params):
    try:
        config_type = config.get('config_type')
        assume_role = params.get("assume_role", False)
        if config_type == "IAM Role":
            if not assume_role:
                raise ConnectorError("Please Assume a Role to execute actions")

            aws_region = params.get('aws_region')
            data = _get_temp_credentials(config)
            aws_session = _assume_a_role(data, params, aws_region)
            return aws_session

        else:
            aws_access_key = config.get('aws_access_key')
            aws_region = config.get('aws_region')
            aws_secret_access_key = config.get('aws_secret_access_key')
            if assume_role:
                data = {
                    "AccessKeyId": aws_access_key,
                    "SecretAccessKey": aws_secret_access_key,
                    "Token": None
                }
                aws_session = _assume_a_role(data, params, aws_region)
            else:
                aws_session = boto3.session.Session(region_name=aws_region, aws_access_key_id=aws_access_key,
                                                aws_secret_access_key=aws_secret_access_key)
            return aws_session
    except Exception as Err:
        raise ConnectorError(Err)


def _get_aws_client(config, params, service):
    try:
        aws_session = _get_session(config, params)
        aws_client = aws_session.client(service)
        return aws_client
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def _get_policy_roles(aws_client, policy_role_list):
    try:
        roles_list = []
        for role in policy_role_list:
            new_role = {}
            new_role.update({'RoleName': role['RoleName']})
            aws_response = aws_client.get_role(RoleName=role['RoleName'])
            aws_response = json.dumps(aws_response, default=_change_date_format)
            aws_response = json.loads(aws_response)
            new_role.update({'RoleId': aws_response['Role']['RoleId']})
            new_role.update({'CreateDate': aws_response['Role']['CreateDate']})
            roles_list.append(new_role)
        return roles_list
    except Exception as Err:
        raise ConnectorError(Err)


def _get_group_policies(aws_client, group_policies_list):
    try:
        policies_list = []
        for policy in group_policies_list:
            new_policy = {}
            new_policy.update({'PolicyName': policy['PolicyName']})
            aws_response = aws_client.get_policy(PolicyArn=policy['PolicyArn'])
            aws_response = json.dumps(aws_response, default=_change_date_format)
            aws_response = json.loads(aws_response)
            new_policy.update({'PolicyId': aws_response['Policy']['PolicyId']})
            new_policy.update({'CreateDate': aws_response['Policy']['CreateDate']})
            if 'UpdateDate' in aws_response['Policy'].keys():
                new_policy.update({'UpdateDate': aws_response['Policy']['UpdateDate']})
            aws_response = aws_client.list_entities_for_policy(PolicyArn=policy['PolicyArn'])
            aws_response = json.dumps(aws_response, default=_change_date_format)
            aws_response = json.loads(aws_response)
            policy_role_list = aws_response['PolicyRoles']
            roles_list = _get_policy_roles(aws_client, policy_role_list)
            new_policy.update({'PolicyRoles': roles_list})
            policies_list.append(new_policy)
        return policies_list
    except Exception as Err:
        raise ConnectorError(Err)


def _get_user_groups_details(username, aws_client):
    try:
        group_list = aws_client.list_groups_for_user(UserName=username)
        group_list = json.dumps(group_list, default=_change_date_format)
        group_list = json.loads(group_list)
        groups = []
        for group in group_list['Groups']:
            temp_groups = {}
            temp_groups.update({'GroupName': group['GroupName'], 'GroupId': group['GroupId'], 'CreateDate': group['CreateDate']})
            aws_response = aws_client.list_attached_group_policies(GroupName=group['GroupName'])
            aws_response = json.dumps(aws_response, default=_change_date_format)
            aws_response = json.loads(aws_response)
            group_policies_list = aws_response['AttachedPolicies']
            policies_list = _get_group_policies(aws_client, group_policies_list)
            temp_groups.update({'GroupPolicies': policies_list})
            groups.append(temp_groups)
        return groups
    except Exception as Err:
        raise ConnectorError(Err)


def _is_mfa_device(aws_client, username):
    try:
        aws_response = aws_client.list_mfa_devices(UserName=username)
        aws_response = json.dumps(aws_response, default=_change_date_format)
        aws_response = json.loads(aws_response)
        if len(aws_response['MFADevices']) > 0:
            return "YES"
        else:
            return "NO"
    except Exception as Err:
        raise ConnectorError(Err)


def _get_user_policies(aws_client, username):
    try:
        aws_response = aws_client.list_attached_user_policies(UserName=username)
        aws_response = json.dumps(aws_response, default=_change_date_format)
        aws_response = json.loads(aws_response)
        return aws_response["AttachedPolicies"]
    except Exception as Err:
        raise ConnectorError(Err)


def _get_aws_resource(config, params, service):
    try:
        aws_session = _get_session(config,params)
        aws_resource = aws_session.resource(service)
        return aws_resource
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def _get_group_ids(group_list, security_groups):
    result = {}
    group_ids = []
    try:
        for group_name in group_list:
            result.update({str(group_name): "Security Group Name/ID Not Found in List of Security Groups"})
            for group in security_groups["SecurityGroups"]:
                if group["GroupName"] == group_name or group["GroupId"] == group_name:
                    group_ids.append(group["GroupId"])
                    result.update({str(group_name): "Security Group Name/ID Added Successfully"})
        return result, group_ids
    except Exception as Err:
        raise ConnectorError(Err)


def _get_list_from_str_or_list(params, parameter):
    try:
        parameter_list = params.get(parameter)
        if parameter_list:
            if isinstance(parameter_list, str):
                parameter_list = parameter_list.split(",")
                return parameter_list
            elif isinstance(parameter_list, list):
                return parameter_list
            else:
                raise ConnectorError("{0} Are Not in Format: {1}".format(parameter, parameter_list))
        else:
            return []
    except Exception as Err:
        raise ConnectorError(Err)

""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

from .utils import _get_aws_client, _get_aws_resource
from connectors.core.connector import get_logger, ConnectorError

logger = get_logger('aws')

def describe_network_acls(config, params):
    try:
        network_acl_ids = params.get("network_acl_ids", None)
        if network_acl_ids:
            if isinstance(network_acl_ids, str):
                network_acl_ids = network_acl_ids.split(',')
            elif isinstance(network_acl_ids, list):
                pass
            else:
                raise ConnectorError("Provide Network ACL IDs in proper format")
        filters = params.get('filters')
        aws_client = _get_aws_client(config, params, 'ec2')
        response = aws_client.describe_network_acls(Filters = filters if filters else [], DryRun = False,
                                                    NetworkAclIds = network_acl_ids if network_acl_ids else [])
        return response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def create_network_acl(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        response = aws_client.create_network_acl(VpcId = params.get('vpc_id'), DryRun = False)
        return response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def delete_network_acl(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        response = aws_client.delete_network_acl(NetworkAclId = params.get('network_acl_id'), DryRun = False)
        return response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def delete_network_acl_rule(config, params):
    try:
        if params.get("egress_rule") == "Inbound Rule":
            egress_rule = False
        else:
            egress_rule = True
        aws_client = _get_aws_client(config, params, 'ec2')
        response = aws_client.delete_network_acl_entry(NetworkAclId = params.get('network_acl_id'), Egress = egress_rule,
                                                       RuleNumber = params.get('rule_number'))
        return response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def add_network_acl_rule(config, params):
    try:
        egress_rule = params.get("egress_rule")
        if egress_rule == "Inbound Rule":
            egress_rule = False
        else:
            egress_rule = True
        aws_resource = _get_aws_resource(config, params, 'ec2')
        aws_nacl = aws_resource.NetworkAcl(params.get('network_acl_id'))
        ip_address = '{0}{1}'.format(params.get('ip_address'), '/32')
        # Protocol='-1' for Protocol Type 'ALL'
        result = aws_nacl.create_entry(CidrBlock=ip_address, Egress=egress_rule, Protocol="-1",
                                       RuleAction=params.get('rule_action'), RuleNumber= params.get('rule_number'))
        aws_nacl.reload()
        return result
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)
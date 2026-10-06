""" Copyright start
  Copyright (C) 2008 - 2025 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """

import json
import boto3
from .network_acl_actions import *
from .utils import _get_aws_client, _change_date_format, _is_mfa_device, _get_user_policies, _get_user_groups_details, \
    _get_temp_credentials, _get_list_from_str_or_list, _get_group_ids, _get_aws_resource

logger = get_logger('aws')
TEMP_CRED_ENDPOINT = 'http://169.254.169.254/latest/meta-data/iam/security-credentials/{}'


def describe_user(config, params):
    try:
        username = params.get('username')
        result = {}
        aws_client = _get_aws_client(config, params, 'iam')
        # User Details
        aws_response = aws_client.get_user(UserName=username)
        aws_response = json.dumps(aws_response, default=_change_date_format)
        aws_response = json.loads(aws_response)
        result.update({'UserName': aws_response['User']['UserName']})
        result.update({'UserID': aws_response['User']['UserId']})
        result.update({'CreateDate': aws_response['User']['CreateDate']})
        if 'PasswordLastUsed' in aws_response['User'].keys():
            result.update({'PasswordLastUsed': aws_response['User']['PasswordLastUsed']})
        # MFA Device
        result.update({'MFADevices': _is_mfa_device(aws_client, username)})
        # User Policies
        result.update({'UserPolicies': _get_user_policies(aws_client, username)})
        # Groups_Details
        result.update({'UserGroups': _get_user_groups_details(username, aws_client)})
        return result
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def check_health(config):
    try:
        config_type = config.get('config_type')
        if config_type == "IAM Role":
            if _get_temp_credentials(config):
                return True
            else:
                logger.error('Invalid Role. Please verify is the role is associated to your instance.')
                raise ConnectorError('Invalid Role. Please verify is the role is associated to your instance.')
        else:
            aws_access_key = config.get('aws_access_key')
            aws_region = config.get('aws_region')
            aws_secret_access_key = config.get('aws_secret_access_key')
            # aws_access_key, aws_region, aws_secret_access_key = _get_credentials_from_config(config)
            client = boto3.client('sts', region_name= aws_region, aws_access_key_id=aws_access_key,
                                  aws_secret_access_key=aws_secret_access_key)
            account_id = client.get_caller_identity()["Account"]
            if account_id:
                return True
            else:
                logger.error(
                    'Invalid Region name or Aws Access Key ID or Aws Secret Access Key')
                raise ConnectorError('Invalid Region name or Aws Access Key ID or Aws Secret Access Key')
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def describe_instance(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        aws_response = aws_client.describe_instances(InstanceIds=[params.get('instance_id')])
        # aws_response = aws_client.describe_instances(MaxResults=30)
        aws_response = json.dumps(aws_response, default=_change_date_format)
        return json.loads(aws_response)
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def detach_instance_from_autoscaling_group(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'autoscaling')
        autoscaling_group_name = params.get('autoscaling_group_name')
        instance_id_list = _get_list_from_str_or_list(params, "instance_id")
        aws_response = aws_client.describe_auto_scaling_instances(InstanceIds=instance_id_list)
        AutoScalingInstances_list = list(
            map(lambda group: group['AutoScalingGroupName'], aws_response['AutoScalingInstances']))
        # First Check Instance is Associate with Auto Scalding Group or Not.
        if len(aws_response['AutoScalingInstances']) <= 0 or autoscaling_group_name not in AutoScalingInstances_list:
            logger.info("Auto Scaling Instances is Empty or {0} is Not Connected to Group Name {1}".format(
                str(instance_id_list), autoscaling_group_name))
            raise ConnectorError("Auto Scaling Instances is Empty or {0} is Not Connected to Group Name {1}".format(
                str(instance_id_list), autoscaling_group_name))
        else:
            aws_response = aws_client.detach_instances(InstanceIds=instance_id_list,
                                                       AutoScalingGroupName=autoscaling_group_name,
                                                       ShouldDecrementDesiredCapacity=False)
            return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def attach_instance_to_auto_scaling_group(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'autoscaling')
        autoscaling_group_name = params.get('autoscaling_group_name')
        instance_id_list = _get_list_from_str_or_list(params, "instance_id")
        if autoscaling_group_name and instance_id_list:
            aws_response = aws_client.attach_instances(InstanceIds=instance_id_list,
                                                       AutoScalingGroupName=autoscaling_group_name)
        else:
            logger.exception("Auto Scaling Group: {0} or Instance ID: {1} is Empty".format(str(autoscaling_group_name),
                                                                                           str(instance_id_list)))
            raise ConnectorError(
                "Auto Scaling Group: {0} or Instance ID: {1} is Empty".format(str(autoscaling_group_name),
                                                                              str(instance_id_list)))
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def instance_api_termination(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        operation = params.get('operation')
        instance_id = params.get('instance_id')
        if operation == 'Disable':
            aws_response = aws_client.modify_instance_attribute(DryRun=False, InstanceId=instance_id,
                                                                Attribute='disableApiTermination', Value='true')
        else:
            aws_response = aws_client.modify_instance_attribute(DryRun=False, InstanceId=instance_id,
                                                                Attribute='disableApiTermination', Value='false')
        aws_response = json.dumps(aws_response, default=_change_date_format)
        return json.loads(aws_response)
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def snapshot_volume(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        aws_response = aws_client.create_snapshot(DryRun=False, VolumeId=params.get('volume_id'),
                                                  Description=params.get('description'))
        aws_response = json.dumps(aws_response, default=_change_date_format)
        return json.loads(aws_response)
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def add_security_group_to_instance(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        group_list = _get_list_from_str_or_list(params, "group_list")
        security_groups = aws_client.describe_security_groups()
        result, group_ids = _get_group_ids(group_list, security_groups)
        if group_ids != []:
            aws_response = aws_client.modify_instance_attribute(DryRun=False, InstanceId=params.get('instance_id'),
                                                                Groups=group_ids)
            aws_response = json.dumps(aws_response, default=_change_date_format)
            aws_response = json.loads(aws_response)
            result.update({"Response": aws_response})
            return result
        else:
            logger.exception(
                "Security Groups Not Found in List of Security Groups or Groups Are Empty: {}".format(str(group_ids)))
            raise ConnectorError(
                "Security Groups Not Found in List of Security Groups or Groups Are Empty: {}".format(str(group_ids)))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def add_tag_to_instance(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        aws_response = aws_client.create_tags(DryRun=False, Resources=[params.get('instance_id')], Tags=[
            {'Key': params.get('tag_key'),
             'Value': params.get('tag_value')
             }])
        aws_response = json.dumps(aws_response, default=_change_date_format)
        return json.loads(aws_response)
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def deregister_instance_from_elb(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'elb')
        elb_name = params.get('elb_name')
        instance_id_list = _get_list_from_str_or_list(params, "instance_id")
        if elb_name and instance_id_list:
            # Create List of dict For. Eg. [{'InstanceId': 'i-d6f6fae3',},{'InstanceId': 'i-207d9717',},{'InstanceId': 'i-afefb49b',},]
            instances = list(map(lambda instance_id: {'InstanceId': instance_id}, instance_id_list))
            response = aws_client.describe_instance_health(LoadBalancerName=elb_name, Instances=instances)
            if len(response['InstanceStates']) < 1:
                logger.exception(
                    'Instance ID {0} is Not Connected to ELB Name : {1}'.format(str(instance_id_list), elb_name))
                raise ConnectorError(
                    'Instance ID {0} is Not Connected to ELB Name : {1}'.format(str(instance_id_list), elb_name))
            else:
                return aws_client.deregister_instances_from_load_balancer(LoadBalancerName=elb_name,
                                                                          Instances=instances)
        else:
            logger.exception('ELB Name {0} or Instance ID {1} are Empty'.format(elb_name, str(instance_id_list)))
            raise ConnectorError('ELB Name {0} or Instance ID {1} are Empty'.format(elb_name, str(instance_id_list)))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def register_instance_to_elb(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'elb')
        elb_name = params.get('elb_name')
        instance_id_list = _get_list_from_str_or_list(params, "instance_id")
        # Create List of dict For. Eg. [{'InstanceId': 'i-d6f6fae3',},{'InstanceId': 'i-207d9717',},{'InstanceId': 'i-afefb49b',},]
        instances = list(map(lambda instance_id: {'InstanceId': instance_id}, instance_id_list))
        if elb_name and instance_id_list:
            return aws_client.register_instances_with_load_balancer(LoadBalancerName=elb_name, Instances=instances)
        else:
            logger.exception('ELB Name {0} or Instance ID {1} are Empty'.format(elb_name, str(instance_id_list)))
            raise ConnectorError('ELB Name {0} or Instance ID {1} are Empty'.format(elb_name, str(instance_id_list)))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def start_instance(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        instance = aws_resource.Instance(params.get('instance_id'))
        aws_response = instance.start(DryRun=False, AdditionalInfo=str(params.get('description')))
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def stop_instance(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        instance = aws_resource.Instance(params.get('instance_id'))
        aws_response = instance.stop(DryRun=False, Force=True)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def reboot_instance(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        instance = aws_resource.Instance(params.get('instance_id'))
        aws_response = instance.reboot(DryRun=False)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def terminate_instance(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        instance = aws_resource.Instance(params.get('instance_id'))
        aws_response = instance.terminate(DryRun=False)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def get_details_for_all_images(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        logger.info('params are = {}'.format(params))
        logger.info('filetr is  ={}'.format(params.get('filters', [])))
        aws_response = aws_client.describe_images(ExecutableUsers=params.get('executable_users')
        if params.get('executable_users') else [],Filters=params.get('filters') if params.get('filters') else [],
                                                  ImageIds=params.get('image_ids') if params.get('image_ids') else [],
                                                  Owners=params.get('owners') if params.get('owners') else [])
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def delete_volume(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        volume = aws_resource.Volume(params.get('volume_id'))
        aws_response = volume.delete(DryRun=False)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def attach_volume(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        volume = aws_resource.Volume(params.get('volume_id'))
        aws_response = volume.attach_to_instance(Device=params.get('device_name'), InstanceId=params.get('instance_id'),
                                                 DryRun=False)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def detach_volume(config, params):
    try:
        aws_resource = _get_aws_resource(config, params, 'ec2')
        volume = aws_resource.Volume(params.get('volume_id'))
        aws_response = volume.detach_from_instance(Device=params.get('device_name'), Force=params.get('force'),
                                                   InstanceId=params.get('instance_id'), DryRun=False)
        return aws_response
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def launch_instance(config, params):
    try:
        input_params = {
            "ImageId": params.get('image_id'),
            "InstanceType": params.get('instance_type'),
            "MaxCount": params.get('maxcount'),
            "MinCount": params.get('mincount'),
            "SubnetId": params.get('subnetid'),
            "DryRun": False
        }
        aws_resource = _get_aws_resource(config, params, 'ec2')
        TagSpecifications = [
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "purpose", "Value": str(params.get('purpose'))},
                    {"Key": "customer_name", "Value": str(params.get('customer_name'))},
                    {"Key": "terminate_by_date", "Value": str(params.get('terminate_by_date'))}
                ]
            }
        ]
        BlockDeviceMappings = [
            {
                "DeviceName": params.get('device_name'),
                "Ebs": {
                    "DeleteOnTermination": params.get('delete_on_termination')
                }
            }
        ]
        input_params.update({"BlockDeviceMappings": BlockDeviceMappings})
        input_params.update({"TagSpecifications": TagSpecifications}),
        security_groups_list = _get_list_from_str_or_list(params, "security_groups_list")
        if security_groups_list:
            input_params.update({"SecurityGroupIds": security_groups_list})
        aws_response = aws_resource.create_instances(**input_params)
        return aws_response[0].describe_attribute(Attribute='instanceType', DryRun=False)
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def authorize_egress(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.authorize_security_group_egress(GroupId=params.get('security_group_id'), DryRun=False,
                                                          IpPermissions=params.get('ip_permissions'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def authorize_ingress(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.authorize_security_group_ingress(GroupId=params.get('security_group_id'), DryRun=False,
                                                           IpPermissions=params.get('ip_permissions'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def revoke_egress(config, params):
    try:
        aws_client = _get_aws_resource(config, params, 'ec2')
        security_group = aws_client.SecurityGroup(params.get('security_group_id'))
        return security_group.revoke_egress(GroupId=params.get('security_group_id'), DryRun=False,
                                            IpPermissions=params.get('ip_permissions'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def revoke_ingress(config, params):
    try:
        aws_client = _get_aws_resource(config, params, 'ec2')
        security_group = aws_client.SecurityGroup(params.get('security_group_id'))
        return security_group.revoke_ingress(GroupId=params.get('security_group_id'), DryRun=False,
                                             IpPermissions=params.get('ip_permissions'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def get_security_groups(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.describe_security_groups()
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def create_security_group(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.create_security_group(GroupName=params.get('group_name'),
                                                Description=params.get('description'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def get_details_of_security_group(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.describe_security_groups(GroupIds=[params.get('security_group_id')])
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


def delete_security_group(config, params):
    try:
        aws_client = _get_aws_client(config, params, 'ec2')
        return aws_client.delete_security_group(GroupId=params.get('security_group_id'))
    except Exception as Err:
        logger.exception(Err)
        raise ConnectorError(Err)


aws_operations = {
    'describe_instance': describe_instance,
    'attach_instance_to_auto_scaling_group': attach_instance_to_auto_scaling_group,
    'detach_instance_from_autoscaling_group': detach_instance_from_autoscaling_group,
    'instance_api_termination': instance_api_termination,
    'add_security_group_to_instance': add_security_group_to_instance,
    'add_tag_to_instance': add_tag_to_instance,
    'deregister_instance_from_elb': deregister_instance_from_elb,
    'register_instance_to_elb': register_instance_to_elb,
    'start_instance': start_instance,
    'stop_instance': stop_instance,
    'terminate_instance': terminate_instance,
    'launch_instance': launch_instance,
    'reboot_instance': reboot_instance,

    'describe_user': describe_user,

    'snapshot_volume': snapshot_volume,
    'attach_volume': attach_volume,
    'detach_volume': detach_volume,
    'delete_volume': delete_volume,

    'get_details_for_all_images': get_details_for_all_images,

    'authorize_egress': authorize_egress,
    'revoke_egress': revoke_egress,
    'authorize_ingress': authorize_ingress,
    'revoke_ingress': revoke_ingress,

    'get_security_groups': get_security_groups,
    'delete_security_group': delete_security_group,
    'create_security_group': create_security_group,
    'get_details_of_security_group': get_details_of_security_group,

    'describe_network_acls': describe_network_acls,
    'create_network_acl': create_network_acl,
    'delete_network_acl': delete_network_acl,
    'delete_network_acl_rule':delete_network_acl_rule,
    'add_network_acl_rule': add_network_acl_rule,
}


# --- aws-extended overlay -------------------------------------------------
# Adds the generic passthrough operations and repairs IpProtocol coercion on
# the security-group rule operations. See overlay/generic_action.py.
from .generic_action import (  # noqa: E402
    generic_action,
    generic_resource_action,
    wrap_ip_permissions,
)

aws_operations['generic_action'] = generic_action
aws_operations['generic_resource_action'] = generic_resource_action

for _sg_op in ('authorize_ingress', 'authorize_egress', 'revoke_ingress', 'revoke_egress'):
    if _sg_op in aws_operations:
        aws_operations[_sg_op] = wrap_ip_permissions(aws_operations[_sg_op])
# --- end aws-extended overlay ---------------------------------------------

import boto3
import botocore
import json
import config
import res.utils as utils
import res.glob  as glob

# =======================================================================================================================
#
#  Supported services   : API Gateway (simple), VPC (in 'compute' module), Route 53, CloudFront
#  Unsupported services : Direct Connect, AWS App Mesh, AWS Cloud Map, Global Accelerator
#
# =======================================================================================================================


#  ------------------------------------------------------------------------
#
#    API Gateway (REST) 
#
#  ------------------------------------------------------------------------

def get_apigateway_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns API Gateway (rest) inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: API Gateway inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/apigateway.html
        ..todo:: add --> plans, api keys, custom domain names, client certificates, vpc links
    """
    
    return glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "apigateway", 
        aws_region = "all", 
        function_name = "get_rest_apis", 
        key_get = "items",
        pagination = True
    )


#  ------------------------------------------------------------------------
#
#    API Gateway V2 (HTTP)
#
#  ------------------------------------------------------------------------

def get_apigatewayv2_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns API Gateway v2 (http) inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: API Gateway inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/apigatewayv2.html
        ..todo:: add --> plans, api keys, custom domain names, client certificates, vpc links
    """

    return glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "apigatewayv2", 
        aws_region = "all", 
        function_name = "get_apis", 
        key_get = "Items",
        pagination = True
    )


#  ------------------------------------------------------------------------
#
#    CloudFront
#
#  ------------------------------------------------------------------------

def get_cloudfront_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns cloudfront inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: Cloudfront inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/cloudfront.html

    """
    
    return glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "cloudfront", 
        aws_region = "global", 
        function_name = "list_distributions", 
        key_get = "Items",
        #key_get = "DistributionList",
        pagination = True
    )


#  ------------------------------------------------------------------------
#
#    Route 53
#
#  ------------------------------------------------------------------------

def get_route53_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns route 53 inventory, partial.

        Traffic policies are not detailed because the detail function needs 2 arguments.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: route 53 inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/route53.html

    """
    
    inventory = {}
    
    inventory['zones'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "route53", 
        aws_region = "global", 
        function_name = "list_hosted_zones_by_name", 
        key_get = "HostedZones",
        detail_function = "list_resource_record_sets", 
        join_key = "Id", 
        detail_join_key = "HostedZoneId", 
        detail_get_key = "ResourceRecordSets",
        pagination = True
    )

    inventory['traffic-policies'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "route53", 
        aws_region = "global", 
        function_name = "list_traffic_policies", 
        key_get = "TrafficPolicySummaries",
        pagination = True
    )

    inventory['domains'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "route53domains", 
        aws_region = "all", 
        function_name = "list_domains", 
        key_get = "Domains"
    )

    return inventory



#  ------------------------------------------------------------------------
#
#    Elastic Load Balancer
#
#  ------------------------------------------------------------------------

def get_elb_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns ELB inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: ELB inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/elb.html

    """

    service = "elb"
    lb_list = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = service,
        aws_region = "all",
        function_name = "describe_load_balancers",
        key_get = "LoadBalancerDescriptions",
        pagination = True
    )

    return _retrieve_lb_tags(oId, profile, service, lb_list)



#  ------------------------------------------------------------------------
#
#    Elastic Load Balancer v2
#
#  ------------------------------------------------------------------------

def get_elbv2_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns ELBv2 inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: ELBv2 inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/elbv2.html

    """
    service = "elbv2"
    lb_list = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = service, 
        aws_region = "all", 
        function_name = "describe_load_balancers", 
        key_get = "LoadBalancers",
        pagination = True
    )

    return _retrieve_lb_tags(oId, profile, service, lb_list)


def _retrieve_lb_tags(oId, profile, service, lb_list):
    if len(lb_list) > 0:
        
        lbs_by_region = {}

        for lb in lb_list:
            if lb['RegionName'] not in lbs_by_region:
                lbs_by_region[lb['RegionName']] = []
            lbs_by_region[lb['RegionName']].append(lb)

        for region, lbs in lbs_by_region.items():

            session = utils.get_boto_session(oId, profile)
            lb_client = session.client(service, region_name=region)
            if service == "elb":
                join_key = "LoadBalancerName"
                tag_key = join_key
                resp = lb_client.describe_tags(LoadBalancerNames=[lb[join_key] for lb in lbs])
            elif service == "elbv2":
                join_key = "LoadBalancerArn"
                tag_key = "ResourceArn"
                resp = lb_client.describe_tags(ResourceArns=[lb[join_key] for lb in lbs])
            else:
                break

            region_tags = resp.get('TagDescriptions')
            for lb_tags in region_tags:
                for lb in lbs:
                    if lb[join_key] == lb_tags[tag_key]:
                        lb["Tags"] = lb_tags.get("Tags")
            
            lb_list.extend(lbs)

    return lb_list
#
# Hey, doc: we're in a module!
#
if (__name__ == '__main__'):
    print('Module => Do not execute')
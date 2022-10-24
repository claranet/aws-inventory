import boto3
import botocore
import json
import config
import res.utils as utils
import res.glob  as glob

# =======================================================================================================================
#
#  Supported services   : RDS, DynamoDB, ElastiCache, Neptune, Amazon Redshift, Amazon QLDB, DocumentDB
#                           Amazon MemoryDB for Redis, Amazon Timestream (but with a bug)
#  Unsupported services : Amazon Keyspaces
#
# =======================================================================================================================

#  ------------------------------------------------------------------------
#
#    RDS 
#
#  ------------------------------------------------------------------------

def get_rds_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns RDS inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: RDS inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/rds.html

    """

    rds_inventory = {}

    rds_inventory['rds-instances'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "rds", 
        aws_region = "all", 
        function_name = "describe_db_instances", 
        key_get = "DBInstances",
        pagination = True
    )

    rds_inventory['rds-clusters'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "rds",
        aws_region = "all",
        function_name = "describe_db_clusters",
        key_get = "DBClusters",
        pagination = True
    )

    return rds_inventory


#  ------------------------------------------------------------------------
#
#    DynamoDB 
#
#  ------------------------------------------------------------------------

def get_dynamodb_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns dynamoDB inventory

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: dynamoDB inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/dynamodb.html

    """

    inventory = []
    service = "dynamodb"

    table_list = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = service, 
        aws_region = "all", 
        function_name = "list_tables", 
        key_get = "TableNames",
        detail_function = "describe_table", 
        join_key = "TableName", 
        detail_join_key = "TableName", 
        detail_get_key = "Table",
        pagination = True
    )

    if len(table_list) > 0:

        tables_by_region = utils.resources_by_region(table_list)

        for region, tables in tables_by_region.items():

            session = utils.get_boto_session(oId, profile)
            dynamodb = session.client(service, region_name=region)

            for table in tables:

                table["Tags"] = dynamodb.list_tags_of_resource(ResourceArn=table["Table"]["TableArn"]).get("Tags", [])
                inventory.append(table)

    return inventory


#  ------------------------------------------------------------------------
#
#    Neptune 
#
#  ------------------------------------------------------------------------

def get_neptune_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns neptune inventory (instances & clusters). Instances are listed in RDS inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: neptune inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/neptune.html

    """

    neptune_inventory = {}

    neptune_inventory['clusters'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "neptune", 
        aws_region = "all", 
        function_name = "describe_db_clusters", 
        key_get = "DBClusters"
    )

    return neptune_inventory
   

#  ------------------------------------------------------------------------
#
#    ElastiCache
#
#  ------------------------------------------------------------------------

def get_elasticache_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns elasticache inventory (instances & clusters). Instances are listed in RDS inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: elasticache inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html

    """

    elasticache_inventory = {}

    elasticache_inventory['cache-clusters'] = get_elasticache_inventory_clusters(oId, profile, boto3_config, selected_regions)

    elasticache_inventory['reserved-cache-nodes'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "elasticache", 
        aws_region = "all", 
        function_name = "describe_reserved_cache_nodes", 
        key_get = "ReservedCacheNodes",
        pagination = True
    )

    return elasticache_inventory


def get_elasticache_inventory_clusters(oId, profile, boto3_config, selected_regions):

    """
        Returns elasticache inventory (clusters only).

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: elasticache inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html

    """
    inventory = []
    service = "elasticache"

    cluster_list = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = service, 
        aws_region = "all", 
        function_name = "describe_cache_clusters", 
        key_get = "CacheClusters",
        pagination = True
    )

    if len(cluster_list) > 0:

        clusters_by_region = utils.resources_by_region(cluster_list)

        for region, clusters in clusters_by_region.items():

            session = utils.get_boto_session(oId, profile)

            resourcegroupstaggingapi = session.client(
                "resourcegroupstaggingapi", region_name=region
            )
            for cluster in clusters:
                response = resourcegroupstaggingapi.get_resources(
                    ResourceARNList=[cluster["ARN"]]
                )
                resource_tag_mapping_list = response["ResourceTagMappingList"]
                if len(resource_tag_mapping_list) > 1:
                    config.logger.warn(
                        "More than one resource was return by AWS API, taking first into account"
                    )
                if len(resource_tag_mapping_list) > 0:
                    cluster["TagList"] = resource_tag_mapping_list[0].get("Tags", [])

                inventory.append(cluster)

    return inventory
   

#  ------------------------------------------------------------------------
#
#    Redshift
#
#  ------------------------------------------------------------------------

def get_redshift_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns redshift inventory (instances & clusters). Instances are listed in RDS inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: redshift inventory
        :rtype: json

        ..note:: http://boto3.readthedocs.io/en/latest/reference/services/redshift.html

    """

    redshift_inventory = {}

    redshift_inventory['clusters'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "redshift", 
        aws_region = "all", 
        function_name = "describe_clusters", 
        key_get = "Clusters",
        pagination = True
    )

    redshift_inventory['reserved-nodes'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "redshift", 
        aws_region = "all", 
        function_name = "describe_reserved_nodes", 
        key_get = "ReservedNodes",
        pagination = True
    )

    return redshift_inventory


#  ------------------------------------------------------------------------
#
#    Amazon QLDB 
#
#  ------------------------------------------------------------------------

def get_qldb_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns Amazon QLDB inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: QLDB inventory
        :rtype: json

        ..note:: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/qldb.html

    """

    qldb_inventory = {}

    qldb_inventory['ledgers'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "qldb", 
        aws_region = "all", 
        function_name = "list_ledgers", 
        key_get = "Ledgers",
        detail_function = "describe_ledger",
        join_key = "Name",
        detail_join_key = "Name",
        detail_get_key = "",
        pagination = False,
        pagination_detail = False,
    )

    return qldb_inventory


#  ------------------------------------------------------------------------
#
#    DocumentDB 
#
#  ------------------------------------------------------------------------

def get_docdb_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns Amazon DocumentDB (docdb) inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: DocumentDB inventory
        :rtype: json

        ..note:: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/docdb.html

    """

    docdb_inventory = {}

    # Looking for instances

    docdb_inventory['instances'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "docdb", 
        aws_region = "all", 
        function_name = "describe_db_instances", 
        key_get = "DBInstances",
        pagination = True
    )

    # Looking for clusters

    docdb_inventory['clusters'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "docdb", 
        aws_region = "all", 
        function_name = "describe_db_clusters", 
        key_get = "DBClusters",
        pagination = True
    )

    return docdb_inventory


#  ------------------------------------------------------------------------
#
#    MemoryDB 
#
#  ------------------------------------------------------------------------

def get_memorydb_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns MemoryDB clusters (memorydb) inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: MemoryDB clusters inventory
        :rtype: json

        ..note:: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/memorydb.html

    """

    inventory = {}

    inventory['clusters'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "memorydb", 
        aws_region = "all", 
        function_name = "describe_clusters", 
        key_get = "Clusters"
    )

    return inventory


#  ------------------------------------------------------------------------
#
#    Timestream 
#
#  ------------------------------------------------------------------------

def get_timestream_inventory(oId, profile, boto3_config, selected_regions):

    """
        Returns Timestream databases inventory.

        :param oId: ownerId (AWS account)
        :type oId: string
        :param profile: configuration profile name used for session
        :type profile: string

        :return: Timestream databases inventory
        :rtype: json

        ..note:: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/timestream-write.html

    """

    inventory = {}

    inventory['databases'] = glob.get_inventory(
        ownerId = oId,
        profile = profile,
        boto3_config = boto3_config,
        selected_regions = selected_regions,
        aws_service = "timestream-write", 
        aws_region = "all", 
        function_name = "list_databases", 
        key_get = "Databases",
        pagination = False,
    )

    return inventory


#
# Hey, doc: we're in a module!
#
if (__name__ == '__main__'):
    print('Module => Do not execute')
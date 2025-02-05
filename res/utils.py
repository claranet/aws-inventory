import boto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError, ProfileNotFound
import pprint
import logging
import json
import datetime
import time
import dateutil
from dateutil.tz import tzutc
import config
import argparse
import config

#
#  Useful functions
#

# --- AWS Regions 

#  ------------------------------------------------------------------------
#     Get all the AWS regions (dynamically, only "not opt-in" regions
#     This function could be called in several modules
#  ------------------------------------------------------------------------

def get_aws_regions(profile_name):

    # Colors may be used in the future for display inventory. The color file must contains more colors than the number of regions.

    with open("color.json","r") as f_col:
        color_list = json.load(f_col)
    colors = color_list["colors"]
        
    # We get the regions list through EC2.

    session = boto3.Session(profile_name=profile_name, region_name="us-east-1")
    client = session.client("ec2")

    regions = client.describe_regions(AllRegions=False)
    region_list = regions["Regions"]

    # We assign one color to each region

    for color, region in zip(colors, region_list):
        region['color'] = color
        
        # Looking for AZ? Why not? But only if you have the rights to...
        current_region = region['RegionName']
        if (region['OptInStatus'] != 'not-opted-in'):
            session = boto3.Session(profile_name=profile_name)
            client = session.client("ec2", region_name=current_region)
            current_zones = client.describe_availability_zones()
            region['zones'] = current_zones['AvailabilityZones']


    config.logger.info(regions)

    return regions["Regions"]


def display(ownerId, function, region_name, function_name):

    """
        Formatting display output, with progression (in %)
    """

    progression = config.nb_units_done / config.nb_units_todo * 100
    config.logger.debug(
        config.display.format(
            ownerId, progression, function, region_name, function_name, " " * 20
        ),
    )
    return

def progress(region_name):

    """
        Shows job progression, depending on services passed in arguments
    """

    if (region_name == "global"):
        config.nb_units_done = config.nb_units_done + config.nb_regions
    else:        
        config.nb_units_done = config.nb_units_done + 1
    config.logger.debug("config.nb_units_done {} config.nb_units_todo {}".format(config.nb_units_done, config.nb_units_todo))        
    return


def check_arguments(arguments):

    """
        Check if the arguments (in command line) are known. If not, we raise an exception.

        We also look for the debug level. If we found it, we adjust the log level but we don't include it in the service list.

        :param arguments: list of arguments
        :type arguments: list

        :return: profile to use (can be None or 'default')
        :rtype: string
        :return: services to inventory
        :rtype: array of strings
        :return: config object to use with boto3
        :rtype: botocore.config.Config
    """   

    parser = argparse.ArgumentParser(description='AWS inventory may have arguments. More information at https://github.com/janiko71/aws-inventory/wiki/How-to-use-it%3F.')

    help_str = ""
    for arg_elem in config.SUPPORTED_COMMANDS:
        help_str = help_str + arg_elem + ", "
    help_str = help_str[:-2]

    #
    # Declaring allowed parameters
    #

    parser.add_argument('--profile', required=False, type=str, default="default", help="Name of the AWS profile to use in {USER_DIR}\.aws\credentials")
    parser.add_argument('--log', required=False, type=str, default="error", help="Log level for output (debug, info, warning, error")
    parser.add_argument('--regions', required=False, type=str, default="", nargs='+', help="Selected regions for inventory, in string format")
    parser.add_argument('--services', required=False, type=str, default="", nargs='+', help="List of AWS services you want to check.\n" \
        "Must be one or many within this list: " + help_str)
    
    args = parser.parse_args()

    profile    = str(args.profile).lower()
    log_level  = str(args.log).lower()

    #
    # Checking log argument
    #

    if (log_level == "debug"):
        config.logger.setLevel(logging.DEBUG)
    elif (log_level == "info"):
        config.logger.setLevel(logging.INFO)
    elif (log_level == "warning"):
        config.logger.setLevel(logging.WARNING)
    elif (log_level == "error"):
        config.logger.setLevel(logging.ERROR)
    else:
        print('Unknown argument for log level [' + args.log + ']')
        exit(1)

    #
    # Verifying profile name. In the case of a CloudShell environment, please
    # note that there is no default profile.
    #

    if ("default" == profile):
        profile = None

    try:
        session = boto3.Session(profile_name=profile)
    except ProfileNotFound as e:
        config.logger.error("Profile name [" + profile + "] not found, please check.")
        exit(1)

    # 
    # For the support of CloudShell, we need to adjust retries settings
    #

    boto3_config = Config(
        retries = {
            'max_attempts': 5,
            'mode': 'standard'
        }
    )

    #
    # Is a list of services provided? If yes, are they in the list of supported services?
    #

    services = []

    for arg in args.services:
        str_service = str(arg).lower()
        if (str_service not in config.SUPPORTED_COMMANDS) and (
            str_service not in config.SUPPORTED_PARAMETERS
        ):
            config.logger.error("Unknown argument [" + arg + "]")
            exit(1)
        else:
            services.append(str_service)

    #
    # Is the regions parameter provided? If yes, we check if it's one region or a list, and if they are existing regions

    selected_regions = []

    # --- We need the AWS Regions list at this point
    config.regions = get_aws_regions(profile)
    config.nb_regions = len(config.regions)

    known_regions_list = []
    for region in config.regions:
        region_name = region['RegionName']
        known_regions_list.append(region_name)

    for arg in args.regions:
        region_name = str(arg).lower()
        if region_name not in known_regions_list:
            config.logger.error("Unknown region [" + region_name + "]")
            exit(1)
        else:
            selected_regions.append(region_name)

    return profile, services, boto3_config, selected_regions


def get_ownerID(profile):

    """
        Get owner ID of the AWS account we are working on

        :return: owner ID
        :rtype: string
    """  

    session = boto3.Session(profile_name=profile)
    sts = session.client('sts')
    identity = sts.get_caller_identity()
    ownerId = identity['Account']
    return ownerId


def datetime_converter(dt):

    """
        Converts a python datetime object (returned by AWS SDK) into a readable and SERIALIZABLE string

        :param dt: datetime
        :type dt: datetime

        :return: datetime in a good format
        :rtype: str
    """

    if isinstance(dt, datetime.datetime):
        return dt.__str__()  


def json_datetime_converter(json_text):

    """
        Parses a json object and converts all datetime objects (returned by AWS SDK) into str objects

        :param json_text: json with datetime objects
        :type json_text: json

        :return: json with date in string format
        :rtype: json
    """

    return json.dumps(json_text, default = datetime_converter)      


def get_boto_session(account_id, profile):
    if hasattr(config, 'sessions') and account_id in config.sessions.keys():
        session = config.sessions[account_id]
        config.logger.debug('Use provided Boto3 {} for account {}'.format(session, account_id))
    else: 
        session = boto3.Session(profile_name=profile)
        config.logger.debug('Create new Boto3 session for account {} and profile {}'.format(account_id, profile))
    return session


def resources_by_region(resources):
    """Create a dict where each key is a region and its value a list of resources."""
    resources_by_region = {}
    for resource in resources:
        resource_region = resource['RegionName']
        if resource_region not in resources_by_region:
            resources_by_region[resource_region] = []
        resources_by_region[resource_region].append(resource)
    return resources_by_region


def chunks_list(lst, size):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

#
# Hey, doc: we're in a module!
#
if (__name__ == '__main__'):
    print('Module => Do not execute')

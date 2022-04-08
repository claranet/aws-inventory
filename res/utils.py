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
from botocore import credentials
import botocore.session
import boto3
import os

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

    regions = client.describe_regions(AllRegions=True)
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

    progression = (config.nb_units_done / config.nb_units_todo * 100)
    print(config.display.format(ownerId, progression, function, region_name, function_name, " "*20), end="\r", flush=True)
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
        print("Profile name [" + profile + "] not found, please check.")
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
        if (str_service not in config.SUPPORTED_COMMANDS) and (str_service not in config.SUPPORTED_PARAMETERS):
            print('Unknown argument [' + arg + ']')
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
        if (region_name not in known_regions_list):
            print('Unknown region [' + region_name + ']')
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

def create_session(account_id, role):
    """Create boto session using the IAM Role or the profile name

    Args:
        account_id (str): the AWS account id
        role (str): The IAM role name or the profile name

    Returns:
        botocore.session: boto3 session
    """
    try:
        session = boto3.Session(profile_name=role) 
        return session
    except botocore.exceptions.ProfileNotFound as ex:
        # By default the cache path is ~/.aws/boto/cache
        cli_cache = os.path.join(os.path.expanduser('~'),'.cache')

        # Construct botocore session with cache
        default_session = botocore.session.get_session()
        default_session.get_component('credential_provider').get_provider('assume-role').cache = credentials.JSONFileCache(cli_cache)

        # Create boto3 client from session
        sts_client = boto3.Session(botocore_session=default_session).client('sts')

        # Create session
        assumed_role_object=sts_client.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{role}",
        RoleSessionName=f"AssumeRoleSession{account_id}",
        )
        credentials_array = (assumed_role_object["Credentials"]["AccessKeyId"], assumed_role_object["Credentials"]["SecretAccessKey"], assumed_role_object["Credentials"]["SessionToken"])
        
        return boto3.Session(botocore_session=default_session,
            aws_access_key_id=credentials_array[0],
            aws_secret_access_key=credentials_array[1],
            aws_session_token=credentials_array[2]
        )
#
# Hey, doc: we're in a module!
#
if (__name__ == '__main__'):
    print('Module => Do not execute')
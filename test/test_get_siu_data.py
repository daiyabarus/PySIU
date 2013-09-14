#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__version__ = 'R12.2D09'
__date__ = '06/06/2013 16:47:46'


# Description     : Run a batch of generic commands against SIUs, with multiprocess.
# Usage           : python scmty_get_siu_data.py -h
# Note            : It has to be run within a proper virtualenv


import datetime
import logging.handlers
import os
import pprint
import socket
import sys
import time
from optparse import OptionParser
import yaml

from pyoss import app_logger
from pyoss import oss_utils
from pyoss import multiprocess_jobs

from pysiu import oss_siu_data
from pysiu import siu_wrapper


def callback_function(siu_data_dict, logger):
    """
    A callback function that is passed to each subprocess Worker, so this function is applied to the
    SIU that is passed with siu_data_dict {'siu_name', 'siu_ip'}
    """

    # Define the sessions with commands to run on the SIU
    siu_job_dict = {
        'session1': {'siu_user': 'some_username', # Replace the real username here
                     'siu_password': 'some_password', # Replace the real password here
                     'command_list': [
                         'getMOAttribute STN=0',
                         'getMOAttribute STN=0,Equipment=0',
                         'getMOAttribute STN=0,MeasurementDefinition=0',
                         'getMOAttribute STN=0,Synchronization=0',
                         'uptime',
                         'debug on',
                         'sysinfo',
                         'pboot show parameters',
                         'debug off',
                         'gettime',
                         'getMOAttribute STN=0,ML-PPP=0',
                         'getMOAttribute STN=0,QosPolicy=0',
                         'getMOAttribute STN=0,EthernetInterface=0',
                         'getMOAttribute STN=0,EthernetInterface=1',
                         'dump -l',
                     ],
        },
    }

    # Launch the job sessions
    session_result_dict_list = []

    for session_id, job_session_dict in sorted(siu_job_dict.iteritems()):
        siu_user = job_session_dict.get('siu_user')
        siu_password = job_session_dict.get('siu_password')
        siu_command_list = job_session_dict.get('command_list', [])

        siu_name = siu_data_dict['siu_name']
        siu_ip = siu_data_dict['siu_ip']

        logger.info('Launching for SIU %s job %s as %s' % (siu_name, session_id, siu_user))

        siuw = siu_wrapper.SIU_Wrapper(logger)

        # Initialize session_result_dict
        session_result_dict = {
            'node':siu_name,
            'ip':siu_ip,
            'session_name':session_id,
            'session_time':str(datetime.datetime.now()),
            'siu_user':siu_user,
            'siu_password':siu_password,
            'session_data':[],
        }

        siu_command_result_dict = siuw.SIU_login(siu_ip, siu_user, siu_password)
        session_result_dict['session_data'].append(siu_command_result_dict)

        if siu_command_result_dict['cmd_success']:
            # Login ok
            siu_command_result_dict = siuw.SIU_wait_for_prompt()
            session_result_dict['session_data'].append(siu_command_result_dict)

            if siu_command_result_dict['cmd_success']:
                # Got the prompt again. Start sending useful commands to the SIU
                siu_command_result_dict_list = siuw.SIU_run_command_list(siu_command_list, siu_user)
                session_result_dict['session_data'] += siu_command_result_dict_list

            # Close the SSH connection
            siuw.SIU_exit()

        # Store this session's result
        session_result_dict_list.append(session_result_dict)

    return session_result_dict_list


#-----------------------------------------------------------------------------
# Constants
POSSIBLE_LOG_LEVELS = {'debug': logging.DEBUG,
                       'info': logging.INFO,
                       'warning': logging.WARNING,
                       'error': logging.ERROR,
                       'critical': logging.CRITICAL}

# Directory names constants
LOG = 'log'
CONFIG = 'etc'
JSON = 'json'


# Filename constants
CONFIG_FILENAME = 'config.yaml'

# Runtime values
script_name = os.path.basename(sys.argv[0]).split('.')[0]
script_usage = ''.join(['Usage: python %prog [options]\n'])
script_path = sys.argv[0]


# Parse the command line options
parser = OptionParser(usage=script_usage, version=__version__)
parser.add_option('-s', '--silent', action='store_true', dest='silent', help='do not print messages to screen [default: %default]', default=False)
parser.add_option('-l', '--log', action='store', dest='log_arg', help='set logging level: info debug warning error critical [default: %default]', default='info')

(options, args) = parser.parse_args()
log_level = POSSIBLE_LOG_LEVELS.get(options.log_arg, logging.INFO)


# Record the initial time
start_time = time.time()
now = time.localtime()
full_timestamp_suffix = time.strftime("%d%b%Y_%H%M%S", now)


# Build the solution directory path
solution_dir = os.path.abspath(os.path.join(script_path, '..'))


# Build the log dir and file
log_dir = os.path.join(solution_dir, LOG)
log_filename = '%s.log' % script_name


# Build the configuration directory path
config_dir = os.path.join(solution_dir, CONFIG)


# Build the config file dirname
configfile_full_pathname = os.path.join(config_dir, CONFIG_FILENAME)


# Build JSON dir
json_dir = os.path.join(solution_dir, JSON)
if not os.path.exists(json_dir):
    os.makedirs(json_dir)


# Instantiate a logger object
logger = app_logger.AppLogger(log_dir, log_filename, log_level, log_tag=script_name, silent_console=options.silent)
logger.info('-' * 80)
logger.info('Starting %s.py %s at %s' % (script_name, __version__, full_timestamp_suffix))
logger.info()


# Check if the invoking user belongs to an authorized Unix group
oss_utils.is_user_group_allowed(['nms', 'staff'], logger)


# Check if this script instance is the only one running
oss_utils.is_instance_unique(os.path.basename(__file__), logger)


# Read parameters from the config file
logger.info('Reading configuration file: %s' % configfile_full_pathname)
with open(configfile_full_pathname) as config_file:
    config_dict = yaml.load(config_file)
logger.debug(pprint.pformat(config_dict))


siu_fdn_black_list = config_dict.get('SIU_BLACK_LIST', [])
siu_base_fdn = config_dict['SIU_BASE_FDN']


# Log the SIU blacklist
if siu_fdn_black_list is not []:
    logger.info('Blacklisted SIUs:')
    for blacklisted_SIU_fdn in siu_fdn_black_list:
        logger.info('  %s' % blacklisted_SIU_fdn)


# Retrieve from SMO the data of all defined SIU nodes, excluding those on the black list
siu_fdn_list = oss_siu_data.get_SIU_fdn_list_from_SMO(logger, siu_fdn_black_list=siu_fdn_black_list)
#siu_fdn_list = siu_fdn_list[:200] # Truncate SIU list for testing
# siu_fdn_list = [
#      'SubNetwork=ONRM_RootMo,SubNetwork=IPRAN,ManagedElement=S1M3152',
#      'SubNetwork=ONRM_RootMo,SubNetwork=IPRAN,ManagedElement=S1M3153',
#      'SubNetwork=ONRM_RootMo,SubNetwork=IPRAN,ManagedElement=S1M4017',
#      ]

if siu_fdn_list == []:
    logger.info('No SIU nodes were found in this OSS!')

else:
    # Get the connection information for the list of SIUs as a list of dicts {'siu_name', 'siu_ip'}
    siu_data_dict_list = oss_siu_data.get_SIU_data(siu_fdn_list, logger, ping_check=False)

    # Define a file to store the SIU sessions results in JSON format
    oss_hostname = socket.gethostname()
    json_dump_full_filename = os.path.join(json_dir, 'siu.getdata.results.%s.%s.json' % (oss_hostname, full_timestamp_suffix))

    # Create and launch multiple processes for the SIU jobs
    multiprocess_jobs.Multiprocess_Master(json_dump_full_filename, logger, siu_data_dict_list,
                                          callback_function,num_workers=40)

    ## If not using multiprocess, do this
    # import json
    # with open(json_dump_full_filename, 'w') as json_dump_file:
    #     for siu_data_dict in siu_data_dict_list:
    #         result_dict_list = callback_function(siu_data_dict, logger)
    #         json.dump(result_dict_list, json_dump_file, encoding='ISO-8859-1')


# Exit
duration = time.time() - start_time
logger.info('Completed %s.py %s in %.4f sec - Bye!\n' % (script_name, __version__, duration))

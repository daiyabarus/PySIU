#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__copyright__ = 'Ericsson Spain 2013'
__version__ = 'R13A01'
__email__ = 'esteban.garcia.gurtubay@gmail.com'
__date__ = '19/06/2013 17:07:15'


# Description     : Helper functions for SIU nodes

import os
import re

from pyoss import cstest_wrapper
from pyoss import oss_utils

# Constants
SMORBS_PATH = '/opt/ericsson/bin/smorbs' # Full path of the smorbs OSS tool


def get_SIU_fdn_list_from_SMO(logger, siu_fdn_black_list=[]):
    """Make a list of dicts with data from all the SIU nodes defined in the OSS SMO

    e.g. [{'siu_name':'SIU_1234', 'siu_ip':'1.2.3.4'},}]
    """

    if not os.path.exists(SMORBS_PATH):
        logger.critical('Could not find the SMO RBS tool at:')
        logger.critical('  %s' % SMORBS_PATH)
        oss_utils.abort_script(logger)

    logger.info('Launching smorbs')
    arguments_list = ['listnes', '-full']

    logger.info('Getting SIU FDNs from smorbs output:')
    command_output, command_error = oss_utils.run_os_command(SMORBS_PATH, arguments_list, logger)

    # Sample output:

    # smorbs listnes -full | grep ManagedElement | grep SIU
    # Name                 Type       Platform   Version FDN
    # BSC123_RXOTG-1       BTS        RBS2000            SubNetwork=ONRM_ROOT_MO,SubNetwork=AXE,ManagedElement=BSC123_RXOTG-1
    # SIU5                 STN        SIU        T11A    SubNetwork=ONRM_ROOT_MO,SubNetwork=STN,ManagedElement=SIU5
    # BSC123_RXOTG-10      BTS        RBS2000            SubNetwork=ONRM_ROOT_MO,SubNetwork=AXE,ManagedElement=BSC123_RXOTG-10
    # BSC123_RXOTG-0       BTS        RBS2000            SubNetwork=ONRM_ROOT_MO,SubNetwork=AXE,ManagedElement=BSC123_RXOTG-0
    # SIU6                 STN        SIU        T11A    SubNetwork=ONRM_ROOT_MO,SubNetwork=STN,ManagedElement=SIU6

    siu_fdn_list = []
    count = 1
    for line in command_output:
        if 'ManagedElement' in line:
            fields_list = line.split()
            if fields_list[2] == 'SIU':
                SIU_fdn = fields_list[4]
                if SIU_fdn in siu_fdn_black_list:
                    logger.info('Ignoring blacklisted SIU: %s' % SIU_fdn)
                else:
                    # e.g. SubNetwork=ONRM_ROOT_MO,SubNetwork=STN,ManagedElement=SIU5
                    logger.info('  %5i  %s' % (count, SIU_fdn))
                    count += 1
                    siu_fdn_list.append(SIU_fdn)
    logger.info('')

    return siu_fdn_list


def get_SIU_data(siu_fdn_list, logger, ping_check=True):
    """Take as input a list of SIU FDNs and get from cstest its IP
    Optionally, do a ping to the SIU. It it does not respond, exclude it from the result
    """

    SIU_dict_list = []
    csw = cstest_wrapper.Cstest_Wrapper(logger)
    num_SIU_candidates = len(siu_fdn_list)
    for count, SIU_fdn in enumerate(siu_fdn_list):
        # The ipAddress is stored at
        # SubNetwork=ONRM_ROOT_MO,SubNetwork=IPRAN,ManagedElement=SIU5,IoInterface=io-0
        IoInterface_fdn = '%s,IoInterface=io-0' % SIU_fdn
        csw_output_list = csw.send_cstest_command('ONRM_CS', 'la ' + IoInterface_fdn + ' -an ipAddress')
        # e.g. csw_output_list = ['  [1] ipAddress (string)            : "10.1.6.29"\n']
        csw_output = csw_output_list[0]

        if 'ipAddress (string)' in csw_output:
            SIU_ipAddress = csw_output.split()[4].split('"')[1]
            SIU_name = SIU_fdn.split('=')[3]
            logger.info('Found CS SIU node: %s - IP: %s [%i of %i]' % (SIU_name, SIU_ipAddress, 1+count, num_SIU_candidates))

            # Some SIU IPs are empty in cstest, so validate it before usage
            if not is_ip_valid(SIU_ipAddress):
                logger.info('Invalid IP address ("%s") for SIU %s. Ignoring node' % (SIU_ipAddress, SIU_name))

            else:
                if ping_check:
                    # Check if there is ping to the SIU
                    logger.info('Pinging SIU node: %s - IP: %s' % (SIU_name, SIU_ipAddress))
                    ping_timeout = 1 # In seconds. By default, this is 20 in Solaris
                    ping_arguments = ['', SIU_ipAddress, str(ping_timeout)]
                    ping_output, ping_error = oss_utils.run_os_command('/usr/sbin/ping', ping_arguments, logger)
                    # ping_output: ['no answer from 10.115.175.10\n']
                    # ping_error: []
                    # or
                    # ping_output: ['10.115.167.67 is alive\n']
                    # ping_error: []
                    if 'no answer from' in ''.join(ping_output):
                        logger.info('There is no ping for SIU %s. Ignoring node' % SIU_name)
                    else:
                        logger.info('Ping was ok')
                        SIU_dict = {}
                        SIU_dict['siu_name'] = SIU_name
                        SIU_dict['siu_ip'] = SIU_ipAddress

                        SIU_dict_list.append(SIU_dict)
                else:
                    # Do not check ping
                    SIU_dict = {}
                    SIU_dict['siu_name'] = SIU_name
                    SIU_dict['siu_ip'] = SIU_ipAddress

                    SIU_dict_list.append(SIU_dict)

        logger.info('')

    csw.close_session()
    logger.info('Found %i valid SIU node(s) in the OSS' % len(SIU_dict_list))
    logger.info('')

    return SIU_dict_list


def is_ip_valid(ip_address):
    """Check that the IP address format is correct"""

    # is_ip_valid('10.1.11.27') = True
    # is_ip_valid('1.2') = False
    # is_ip_valid('260.34.21.4') = False
    # is_ip_valid('') = False

    pattern = r"\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    return re.match(pattern, ip_address) != None


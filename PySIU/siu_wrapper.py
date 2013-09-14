#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__version__ = 'R13A01'
__date__ = '19/06/2013 17:07:15'


# Description     : A wrapper library to interact with SIU nodes

import datetime
import pprint
import signal
import time
import paramiko


class SIU_Wrapper(object):
    """A set of wrapping functions to interact with a single SIU"""

    def __init__(self, logger):
        self.logger = logger


    def signal_handler(self, signum, frame):
        """A handler for UNIX signals, used for timeouts"""

        self.logger.error('Signal handler got SIGALARM')
        raise IOError('UNIX timeout signal received')


    def SIU_login(self, siu_ip, siu_user, siu_password, timeout=10):
        """Login into the given SIU with an SSH session"""

        self.chan = None
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        siu_communication_result_dict = {}
        siu_communication_result_dict['comm_time'] = self.get_timestamp()
        siu_communication_result_dict['comm_data'] = ''

        siu_command_result_dict = {}
        siu_command_result_dict['cmd_string'] = 'ssh login'
        siu_command_result_dict['cmd_time'] = self.get_timestamp()

        self.logger.info('Login into SIU %s' % siu_ip)
        try:
            # Sometimes the SSH connection to a SIU hangs forever, even from command line.
            # An extra timeout mechanism is required, or a Worker task will never finish
            # and the whole script will hang.

            # Set an extra timeout with UNIX signals
            signal.signal(signal.SIGALRM, self.signal_handler)
            signal.alarm(timeout+5)
            self.ssh.connect(siu_ip, username=siu_user, password=siu_password, timeout=5)
            self.logger.info('Login was successful')

            self.logger.info('Invoking SIU shell')
            self.chan = self.ssh.invoke_shell()
            self.logger.info('Got SIU shell')

        except IOError as e:
            siu_communication_result_dict['comm_success'] = False
            siu_communication_result_dict['comm_error'] = 'IOError while connecting to SIU'
            siu_communication_result_dict['comm_data'] = str(e)
            siu_command_result_dict['cmd_success'] = False

            self.logger.error('Login failed')
            self.logger.error('%s:' % siu_communication_result_dict['comm_error'])
            self.logger.error('  %s' % siu_communication_result_dict['comm_data'])

        except Exception as e:
            siu_communication_result_dict['comm_success'] = False
            siu_communication_result_dict['comm_error'] = 'Exception while connecting to SIU'
            siu_communication_result_dict['comm_data'] = str(e)
            siu_command_result_dict['cmd_success'] = False

            self.logger.error('Login failed')
            self.logger.error('%s:' % siu_communication_result_dict['comm_error'])
            self.logger.error('  %s' % siu_communication_result_dict['comm_data'])

        else:
            siu_communication_result_dict['comm_success'] = True
            siu_command_result_dict['cmd_success'] = True

        finally:
            # Disable the UNIX timeout signal
            signal.alarm(0)

        siu_command_result_dict['cmd_data'] = siu_communication_result_dict

        return siu_command_result_dict


    def SIU_wait_for_prompt(self):
        """Send an empty line and wait for the SIU prompt"""

        siu_command_result_dict = {}
        siu_command_result_dict['cmd_string'] = 'wait for prompt'
        siu_command_result_dict['cmd_time'] = self.get_timestamp()

        siu_communication_dict = self.SIU_read_response(expected_response_list=['OSmon> ', '[root]# '])
        self.logger.info('Waiting for SIU prompt')

        if siu_communication_dict['comm_success']:
            siu_command_result_dict['cmd_success'] = True
            siu_command_result_dict['cmd_data'] = siu_communication_dict
            self.logger.info('Got SIU prompt')

        else:
            siu_command_result_dict['cmd_success'] = False
            siu_command_result_dict['cmd_error'] = 'Could not get SIU prompt'
            siu_command_result_dict['cmd_data'] = siu_communication_dict

            self.logger.error('%s:' % siu_command_result_dict['cmd_error'])
            self.logger.error('  %s' % siu_command_result_dict['cmd_data'])

        return siu_command_result_dict


    def SIU_send_string(self, cmd, timeout=15):
        """Send a string to the SIU"""

        # Add a trailing Carriage Return if not present already. This can be \r or \r\n ??
        if cmd == '' or cmd[-1] != '\r':
            cmd += '\r'

        success_status = None

        self.chan.settimeout(timeout) # Timeout for the channel
        self.logger.debug('> Sending to SIU: %s' % str(cmd.splitlines()))

        try:
            # Set an extra timeout with UNIX signals
            signal.signal(signal.SIGALRM, self.signal_handler)
            signal.alarm(timeout+5)
            self.chan.send(cmd)

        except IOError as e:
            self.logger.error('IOError while sending string to SIU')
            self.logger.error(str(e))
            self.logger.error('')
            success_status = False

        except Exception as e:
            self.logger.error('Exception while sending string to SIU')
            self.logger.error(str(e))
            self.logger.error('')
            success_status = False

        else:
            self.logger.debug('< Sending done')
            success_status = True

        finally:
            # Disable the UNIX timeout signal
            signal.alarm(0)

        return success_status


    def SIU_read_response(self, expected_response_list, timeout=15):
        """Read the SIU response in the input channel until we detect any of the messages in expected_response_list,
         or timeout

        Return a siu_communication_result_dict with info about the OSS/SIU data exchange
        """

        self.logger.debug('> Waiting response from SIU. Valid responses are: %s' % expected_response_list)
        input_buffer = ''
        siu_communication_result_dict = {}
        siu_communication_result_dict['comm_success'] = None
        siu_communication_result_dict['comm_time'] = self.get_timestamp()
        siu_communication_result_dict['comm_data'] = ''

        # Wait a bit before reading the output buffer. SIUs are sometimes slow in responding
        time.sleep(0.1)

        self.chan.settimeout(timeout) # Timeout for the channel. This should avoid chan.recv(1) hanging
        try:
            # Set an extra timeout with UNIX signals
            signal.signal(signal.SIGALRM, self.signal_handler)
            signal.alarm(timeout+5)

            while siu_communication_result_dict['comm_success'] == None:
                # Buffer characters
                input_buffer += self.chan.recv(1)
                ##self.logger.debug(' Input_buffer: %s' % str(input_buffer.splitlines()))

                # Examine the buffer for expected patterns
                for expected_response in expected_response_list:
                    if expected_response in input_buffer:
                        siu_communication_result_dict['comm_success'] = True # To exit the loop
                        siu_communication_result_dict['comm_data'] = input_buffer.splitlines()
                        self.logger.debug('< Found a match in the response: [\'%s\']' % str(expected_response))

        except IOError as e:
            siu_communication_result_dict['comm_success'] = False
            siu_communication_result_dict['comm_error'] = 'IOError while reading response from SIU: %s' % str(e)
            self.logger.error('< %s:' % siu_communication_result_dict['comm_error'])
            self.logger.error('  %s' % siu_communication_result_dict['comm_data'])

        except Exception as e:
            siu_communication_result_dict['comm_success'] = False
            siu_communication_result_dict['comm_error'] = 'Exception while reading response from SIU: %s' % str(e)
            self.logger.error('< %s:' % siu_communication_result_dict['comm_error'])
            self.logger.error('  %s' % siu_communication_result_dict['comm_data'])

        finally:
            # Disable the UNIX timeout signal
            signal.alarm(0)

        return siu_communication_result_dict


    def SIU_send_command(self, command_string, error_msg=None, expected_response_list=['OSmon> '], timeout=15):
        """Send the given command_string to the SIU, return a siu_command_result_dict

        Return a siu_command_result_dict with info about the command result"""

        if error_msg is None:
            error_msg = 'Failure for %s' % command_string

        siu_command_result_dict = {}
        siu_command_result_dict['cmd_string'] = command_string
        siu_command_result_dict['cmd_time'] = self.get_timestamp()

        success_status = self.SIU_send_string(command_string, timeout)
        if not success_status:
            # The string sending failed
            siu_command_result_dict['cmd_success'] = False
            siu_command_result_dict['cmd_error'] = 'Exception while sending command to SIU'
            self.logger.error(siu_command_result_dict['cmd_error'])
            self.logger.error('')

        else:
            # The command sending succeeded. Proceed to read the SIU response
            siu_communication_dict = self.SIU_read_response(expected_response_list, timeout)
            if siu_communication_dict['comm_success']:
                siu_response_list = siu_communication_dict['comm_data']
                if self.get_index_of_substring(siu_response_list, 'OperationSucceeded'):
                    siu_command_result_dict['cmd_success'] = True
                    siu_command_result_dict['cmd_data'] = siu_communication_dict

                elif self.get_index_of_substring(siu_response_list, 'OperationFailed'):
                    siu_command_result_dict['cmd_success'] = False
                    siu_command_result_dict['cmd_error'] = error_msg
                    siu_command_result_dict['cmd_data'] = siu_communication_dict

                elif self.get_index_of_substring(siu_response_list, 'OSmon> '):
                    # Got the prompt, but not the operation result
                    siu_command_result_dict['cmd_success'] = None
                    siu_command_result_dict['cmd_error'] = 'Got the prompt, but could not match any expected result'
                    siu_command_result_dict['cmd_data'] = siu_communication_dict

                # Handle root session
                elif self.get_index_of_substring(siu_response_list, '[root]# '):
                    # Got the prompt, but not the operation result
                    siu_command_result_dict['cmd_success'] = None
                    siu_command_result_dict['cmd_error'] = 'Got the prompt, but could not match any expected result'
                    siu_command_result_dict['cmd_data'] = siu_communication_dict

                else:
                    # Strange... Got an error before the prompt?
                    siu_command_result_dict['cmd_success'] = None
                    siu_command_result_dict['cmd_error'] = 'Got an unknown response before the prompt'
                    siu_command_result_dict['cmd_data'] = siu_communication_dict

            else:
                # Something went wrong when communicating with the SIU, e.g. a timeout while waiting for
                # the SIU response to our command
                siu_command_result_dict['cmd_success'] = False
                siu_command_result_dict['cmd_error'] = 'Response error. Timeout maybe?'
                siu_command_result_dict['cmd_data'] = siu_communication_dict

        self.logger.debug('siu_command_result_dict:')
        self.logger.debug(pprint.pformat(siu_command_result_dict))
        self.logger.debug('')

        return siu_command_result_dict


    def SIU_run_command_list(self, siu_command_list, user_name):
        """Run a list of SIU commands

        siu_command_list = ['command_string', ...]

        e.g.
        siu_command_list = ['getMOAttribute STN=0,TrafficManager=QoS_WAN diffServMinRateRelative_2',
                            'getMOAttribute',
                            'setMOAttribute STN=0,TrafficManager=QoS_WAN diffServMinRateRelative_2 200',
                            'uptime',
                            ...
                           ]
        The first word in the command_string is the SIU command
        When the command is one of the following, it is automatically wrapped in its own transaction:
        - setMOAttribute ...
        - deleteMO ...
        - createMO ...
        """

        siu_command_result_dict_list = []

        # A guard against empty lists
        if siu_command_list is None:
            siu_command_list = []

        if user_name == 'root':
            # Login as 'root'

            known_siu_root_commands = ['grep', 'ls',]

            for command_string in siu_command_list:
                if command_string.strip() == '':
                    # Ignore empty commands
                    continue

                command = command_string.split()[0]

                if command.lower() in known_siu_root_commands:
                    siu_command_result_dict = self.SIU_send_command(command_string, expected_response_list=['[root]# '])
                else:
                    self.logger.error('Command %s is unknown' % command_string)
                    siu_command_result_dict = {'cmd_success': False,
                                        'cmd_error':'Command %s is unknown' % command_string,
                    }

                siu_command_result_dict_list.append(siu_command_result_dict)

        else:
            # Non 'root' login (i.e. login as 'admin')
            known_siu_commands_with_transaction_list = [
                'setmoattribute', 'createmo', 'deletemo'
            ]

            known_siu_commands_without_transaction_list = [
                'uptime', 'debug', 'sysinfo', 'pboot', 'gettime',
                'getmoattribute', 'starttransaction', 'endtransaction',
                'commit', 'subscribe', 'unsubscribe', 'getsubscriptionstatus',
                'gettransactionstatus', 'checkconsistency', 'gettransactionid',
                'dump', 'getcounters', 'getalarmlist', 'changepwdrs',
                'startsession', 'backup', 'endsession', 'uselocalsftp',
            ]

            for command_string in siu_command_list:
                if command_string.strip() == '':
                    # Ignore empty commands
                    continue

                command = command_string.split()[0]

                # Check if the command needs a wrapping transaction
                if command.lower() in known_siu_commands_with_transaction_list:
                    #siu_command_result_dict = self.SIU_run_command_list_within_transaction([command_string])
                    siu_command_result_dict = self.SIU_send_command(command_string)

                elif command.lower() in known_siu_commands_without_transaction_list:
                    siu_command_result_dict = self.SIU_send_command(command_string)

                else:
                    self.logger.error('Command %s is unknown' % command_string)
                    siu_command_result_dict = {'cmd_success': False,
                                        'cmd_error':'Command %s is unknown' % command_string,
                    }

                siu_command_result_dict_list.append(siu_command_result_dict)

        return siu_command_result_dict_list


    def SIU_exit(self):
        """Disconnect the SSH session by sending an exit command

        OSmon> exit
        """

        self.logger.info('Exiting from SIU')
        self.SIU_send_string('exit')
        time.sleep(1.5)
        self.SIU_close_channel()


    def SIU_close_channel(self):
        """Close the underlyng SSH channel"""

        if self.chan is not None:
            self.chan.close()


    def get_timestamp(self):
        """Return a timestamp

        e.g. '2013-05-22 13:35:02.982256'
        """

        return str(datetime.datetime.now())


    def get_index_of_substring(self, string_list, substring):
        """Helper function to find the first index of a substring in a list

        e.g.:
        get_index_of_substring(['OSmon> OperationFailed', 'OSmon> OperationSucceeded'], 'OperationSucceeded') = 1
        """

        for i, s in enumerate(string_list):
            if substring in s:
                return i
        return None

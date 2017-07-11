# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""
import bottle
import logging
import subprocess

from .. import m_common

# module logger
logger = logging.getLogger(__name__)

# commands
GET_COMMANDS = [
    m_common.COMMAND_STATUS,
    m_common.COMMAND_VERSION,
    m_common.COMMAND_SYNC
]

POST_COMMANDS = [
    m_common.COMMAND_LOG
]

# POST request arguments
SINCE = 'since'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_LOG: {'files': [], 'forms': [SINCE]}
}


class System:
    def __init__(self):
        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_VERSION: self.version,
            m_common.COMMAND_SYNC: self.synchronization,
            m_common.COMMAND_LOG: self.log
        }

    def status(self):
        synchronization = self.synchronization()
        version = self.version()
        return {
            'version': version['version'],
            'synchronization': {
                'source': synchronization['sync_source'],
                'offset': synchronization['offset'],
                'offset_std': synchronization['offset_std']
            }
        }

    @staticmethod
    def version():
        return {'version': m_common.VERSION}

    @staticmethod
    def synchronization():
        try:
            tracking = subprocess.check_output(
                'tail -n 1 {0}'.format(m_common.CHRONY_LOG_FILE),
                shell=True
            ).decode('utf-8')
            tokens = tracking.split()
            return {
                'date': '{0} {1}'.format(tokens[0], tokens[1]),
                'sync_source': tokens[2],
                'offset': tokens[6],
                'offset_std': tokens[9]
            }
        except subprocess.CalledProcessError as e:
            logger.error('command {0} error {1}: {2}'.format('synchronization', e.returncode, e.output))
            raise m_common.SystemCommandException(m_common.ERROR_COMMAND_FAILED.format('log', e.output))

    @staticmethod
    def log(since):
        try:
            log = subprocess.check_output(
                'journalctl --since "{0}" -u sensorlab-node'.format(since),
                stderr=subprocess.STDOUT,
                shell=True).decode('utf-8')
            return {
                'log': log
            }
        except subprocess.CalledProcessError as e:
            raise m_common.SystemCommandException(e.output.decode('utf-8'))

    def rest_get_command(self, command):
        # verify that the command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        try:
            logger.info('executing command {0}'.format(command))
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            return self.commands[command]()
        except m_common.IOException as e:
            logger.error('command {0} error: '.format(command, e.message))
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

    def rest_post_command(self, command):
        # check that command exists
        if command not in POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
        # arguments
        arguments = {}
        for required_file_argument in REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(missing_arguments)
            # issue the command
        try:
            logger.info('executing command {0} with arguments: {1}'.format(command, arguments))
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return
            return self.commands[command](**arguments)
        except m_common.SystemException as e:
            logger.error('command {0} error: '.format(command, e.message))
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_FAILED.format(command, e.message)

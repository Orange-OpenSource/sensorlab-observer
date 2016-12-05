# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""
import os
import bottle

from .. import m_common

# commands
GET_COMMANDS = [
    m_common.COMMAND_STATUS,
    m_common.COMMAND_VERSION,
    m_common.COMMAND_SYNC
]


class System:
    def __init__(self):
        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_VERSION: self.version,
            m_common.COMMAND_SYNC: self.synchronization,
        }

    def status(self):
        synchronization = self.synchronization()
        version = self.version()
        return {
            'version': version,
            'synchronization': {
                'source': synchronization['sync_source'],
                'offset': synchronization['offset'],
                'offset_std': synchronization['offset_std']
            }
        }

    def version(self):
        return m_common.VERSION

    def synchronization(self):
        tracking = os.popen('tail -n 1 {0}'.format(m_common.CHRONY_LOG_FILE)).read()
        tokens = tracking.split()

        return {
            'date': '{0} {1}'.format(tokens[0], tokens[1]),
            'sync_source': tokens[2],
            'offset': tokens[6],
            'offset_std': tokens[9]
        }

    def rest_get_command(self, command):
        # verify that the command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        try:
            self.commands[command]()
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            return self.commands[command]()
        except m_common.IOException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

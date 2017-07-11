# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2017/03/06
Copyright 2017 Orange
"""

import os
import bottle
import yaml
import logging
import threading

from collections import deque
from pydispatch import dispatcher
from pymongo import errors, MongoClient

from .. import m_common


# module logger
logger = logging.getLogger(__name__)

# persistent configuration filename
LAST_CONFIGURATION = os.path.join(m_common.PERSISTENCE_DIR, 'last_configuration.yml')

# Input/Output states
IO_DISCONNECTED = 0
IO_READY = 1
IO_CONNECTING = 2
IO_CONNECTED = 3
IO_DISCONNECTING = 4
IO_STATES = ('disconnected', 'ready', 'connecting', 'connected', 'disconnecting')

# commands
GET_COMMANDS = [m_common.COMMAND_STATUS,
                m_common.COMMAND_START,
                m_common.COMMAND_STOP,
                m_common.COMMAND_RESET]

POST_COMMANDS = [m_common.COMMAND_SETUP]

IO_COMMAND_ALLOWED_STATES = {
    m_common.COMMAND_STATUS: [
        IO_DISCONNECTED,
        IO_CONNECTED,
    ],
    m_common.COMMAND_START: [
        IO_DISCONNECTED
    ],
    m_common.COMMAND_STOP: [
        IO_CONNECTED
    ],
    m_common.COMMAND_RESET: [
        IO_CONNECTED,
        IO_DISCONNECTED
    ],
    m_common.COMMAND_SETUP: [
        IO_DISCONNECTED,
    ]
}

# POST request arguments
DB_ADDRESS = 'address'
DB_NAME = 'database'
DB_PORT = 'port'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [DB_ADDRESS]}
}

BD_ADDRESS_UNDEFINED = 'undefined'
BD_NAME_UNDEFINED  = 'undefined'
BD_PORT_UNDEFINED = 'undefined'


class IO:
    def __init__(self):
        self.state = IO_DISCONNECTED
        self.thread = None
        self.thread_running = False
        self.client = None
        self.database = None
        self.database_name = None
        self.database_address = None
        self.database_port = None
        self.record_queue = deque()

        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start,
            m_common.COMMAND_STOP: self.stop,
            m_common.COMMAND_RESET: self.reset
        }

        # setup IO with last configuration, if it exists
        if os.path.exists(LAST_CONFIGURATION):
            try:
                with open(LAST_CONFIGURATION, 'r') as configuration_file:
                    configuration = yaml.load(configuration_file.read())
                    self.setup(
                        configuration['database_address'],
                        configuration['database_port'],
                        configuration['database_name']
                    )
            except (OSError, yaml.YAMLError, m_common.IOSetupException):
                pass

    def _run(self):
        while self.thread_running and len(self.record_queue) > 0:
            record = self.record_queue.popleft()
            try:
                collection = self.database.get_collection('{0}.{1}'.format(record['experiment'], record['type']))
                insert_result = collection.insert_one(record['event'])
                if not insert_result.acknowledged:
                    logger.error('record not acknowledged: {0}, retrying...'.format(insert_result))
                    self.record_queue.appendleft(record)
            except errors.ServerSelectionTimeoutError as e:
                self.record_queue.appendleft(record)
                logger.error('MongoDB currently not available: {0}:{1}'.format(self.database_name, self.database_port))
        self.thread_running = False

    def status(self):
        return {'state': IO_STATES[self.state],
                'address': self.database_address if self.database_address else BD_ADDRESS_UNDEFINED,
                'port': self.database_port if self.database_port else BD_PORT_UNDEFINED,
                'database': self.database_name if self.database_name else BD_NAME_UNDEFINED}

    def setup(self, address, port=m_common.IO_DATABASE_PORT_DEFAULT, name=m_common.IO_DATABASE_NAME_DEFAULT):
        self.database_address = address
        self.database_port = int(port)
        self.database_name = name

        try:
            return self.start()
        except:
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.database_address, self.database_port)
                )
            )

    def send(self, experiment, event, type):
        self.record_queue.append({'experiment': experiment, 'event': event, 'type': type})
        if not self.thread_running:
            self.thread_running = True
            self.thread = threading.Thread(target=self._run)
            self.thread.setDaemon(True)
            self.thread.start()

    def start(self):
        logger.info('connecting to {0}:{1} ...'.format(self.database_address, self.database_port))
        try:
            self.client = MongoClient("{0}:{1}".format(self.database_address, self.database_port))
            self.database = self.client.get_database(self.database_name)
            self.client.admin.command('ismaster')
            self.state = IO_CONNECTED
            logger.info('connected to {0}:{1}.'.format(self.database_address, self.database_port))
            dispatcher.connect(self.send, signal=m_common.IO_SEND)
        except (errors.InvalidURI, errors.ConnectionFailure, errors.ServerSelectionTimeoutError) as e:
            self.state = IO_DISCONNECTED
            logger.error('cannot connect to {0}:{1}'.format(self.database_address, self.database_port))
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.database_address, self.database_port)
                )
            )
        try:
            with open(LAST_CONFIGURATION, 'w') as configuration_file:
                configuration = yaml.dump({
                    'database_address': self.database_address,
                    'database_port': self.database_port,
                    'database_name': self.database_name
                })
                configuration_file.write(configuration)
        except (OSError, yaml.YAMLError):
            raise m_common.IOSetupException(
                'error while saving the configuration: {0}:{1}({2})'.format(
                    self.database_address,
                    self.database_port,
                    self.database_name
                )
            )
        return self.status()

    def stop(self):
        dispatcher.disconnect(self.send, signal=m_common.IO_SEND)
        self.thread_running = False
        self.thread.join()
        self.client.close()
        self.state = IO_DISCONNECTED
        return self.status()

    def reset(self):
        if self.state != IO_DISCONNECTED:
            self.stop()
        self.record_queue.clear()
        return self.status()

    def rest_get_command(self, command):
        # verify that the command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # check that command is allowed in this context
        if self.state not in IO_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(IO_STATES[self.state])
            )
        # issue the command and return
        try:
            logger.info('executing command {0}'.format(command))
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            return self.commands[command]()
        except m_common.IOException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

    def rest_post_command(self, command):
        # check that command exists
        if command not in POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
        # check that command is allowed in this context
        if self.state not in IO_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(IO_STATES[self.state])
            )
        # load arguments
        arguments = {}
        for required_file_argument in REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        for argument in bottle.request.files:
            if argument not in arguments.keys():
                arguments[argument] = bottle.request.files.get(argument)
        for argument in bottle.request.forms:
            if argument not in arguments.keys():
                arguments[argument] = bottle.request.forms.get(argument)

        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(missing_arguments)
        # issue the command
        try:
            logger.info('executing command {0} with arguments: {1}'.format(command, arguments))
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the io status
            return self.commands[command](**arguments)
        except m_common.IOException as e:
            logger.error('command {0} error: '.format(command, e.message))
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

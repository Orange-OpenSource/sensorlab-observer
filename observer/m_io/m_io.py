# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""
import os
import errno
import bottle
from pydispatch import dispatcher
import socket
import paho.mqtt.client as mqtt
import yaml
from .. import m_common

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

# POST request arguments
BROKER_ADDRESS = 'address'
BROKER_PORT = 'port'
KEEPALIVE_PERIOD = 'keepalive_period'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [BROKER_ADDRESS, BROKER_PORT]}
}

BROKER_ADDRESS_UNDEFINED = 'undefined'
BROKER_PORT_UNDEFINED = 'undefined'
KEEPALIVE_PERIOD_UNDEFINED = 'undefined'


class IO:
    def __init__(self, node_id):
        self.state = IO_DISCONNECTED
        self.node_id = node_id
        self.client_id = 'node-{0}'.format(node_id)
        self.broker_address = None
        self.broker_port = None
        self.keepalive_period = None
        self.client = None
        self.thread = None

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
                        configuration['broker_address'],
                        configuration['broker_port'],
                        configuration['keepalive_period']
                    )
            except (OSError, yaml.YAMLError, m_common.IOSetupException):
                pass

    def status(self):
        return {'state': IO_STATES[self.state],
                'address': self.broker_address if self.broker_address else BROKER_ADDRESS_UNDEFINED,
                'port': self.broker_port if self.broker_port else BROKER_PORT_UNDEFINED}

    def setup(self, address, port, keepalive_period=60):
        self.broker_address = address
        self.broker_port = int(port)
        self.keepalive_period = int(keepalive_period)
        try:
            self.client = mqtt.Client(client_id=self.client_id, clean_session=True, userdata=None, protocol='MQTTv311')

            def on_connect(client, userdata, connection_result):
                del userdata
                if connection_result is 0:
                    self.state = IO_CONNECTED
                    client.subscribe(m_common.IO_TOPIC_NODE_INPUT.format(observer_id=self.node_id))
                    dispatcher.connect(self._send, signal=m_common.IO_SEND)
                    # save configuration for next bootstrap
                    try:
                        os.makedirs(os.path.dirname(LAST_CONFIGURATION))
                    except OSError as exception:
                        if exception.errno != errno.EEXIST:
                            raise
                    try:
                        with open(LAST_CONFIGURATION, 'w') as configuration_file:
                            configuration = yaml.dump({
                                'broker_address': self.broker_address,
                                'broker_port': self.broker_port,
                                'keepalive_period': self.keepalive_period
                            })
                            configuration_file.write(configuration)
                    except (OSError, yaml.YAMLError):
                        raise m_common.IOSetupException(
                            'error while saving the configuration: {0}:{1}({2})'.format(
                                self.broker_address,
                                self.broker_port,
                                self.keepalive_period
                            )
                        )
                else:
                    pass

            def on_message(client, userdata, message):
                del client, userdata
                self._receive(message)

            def on_disconnect(client, userdata, connection_result):
                if connection_result != 0:
                    pass

            def on_subscribe(client, userdata, mid, granted_qos):
                del client, userdata, mid, granted_qos
                pass

            def on_log(client, userdata, level, buf):
                pass

            self.client.on_connect = on_connect
            self.client.on_message = on_message
            self.client.on_disconnect = on_disconnect
            self.client.on_subscribe = on_subscribe
            self.client.on_log = on_log

            self.state = IO_READY
            self.start()
        except:
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.broker_address, self.broker_port)
                )
            )

    def _send(self, topic, message):
        self.client.publish(topic, message, qos=2)

    def _receive(self, message):
        if self.state == IO_CONNECTED:
            dispatcher.send(signal=m_common.IO_RECV, message=message.payload)

    def start(self):
        self.state = IO_CONNECTING
        try:
            self.client.connect(self.broker_address,
                                self.broker_port,
                                self.keepalive_period)
            self.client.loop_start()
        except socket.gaierror:
            self.state = IO_DISCONNECTED
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.broker_address, self.broker_port)
                )
            )

    def stop(self):
        if self.client:
            self.state = IO_DISCONNECTING
            self.client.disconnect()
            self.client.loop_stop()
            self.state = IO_READY

    def reset(self):
        if self.state == IO_CONNECTED:
            self.stop()
        self.state = IO_DISCONNECTED
        self.broker_address = None
        self.broker_port = None
        self.keepalive_period = None
        self.client = None
        dispatcher.disconnect(self._send, signal=m_common.IO_SEND)

    def rest_get_command(self, command):
        # verify that the command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        try:
            self.commands[command]()
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            return self.status()
        except m_common.IOException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

    def rest_post_command(self, command):
        # check that command exists
        if command not in POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
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
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the io status
            return self.status()
        except m_common.IOException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return e.message

# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""
import bottle
from pydispatch import dispatcher
import socket
import paho.mqtt.client as mqtt
from .. import m_common

# Input/Output states
IO_DISCONNECTED = 0
IO_READY = 1
IO_CONNECTING = 2
IO_CONNECTED = 3
IO_DISCONNECTING = 4
IO_STATES = ('disconnected', 'ready', 'connecting', 'connected', 'disconnecting')

IO_TOPIC_INPUT_RAW = 'sensorlab/data/to_node/{0}'
IO_TOPIC_OUTPUT_RAW = 'sensorlab/data/from_node/{0}'
IO_TOPIC_OUTPUT_OBSERVER = 'sensorlab/observer/from_node/{0}'

# commands
GET_COMMANDS = [m_common.COMMAND_STATUS,
                m_common.COMMAND_START,
                m_common.COMMAND_STOP]
POST_COMMANDS = [m_common.COMMAND_SETUP]

# POST request arguments
SOURCE = 'source'
BROKER_ADDRESS = 'address'
BROKER_PORT = 'port'
KEEPALIVE_PERIOD = 'keepalive_period'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [BROKER_ADDRESS,
                                                    BROKER_PORT,
                                                    KEEPALIVE_PERIOD,
                                                    SOURCE]}
}

IO_SOURCE_NODE = 'node'
IO_SOURCE_EXPERIMENT = 'experiment'
AVAILABLE_SOURCES = (IO_SOURCE_NODE, IO_SOURCE_EXPERIMENT)

SOURCE_TO_SIGNAL = {
    IO_SOURCE_NODE: (m_common.IO_RAW_FROM_NODE, m_common.IO_OBSERVER_FROM_NODE),
    IO_SOURCE_EXPERIMENT: (m_common.IO_RAW_FROM_EXPERIMENT, m_common.IO_OBSERVER_FROM_EXPERIMENT)
}

SOURCE_UNDEFINED = 'undefined'
BROKER_ADDRESS_UNDEFINED = 'undefined'
BROKER_PORT_UNDEFINED = 'undefined'
KEEPALIVE_PERIOD_UNDEFINED = 'undefined'


class IO:
    def __init__(self, node_id):
        self.state = IO_DISCONNECTED
        self.node_id = node_id
        self.client_id = 'node-{0}'.format(node_id)
        self.source = None
        self.broker_address = None
        self.broker_port = None
        self.keepalive_period = None
        self.client = None
        self.raw_signal = m_common.IO_RAW_FROM_NODE
        self.observer_signal = m_common.IO_OBSERVER_FROM_NODE
        self.thread = None

        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start,
            m_common.COMMAND_STOP: self.stop,
        }

    def status(self):
        return {'state': IO_STATES[self.state],
                'source': self.source if self.source else SOURCE_UNDEFINED,
                'broker_address': self.broker_address if self.broker_address else BROKER_ADDRESS_UNDEFINED,
                'broker_port': self.broker_port if self.broker_port else BROKER_PORT_UNDEFINED,
                'keepalive_period': self.keepalive_period if self.keepalive_period else KEEPALIVE_PERIOD_UNDEFINED}

    def setup(self, source, address, port, keepalive_period=60):
        self.broker_address = address
        self.broker_port = int(port)
        self.keepalive_period = int(keepalive_period)
        if source not in AVAILABLE_SOURCES:
            raise m_common.IOSetupException(m_common.ERROR_CONFIGURATION_UNKNOWN_ITEM.format(source))
        self.source = source
        self.raw_signal = SOURCE_TO_SIGNAL[self.source][0]
        self.observer_signal = SOURCE_TO_SIGNAL[self.source][1]
        try:
            self.client = mqtt.Client(client_id=self.client_id, clean_session=True, userdata=None, protocol='MQTTv311')

            def on_connect(client, userdata, connection_result):
                del userdata, connection_result
                print('connected to {0}:{1}'.format(self.broker_address, self.broker_port))
                self.state = IO_CONNECTED
                client.subscribe(IO_TOPIC_INPUT_RAW.format(self.node_id))

                dispatcher.connect(self._raw_send, signal=self.raw_signal)
                dispatcher.connect(self._observer_send, signal=self.observer_signal)

            def on_message(client, userdata, message):
                del client, userdata
                self._on_receive(message)

            self.client.on_connect = on_connect
            self.client.on_message = on_message

            self.state = IO_READY
        except (OSError, socket.error) as e:
            raise m_common.IOException(e.message)

    def _on_receive(self, message):
        if self.state == IO_CONNECTED:
            dispatcher.send(signal=m_common.IO_RAW_FROM_PLATFORM, message=message)

    def _raw_send(self, message):
        if self.state == IO_CONNECTED:
            self.client.publish(IO_TOPIC_OUTPUT_RAW.format(self.node_id), bytearray(message))

    def _observer_send(self, message):
        if self.state == IO_CONNECTED:
            self.client.publish(IO_TOPIC_OUTPUT_OBSERVER.format(self.node_id), bytearray(message))

    def start(self):
        self.state = IO_CONNECTING
        print('connecting to {0}:{1}'.format(self.broker_address, self.broker_port))
        print(repr(self.client.on_connect))

        self.client.connect(self.broker_address,
                            self.broker_port,
                            self.keepalive_period)
        self.client.loop_start()

    def stop(self):
        self.state = IO_DISCONNECTING
        self.client.disconnect()
        self.client.loop_stop()
        self.state = IO_READY

    def rest_get_command(self, command):
        # verify that the command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        self.commands[command]()
        bottle.response.status = m_common.REST_REQUEST_FULFILLED
        return self.status()

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
        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_MISSING_ARGUMENT.format(missing_arguments)
        # issue the command
        try:
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.IOException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

# -*- coding: utf-8 -*-
"""
Input/Output module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2016/12/05
Copyright 2016 Orange

"""
import os
import errno
import bottle
from pydispatch import dispatcher
import socket
import paho.mqtt.client as mqtt
import yaml
import subprocess
import logging
import threading
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
        IO_READY,
        IO_CONNECTING,
        IO_CONNECTED,
        IO_DISCONNECTING
    ],
    m_common.COMMAND_START: [
        IO_READY,
        IO_DISCONNECTED
    ],
    m_common.COMMAND_STOP: [
        IO_CONNECTED
    ],
    m_common.COMMAND_RESET: [
        IO_READY,
        IO_DISCONNECTED
    ],
    m_common.COMMAND_SETUP: [
        IO_READY,
        IO_DISCONNECTED,
    ]
}

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

    @staticmethod
    def on_connect(client, io, flags, rc):
        """
        Callback triggered when the MQTT client is connected
        :param client: MQTT client
        :param io: the IO instance
        :param flags: MQTT flags, reported by the MQTT broker
        :param rc: connection result
        :return: None
        """
        del flags
        if rc is mqtt.CONNACK_ACCEPTED:
            logger.info('connected to {0}:{1}'.format(io.broker_address, io.broker_port))
            io.state = IO_CONNECTED
            # save configuration for next bootstrap
            try:
                os.makedirs(os.path.dirname(LAST_CONFIGURATION))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            try:
                with open(LAST_CONFIGURATION, 'w') as configuration_file:
                    configuration = yaml.dump({
                        'broker_address': io.broker_address,
                        'broker_port': io.broker_port,
                        'keepalive_period': io.keepalive_period
                    })
                    configuration_file.write(configuration)
            except (OSError, yaml.YAMLError):
                raise m_common.IOSetupException(
                    'error while saving the configuration: {0}:{1}({2})'.format(
                        io.broker_address,
                        io.broker_port,
                        io.keepalive_period
                    )
                )
            dispatcher.connect(io.send, signal=m_common.IO_SEND)
            client.subscribe(m_common.IO_TOPIC_NODE_INPUT.format(observer_id=io.node_id))
        else:
            logger.error('connection error: {0}'.format(mqtt.connack_string(rc)))
            io.state = IO_DISCONNECTED

    @staticmethod
    def on_disconnect(client, io, rc):
        """
        Callback triggered when the MQTT client is disconnected
        :param client: MQTT client
        :param io: the IO instance
        :param rc: disconnection result
        :return: None
        """
        if rc is mqtt.MQTT_ERR_SUCCESS:
            logger.info('disconnected from {0}:{1}'.format(io.broker_address, io.broker_port))
            dispatcher.disconnect(io.send, signal=m_common.IO_SEND)
            # MQTT client disconnected, stop its thread
            io.alive = False
        else:
            logger.error('disconnected unexpectedly from {0}:{1} with error: {2}'.format(
                io.broker_address, io.broker_port, rc
            ))
            logger.error('diagnosing the issue...')
            with subprocess.Popen(["ping", "-c5", io.broker_address], stdout=subprocess.PIPE) as output:
                connectivity = output.stdout.read()
            with subprocess.Popen(["ifconfig", "-a"], stdout=subprocess.PIPE) as output:
                interfaces = output.stdout.read()
            with subprocess.Popen(["systemctl", "status", "wvdial-startup"], stdout=subprocess.PIPE) as output:
                broadband = output.stdout.read()
            logger.error('unexpectedly disconnected from {0}:{1}'
                         .format(io.broker_address, io.broker_port))
            for line in connectivity.decode('utf-8').splitlines(True):
                logger.error(line)
            for line in interfaces.decode('utf-8').splitlines(True):
                logger.error(line)
            for line in broadband.decode('utf-8').splitlines(True):
                logger.error(line)
            io.state = IO_DISCONNECTED
            # reconnect attempts loop
            again = True
            while io.alive and again:
                logger.info('trying to reconnect to {0}:{1}'.format(io.broker_address, io.broker_port))
                try:
                    again = False
                    client.reconnect()
                except socket.error as e:
                    logger.error('could not reconnect to {0}:{1}: {2}'
                                 .format(io.broker_address, io.broker_port, e.strerror))
                    again = True

    @staticmethod
    def on_subscribe(client, io, mid, granted_qos):
        """
        Callback triggered when the MQTT client subscription is acknowledged by the broker
        :param client: MQTT client - unused
        :param io: the IO instance
        :param mid: message ID - unused
        :param granted_qos: QoS granted to subscription
        :return: None
        """
        del client, mid
        logger.info(
            'subscribed to : ' + m_common.IO_TOPIC_NODE_INPUT.format(observer_id=io.node_id) +
            ' (QoS: {0})'.format(granted_qos))

    @staticmethod
    def on_unsubscribe(client, io, mid):
        """
        Callback triggered when the MQTT client unsubscription is acknowledged by the broker
        :param client: MQTT client - unused
        :param io: the IO instance
        :param mid: message ID - unused
        :return:
        """
        del mid
        logger.info('unsubscribed from : ' + m_common.IO_TOPIC_NODE_INPUT.format(observer_id=io.node_id))
        logger.info('disconnecting from from {0}:{1}'.format(io.broker_address, io.broker_port))
        client.disconnect()

    @staticmethod
    def on_message(client, io, message):
        """
        Callback triggered when the MQTT client receives a message
        :param client: MQTT client - unused
        :param io: the IO instance
        :param message: message
        :return:
        """
        del client
        logger.info('received message: ' + str(message))
        io.receive(message)

    @staticmethod
    def on_publish(client, io, mid):
        """
        Callback triggered when the MQTT published message is acknowledged
        :param client: MQTT client - unused
        :param io: the IO instance
        :param mid: message ID - unused
        :return:
        """
        del client, io, mid
        # logger.info("message acknowledged")

    @staticmethod
    def on_log(client, io, level, buf):
        del client, io
        if level is mqtt.MQTT_LOG_DEBUG:
            logger.debug(buf)
        elif level is mqtt.MQTT_LOG_INFO:
            logger.info(buf)
        elif level is mqtt.MQTT_LOG_NOTICE:
            logger.info(buf)
        elif level is mqtt.MQTT_LOG_WARNING:
            logger.warning(buf)
        elif level is mqtt.MQTT_LOG_ERR:
            logger.error(buf)
        else:
            logger.error(buf)

    def __init__(self, node_id):
        self.state = IO_DISCONNECTED
        self.node_id = node_id
        self.client_id = 'node-{0}'.format(node_id)
        self.broker_address = None
        self.broker_port = None
        self.keepalive_period = None
        self.client = None
        self.thread = None
        self.alive = False

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
            return self.start()
        except:
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.broker_address, self.broker_port)
                )
            )

    def send(self, topic, message):
        self.client.publish(topic, message, qos=2)

    def receive(self, message):
        if self.state == IO_CONNECTED:
            dispatcher.send(signal=m_common.IO_RECV, message=message.payload)

    def start(self):
        logger.info('invoking MQTT client and network loop thread...')
        self.alive = True
        self.thread = threading.Thread(target=self._run)
        self.client = mqtt.Client(client_id=self.client_id, clean_session=True, userdata=self, protocol='MQTTv311')
        self.client.max_inflight_messages_set(100)
        self.client.on_connect = IO.on_connect
        self.client.on_message = IO.on_message
        self.client.on_disconnect = IO.on_disconnect
        self.client.on_subscribe = IO.on_subscribe
        self.client.on_unsubscribe = IO.on_unsubscribe
        self.client.on_publish = IO.on_publish
        self.client.on_log = IO.on_log
        self.state = IO_READY

        self.thread.start()
        self.state = IO_CONNECTING
        try:
            logger.info('connecting to {0}:{1}'.format(self.broker_address, self.broker_port))
            self.client.connect(self.broker_address, self.broker_port, self.keepalive_period)
            return self.status()
        except socket.error:
            self.state = IO_DISCONNECTED
            logger.error('cannot connect to {0}:{1}'.format(self.broker_address, self.broker_port))
            raise m_common.IOSetupException(
                m_common.ERROR_CONFIGURATION_FAIL.format(
                    'cannot connect to {0}:{1}'.format(self.broker_address, self.broker_port)
                )
            )

    def stop(self):
        if self.client:
            self.state = IO_DISCONNECTING
            logger.info('unsubscribing from : ' + m_common.IO_TOPIC_NODE_INPUT.format(observer_id=self.node_id))
            self.client.unsubscribe(m_common.IO_TOPIC_NODE_INPUT.format(observer_id=self.node_id))
            # MQTT client disconnected, stop its thread
            self.thread.join()
            self.client = None
            self.state = IO_READY
            return self.status()

    def reset(self):
        logger.info('resetting configuration...')
        self.client = None
        self.thread = None
        self.alive = False
        self.state = IO_DISCONNECTED
        self.broker_address = None
        self.broker_port = None
        self.keepalive_period = None
        self.client = None
        return self.status()

    def _run(self):
        while self.alive:
            self.client.loop()
        logger.info('mqtt client thread stopped')

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

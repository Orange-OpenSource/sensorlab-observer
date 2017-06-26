# -*- coding: utf-8 -*-
"""
Node/Experiment module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2016/12/05
Copyright 2015 Orange

"""
from pydispatch import dispatcher

from .. import m_common
from .. import m_sensorlab

from . import m_node_setup
from . import m_node_controller
from . import m_node_serial

from . import m_experiment_setup
from . import m_experiment_scheduler

from datetime import datetime

import time

import struct
import bottle
import tempfile
import os
import errno
import json

# node states
NODE_UNDEFINED = 0
NODE_LOADING = 1
NODE_READY = 2
NODE_HALTED = 3
NODE_RUNNING = 4
NODE_STATES = ('undefined', 'loading', 'ready', 'halted', 'running')

# experiment states
EXPERIMENT_UNDEFINED = 0
EXPERIMENT_LOADING = 1
EXPERIMENT_READY = 2
EXPERIMENT_HALTED = 3
EXPERIMENT_RUNNING = 4
EXPERIMENT_STATES = ('undefined', 'loading', 'ready', 'halted', 'running')

# node commands
NODE_GET_COMMANDS = [m_common.COMMAND_STATUS,
                     m_common.COMMAND_INIT,
                     m_common.COMMAND_START,
                     m_common.COMMAND_STOP,
                     m_common.COMMAND_RESET]

NODE_POST_COMMANDS = [m_common.COMMAND_SETUP,
                      m_common.COMMAND_LOAD]

NODE_COMMAND_ALLOWED_STATES = {
    m_common.COMMAND_STATUS: [
        NODE_UNDEFINED,
        NODE_LOADING,
        NODE_READY,
        NODE_HALTED,
        NODE_RUNNING
    ],
    m_common.COMMAND_START: [
        NODE_READY,
        NODE_HALTED
    ],
    m_common.COMMAND_STOP: [
        NODE_RUNNING
    ],
    m_common.COMMAND_RESET: [
        NODE_READY,
        NODE_HALTED
    ],
    m_common.COMMAND_SETUP: [
        NODE_UNDEFINED,
        NODE_HALTED,
        NODE_READY
    ]
}

# experiment commands
EXPERIMENT_GET_COMMANDS = [m_common.COMMAND_STATUS,
                           m_common.COMMAND_START,
                           m_common.COMMAND_STOP,
                           m_common.COMMAND_RESET]

EXPERIMENT_POST_COMMANDS = [m_common.COMMAND_SETUP]

EXPERIMENT_COMMAND_ALLOWED_STATES = {
    m_common.COMMAND_STATUS: [
        EXPERIMENT_UNDEFINED,
        EXPERIMENT_LOADING,
        EXPERIMENT_READY,
        EXPERIMENT_HALTED,
        EXPERIMENT_RUNNING
    ],
    m_common.COMMAND_START: [
        EXPERIMENT_READY
    ],
    m_common.COMMAND_STOP: [
        EXPERIMENT_RUNNING
    ],
    m_common.COMMAND_RESET: [
        EXPERIMENT_READY,
        EXPERIMENT_HALTED
    ],
    m_common.COMMAND_SETUP: [
        EXPERIMENT_UNDEFINED,
        EXPERIMENT_HALTED,
        EXPERIMENT_READY
    ]
}

# persistent profile and experiment filenames
LAST_PROFILE = os.path.join(m_common.PERSISTENCE_DIR, 'last_profile.tar.gz')
LAST_EXPERIMENT = os.path.join(m_common.PERSISTENCE_DIR, 'last_experiment.tar.gz')


# node POST request arguments
PROFILE_FILE = 'profile'
FIRMWARE_FILE = 'firmware'
FIRMWARE_NAME = 'firmware_id'

# node POST required arguments
NODE_REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [PROFILE_FILE], 'forms': []},
    m_common.COMMAND_LOAD: {'files': [FIRMWARE_FILE], 'forms': [FIRMWARE_NAME]},
}

# experiment POST request arguments
BEHAVIOR_FILE = 'behavior'
EXPERIMENT_ID = 'experiment_id'

# experiment POST required arguments
EXPERIMENT_REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [BEHAVIOR_FILE], 'forms': [EXPERIMENT_ID]},
}

# default values
HARDWARE_UNDEFINED = 'undefined'
CONTROLLER_UNDEFINED = 'undefined'
SERIAL_UNDEFINED = 'undefined'
FIRMWARE_UNDEFINED = 'undefined'

OUTPUT_BINARY = 'binary'
OUTPUT_JSON = 'json'
OUTPUT_BOTH = 'both'


class Node:
    def __init__(self, node_id, debug=False):
        # initialize instances attributes
        self.node_id = node_id
        self.node_hardware = None
        self.node_state = NODE_UNDEFINED
        self.node_firmware = None
        self.node_controller = None
        self.node_serial = None
        self.node_loader = None

        self.latitude = None
        self.longitude = None
        self.altitude = None

        #Current Monitor
        self.shunt_voltage = []
        self.bus_voltage = []
        self.current = []
        self.power = []
        self.timestamp = []
        

        self.experiment_id = None
        self.experiment_state = EXPERIMENT_UNDEFINED
        self.experiment_firmwares = None
        self.experiment_scheduler = m_experiment_scheduler.Scheduler()
        self.experiment_loader = None

        self.output = None
        self.decoder = None

        self.debug = debug

        self.node_commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.node_setup,
            m_common.COMMAND_INIT: self.node_init,
            m_common.COMMAND_LOAD: self.node_load,
            m_common.COMMAND_START: self.node_start,
            m_common.COMMAND_STOP: self.node_stop,
            m_common.COMMAND_RESET: self.node_reset,
            m_common.COMMAND_SEND: self.node_send
        }

        self.experiment_commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.experiment_setup,
            m_common.COMMAND_START: self.experiment_start,
            m_common.COMMAND_STOP: self.experiment_stop,
            m_common.COMMAND_RESET: self.experiment_reset,
        }

        for command, method in self.node_commands.items():
            dispatcher.connect(method, "node.{0}".format(command))

        dispatcher.connect(self._location_update, m_common.LOCATION_UPDATE)
        dispatcher.connect(self._current_monitor_update, m_common.CURRENT_MONITOR_UPDATE)

        # setup node with last profile, if it exists
        if os.path.exists(LAST_PROFILE):
            try:
                self.node_setup(LAST_PROFILE)
            except (m_common.NodeControllerCommandException, m_common.NodeSetupException):
                pass

        # setup experiment with last experiment profile, if node setup went smoothly
        if self.node_state == NODE_READY and os.path.exists(LAST_EXPERIMENT):
            now = datetime.now()
            try:
                self.experiment_setup(
                    'experiment-{0}-{1}{2}{3}-{4}'.format(self.node_id, now.year, now.month, now.day, now.hour),
                    LAST_EXPERIMENT
                )
            except m_common.ExperimentSetupException:
                pass

    def status(self):
        status = {
            'id': self.node_id,
            'hardware': {
                'id': self.node_hardware if self.node_hardware else HARDWARE_UNDEFINED,
                'state': NODE_STATES[self.node_state],
                'firmware': self.node_firmware if self.node_firmware else FIRMWARE_UNDEFINED
            }
        }
        if self.experiment_state is EXPERIMENT_READY:
            status['experiment'] = {
                'id': self.experiment_id,
                'state': EXPERIMENT_STATES[self.experiment_state],
                'duration': self.experiment_scheduler.duration_status(),
            }
        elif self.experiment_state in [EXPERIMENT_RUNNING, EXPERIMENT_HALTED]:
            status['experiment'] = {
                'id': self.experiment_id,
                'state': EXPERIMENT_STATES[self.experiment_state],
                'duration': self.experiment_scheduler.duration_status(),
                'remaining': self.experiment_scheduler.remaining_status(),
                'progress': self.experiment_scheduler.progress_status()
            }
        return status

    def node_setup(self, profile, output=OUTPUT_BOTH):
        self._io_debug('setup')
        # clean current node_state
        if self.node_state == NODE_RUNNING:
            self.node_stop()
        if self.node_state == NODE_HALTED:
            self.node_controller.reset()
        if self.node_loader:
            self.node_loader.clean()
            self.node_loader = None

        # set output formats
        self.output = output

        # reset node state
        self.node_state = NODE_UNDEFINED
        self.node_firmware = None
        # load node profile archive
        self.node_loader = m_node_setup.Loader(profile)
        node_profile = self.node_loader.manifest
        # save profile for next bootstrap
        if type(profile) is bottle.FileUpload:
            try:
                os.makedirs(os.path.dirname(LAST_PROFILE))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            profile.save(LAST_PROFILE, overwrite=True)
        # identify hardware
        self.node_hardware = node_profile['hardware']
        # load node modules
        self.node_controller = m_node_controller.Controller(node_profile['controller'])
        self.node_serial = m_node_serial.Serial(node_profile['serial'], self._io_data, self._io_log)
        # attempt to halt and init hardware node
        try:
            self.node_controller.stop()
            self.node_controller.reset()
            self.node_controller.init()
            self.node_serial.init()
            self.node_state = NODE_READY
            self.decoder = m_sensorlab.Decoder()

            data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_ADD, 2)
            data += m_sensorlab.property_declaration_payload(
                m_sensorlab.STATE_PROPERTY_ID,
                m_sensorlab.PREFIX_NONE,
                m_sensorlab.UNIT_NONE,
                m_sensorlab.TYPE_ASCII_ARRAY,
                len('state'),
                len('undefined'),
                'state',
                'undefined')

            data += m_sensorlab.property_declaration_payload(m_sensorlab.FIRMWARE_PROPERTY_ID,
                                                             m_sensorlab.PREFIX_NONE,
                                                             m_sensorlab.UNIT_NONE,
                                                             m_sensorlab.TYPE_ASCII_ARRAY,
                                                             len('firmware'),
                                                             len('undefined'),
                                                             'firmware',
                                                             'undefined')
            # send it
            timestamp = time.time()
            self._io_log(timestamp, data)

        except m_common.NodeControllerCommandException:
            # commands passed to the node failed, reset state
            self.node_state = NODE_UNDEFINED
            self.node_hardware = HARDWARE_UNDEFINED
            self.node_firmware = None
            self.node_controller = None
            self.node_serial = None
            raise m_common.NodeControllerCommandException('could not initialize node. Wrong profile?')

    def node_init(self):
        self._io_debug('init')
        self.node_controller.stop()
        self.node_controller.init()
        self.node_serial.init()
        self.node_state = NODE_READY
        self.decoder.reset()

        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(
            m_sensorlab.STATE_PROPERTY_ID,
            m_sensorlab.TYPE_ASCII_ARRAY,
            len('initialized'),
            'initialized')
        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

    def node_start(self):
        self._io_debug('start')
        if self.node_state in (NODE_READY, NODE_HALTED):
            self.node_state = NODE_RUNNING
            self.node_serial.start()
            self.node_controller.start()
            dispatcher.connect(self.node_send, m_common.IO_RECV)

        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(
                    m_sensorlab.STATE_PROPERTY_ID,
                    m_sensorlab.TYPE_ASCII_ARRAY,
                    len('running'),
                    'running')
        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

    def node_stop(self):
        self._io_debug('stop')
        if self.node_state == NODE_RUNNING:
            self.node_controller.stop()
            self.node_serial.stop()
            dispatcher.disconnect(self.node_send, m_common.IO_RECV)
        elif self.node_state == NODE_READY:
            self.node_init()
        self.node_state = NODE_HALTED

        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('halted'),
                                                       'halted')
        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

    def node_reset(self):
        self._io_debug('reset')
        if self.node_state == NODE_RUNNING:
            self.node_stop()
        if self.node_controller:
            self.node_controller.reset()
        if self.node_serial:
            self.node_serial.reset()
        self.node_state = NODE_READY

        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('reset'),
                                                       'reset')
        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)
        self.decoder.reset()

    def node_load(self, firmware_id, firmware=None):
        self._io_debug('load {0}'.format(firmware_id))
        if self.node_state == NODE_RUNNING:
            self.node_stop()
        if self.node_state == NODE_HALTED:
            self.node_reset()
        self.node_state = NODE_LOADING
        if isinstance(firmware, bottle.FileUpload):
            temp_directory = tempfile.mkdtemp()
            firmware_path = os.path.join(temp_directory + firmware.name)
            firmware.save(firmware_path)
            firmware = firmware_path
        else:
            firmware = self.experiment_firmwares[firmware_id]

        self.node_controller.load(firmware)
        self.node_firmware = firmware_id
        self.node_state = NODE_READY
        self.decoder.reset()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.FIRMWARE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len(self.node_firmware),
                                                       self.node_firmware)
        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

    def node_send(self, message):
        self._io_debug('send {0}'.format(message))
        if self.node_state == NODE_RUNNING:
            self.node_serial.send(message)

    def experiment_setup(self, experiment_id, behavior, output=OUTPUT_BOTH):
        self._io_debug('setup {0}'.format(experiment_id))
        self.experiment_id = experiment_id
        self.experiment_loader = m_experiment_setup.Loader(behavior)
        self.experiment_firmwares = self.experiment_loader.firmwares
        self.experiment_scheduler.setup(self.experiment_loader.schedule)
        # save profile for next bootstrap
        if type(behavior) is bottle.FileUpload:
            try:
                os.makedirs(os.path.dirname(LAST_EXPERIMENT))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            behavior.save(LAST_EXPERIMENT, overwrite=True)
        # choose the output formats
        self.output = output
        # declare the experiment ready
        self.experiment_state = EXPERIMENT_READY

    def experiment_start(self):
        self._io_debug('start')
        # declare the experiment running
        self.experiment_state = EXPERIMENT_RUNNING
        # advertise the addition of a new node to the experiment
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_ADD, 5)
        # including the node initial location
        data += m_sensorlab.property_declaration_payload(m_sensorlab.LATITUDE_PROPERTY_ID,
                                                         m_sensorlab.PREFIX_NONE,
                                                         m_sensorlab.UNIT_NONE,
                                                         m_sensorlab.TYPE_FLOAT,
                                                         len('latitude'),
                                                         4,
                                                         'latitude',
                                                         self.latitude if type(self.latitude) is float else -1)
        data += m_sensorlab.property_declaration_payload(m_sensorlab.LONGITUDE_PROPERTY_ID,
                                                         m_sensorlab.PREFIX_NONE,
                                                         m_sensorlab.UNIT_NONE,
                                                         m_sensorlab.TYPE_FLOAT,
                                                         len('longitude'),
                                                         4,
                                                         'longitude',
                                                         self.longitude if type(self.longitude) is float else -1)
        data += m_sensorlab.property_declaration_payload(m_sensorlab.ALTITUDE_PROPERTY_ID,
                                                         m_sensorlab.PREFIX_NONE,
                                                         m_sensorlab.UNIT_NONE,
                                                         m_sensorlab.TYPE_FLOAT,
                                                         len('altitude'),
                                                         4,
                                                         'altitude',
                                                         self.altitude if type(self.altitude) is float else -1)
        # with a firmware property set to 'none'
        data += m_sensorlab.property_declaration_payload(m_sensorlab.FIRMWARE_PROPERTY_ID,
                                                         m_sensorlab.PREFIX_NONE,
                                                         m_sensorlab.UNIT_NONE,
                                                         m_sensorlab.TYPE_ASCII_ARRAY,
                                                         len('firmware'),
                                                         len('none'),
                                                         'firmware',
                                                         'none')
        # and state property set to 'inactive'
        data += m_sensorlab.property_declaration_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                         m_sensorlab.PREFIX_NONE,
                                                         m_sensorlab.UNIT_NONE,
                                                         m_sensorlab.TYPE_ASCII_ARRAY,
                                                         len('state'),
                                                         len('inactive'),
                                                         'state',
                                                         'inactive')

        # send it
        timestamp = time.time()
        self._io_log(timestamp, data)

        # start the scheduler
        self.experiment_scheduler.start(self._experiment_end)

    def experiment_stop(self):
        self._io_debug('stop')

        # stop the node
        self.node_stop()
        self.node_reset()
        # stop the scheduler
        self.experiment_scheduler.stop()
        timestamp = time.time()

        # advertise to the new node state
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 2)
        data += m_sensorlab.property_reference_payload(m_sensorlab.FIRMWARE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('none'),
                                                       'none')
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('terminated'),
                                                       'terminated')

        # send it
        self._io_log(timestamp, data)

        # declare the experiment halted
        self.experiment_state = EXPERIMENT_HALTED

    def experiment_reset(self):
        self._io_debug('reset')
        # clean the loader files
        if self.experiment_loader:
            self.experiment_loader.clean()
            self.experiment_loader = None

        # reset node state
        self.node_reset()

        # reset the experiment state
        self.experiment_id = None
        self.experiment_state = EXPERIMENT_UNDEFINED
        self.experiment_firmwares = None
        self.experiment_scheduler = m_experiment_scheduler.Scheduler()

        # try to reload the last experiment
        if self.node_state == NODE_READY and os.path.exists(LAST_EXPERIMENT):
            now = datetime.now()
            try:
                self.experiment_setup(
                    'experiment-{0}-{1}{2}{3}-{4}'.format(self.node_id, now.year, now.month, now.day, now.hour),
                    LAST_EXPERIMENT
                )
            except m_common.ExperimentSetupException:
                pass

    def _experiment_end(self):
        self._io_debug('end')
        self.experiment_stop()
        self.experiment_reset()

    def _io_data(self, _, message):
        if self.experiment_state == EXPERIMENT_RUNNING:
            topic = m_common.IO_TOPIC_EXPERIMENT_OUTPUT_DATA.format(
                experiment_id=self.experiment_id,
                node_id=self.node_id
            )
        else:
            topic = m_common.IO_TOPIC_NODE_OUTPUT_DATA.format(
                node_id=self.node_id
            )

        dispatcher.send(
            signal=m_common.IO_SEND,
            sender=self,
            topic=topic,
            message=message
        )

    def _io_log(self, timestamp, message):
        # build message with PCAP record, etc.
        time_s = int(timestamp)
        time_us = int(round((timestamp - time_s) * 10 ** 6))
        # build the packet record
        # prepend node ID to the message
        data = struct.pack("<I", self.node_id) + message

        if self.output is not OUTPUT_JSON:
            # build the PCAP record
            record = m_sensorlab.pcap_record(time_s, time_us, data)
            if self.experiment_state == EXPERIMENT_RUNNING:
                topic = m_common.IO_TOPIC_EXPERIMENT_OUTPUT_BINARY.format(experiment_id=self.experiment_id)
            else:
                topic = m_common.IO_TOPIC_NODE_OUTPUT_BINARY

            dispatcher.send(
                signal=m_common.IO_SEND,
                sender=self,
                topic=topic,
                message=bytearray(record)
            )

        if self.output is not OUTPUT_BINARY:
            if self.experiment_state == EXPERIMENT_RUNNING:
                topic = m_common.IO_TOPIC_EXPERIMENT_OUTPUT_JSON.format(experiment_id=self.experiment_id)
            else:
                topic = m_common.IO_TOPIC_NODE_OUTPUT_JSON
            try:
                json_object = self.decoder.decode(timestamp, bytearray(data))

                dispatcher.send(
                    signal=m_common.IO_SEND,
                    sender=self,
                    topic=topic,
                    message=json.dumps(json_object)
                )
            except m_common.DecoderException as e:
                dispatcher.send(
                    signal=m_common.IO_SEND,
                    sender=self,
                    topic=topic,
                    message=json.dumps({'nodeId': self.node_id, 'error': e.message})
                )

    def _io_debug(self, message):
        if self.debug is True:
            if self.experiment_state is EXPERIMENT_UNDEFINED:
                dispatcher.send(
                    signal=m_common.IO_SEND,
                    sender=self,
                    topic=m_common.IO_TOPIC_PLATFORM_LOG.format(observer_id=self.node_id, module='node'),
                    message=str(message)
                )
            else:
                dispatcher.send(
                    signal=m_common.IO_SEND,
                    sender=self,
                    topic=m_common.IO_TOPIC_PLATFORM_LOG.format(observer_id=self.node_id, module='experiment'),
                    message=str(message)
                )

    def _location_update(self, latitude, longitude, altitude):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        # self._io_debug('location update: ({0},{1})[{2}]'.format(latitude, longitude, altitude))
        if self.experiment_state == EXPERIMENT_RUNNING\
                and self.experiment_scheduler.state == m_experiment_scheduler.SCHEDULER_RUNNING:
            data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 3)
            data += m_sensorlab.property_reference_payload(m_sensorlab.LATITUDE_PROPERTY_ID,
                                                           m_sensorlab.TYPE_FLOAT,
                                                           4,
                                                           self.latitude)
            data += m_sensorlab.property_reference_payload(m_sensorlab.LONGITUDE_PROPERTY_ID,
                                                           m_sensorlab.TYPE_FLOAT,
                                                           4,
                                                           self.longitude)
            data += m_sensorlab.property_reference_payload(m_sensorlab.ALTITUDE_PROPERTY_ID,
                                                           m_sensorlab.TYPE_FLOAT,
                                                           4,
                                                           self.altitude)
            timestamp = time.time()
            self._io_log(timestamp, data)

    def _current_monitor_update(self, shunt_voltage, bus_voltage, current, power,timestamp):
        self.shunt_voltage = shunt_voltage
        self.bus_voltage = bus_voltage
        self.current = current
        self.power = power
        self.timestamp = timestamp
        #self._io_debug('current monitor update: ({0},{1},{2},{3})'.format(shunt_voltage,bus_voltage,current,power))

        if self.experiment_state == EXPERIMENT_RUNNING\
                and self.experiment_scheduler.state == m_experiment_scheduler.SCHEDULER_RUNNING:
            data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 4)
            data += m_sensorlab.property_reference_payload(m_sensorlab.SHUNT_VOLTAGE_PROPERTY_ID,
                                                            m_sensorlab.TYPE_FLOAT_ARRAY,
                                                            len(self.shunt_voltage), 
                                                            self.shunt_voltage)
            data += m_sensorlab.property_reference_payload(m_sensorlab.BUS_VOLTAGE_PROPERTY_ID,
                                                            m_sensorlab.TYPE_FLOAT_ARRAY,
                                                            len(self.bus_voltage),
                                                            self.bus_voltage)
            data += m_sensorlab.property_reference_payload(m_sensorlab.CURRENT_PROPERTY_ID,
                                                            m_sensorlab.TYPE_FLOAT_ARRAY,
                                                            len(self.current),
                                                            self.current)
            data += m_sensorlab.property_reference_payload(m_sensorlab.POWER_PROPERTY_ID,
                                                            m_sensorlab.TYPE_FLOAT_ARRAY,
                                                            len(self.power),
                                                            self.power)
            data += m_sensorlab.property_reference_payload(m_sensorlab.POWER_PROPERTY_ID,
                                                            m_sensorlab.TYPE_FLOAT_ARRAY,
                                                            len(self.timestamp),
                                                            self.timestamp)                                             
            timestamp = time.time()
            self._io_log(timestamp, data)
           
    def rest_get_node_command(self, command):
        # check that command exists
        if command not in NODE_GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # check that command is allowed in this context
        if self.node_state not in NODE_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(NODE_STATES[self.node_state])
            )
        # issue the command and return
        try:
            self.node_commands[command]()
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.REST_INTERNAL_ERROR.format(e.message)

    def rest_post_node_command(self, command):
        # check that command exists
        if command not in NODE_POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
        # check that command is allowed in this context
        if self.node_state not in NODE_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(NODE_STATES[self.node_state])
            )
        # node_load arguments
        arguments = {}
        for required_file_argument in NODE_REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in NODE_REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_REQUEST.format(missing_arguments)
        # issue the command
        try:
            self.node_commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

    def rest_get_experiment_command(self, command):
        # check that command exists
        if command not in EXPERIMENT_GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # check that command is allowed in this context
        if self.experiment_state not in EXPERIMENT_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(EXPERIMENT_STATES[self.node_state])
            )
        # issue the command and return
        try:
            self.experiment_commands[command]()
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.REST_INTERNAL_ERROR.format(e.message)

    def rest_post_experiment_command(self, command):
        # check that command exists
        if command not in EXPERIMENT_POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
        # check that command is allowed in this context
        if self.experiment_state not in EXPERIMENT_COMMAND_ALLOWED_STATES[command]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(
                command,
                'state: {0}'.format(EXPERIMENT_STATES[self.node_state])
            )
        # load arguments
        arguments = {}
        for required_file_argument in EXPERIMENT_REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in EXPERIMENT_REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_REQUEST.format(missing_arguments)
        # issue the command
        try:
            self.experiment_commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Sensorlab node module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2016/06/16
Copyright 2016 Orange

# Overview
-----------
This module is a configurable module that controls the execution flow of the hardware device - or `node` - that is
 connected to the observer. To interact with this module, one uses the observer's REST API, more specifically `node` and
 `experiment` prefixed commands. `node` prefixed and `experiment` prefixed commands are mapped to  `node_` and
 `experiment_` methods listed below:
    - using `node_` prefixed commands, one interacts directly with the node, e.g. `node_load` flashes a firmware on the
    hardware node as soon as the command is received. These commands are further detailed in the *Node API* section.
    - using `experiment_` prefixed commands, one interacts with the hardware via a scenario - or `behavior` -.
    This `behavior` defines a schedule of node commands (and parameters), i.e. commands and time intervals between
    those commands. These commands are further detailed in the *Experiment API* section.

## Node API
-------------------------------------------
The node module API consists of a 7 node commands: `node_setup`, `node_init`, `node_load`, `node_start`, `node_stop`,
`node_reset` and `node_send`.

    - `node_setup`(`profile`)        			:	Setups the node module to interact with a specific hardware.
    - `node_init`(`none`)						:	initialize the node hardware.
    - `node_load`(`firmware`)					:	load firmware in the node hardware.
    - `node_start`								:	start the node hardware.
    - `node_stop`								:	stop the node hardware.
    - `node_reset`								:	reset the node hardware.
    - `node_send`(`message`)					:	send a message to the node hardware via its serial interface.

'''


### Setup of the node module
---------------------------
This module, more specifically two of its sub-modules: `controller`and `serial`, can be configured to handle
a variety of node hardware. The configuration is provided  in the form of a `profile` archive, of type **tar.gz**, which
must contain the following directories and files:

    - `controller/`: configuration files and executables used by the node controller.

        - `executables/`: executables used in control node_commands.

        - `configuration_files/`: executables configuration files.

    - `serial/`: contains the python module that reports frames sent on the node_serial interface.

    - `manifest.yml`: controller command lines and serial configuration file.

#### Manifest.yml
-----------------
The manifest file complies to the YAML specification.
It must contain the following structure: 

    - `controller`:
        - `commands`:
            - `load` 		:	load a node_firmware into the node
            - `start`	 	: 	start the node
            - `stop` 		:	stop the node
            - `reset`     	:	reset the node

        - `executables`:
            - `id` 			:	executable ID
              `file` 		:	executable
              `brief`		: 	executable short description
            - ...

        - `configuration_files`
            - `id`	 		:	configuration file ID
              `file` 		:	configuration file
              `brief`		: 	configuration file short description
            - ...

    - `serial`:
        - `port` 		:    the node_serial port
        - `baudrate`	:    node_serial interface baudrate
        - `parity`	 	:    parity bits
        - `stopbits` 	:    node_stop bits
        - `bytesize` 	:    byte word size
        - `rtscts`		:    RTS/CTS
        - `xonxoff`		:    XON/XOFF
        - `timeout`		:    timeout of the read action
        - `module` 		:    name of the module that handles node_serial frames

    - `hardware`:
        - `id`			:	the hardware name, e.g. OpenMote

Controller node_commands may contain two types of placeholders :
    - executable placeholders			: identified by a <!name> tag where name is the executable ID.
    - configuration file placeholders	: identified by a <#name> tag where name is the configuration file ID.

Placeholders are resolved when the manifest is parsed for the first time.

## Experiment API
------------------
The experiment API provides the user with a way to submit an experiment script that will be executed
by the observer:
    - `experiment_setup`(`behavior_id`,`behavior`)      :	setup an experiment scenario.
    - `experiment_start`(`none`)						:	start the experiment.
    - `experiment_stop`(`none`)						    : 	stop the experiment.
    - `experiment_reset`(`none`)						:	reset the experiment module.

### Experiment setup
--------------------
The experiment module is configured via the `setup` command.
This `setup` command is sent to the supervisor as a HTTP POST request containing two arguments:
    - `experiment_id            : id of the experiment.
    - `behavior`                : behavior archive.

### Experiment behavior archive
-------------------------------------
The behavior archive is of type **tar.gz** and contains the following directories and files:
    - `firmwares/`: firmwares to load on the hardware node during the experiment.
    - `manifest.yml`: defines the experiment ID, its schedule and I/Os.

#### Manifest.yml
-----------------
The manifest file complies to the YAML specification.
It must contain the following structure:
    - `firmwares`:
        - `id`	 		:	configuration file ID
          `file` 		:	configuration file
          `brief`		: 	configuration file short description
        ...
    - `schedule`:
        - time:             { `origin`, `on-last-event-completion`, duration }
          action:           { `load`, `start`, `stop` }
          parameters:
            parameter:        value
        ...


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
import json
import shutil

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

# experiment commands
EXPERIMENT_GET_COMMANDS = [m_common.COMMAND_STATUS,
                           m_common.COMMAND_START,
                           m_common.COMMAND_STOP,
                           m_common.COMMAND_RESET]

EXPERIMENT_POST_COMMANDS = [m_common.COMMAND_SETUP]

# persistent profile and experiment filenames
LAST_PROFILE = 'last_profile.tar.gz'
LAST_EXPERIMENT = 'last_experiment.tar.gz'


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
                    'experiment-{0}{1}{2}-{3}'.format(now.year, now.month, now.day, now.hour),
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
            if os.path.exists(LAST_PROFILE):
                os.remove(LAST_PROFILE)
            profile.save(LAST_PROFILE)
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
            if os.path.exists(LAST_EXPERIMENT):
                os.remove(LAST_EXPERIMENT)
            behavior.save(LAST_EXPERIMENT)
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

        # reset the experiment state
        self.experiment_id = None
        self.experiment_state = EXPERIMENT_UNDEFINED
        self.experiment_firmwares = None
        self.experiment_scheduler = m_experiment_scheduler.Scheduler()

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

    def rest_get_node_command(self, command):
        # check that command exists
        if command not in NODE_GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
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

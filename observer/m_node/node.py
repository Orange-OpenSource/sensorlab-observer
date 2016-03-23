#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Sensorlab node module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

# Overview
-----------
This module is an abstraction layer on top of the  "hardware" node under test.

# Node abstraction
---------------------
The hardware node is modelled as a state machine, consisting of 5 states:
`undefined`, `loading`, `ready`, `halted`, `running`.

    - `undefined` : the hardware node is in an undefined/unknown state, possibly running or halted.
    - `loading`	  : the hardware node is loading a firmware.
    - `ready`	  : the hardware node is ready to start.
    - `halted`	  : the hardware node is halted. Execution is pending.
    - `running`   : the hardware node is running.


# Node API
----------------
The node module API consists of 7 commands: `status`, `setup`, `init`, `load`, `start`, `stop`, `reset`.

    - `status`(`none`) 						:	Returns information on the node under test.
    - `setup`(`profile`)        			:	Setups the node controller and serial drivers.
    - `init`(`none`)						:	initialize the node hardware.
    - `load`(`firmware`)					:	load firmware in the node hardware.
    - `start`								:	start the node hardware.
    - `stop`								:	stop the node hardware.
    - `reset`								:	reset the node hardware.
    - `send`(`message`)						:	send a message to the node hardware via its serial interface.

'''

# Signal API
----------------
The node module also provide a signal API that allows other modules, e.g. the experiment module, to control the node
activity. There are 6 signals.

    - `NODE_INIT`(`none`)					:	initialize the node hardware.
    - `NODE_LOAD`(`firmware`)				:	load firmware in the node hardware.
    - `NODE_START`(`none`)					:	start the node hardware.
    - `NODE_STOP`(`none`)					:	stop the node hardware.
    - `NODE_RESET`(`none`)					:	reset the node hardware.
    - `NODE_SEND`(`message`)				:	send a message to the node hardware via its serial interface.


## Node profile archive
-----------------------
The profile archive is of type **tar.gz** and contains the following directories and files:

    - `controller/`: configuration files and executables used by the node controller.

        - `executables/`: executables used in control commands.

        - `configuration_files/`: executables configuration files.

    - `serial/`: contains the python module that reports frames sent on the serial interface.

    - `manifest.yml`: controller command lines and serial configuration file.

### Manifest.yml
-----------------
The manifest file complies to the YAML specification.
It must contain the following structure: 

    - `controller`:
        - `commands`:
            - `load` 		:	load a firmware into the node
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
        - `port` 		:    the serial port
        - `baudrate`	:    serial interface baudrate
        - `parity`	 	:    parity bits
        - `stopbits` 	:    stop bits
        - `bytesize` 	:    byte word size
        - `rtscts`		:    RTS/CTS
        - `xonxoff`		:    XON/XOFF
        - `timeout`		:    timeout of the read action
        - `module` 		:    name of the module that handles serial frames

    - `node`:
        - `id`			:	NodeID
          `file`		:	image.png
          `brief`		:	node image short description

Controller commands may contain two types of placeholders : 
    - executable placeholders			: identified by a <!name> tag where name is the executable ID.
    - configuration file placeholders	: identified by a <#name> tag where name is the configuration file ID.

Placeholders are resolved when the manifest is parsed for the first time. 



# I/Os
--------
The `serial` driver is in charge of sending and receiving frames from/to the node serial interface. 

The node module proxies the I/Os and and advertise frames from the hardware node via signals:
    - `m_common.IO_RAW_FROM_NODE` 		: raw data from node
    - `m_common.IO_OBSERVER_FROM_NODE` 	: observer message from node

the node module also register as an handler to `m_common.IO_RAW_TO_NODE` signals. Those signals are sent alongside
with a message that is sent to the hardware node via the `serial` module.


"""
from .. import m_common
from . import m_setup
from . import m_controller
from . import m_serial

import argparse
import platform
import random
import bottle
import tempfile
import os
from pydispatch import dispatcher

# node states
NODE_UNDEFINED = 0
NODE_LOADING = 1
NODE_CONFIGURED = 2
NODE_READY = 3
NODE_HALTED = 4
NODE_RUNNING = 5
NODE_STATES = ('undefined', 'loading', 'configured', 'ready', 'halted', 'running')

# commands
GET_COMMANDS = [m_common.COMMAND_STATUS,
                m_common.COMMAND_INIT,
                m_common.COMMAND_START,
                m_common.COMMAND_STOP,
                m_common.COMMAND_RESET]

POST_COMMANDS = [m_common.COMMAND_SETUP,
                 m_common.COMMAND_LOAD]

# POST request arguments
PROFILE_FILE = 'profile'
FIRMWARE_FILE = 'firmware'
FIRMWARE_NAME = 'firmware_id'

# POST required arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [PROFILE_FILE], 'forms': []},
    m_common.COMMAND_LOAD: {'files': [FIRMWARE_FILE], 'forms': [FIRMWARE_NAME]},
}

# default values
CONTROLLER_UNDEFINED = 'undefined'
SERIAL_UNDEFINED = 'undefined'
FIRMWARE_UNDEFINED = 'undefined'


class Node:
    def __init__(self, node_id):
        # initialize instances attributes
        self.id = node_id
        self.state = NODE_UNDEFINED
        self.firmware = None
        self.controller = None
        self.serial = None
        self.loader = None
        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_INIT: self.init,
            m_common.COMMAND_LOAD: self.load,
            m_common.COMMAND_START: self.start,
            m_common.COMMAND_STOP: self.stop,
            m_common.COMMAND_RESET: self.reset,
            m_common.COMMAND_SEND: self.send
        }
        # connect signals to commands
        for command, method in self.commands.items():
            dispatcher.connect(method, "node.{0}".format(command))

    def status(self):
        return {'id': self.id,
                'state': NODE_STATES[self.state],
                'controller': self.controller.status() if self.controller else CONTROLLER_UNDEFINED,
                'serial': self.serial.status() if self.serial else SERIAL_UNDEFINED,
                'firmware': self.firmware if self.firmware else FIRMWARE_UNDEFINED}

    def setup(self, profile):
        # clean current state
        if self.state == NODE_RUNNING:
            self.stop()
        if self.state == NODE_HALTED:
            self.controller.reset()
        # reset node state
        self.state = NODE_UNDEFINED
        self.firmware = None
        if self.loader:
            self.loader.clean()
        # load archive
        self.loader = m_setup.Loader(profile)
        node_configuration = self.loader.manifest
        # load modules
        self.controller = m_controller.Controller(node_configuration['controller'])
        self.serial = m_serial.Serial(node_configuration['serial'], self._from_node_raw, self._from_node_observer)
        self.state = NODE_CONFIGURED

    def init(self):
        # initialize state after setup is ready
        self.controller.stop()
        self.controller.init()
        self.serial.init()
        self.state = NODE_READY

    def start(self):
        if self.state == NODE_CONFIGURED:
            self.init()
        if self.state in (NODE_READY, NODE_HALTED):
            self.state = NODE_RUNNING
            self.serial.start()
            self.controller.start()
            dispatcher.connect(self.send, m_common.IO_RAW_TO_NODE)

    def stop(self):
        if self.state == NODE_RUNNING:
            self.controller.stop()
            self.serial.stop()
            dispatcher.disconnect(self.send, m_common.IO_RAW_TO_NODE)
        elif self.state == NODE_CONFIGURED:
            self.init()
        self.state = NODE_HALTED

    def reset(self):
        if self.state == NODE_RUNNING:
            self.stop()
        if self.controller:
            self.controller.reset()
        if self.serial:
            self.serial.reset()
        self.state = NODE_READY

    def load(self, firmware, firmware_id):
        if self.state == NODE_RUNNING:
            self.stop()
        if self.state == NODE_HALTED:
            self.reset()
        self.state = NODE_LOADING
        if isinstance(firmware, bottle.FileUpload):
            temp_directory = tempfile.mkdtemp()
            firmware_path = os.path.join(temp_directory + firmware.name)
            firmware.save(firmware_path)
            firmware = firmware_path
        self.controller.load(firmware)
        self.firmware = firmware_id
        self.state = NODE_READY

    def send(self, message):
        if self.state == NODE_RUNNING:
            self.serial.send(message)

    def _from_node_raw(self, timestamp, message):
        if self.state == NODE_RUNNING:
            dispatcher.send(signal=m_common.IO_RAW_FROM_NODE, sender=self, timestamp=timestamp, message=message)

    def _from_node_observer(self, timestamp, message):
        if self.state == NODE_RUNNING:
            dispatcher.send(signal=m_common.IO_OBSERVER_FROM_NODE, sender=self, timestamp=timestamp, message=message)

    def rest_get_command(self, command):
        # check that command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        try:
            self.commands[command]()
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.REST_INTERNAL_ERROR.format(e.message)

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
            print('command: '+command)
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            # return the node status
            return self.status()
        except m_common.NodeException as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)


def main():
    # initialize the arguments parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-cp', '--command_port', type=int, default=5555, help='command port')
    parser.add_argument('-d', '--debug', type=bool, default=True, help='debug output')
    arguments = parser.parse_args()
    # initialize the node module
    hostname = platform.node()
    node_id = hostname.lstrip('observer-') if 'observer-' in hostname else str(random.randint(0, 255))
    node = Node(node_id)

    @bottle.route(['/', '/<command>'])
    def node_get_command(command=m_common.COMMAND_STATUS):
        return node.rest_get_command(command)

    @bottle.route(['/', '/<command>'], method='POST')
    def node_post_command(command=m_common.COMMAND_STATUS):
        return node.rest_post_command(command)

    bottle.run(host='0.0.0.0', port=arguments.command_port, debug=arguments.debug)

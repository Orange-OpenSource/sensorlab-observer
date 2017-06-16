# -*- coding: utf-8 -*-
"""
Observer module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2016/06/16
Copyright 2016 Orange

This module is the front-end of the monitor.
It exposes a REST interface to either control the node or to submit an experiment
scenario that is locally executed by the observer's scheduler.


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



# I/O module
-------------
The I/O module is in charge of relaying 'messages' to and from the platform using the MQTT protocol.
The I/O module exposes 3 methods, respectively to node_setup, initiate and terminate the platform broker connection:

    - `setup`(`address`, `port`)		:	setup the I/O module to connect to address:port
    - `start`(`none`)					:	connect the I/O module.
    - `stop`(`none`)					: 	disconnect the I/O module.
    - `status`(`none`)					: 	Returns information on the I/O module.

# Location module
---------------------
The location module provides information on the node location. It exposes 2 methods, i.e.:

    - `status`(`none`)						: 	Returns information on the location module.
    - `setup`(`latitude`, `longitude`)		:	node_setup the location module to specified location.

# System module
---------------------
The system module provides information on the system state. It exposes 1 method:

    - `status`(`none`)                      :   returns general information on the observer system.
    - `version`(`node`)                     :   returns the observer version number.
    - `sync`(`none`)                        :   returns information on the synchronization state of the system.



# Command API
----------------

This module runs as a standalone process and receives node_commands via a REST web server which serves
incoming requests.

The command API is organised as follows:

    - `/`	: redirects to `/node_status`

        - `node_status`(`none`)							:	 returns information on the observer module.

        - `node/`		:	redirects to `node/status`

            - `setup`(`profile`)    			:	setups the node node_controller and node_serial drivers.
            - `init`(`none`)					:	initialize the node hardware.
            - `load`(`node_firmware`)			:	load node_firmware in the node hardware.
            - `start`(`none`)					:	start the node hardware.
            - `stop`(`none`)					:	stop the node hardware.
            - `reset`(`none`)					:	reset the node hardware.
            - `send`(`message`)					:	send a message to the node hardware via its node_serial interface.
            - `status`(`none`) 					:	returns information on the node module.

        - `experiment/`	:	redirects to `experiment/status`

            - `setup`(`behavior_id`, `behavior`)	:	setup an experiment scenario.
            - `start`(`none`)						:	start the experiment.
            - `stop`(`none`)						: 	stop the experiment.
            - `reset`(`none`)						:	reset the experiment module.
            - `status`(`none`) 						:	returns information on the experiment module.

        - `io/`			:	redirects to `io/status`

            - `setup`(`address`, `port`)	:   setup the I/O module.
            - `start`(`none`)			    :   connect the I/O module.
            - `stop`(`none`)				: 	disconnect the I/O module.
            - `status`(`none`)				: 	returns information on the I/O module.

        - `location/`	:	redirects to `location/status`

            - `status`(`none`)						:	returns information on the location module.
            - `setup`(`latitude`, `longitude`)		:	setup the location module to specified location.

        - `system/`	:	redirects to `system/status`

            - `status`(`none`)						:	returns information on the system module.
            - `version`(`none`)                     :   returns the observer's version.
            - `synchronization`(`none`)		        :	setup the location module to specified location.

Commands requiring no arguments are of type `HTTP GET` while those who require arguments are of type `HTTP POST`.


"""
from . import m_common
from . import m_node
from . import m_io
from . import m_location
from . import m_system
from . import m_current_monitor

import argparse
import platform
import random
import bottle

OBSERVER_UNDEFINED = 0
OBSERVER_READY = 1
OBSERVER_EXPERIMENT_RUNNING = 2
OBSERVER_STATES = ('undefined', 'ready', 'experiment running')

GET_COMMANDS = [m_common.COMMAND_STATUS]
POST_COMMANDS = []

# POST request arguments
OBSERVER_IO_TYPE = 'type'

# POST required arguments
REQUIRED_ARGUMENTS = {}


class Observer:
    def __init__(self, debug=False):
        self.state = OBSERVER_UNDEFINED
        self.io = None
        self.node = None
        self.location = None
        self.current_monitor = None
        self.system = None
        self.debug = debug

        # initialize the node module
        hostname = platform.node()
        node_id = int(hostname.lstrip('observer-')) if 'observer-' in hostname else random.randint(0, 255)
        self.node = m_node.Node(node_id, debug=self.debug)

        # initialize the I/O module
        self.io = m_io.IO(node_id)

        # initialize the GPS module
        #self.location = m_location.GPS()

        # initialize the current monitoring module
        self.current_monitor = m_current_monitor.CurrentMonitor()

        # initialize the m_system module
        self.system = m_system.System()

        # link node_commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
        }

        # ready the supervisor
        self.state = OBSERVER_READY

    def reset(self):
        self.__init__()

    def status(self):
        return {'node': self.node.status(),
                'location': self.location.status(),
                'io': self.io.status(),
                'current_monitor': self.current_monitor.status()}

    def rest_get_command(self, command):
        # check that command exists
        if command not in GET_COMMANDS:
            bottle.response.node_status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(GET)')
        # issue the command and return
        self.commands[command]()
        bottle.response.node_status = m_common.REST_REQUEST_FULFILLED
        return self.status()

    def rest_post_command(self, command):
        # check that command exists
        if command not in POST_COMMANDS:
            bottle.response.node_status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_UNKNOWN.format(command + '(POST)')
        # node_load arguments
        arguments = {}
        for required_file_argument in REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        # check that all arguments have been filled
        if any(argument is None for argument in arguments):
            missing_arguments = filter(lambda argument: arguments[argument] is None, arguments.keys())
            bottle.response.node_status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_MISSING_ARGUMENT.format(command, missing_arguments)
        # issue the command
        self.commands[command](**arguments)
        bottle.response.node_status = m_common.REST_REQUEST_FULFILLED
        # return the node node_status
        return self.status()


def main():
    # initialize the arguments parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-cp', '--command_port', type=int, default=5555, help='command port')
    parser.add_argument('-d', '--debug', type=bool, default=True, help='debug output')
    arguments = parser.parse_args()

    observer = Observer(debug=arguments.debug)

    @bottle.route(['/node', '/node/', '/node/<command>'])
    def node_get_command(command=m_common.COMMAND_STATUS):
        if observer.node.experiment_state in [m_node.EXPERIMENT_RUNNING, m_node.EXPERIMENT_HALTED] \
                and command is not m_common.COMMAND_STATUS:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(command + '(GET)',
                                                           OBSERVER_STATES[OBSERVER_EXPERIMENT_RUNNING])
        else:
            return observer.node.rest_get_node_command(command)

    @bottle.route(['/node', '/node/', '/node/<command>'], method='POST')
    def node_post_command(command=m_common.COMMAND_STATUS):
        if observer.node.experiment_state in [m_node.EXPERIMENT_RUNNING, m_node.EXPERIMENT_HALTED]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(command + '(POST)')
        else:
            return observer.node.rest_post_node_command(command)

    @bottle.route(['/experiment', '/experiment/', '/experiment/<command>'])
    def experiment_get_command(command=m_common.COMMAND_STATUS):
        return observer.node.rest_get_experiment_command(command)

    @bottle.route(['/experiment', '/experiment/', '/experiment/<command>'], method='POST')
    def experiment_post_command(command=m_common.COMMAND_STATUS):
        return observer.node.rest_post_experiment_command(command)

    @bottle.route(['/io', '/io/', '/io/<command>'])
    def io_get_command(command=m_common.COMMAND_STATUS):
        return observer.io.rest_get_command(command)

    @bottle.route(['/io', '/io/', '/io/<command>'], method='POST')
    def io_post_command(command=m_common.COMMAND_STATUS):
        return observer.io.rest_post_command(command)

    @bottle.route(['/location', '/location/', '/location/<command>'])
    def location_get_command(command=m_common.COMMAND_STATUS):
        return observer.location.rest_get_command(command)

    @bottle.route(['/location', '/location/', '/location/<command>'], method='POST')
    def location_post_command(command=m_common.COMMAND_STATUS):
        return observer.location.rest_post_command(command)

    @bottle.route(['/current_monitor', '/current_monitor/', '/current_monitor/<command>'])
    def current_monitor_get_command(command=m_common.COMMAND_STATUS):
        return observer.current_monitor.rest_get_command(command)

    @bottle.route(['/current_monitor', '/current_monitor/', '/current_monitor/<command>'], method='POST')
    def location_post_command(command=m_common.COMMAND_STATUS):
        return observer.current_monitor.rest_post_command(command)

    @bottle.route(['/system', 'system/', '/system/<command>'], method='GET')
    def system_get_command(command=m_common.COMMAND_STATUS):
        return observer.system.rest_get_command(command)

    @bottle.route(['/', '/<command>'])
    def supervisor_get_command(command=m_common.COMMAND_STATUS):
        return observer.rest_get_command(command)

    @bottle.route(['/', '/<command>'], method='POST')
    def supervisor_post_command(command=m_common.COMMAND_STATUS):
        return observer.rest_post_command(command)

    bottle.run(host='0.0.0.0', port=arguments.command_port, debug=arguments.debug)

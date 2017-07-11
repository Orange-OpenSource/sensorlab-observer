# -*- coding: utf-8 -*-
"""
Observer module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange


This module is the front-end of the monitor.
It exposes a REST interface to either control the node or to submit an experiment
scenario that is locally executed by the supervisor's scheduler.


# Node module
-------------------
The node module exposes 8 methods to control the behaviour of the hardware node:

    - `setup`(`configuration`)				:	Setup the node controller and serial drivers.
    - `init`(`none`)						:	initialize the node hardware.
    - `load`(`firmware`)					:	load firmware in the node hardware.
    - `start`(`none`)						:	start the node hardware.
    - `stop`(`none`)						:	stop the node hardware.
    - `reset`(`none`)						:	reset the node hardware.
    - `send`(`message`)						:	send a message to the node hardware via its serial interface.
    - `status`(`none`) 						:	Returns information on the node module.

Those functions are only accessible when no experiment is running. In case of an attempt to
issue node commands while an experiment is running, an error message is returned to the user.

The hardware node is modelled as a state machine, consisting of 5 states:
`undefined`, `loading`, `ready`, `halted`, `running`.

    - `undefined` : the hardware node is in an undefined/unknown state, possibly running or halted.
    - `loading`	  : the hardware node is loading a firmware.
    - `ready`	  : the hardware node is ready to start.
    - `halted`	  : the hardware node is halted. Execution is pending.
    - `running`   : the hardware node is running.

## Node Setup
--------------
The node module is configured via the `setup` command.
This `setup` command is sent to the supervisor as a HTTP POST request containing one argument:

    - `node_configuration`: the module configuration archive.

### Node configuration archive
-------------------------------
The configuration archive is of type **tar.gz** and contains the following directories and files:

    - `controller/`: configuration files and executables used by the node controller.

        - `executables/`: executables used in control commands.

        - `configuration_files/`: executables configuration files.

    - `serial/`: contains the python module that reports frames sent on the serial interface.

    - `manifest.yml`: controller command lines and serial configuration file.

#### Manifest.yml
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

Controller commands may contain two types of placeholders : 
    - executable placeholders			: identified by a <!name> tag where name is the executable ID.
    - configuration file placeholders	: identified by a <#name> tag where name is the configuration file ID.

Placeholders are resolved when the manifest is parsed for the first time. 


# Experiment module
--------------------
The experiment module provides the user with a way to submit an experiment script that will be executed
by the supervisor. The experiment module exposes 4 methods to submit and control experiments:

    - `setup`(`configuration`,`id`)			:	setup an experiment scenario.
    - `start`(`none`)						:	start the experiment.
    - `stop`(`none`)						: 	stop the experiment.
    - `reset`(`none`)						:	reset the experiment module.

## Experiment setup
--------------------
The experiment module is configured via the `setup` command.
This `setup` command is sent to the supervisor as a HTTP POST request containing one argument:

    - `experiment_configuration`: the module configuration archive.

### Experiment configuration archive
-------------------------------------
The configuration archive is of type **tar.gz** and contains the following directories and files:

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
The I/O module exposes 3 methods, respectively to setup, initiate and terminate the platform broker connection:

    - `setup`(`source`, `address`, `port`, `keepalive_period`)		:	setup the I/O module to connect to address:port
    - `start`(`none`)												:	connect the I/O module.
    - `stop`(`none`)												: 	disconnect the I/O module.
    - `status`(`none`)												: 	Returns information on the I/O module.

# Location/GPS module
---------------------
The GPS module provides information on the node location. It exposes 1 method, i.e.:

    - `status`(`none`)												: 	Returns information on the GPS module.



# Command API
----------------

This module runs as a standalone process and receives commands via a REST web server which serves
incoming requests.

The command API is organised as follows:

    - `/`	: redirects to `/status`

        - `status`(`none`)							:	 returns information on the supervisor module.

        - `node/`		:	redirects to `node/status`

            - `setup`(`configuration`)				:	Setups the node controller and serial drivers.
            - `init`(`none`)						:	initialize the node hardware.
            - `load`(`firmware`)					:	load firmware in the node hardware.
            - `start`(`none`)						:	start the node hardware.
            - `stop`(`none`)						:	stop the node hardware.
            - `reset`(`none`)						:	reset the node hardware.
            - `send`(`message`)						:	send a message to the node hardware via its serial interface.
            - `status`(`none`) 						:	returns information on the node module.

        - `experiment/`	:	redirects to `experiment/status`

            - `setup`(`configuration`, `id`)		:	setup an experiment scenario with ID=id.
            - `start`(`none`)						:	start the experiment.
            - `stop`(`none`)						: 	stop the experiment.
            - `reset`(`none`)						:	reset the experiment module.
            - `status`(`none`) 						:	returns information on the experiment module.

        - `io/`			:	redirects to `io/status`

            - `setup`(`source`, `address`, `port`, `keepalive_period`)	:   setup the I/O module.
            - `start`(`none`)											:   connect the I/O module.
            - `stop`(`none`)											: 	disconnect the I/O module.
            - `status`(`none`)											: 	returns information on the I/O module.

        - `location/`	:	redirects to `location/status`

        - `status`(`none`)											:	returns information on the location module.
        - `setup`(`latitude`, `longitude`)							:	setup the location module to specified location.

Commands requiring no arguments are of type `HTTP GET` while those who require arguments are of type `HTTP POST`.


"""
from . import m_common
from . import m_node
from . import m_experiment
from . import m_io
from . import m_location

import argparse
import platform
import random
import bottle


SUPERVISOR_UNDEFINED = 0
SUPERVISOR_READY = 1
SUPERVISOR_EXPERIMENT_RUNNING = 2
SUPERVISOR_STATES = ('undefined', 'ready', 'experiment running')

GET_COMMANDS = [m_common.COMMAND_STATUS]
POST_COMMANDS = []

# POST request arguments
SUPERVISOR_IO_TYPE = 'type'

# POST required arguments
REQUIRED_ARGUMENTS = {}


class Supervisor:
    def __init__(self):
        self.state = SUPERVISOR_UNDEFINED
        self.io = None
        self.node = None
        self.location = None
        # initialize the node module
        hostname = platform.node()
        node_id = int(hostname.lstrip('observer-')) if 'observer-' in hostname else random.randint(0, 255)
        self.node = m_node.Node(node_id)

        # initialize the experiment module
        self.experiment = m_experiment.Experiment(node_id)

        # initialize the I/O module
        self.io = m_io.IO(node_id)

        # initialize the GPS module
        self.location = m_location.GPS()

        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
        }

        # ready the supervisor
        self.state = SUPERVISOR_READY

    def reset(self):
        self.__init__()

    def status(self):
        return {'state': SUPERVISOR_STATES[self.state],
                'node': self.node.status(),
                'location': self.location.status(),
                'experiment': self.experiment.status(),
                'io': self.io.status()}

    def rest_get_command(self, command):
        # check that command exists
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
        if any(argument is None for argument in arguments):
            missing_arguments = filter(lambda argument: arguments[argument] is None, arguments.keys())
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_COMMAND_MISSING_ARGUMENT.format(command, missing_arguments)
        # issue the command
        self.commands[command](**arguments)
        bottle.response.status = m_common.REST_REQUEST_FULFILLED
        # return the node status
        return self.status()


def main():
    # initialize the arguments parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-cp', '--command_port', type=int, default=5555, help='command port')
    parser.add_argument('-d', '--debug', type=bool, default=True, help='debug output')
    arguments = parser.parse_args()

    supervisor = Supervisor()

    @bottle.route(['/node', '/node/', '/node/<command>'])
    def node_get_command(command=m_common.COMMAND_STATUS):
        if supervisor.experiment.state in [m_experiment.EXPERIMENT_RUNNING, m_experiment.EXPERIMENT_HALTED]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(command + '(GET)',
                                                           SUPERVISOR_STATES[SUPERVISOR_EXPERIMENT_RUNNING])
        else:
            return supervisor.node.rest_get_command(command)

    @bottle.route(['/node', '/node/', '/node/<command>'], method='POST')
    def node_post_command(command=m_common.COMMAND_STATUS):
        if supervisor.experiment.state in [m_experiment.EXPERIMENT_RUNNING, m_experiment.EXPERIMENT_HALTED]:
            bottle.response.status = m_common.REST_REQUEST_FORBIDDEN
            return m_common.ERROR_COMMAND_FORBIDDEN.format(command + '(POST)')
        else:
            return supervisor.node.rest_post_command(command)

    @bottle.route(['/experiment', '/experiment/', '/experiment/<command>'])
    def experiment_get_command(command=m_common.COMMAND_STATUS):
        return supervisor.experiment.rest_get_command(command)

    @bottle.route(['/experiment', '/experiment/', '/experiment/<command>'], method='POST')
    def experiment_post_command(command=m_common.COMMAND_STATUS):
        return supervisor.experiment.rest_post_command(command)

    @bottle.route(['/io', '/io/', '/io/<command>'])
    def io_get_command(command=m_common.COMMAND_STATUS):
        return supervisor.io.rest_get_command(command)

    @bottle.route(['/io', '/io/', '/io/<command>'], method='POST')
    def io_post_command(command=m_common.COMMAND_STATUS):
        return supervisor.io.rest_post_command(command)

    @bottle.route(['/location', '/location/', '/location/<command>'])
    def location_get_command(command=m_common.COMMAND_STATUS):
        return supervisor.location.rest_get_command(command)

    @bottle.route(['/location', '/location/', '/location/<command>'], method='POST')
    def location_post_command(command=m_common.COMMAND_STATUS):
        return supervisor.location.rest_post_command(command)

    @bottle.route(['/', '/<command>'])
    def supervisor_get_command(command=m_common.COMMAND_STATUS):
        return supervisor.rest_get_command(command)

    @bottle.route(['/', '/<command>'], method='POST')
    def supervisor_post_command(command=m_common.COMMAND_STATUS):
        return supervisor.rest_post_command(command)

    bottle.run(host='0.0.0.0', port=arguments.command_port, debug=arguments.debug)

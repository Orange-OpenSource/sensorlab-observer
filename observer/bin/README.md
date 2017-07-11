# Observer : Documentation

| *document* | Observer Doc                                                   |
|:----------:|:---------------------------------------------------------------|
| *version*  | 1.0                                                            |
| *date*     | 2015/10/5                                                      |
| *author*   | Quentin Lampin, <quentin.lampin@orange.com>                    |
|            | Mollé Benjamin, <benjamin.molle@gmail.com>                     |
| *copyright*| Copyright 2015 Orange                                          |
| *license*  | CC BY SA                                                       |

## Brief

This document describes the Observer interface.

## Summary

- [Supervisor](#supervisor-module)
- [Node](#node-module)

## Observer module

This module exposes a REST interface to either control the node or to submit an experiment scenario that is locally executed by the supervisor's scheduler.

### Node module

The node module exposes 8 methods to control the behaviour of the hardware node:
  
- `setup`(`configuration`)				:	Setups the node controller and serial drivers.
- `init`(`none`)						:	initialize the node hardware.
- `load`(`firmware`)					:	load firmware in the node hardware.
- `start`(`none`)						:	start the node hardware.
- `stop`(`none`)						:	stop the node hardware.
- `reset`(`none`)						:	reset the node hardware.
- `send`(`message`)						:	send a message to the node hardware via its serial interface.
- `status`(`none`) 						:	Returns information on the node module.
  
Those functions ( except `status`) are only accessible when no experiment is running. In case of an attempt to
issue node commands while an experiment is running, an error message is returned to the user.
  
The hardware node is modelled as a state machine, consisting of 5 states:
`undefined`, `loading`, `ready`, `halted`, `running`.
  	
- `undefined` : the hardware node is in an undefined/unknown state, possibly running or halted.
- `loading`	  : the hardware node is loading a firmware.
- `ready`	  : the hardware node is ready to start.
- `halted`	  : the hardware node is halted. Execution is pending.
- `running`   : the hardware node is running.
  
### Node Setup

The node module is configured via the `setup` command.
This `setup` command is sent to the supervisor as a HTTP POST request containing one argument:
  
- `node_configuration`: the module configuration archive.
  
#### Node configuration archive

The configuration archive is of type **tar.gz** and contains the following directories and files:
  	
- `controller/`: configuration files and executables used by the node controller.
  
	- `executables/`: executables used in control commands.
  
	- `configuration_files/`: executables configuration files.
  
- `serial/`: contains the python module that reports frames sent on the serial interface.
  
- `manifest.yml`: controller command lines and serial configuration file.
  
##### Manifest.yml

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
  
  
## Experiment module

The experiment module provides the user with a way to submit an experiment script that will be executed
by the supervisor. The experiment module exposes 4 methods to submit and control experiments:
  
- `setup`(`configuration`,`id`)			:	setup an experiment scenario.
- `start`(`none`)						:	start the experiment.
- `stop`(`none`)						: 	stop the experiment.
- `reset`(`none`)						:	reset the experiment module.
  
### Experiment setup

The experiment module is configured via the `setup` command.
This `setup` command is sent to the supervisor as a HTTP POST request containing one argument:
  
- `experiment_configuration`: the module configuration archive.
  
#### Experiment configuration archive

The configuration archive is of type **tar.gz** and contains the following directories and files:
  
- `firmwares/`: firmwares to load on the hardware node during the experiment.
- `manifest.yml`: defines the experiment ID, its schedule and I/Os.
  
##### Manifest.yml

The manifest file complies to the YAML specification.
It must contain the following structure:
  
- `firmwares`:
	- `id`	 		:	configuration file ID
	  `file` 		:	configuration file
	  `brief`		: 	configuration file short description
	...
  
- `schedule`:
    - `time`:             { `origin`, `on-last-event-completion`, `duration` }
      `action`:           { `load`, `start`, `stop` }
      `parameters`:
        `parameter`:        value
    ...


## I/O module

The I/O module is in charge of relaying 'messages' to and from the platform using the MQTT protocol. The I/O module exposes 3 methods,
respectively to setup, initiate and terminate the platform broker connection:
  
- `setup`(`source`, `address`, `port`, `keepalive_period`)		:	setup the I/O module to connect to address:port
- `start`(`none`)												:	connect the I/O module.
- `stop`(`none`)												: 	disconnect the I/O module.
- `status`(`none`)												: 	Returns information on the I/O module.
  
## Location/GPS module

The GPS module provides information on the node location. It exposes 1 method, i.e.:
  
- `status`(`none`)												: 	Returns information on the GPS module.
- `setup`(`latitude`, `longitude`)                              :   Stop GPS module and set a fix location
- `start`(`none`)                                               :   Start GPS module
- `stop`(`none`)                                                :   Stop GPS module


## Command API

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

		- `setup`(`source`, `address`, `port`, `keepalive_period`)		:	setup the I/O module to connect to address:port
		- `start`(`none`)												:	connect the I/O module.
		- `stop`(`none`)												: 	disconnect the I/O module.
		- `status`(`none`)												: 	returns information on the I/O module.

	- `location/`	:	redirects to `location/status`

		- `status`(`none`)												:	returns information on the location module.
		- `setup`(`latitude`, `longitude`)								:	setup the location module to specified location.

Commands requiring no arguments are of type `HTTP GET` while those who require arguments are of type `HTTP POST`.
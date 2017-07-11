#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Sensorlab supervisor commons.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange
"""

# version number
VERSION = '1.3.4e'

# configuration persistence directory
PERSISTENCE_DIR = '/var/cache/sensorlab/'

# chrony sync logs
CHRONY_LOG_FILE = '/var/log/chrony/tracking.log'

# commands
COMMAND_STATUS = 'status'
COMMAND_SETUP = 'setup'
COMMAND_LOAD = 'load'
COMMAND_INIT = 'init'
COMMAND_START = 'start'
COMMAND_STOP = 'stop'
COMMAND_RESET = 'reset'
COMMAND_SEND = 'send'
COMMAND_VERSION = 'version'
COMMAND_SYNC = 'synchronization'
COMMAND_LOG = 'log'

# REST node_commands return codes
REST_REQUEST_FULFILLED = 200
REST_REQUEST_ERROR = 400
REST_REQUEST_FORBIDDEN = 403
REST_INTERNAL_ERROR = 500

# serial signals
SERIAL_SEND = 'serial_send'
SERIAL_RECV = 'serial_recv'

# I/O signals
IO_SEND = 'io_send'
IO_RECV = 'io_recv'

# Location update signals
LOCATION_UPDATE = 'location_update'
##################

# Current monitor update signals
CURRENT_MONITOR_UPDATE = 'current_monitor_update'
#############

# I/O MongoDB
IO_DATABASE_PORT_DEFAULT = 27017
IO_DATABASE_NAME_DEFAULT = 'sensorlab-experiments'

# I/O MQTT topics
IO_TOPIC_PLATFORM_LOG = 'sensorlab/log/observer-{observer_id}/{module}/'
IO_TOPIC_NODE_INPUT = 'sensorlab/node-{observer_id}/input/'

IO_TOPIC_NODE_OUTPUT_DATA = 'sensorlab/node-{node_id}/output/data/'
IO_TOPIC_NODE_OUTPUT_BINARY = 'sensorlab/output/binary/'
IO_TOPIC_NODE_OUTPUT_JSON = 'sensorlab/output/json/'


IO_TOPIC_EXPERIMENT_OUTPUT_DATA = 'sensorlab/experiment/{experiment_id}/output/data/'
IO_TOPIC_EXPERIMENT_OUTPUT_BINARY = 'sensorlab/experiment/{experiment_id}/output/binary/'
IO_TOPIC_EXPERIMENT_OUTPUT_JSON = 'sensorlab/experiment/{experiment_id}/output/json/'


# Sensorlab Base exception
class SensorlabException(Exception):
    """Base exception for all of the Sensorlab software"""

    def __init__(self, message):
        self.message = message
        super(SensorlabException, self).__init__(message)


# Node Base exception
class NodeException(SensorlabException):
    """Base exception class for the node module"""


# Node Setup exception
class NodeSetupException(NodeException):
    """Base exception class for the node node_setup module"""


# Node Controller exception
class NodeControllerException(NodeException):
    """Base exception class for the node node_controller module"""


class NodeControllerSetupException(NodeControllerException):
    """exception raised when the node_controller node_setup fails"""


class NodeControllerCommandException(NodeControllerException):
    """exception raised when a command issued to the node_controller fails"""


# Node Serial exception
class NodeSerialException(NodeException):
    """Base exception class for the node node_serial module"""


class NodeSerialSetupException(NodeControllerException):
    """exception raised when the node_serial node_setup fails"""


class NodeSerialCommandException(NodeControllerException):
    """exception raised when a command issued to the node_serial fails"""


class NodeSerialRuntimeException(NodeControllerException):
    """exception raised when a command issued to the node_serial fails"""


# Experiment Base exception
class ExperimentException(SensorlabException):
    """base exception class for the experiment module"""


class ExperimentSetupException(ExperimentException):
    """raised when an error occurs in the experiment configuration archive loading"""


class ExperimentRuntimeException(ExperimentException):
    """exception raised when a command issued to the experiment fails"""


class IOException(SensorlabException):
    """Arises when an error occurs in the IO module"""


class IOSetupException(IOException):
    """Arises when an error occurs during the IO module node_setup"""


class LocationException(SensorlabException):
    """Arises when an error occurs in the location module"""


class LocationSetupException(LocationException):
    """Arises when an error occurs during the location module node_setup"""

class CurrentMonitorException(SensorlabException):
    """Arises when an error occurs in the current monitoring module"""


class CurrentMonitorSetupException(CurrentMonitorException):
    """Arises when an error occurs during the current monitoring module node_setup"""


class SupervisorException(SensorlabException):
    """raised when an error occurs in the supervisor module"""


class DecoderException(SensorlabException):
    """raised when an error occurs in the decoder module"""


class SystemException(SensorlabException):
    """raised when an error occurs in the system module"""


class SystemCommandException(SystemException):
    """exception raised when a command issued to the system fails"""



# generic error
ERROR_RUNTIME = "error: caught an exception while running: {0}"

# command error messages
ERROR_COMMAND_UNKNOWN = 'error: command "{0}" unknown'
ERROR_COMMAND_FAILED = 'error: command "{0}" failed with error: "{1}"'
ERROR_COMMAND_MISSING_ARGUMENT = 'error: command "{0}" argument(s) missing: "{1}"'
ERROR_COMMAND_FORBIDDEN = 'error: command "{0}" forbidden, reason: {1}'

# configuration error messages
ERROR_CONFIGURATION_FAIL = 'error: setup failed with message: {0}'
ERROR_MISSING_ARGUMENT_IN_ARCHIVE = 'missing argument(s) in archive: {0}'
ERROR_MISSING_ARGUMENT_IN_MANIFEST = 'missing argument(s) in manifest: {0}'
ERROR_MISSING_ARGUMENT_IN_REQUEST = 'missing argument(s) in request: {0}'
ERROR_CONFIGURATION_UNKNOWN_ITEM = 'unknown item(s): {0}'

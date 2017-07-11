#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Sensorlab supervisor commons.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange
"""

# commands
COMMAND_STATUS = 'status'
COMMAND_SETUP = 'setup'
COMMAND_LOAD = 'load'
COMMAND_INIT = 'init'
COMMAND_START = 'start'
COMMAND_STOP = 'stop'
COMMAND_RESET = 'reset'
COMMAND_SEND = 'send'
COMMAND_ICON = 'icon'

# REST commands return codes
REST_REQUEST_FULFILLED = 200
REST_REQUEST_ERROR = 400
REST_REQUEST_FORBIDDEN = 403
REST_INTERNAL_ERROR = 500

# I/O signals
IO_RAW_FROM_NODE = 'raw_from_node'
IO_RAW_FROM_EXPERIMENT = 'raw_from_experiment'
IO_RAW_FROM_PLATFORM = 'raw_from_platform'
IO_RAW_TO_NODE = 'raw_to_node'
IO_OBSERVER_FROM_NODE = 'observer_from_node'
IO_OBSERVER_FROM_EXPERIMENT = 'observer_from_experiment'


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
    """Base exception class for the node setup module"""


# Node Controller exception
class NodeControllerException(NodeException):
    """Base exception class for the node controller module"""


class NodeControllerSetupException(NodeControllerException):
    """exception raised when the controller setup fails"""


class NodeControllerCommandException(NodeControllerException):
    """exception raised when a command issued to the controller fails"""


# Node Serial exception
class NodeSerialException(NodeException):
    """Base exception class for the node serial module"""


class NodeSerialSetupException(NodeControllerException):
    """exception raised when the serial setup fails"""


class NodeSerialCommandException(NodeControllerException):
    """exception raised when a command issued to the serial fails"""


class NodeSerialRuntimeException(NodeControllerException):
    """exception raised when a command issued to the serial fails"""


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
    """Arises when an error occurs during the IO module setup"""


class LocationException(SensorlabException):
    """Arises when an error occurs in the location module"""


class LocationSetupException(LocationException):
    """Arises when an error occurs during the location module setup"""


class SupervisorException(SensorlabException):
    """raised when an error occurs in the supervisor module"""


# generic error
ERROR_RUNTIME = "error: caught an exception while running: {0}"

# command error messages
ERROR_COMMAND_UNKNOWN = 'error: command "{0}" unknown'
ERROR_COMMAND_FAILED = 'error: command "{0}" failed with return code: "{1}"'
ERROR_COMMAND_MISSING_ARGUMENT = 'error: command "{0}" argument(s) missing: "{1}"'
ERROR_COMMAND_FORBIDDEN = 'error: command "{0}" forbidden, reason: {1}'

# configuration error messages
ERROR_CONFIGURATION_FAIL = 'error: configuration failed with message: {0}'
ERROR_CONFIGURATION_MISSING_ARGUMENT = 'error: missing argument(s) in configuration: {0}'
ERROR_CONFIGURATION_UNKNOWN_ITEM = 'error: unknown item(s): {0}'

# -*- coding: utf-8 -*-
"""Sensorlab experiment module.

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/12
Copyright 2015 Orange

"""

from .. import m_common
from . import m_sensorlab
from . import m_setup
from . import m_scheduler

from pydispatch import dispatcher
import bottle
import time
import struct

# experiment states
EXPERIMENT_UNDEFINED = 0
EXPERIMENT_LOADING = 1
EXPERIMENT_READY = 2
EXPERIMENT_HALTED = 3
EXPERIMENT_RUNNING = 4
EXPERIMENT_STATES = ('undefined', 'loading', 'ready', 'halted', 'running')

# commands
GET_COMMANDS = [m_common.COMMAND_STATUS,
                m_common.COMMAND_START,
                m_common.COMMAND_STOP,
                m_common.COMMAND_RESET]

POST_COMMANDS = [m_common.COMMAND_SETUP]

# POST request arguments
CONFIGURATION_FILE = 'behavior'
EXPERIMENT_ID = 'experiment_id'

REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [CONFIGURATION_FILE], 'forms': [EXPERIMENT_ID]},
}

# default values
EXPERIMENT_NONE = 'none'
SCHEDULER_UNDEFINED = 'undefined'
FIRMWARES_UNDEFINED = 'undefined'


class Experiment:
    """

    """

    def __init__(self, node_id):
        self.id = None
        self.node_id = node_id
        self.state = EXPERIMENT_UNDEFINED
        self.loader = None
        self.firmwares = None
        self.scheduler = m_scheduler.Scheduler()

        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start,
            m_common.COMMAND_STOP: self.stop,
            m_common.COMMAND_RESET: self.reset
        }

        self.node_commands = {
            "node.{0}".format(m_common.COMMAND_LOAD): self.node_load,
            "node.{0}".format(m_common.COMMAND_INIT): self.node_init,
            "node.{0}".format(m_common.COMMAND_START): self.node_start,
            "node.{0}".format(m_common.COMMAND_STOP): self.node_stop,
            "node.{0}".format(m_common.COMMAND_SEND): self.node_send
        }

        # connect signals to commands
        for command, method in self.commands.items():
            dispatcher.connect(method, signal="experiment.{0}".format(command))

    def status(self):
        return {'id': self.id if self.id else EXPERIMENT_NONE,
                'state': EXPERIMENT_STATES[self.state],
                'scheduler': self.scheduler.status() if self.scheduler else SCHEDULER_UNDEFINED,
                'firmwares': self.firmwares if self.firmwares else FIRMWARES_UNDEFINED}

    def setup(self, experiment_id, behavior):

        # setup the experiment
        self.id = experiment_id
        self.loader = m_setup.Loader(behavior)
        self.firmwares = self.loader.firmwares
        self.scheduler.setup(self.loader.schedule)

        # declare the experiment ready
        self.state = EXPERIMENT_READY

    def start(self):
        # declare the experiment running
        self.state = EXPERIMENT_RUNNING
        # advertise the addition of a new node to the experiment
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_ADD, 2)
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

        self._from_node_to_platform_observer(timestamp, data)

        # connect node commands
        for command, method in self.node_commands.items():
            dispatcher.connect(method, signal="experiment.{0}".format(command))

        # connect I/Os
        dispatcher.connect(self._from_node_to_platform_raw, signal=m_common.IO_RAW_FROM_NODE)
        dispatcher.connect(self._from_node_to_platform_observer, signal=m_common.IO_OBSERVER_FROM_NODE)
        dispatcher.connect(self._from_platform_to_node_raw, signal=m_common.IO_RAW_FROM_PLATFORM)

        # start the scheduler
        self.scheduler.start(self._end)

    def stop(self):
        # stop the scheduler
        self.scheduler.stop()
        timestamp = time.time()

        # disconnect node commands
        for command, method in self.node_commands.items():
            dispatcher.disconnect(method, signal="experiment.{0}".format(command))

        # disconnect I/Os
        dispatcher.disconnect(self._from_node_to_platform_raw, signal=m_common.IO_RAW_FROM_NODE)
        dispatcher.disconnect(self._from_node_to_platform_observer, signal=m_common.IO_OBSERVER_FROM_NODE)
        dispatcher.disconnect(self._from_platform_to_node_raw, signal=m_common.IO_RAW_FROM_PLATFORM)

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

        self._from_node_to_platform_observer(timestamp, data)

        # declare the experiment halted
        self.state = EXPERIMENT_HALTED

    def reset(self):
        # clean the loader files
        if self.loader:
            self.loader.clean()
            self.loader = None
        # reset the experiment state
        self.id = None
        self.state = EXPERIMENT_UNDEFINED
        self.loader = None
        self.firmwares = None
        self.scheduler = m_scheduler.Scheduler()

    def node_load(self, firmware_id):
        firmware = self.firmwares[firmware_id]
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_LOAD),
                        experiment=self,
                        firmware=firmware,
                        firmware_id=firmware_id)
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.FIRMWARE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len(firmware_id),
                                                       firmware_id)
        self._from_node_to_platform_observer(timestamp, data)

    def node_init(self):
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_INIT),
                        experiment=self)
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('initialized'),
                                                       'initialized')
        self._from_node_to_platform_observer(timestamp, data)

    def node_start(self):
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_START),
                        experiment=self)
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('running'),
                                                       'running')
        self._from_node_to_platform_observer(timestamp, data)

    def node_stop(self):
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_STOP),
                        experiment=self)
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('halted'),
                                                       'halted')
        self._from_node_to_platform_observer(timestamp, data)

    def node_reset(self):
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_RESET),
                        experiment=self)
        timestamp = time.time()
        data = struct.pack("<BB", m_sensorlab.EVENT_NODE_PROPERTY_UPDATE, 1)
        data += m_sensorlab.property_reference_payload(m_sensorlab.STATE_PROPERTY_ID,
                                                       m_sensorlab.TYPE_ASCII_ARRAY,
                                                       len('reset'),
                                                       'reset')
        self._from_node_to_platform_observer(timestamp, data)

    def node_send(self, message):
        dispatcher.send(signal="node.{0}".format(m_common.COMMAND_SEND),
                        experiment=self,
                        message=message)

    def _end(self):
        self.stop()
        self.reset()

    def _from_node_to_platform_raw(self, _, message):
        if self.state == EXPERIMENT_RUNNING:
            dispatcher.send(signal=m_common.IO_RAW_FROM_EXPERIMENT, experiment=self, message=message)

    def _from_node_to_platform_observer(self, timestamp, message):
        if self.state == EXPERIMENT_RUNNING:
            # build message with PCAP record, etc.
            time_s = int(timestamp)
            time_us = int(round((timestamp - time_s) * 10 ** 6))
            # build the packet record
            # prepend node_id to the message
            data = struct.pack("<I", self.node_id) + message
            # build the PCAP record
            record = m_sensorlab.pcap_record(time_s, time_us, data)
            # forward it
            dispatcher.send(signal=m_common.IO_OBSERVER_FROM_EXPERIMENT, experiment=self, message=record)

    def _from_platform_to_node_raw(self, message):
        if self.state == EXPERIMENT_RUNNING:
            dispatcher.send(signal=m_common.IO_RAW_FROM_NODE, message=message)

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
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_MISSING_ARGUMENT.format(missing_arguments)
        # issue the command
        try:
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
        except (m_common.ExperimentSetupException, m_common.ExperimentRuntimeException) as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_RUNTIME.format(e.message)
        # return the node status
        return self.status()

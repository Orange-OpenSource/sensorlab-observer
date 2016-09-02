# -*- coding: utf-8 -*-
"""Sensorlab open node node_controller handler module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""
import os

from ..m_common import m_common

CONTROLLER_UNDEFINED = 0
CONTROLLER_READY = 1
CONTROLLER_BUSY = 2
CONTROLLER_STATES = ('undefined', 'ready', 'busy')


class Controller:
    def __init__(self, configuration):
        """
        setup the node controller according to `configuration`
        `configuration`(dict):
            - commands:
                - load 	: 	{...}
                - start :	{...}
                - stop 	:  	{...}
                -reset :	{...}
            - configuration_files:
                * id 	:	{...}
                  file 	:   {...}
                  brief	:   {...}
                * {...}
        """
        self.state = CONTROLLER_UNDEFINED
        # retrieve commands
        self.commands = {}
        try:
            self.commands['load'] = configuration['commands']['load']
            self.commands['init'] = configuration['commands']['init']
            self.commands['start'] = configuration['commands']['start']
            self.commands['stop'] = configuration['commands']['stop']
            self.commands['reset'] = configuration['commands']['reset']
            self.configuration_files = configuration['configuration_files']
        except AttributeError as missing_key:
            raise m_common.NodeControllerSetupException(
                m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(missing_key, configuration))
        self.state = CONTROLLER_READY

    def status(self):
        return {'state': CONTROLLER_STATES[self.state]}

    def load(self, firmware):
        self.state = CONTROLLER_BUSY
        load_command = self.commands['load'].replace("<#firmware>", firmware)
        return_code = os.system(load_command)
        if return_code != 0:
            self.state = CONTROLLER_UNDEFINED
            raise m_common.NodeControllerCommandException(m_common.ERROR_COMMAND_FAILED.format('load', return_code))
        else:
            self.state = CONTROLLER_READY

    def init(self):
        self.state = CONTROLLER_BUSY
        return_code = os.system(self.commands['init'])
        if return_code != 0:
            self.state = CONTROLLER_UNDEFINED
            raise m_common.NodeControllerCommandException(m_common.ERROR_COMMAND_FAILED.format('init', return_code))
        else:
            self.state = CONTROLLER_READY

    def start(self):
        self.state = CONTROLLER_BUSY
        return_code = os.system(self.commands['start'])
        if return_code != 0:
            self.state = CONTROLLER_UNDEFINED
            raise m_common.NodeControllerCommandException(m_common.ERROR_COMMAND_FAILED.format('start', return_code))
        else:
            self.state = CONTROLLER_READY

    def stop(self):
        self.state = CONTROLLER_BUSY
        return_code = os.system(self.commands['stop'])
        if return_code != 0:
            self.state = CONTROLLER_UNDEFINED
            raise m_common.NodeControllerCommandException(m_common.ERROR_COMMAND_FAILED.format('stop', return_code))
        else:
            self.state = CONTROLLER_READY

    def reset(self):
        self.state = CONTROLLER_BUSY
        return_code = os.system(self.commands['reset'])
        if return_code != 0:
            self.state = CONTROLLER_UNDEFINED
            raise m_common.NodeControllerCommandException(m_common.ERROR_COMMAND_FAILED.format('reset', return_code))
        else:
            self.state = CONTROLLER_READY

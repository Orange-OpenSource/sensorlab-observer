# -*- coding: utf-8 -*-
"""Sensorlab open node node_serial handler module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

"""

import sys
import os
import importlib
import serial
import threading
import collections
import time

from ..m_common import m_common

SERIAL_UNDEFINED = 0
SERIAL_CONFIGURED = 1
SERIAL_READY = 2
SERIAL_HALTED = 3
SERIAL_RUNNING = 4

SERIAL_STATES = ('undefined', 'configured', 'ready', 'halted', 'running')


class Serial:
    def __init__(self, serial_configuration, from_node_raw_cb, from_node_observer_cb):
        self.state = SERIAL_UNDEFINED
        self.configuration = serial_configuration
        self.serial = None
        self.reader = None
        self.writer = None
        self.fifo = None
        self.raw_output = None
        self.observer_output = None
        self.alive = False
        self._reader_alive = False
        self._writer_alive = False

        try:
            sys.path.append(os.path.dirname(self.configuration['module']))
            mname = os.path.splitext(os.path.basename(self.configuration['module']))[0]
            self.serial_module = importlib.import_module(mname)
            sys.path.pop()
            self.state = SERIAL_CONFIGURED
            self.raw_output = from_node_raw_cb
            self.observer_output = from_node_observer_cb

        except Exception as e:
            raise m_common.NodeSerialSetupException(m_common.ERROR_CONFIGURATION_FAIL.format(e))

    def status(self):
        return {'state': SERIAL_STATES[self.state],
                'module': self.serial_module.__name__}

    def _start_reader(self):
        self._reader_alive = True
        self.reader_thread = threading.Thread(target=self.read)
        self.reader_thread.setDaemon(True)
        self.reader_thread.start()

    def _stop_reader(self):
        self._reader_alive = False
        self.reader_thread.join()

    def _start_writer(self):
        self._writer_alive = True
        self.writer_thread = threading.Thread(target=self.write)
        self.writer_thread.setDaemon(True)
        self.writer_thread.start()

    def _stop_writer(self):
        self._writer_alive = False
        self.writer_thread.join()

    def init(self):
        self.reader = getattr(self.serial_module, 'Reader')()
        self.writer = getattr(self.serial_module, 'Writer')()
        self.fifo = collections.deque()
        try:
            self.serial = serial.serial_for_url(self.configuration['port'],
                                                self.configuration['baudrate'],
                                                parity=getattr(serial, self.configuration['parity']),
                                                stopbits=getattr(serial, self.configuration['stopbits']),
                                                bytesize=getattr(serial, self.configuration['bytesize']),
                                                rtscts=self.configuration['rtscts'],
                                                xonxoff=self.configuration['xonxoff'],
                                                timeout=self.configuration['timeout'])
            self.state = SERIAL_READY
        except serial.SerialException as e:
            raise m_common.NodeSerialCommandException(m_common.ERROR_COMMAND_FAILED.format('init', e))

    def reset(self):
        if self.state == SERIAL_RUNNING:
            self.join()
        if self.state in [SERIAL_READY, SERIAL_HALTED]:
            self.serial.close()
            self.state = SERIAL_CONFIGURED
        self.init()

    def start(self):
        if self.state == SERIAL_CONFIGURED:
            self.init()
        if self.state in [SERIAL_READY, SERIAL_HALTED]:
            self.state = SERIAL_RUNNING
            self.alive = True
            self._start_reader()
        else:
            raise m_common.NodeSerialCommandException(
                m_common.ERROR_COMMAND_FAILED.format('start', SERIAL_STATES[self.state]))

    def stop(self):
        self.alive = False
        self.join()

    def send(self, data):
        formatted_data = self.writer.format(data)
        self.fifo.extend(formatted_data)
        if not self._writer_alive:
            self._start_writer()

    def join(self, timeout=None):
        self.state = SERIAL_UNDEFINED
        self.reader_thread.join(timeout)
        if self._writer_alive:
            self.writer_thread.join(timeout)
        self.state = SERIAL_HALTED

    def read(self):
        try:
            while self.alive and self._reader_alive:
                byte_s = self.serial.read()
                if byte_s:
                    for byte in byte_s:
                        payload = self.reader.decode(byte)
                        if payload:
                            timestamp = time.time() - self.time_spent_receiving(payload['content'])
                            if payload['type'] == 'raw':
                                self.raw_output(timestamp=timestamp, message=payload['content'])
                            elif payload['type'] == 'observer':
                                self.observer_output(timestamp=timestamp, message=payload['content'])
        except serial.SerialException as e:
            self.alive = False
            raise m_common.NodeSerialRuntimeException(m_common.ERROR_RUNTIME.format(e))

    def write(self):
        try:
            while self.alive and len(self.fifo) > 0:
                c = self.fifo.popleft()
                self.serial.format(c)
        except serial.SerialException as e:
            self.alive = False
            raise m_common.NodeSerialRuntimeException(m_common.ERROR_RUNTIME.format(e))

    def time_spent_receiving(self, data):
        parity_bits_per_byte = 1 if self.serial.parity != serial.PARITY_NONE else 0
        time_spent = len(data) * (
            self.serial.bytesize + parity_bits_per_byte + self.serial.stopbits) / self.serial.baudrate
        return time_spent

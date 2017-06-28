# -*- coding: utf-8 -*-

"""
Location module.

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/12
Copyright 2015 Orange

"""
from .. import m_common
from . import m_gpsd

from pydispatch import dispatcher
from geopy.distance import vincenty

import threading
import bottle
import logging

# module logger
logger = logging.getLogger(__name__)

# experiment states
GPS_UNDEFINED = 0
GPS_OFFLINE = 1
GPS_ONLINE = 2
GPS_STATES = ('undefined', 'offline', 'online')

# node_commands
GET_COMMANDS = [m_common.COMMAND_STATUS, m_common.COMMAND_START, m_common.COMMAND_STOP]
POST_COMMANDS = [m_common.COMMAND_SETUP]

# POST request arguments
LATITUDE = 'latitude'
LONGITUDE = 'longitude'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [LATITUDE, LONGITUDE]}
}

COORDINATE_UNDEFINED = 'undefined'
ERROR_ESTIMATE_UNDEFINED = 'undefined'

# exception messages
GPS_ROUTINE_ALREADY_RUNNING = 'GPS routine already running'


class GPS(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.gpsd = m_gpsd.GPS(mode=m_gpsd.WATCH_ENABLE)  # starting the stream of info
        self.running = False
        self.state = GPS_UNDEFINED
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.speed = None
        self.error_estimate_latitude = None
        self.error_estimate_longitude = None
        self.error_estimate_altitude = None
        self.satellites = []
        self.need_update = True
        self.last_reported_latitude = None
        self.last_reported_longitude = None
        self.last_reported_altitude = None
        self.start()
        # link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start_proxy,
            m_common.COMMAND_STOP: self.stop,
        }

    def run(self):
        self.running = True
        self.state = GPS_OFFLINE
        while self.running:
            # grab EACH set of gpsd info to clear the buffer
            self.gpsd.next()
            # update information
            if self.gpsd.fix.mode == m_gpsd.MODE_3D:

                distance = vincenty(
                    (self.gpsd.fix.latitude, self.gpsd.fix.longitude),
                    (self.last_reported_latitude, self.last_reported_longitude)
                ).meters
                self.need_update = distance > min(self.gpsd.fix.epx, self.gpsd.fix.epy)
                self.state = GPS_ONLINE
                self.latitude = self.gpsd.fix.latitude
                self.longitude = self.gpsd.fix.longitude
                self.altitude = self.gpsd.fix.altitude
                self.speed = self.gpsd.fix.speed
                self.error_estimate_longitude = self.gpsd.fix.epx
                self.error_estimate_latitude = self.gpsd.fix.epy
                self.error_estimate_altitude = self.gpsd.fix.epv
                self.satellites = self.gpsd.satellites
                if self.need_update is True:
                    # logger.info('location changed to: (lat:{0}, lon:{1})'.format(self.latitude, self.longitude))
                    dispatcher.send(
                        signal=m_common.LOCATION_UPDATE,
                        sender=self,
                        latitude=self.latitude,
                        longitude=self.longitude,
                        altitude=self.altitude,
                        speed=self.speed,
                        error_estimate_longitude=self.error_estimate_longitude,
                        error_estimate_latitude=self.error_estimate_latitude,
                        error_estimate_altitude=self.error_estimate_altitude
                    )
                    self.last_reported_latitude = self.latitude
                    self.last_reported_longitude = self.longitude
                    self.last_reported_altitude = self.altitude

            elif self.gpsd.fix.mode == m_gpsd.MODE_NO_FIX:
                self.state = GPS_OFFLINE
                self.satellites = self.gpsd.satellites

    def status(self):
        return {
            'state': GPS_STATES[self.state],
            'latitude': self.latitude if self.latitude else COORDINATE_UNDEFINED,
            'longitude': self.longitude if self.longitude else COORDINATE_UNDEFINED,
            'altitude': self.altitude if self.altitude else COORDINATE_UNDEFINED,
            'error_estimate_latitude': self.error_estimate_latitude if self.error_estimate_latitude
            else ERROR_ESTIMATE_UNDEFINED,
            'error_estimate_longitude': self.error_estimate_longitude if self.error_estimate_longitude
            else ERROR_ESTIMATE_UNDEFINED,
            'error_estimate_altitude': self.error_estimate_altitude if self.error_estimate_altitude
            else ERROR_ESTIMATE_UNDEFINED
        }

    def setup(self, latitude, longitude):
        self.stop()
        self.state = GPS_OFFLINE
        self.latitude = latitude
        self.longitude = longitude
        return self.status()

    def start_proxy(self):
        if self.running:
            raise m_common.LocationException(
                m_common.ERROR_COMMAND_FORBIDDEN.format(m_common.COMMAND_START, GPS_ROUTINE_ALREADY_RUNNING))
        else:
            threading.Thread.__init__(self)

    def stop(self):
        self.running = False
        self.join()

    @property
    def fix(self):
        return self.gpsd.fix

    @property
    def utc(self):
        return self.gpsd.utc

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
        # node_load arguments
        arguments = {}
        for required_file_argument in REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        # check that all arguments have been filled
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(missing_arguments)
            # issue the command
        try:
            bottle.response.status = m_common.REST_REQUEST_FULFILLED
            return self.commands[command](**arguments)
        except m_common.LocationException as e:
            logger.error('command {0} error: '.format(command, e.message))
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

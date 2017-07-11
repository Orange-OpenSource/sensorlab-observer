"""
Observer GPS module.

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/12
Copyright 2015 Orange
"""
from .. import m_common
from . import m_gpsd
import threading
import bottle
import math

# experiment states
GPS_UNDEFINED  =   0
GPS_OFFLINE    =   1
GPS_ONLINE     =   2
GPS_STATES = ('undefined', 'offline', 'online')

# commands
GET_COMMANDS        =   [   m_common.COMMAND_STATUS, m_common.COMMAND_START, m_common.COMMAND_STOP   ]
POST_COMMANDS       =   [   m_common.COMMAND_SETUP      ]

# POST request arguments
LATITUDE             =   'latitude'
LONGITUDE            =   'longitude'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP  :   {   'files':[   ],  'forms':[ LATITUDE, LONGITUDE ] }
}

COORDINATE_UNDEFINED  = 'undefined'
ERROR_ESTIMATE_UNDEFINED = 'undefined'

# exception messages
GPS_ROUTINE_ALREADY_RUNNING = 'GPS routine already running'


class GPS(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.gpsd = m_gpsd.GPS(mode=m_gpsd.WATCH_ENABLE) #starting the stream of info
        self.running = False
        self.state = GPS_UNDEFINED
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.error_estimate_latitude = None
        self.error_estimate_longitude = None
        self.error_estimate_altitude = None
        self.satellites = []
        self.start()
        #link commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS : self.status,
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
            #update information
            if self.gpsd.fix.mode == m_gpsd.MODE_3D:
                self.state = GPS_ONLINE
                self.latitude = self.gpsd.fix.latitude if not math.isnan(self.gpsd.fix.latitude) else COORDINATE_UNDEFINED
                self.longitude = self.gpsd.fix.longitude if not math.isnan(self.gpsd.fix.longitude) else COORDINATE_UNDEFINED
                self.altitude = self.gpsd.fix.altitude if not math.isnan(self.gpsd.fix.altitude) else COORDINATE_UNDEFINED
                self.error_estimate_longitude = self.gpsd.fix.epx if not math.isnan(self.gpsd.fix.epx) else ERROR_ESTIMATE_UNDEFINED
                self.error_estimate_latitude = self.gpsd.fix.epy if not math.isnan(self.gpsd.fix.epy) else ERROR_ESTIMATE_UNDEFINED
                self.error_estimate_altitude = self.gpsd.fix.epv if not math.isnan(self.gpsd.fix.epv) else ERROR_ESTIMATE_UNDEFINED
                self.satellites = self.gpsd.satellites
            elif self.gpsd.fix.mode == m_gpsd.MODE_NO_FIX:
                self.state = GPS_OFFLINE
                self.satellites = self.gpsd.satellites

    def status(self):
        return {    'state'                     :   GPS_STATES[self.state],
                    'latitude'                  :   self.latitude if self.latitude else COORDINATE_UNDEFINED,
                    'longitude'                 :   self.longitude if self.longitude else COORDINATE_UNDEFINED,
                    'altitude'                  :   self.altitude if self.altitude else COORDINATE_UNDEFINED,
                    'error_estimate_latitude'   :   self.error_estimate_latitude if self.error_estimate_latitude else ERROR_ESTIMATE_UNDEFINED,
                    'error_estimate_longitude'  :   self.error_estimate_longitude if self.error_estimate_longitude else ERROR_ESTIMATE_UNDEFINED,
                    'error_estimate_altitude'   :   self.error_estimate_altitude if self.error_estimate_altitude else ERROR_ESTIMATE_UNDEFINED}
                    #'satellites'                :   self.satellites     }

    def setup(self, latitude, longitude):
        self.stop()
        self.state = GPS_OFFLINE
        self.latitude = latitude
        self.longitude = longitude

    def start_proxy(self):
        if self.running:
            raise m_common.LocationException(m_common.ERROR_COMMAND_FORBIDDEN.format(m_common.COMMAND_START, GPS_ROUTINE_ALREADY_RUNNING))
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
        #check that command exists
        if command not in GET_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return                   m_common.ERROR_COMMAND_UNKNOWN.format(command+'(GET)')
        #issue the command and return
        self.commands[command]()
        bottle.response.status  = m_common.REST_REQUEST_FULLFILLED
        return                    self.status()

    def rest_post_command(self, command):
        #check that command exists
        if command not in POST_COMMANDS:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return                   m_common.ERROR_COMMAND_UNKNOWN.format(command+'(POST)')
        #load arguments
        arguments = {}
        for required_file_argument in REQUIRED_ARGUMENTS[command]['files']:
            arguments[required_file_argument] = bottle.request.files.get(required_file_argument)
        for required_form_argument in REQUIRED_ARGUMENTS[command]['forms']:
            arguments[required_form_argument] = bottle.request.forms.get(required_form_argument)
        #check that all arguments have been filled
        if any( value is None for argument,value in arguments.items() ):
            missing_arguments = missing_arguments = [argument for argument in arguments.keys() if arguments[argument] == None]
            bottle.response.status  = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_MISSING_ARGUMENT.format(missing_arguments)  
        #issue the command
        try:
            self.commands[command](**arguments)
            bottle.response.status = m_common.REST_REQUEST_FULLFILLED
            #return the node status
            return self.status()
        except (m_common.LocationException) as e:
            bottle.response.status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

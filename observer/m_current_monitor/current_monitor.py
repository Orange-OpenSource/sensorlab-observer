# -*- coding: utf-8 -*-

"""
Current monitoring module.

`author`    :   Guillaume LARUE <guillaume.larue@orange.com>
`license`   :   MPL
`date`      :   2017/15/06
Copyright 2017 Orange

"""


import time
import threading
import bottle
from   select import poll, POLLIN
from pydispatch import dispatcher
from .. import m_common
from . import m_ina226

# experiment states
CURRENT_MONITOR_HALTED = 0
CURRENT_MONITOR_RUNNING = 1
CURRENT_MONITOR_UNDEFINED = 2
CURRENT_MONITOR_STATES = ('halted', 'running', 'undefined')

# node_commands
GET_COMMANDS = [m_common.COMMAND_STATUS, m_common.COMMAND_START, m_common.COMMAND_STOP]
POST_COMMANDS = [m_common.COMMAND_SETUP]

# POST request arguments
CALIBRE = 'calibre' #choose between [0.05,0.1,0.2] depending on solder jump connextion 
BUFFER_LENGTH = 'buffer_length'
AVERAGE_NUMBER = 'average_number'
SHUNT_VOLTAGE_INTEGRATION_TIME = 'shunt_voltage_integration_time'
BUS_VOLTAGE_INTEGRATION_TIME = 'bus_voltage_integration_time'
OPERATING_MODE = 'operating_mode'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [CALIBRE, BUFFER_LENGTH, AVERAGE_NUMBER, SHUNT_VOLTAGE_INTEGRATION_TIME, BUS_VOLTAGE_INTEGRATION_TIME, OPERATING_MODE]}
}

CURRENT_UNDEFINED = 'current undefined'
SHUNT_VOLTAGE_UNDEFINED = 'shunt voltage undefined'
BUS_VOLTAGE_UNDEFINED = 'bus voltage undefined'
POWER_UNDEFINED = 'power undefined'
TIMESTAMP_UNDEFINED = 'time stamp undefined'

# exception messages
CURRENT_MEASUREMENT_ROUTINE_ALREADY_RUNNING = 'current measurement routine already running'

#####
def start(self):
    self.threadlock = threading.Lock()
    threading.Thread(target=self.run)
####

class CurrentMonitor(threading.Thread):
    
    def __init__(self):
       
        threading.Thread.__init__(self)
        self.running = False
        self.state = CURRENT_MONITOR_UNDEFINED
        self.reader_running = False
        self.reader_thread = None
        self.ina226 = m_ina226.ina226('/sys/bus/i2c/devices/1-0040/iio:device0/')
        self.device_path = "/dev/iio:device0"
        
        self.CALIBRATION = 0x0847
        self.offset = None
        self.buffer_length = None
        self.current_LSB = None
        self.shunt_voltage_LSB = 0.0000025
        self.bus_voltage_LSB = 0.00125
        self.power_LSB = None

        self.current = None
        self.shunt_voltage = None
        self.bus_voltage = None
        self.power = None
        self.timestamp = None
        
        # link node_commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start_proxy,
            m_common.COMMAND_STOP: self.stop,
        }

    def setup(self,calibre,buffer_length,average_number,shunt_voltage_integration_time,bus_voltage_integration_time,operating_mode):
		
        if self.running:
            self.stop()
       
        self.state = CURRENT_MONITOR_HALTED
        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []

        self.buffer_length = int(buffer_length)
        self.current_LSB = float(calibre)/pow(2,15)
        self.power_LSB = self.current_LSB*25
        
        #disable buffer in case it is enabled
        self.ina226.disable_buffer()
        #configure ina226
        self.ina226.set_calibration(self.CALIBRATION)
        self.ina226.set_buffer_length(int(buffer_length))
        self.ina226.enable_channel_bus_voltage()
        self.ina226.enable_channel_shunt_voltage()
        self.ina226.enable_channel_timestamp()
        self.ina226.enable_channel_current()
        self.ina226.enable_channel_power()
        self.ina226.set_average(int(average_number))
        self.ina226.set_shunt_voltage_integration_time(float(shunt_voltage_integration_time))
        self.ina226.set_bus_voltage_integration_time(float(bus_voltage_integration_time))
        self.ina226.set_operating_mode(int(operating_mode))

    
    
    def run(self):   
        self.running = True
        self.state = CURRENT_MONITOR_RUNNING

        try:
            #enable buffer 
            self.ina226.enable_buffer()
            buffer_ina226 = open(self.device_path, "rb")
            
            p = poll()
            p.register(buffer_ina226.fileno(), POLLIN)
            cnt = 0

            print("Capture in progress")

            while self.running:
                #
                events = p.poll(10)               
                #
                for e in events:
                    
                    data = buffer_ina226.read(16)
                    ###STRUCT
                    voltage0 = (0xFFFF) & (data[0] | data[1] << 8)
                    voltage1 = (0xFFFF) & (data[2] | data[3] << 8)
                    power2 =   (0xFFFF) & (data[4] | data[5] << 8)
                    current3 = (0xFFFF) & (data[6] | data[7] << 8)
                    timestamp = (0xFFFFFFFFFFFFFFFF) & (data[8] | data[9] << 8 | data[10] << 16 | data[11] << 24 | data[12] << 32 | data[13] << 40 | data[14] << 48 | data[15] << 56 )
                    
                    
                    self.current.append(current3*self.current_LSB)
                    self.shunt_voltage.append(voltage0*self.shunt_voltage_LSB)
                    self.bus_voltage.append(voltage1*self.bus_voltage_LSB)
                    self.power.append(power2*self.power_LSB)
                    self.timestamp.append(timestamp)

                    cnt += 1
                                        
                if (cnt%50 == 0): 
                    print(str(cnt) +'values read:')   
                    dispatcher.send(
                        signal=m_common.CURRENT_MONITOR_UPDATE,
                        sender=self,
                        shunt_voltage  = self.shunt_voltage,
                        bus_voltage = self.bus_voltage,
                        current=self.current,
                        power=self.power,
                        timestamp = self.timestamp
                        
                    )
                    self.current = []
                    self.shunt_voltage = []
                    self.bus_voltage = []
                    self.power = []
                    self.timestamp = []
                
                               
            buffer_ina226.close                     
           
        except Exception as e:
            self.running = False

    def status(self):
        
        return {
            #Properties ##
            'Current': self.current if self.current else CURRENT_UNDEFINED,
            'Shunt voltage': self.shunt_voltage if self.shunt_voltage else SHUNT_VOLTAGE_UNDEFINED,
            'Bus voltage': self.bus_voltage if self.bus_voltage else BUS_VOLTAGE_UNDEFINED,
            'Power': self.power if self.power else POWER_UNDEFINED,
            'Time stamp': self.timestamp if self.timestamp else TIMESTAMP_UNDEFINED,
            'State': CURRENT_MONITOR_STATES[self.state]
            }
        

    def start_proxy(self):
        if self.running:
            raise m_common.CurrentMonitorException(
                m_common.ERROR_COMMAND_FORBIDDEN.format(m_common.COMMAND_START, CURRENT_MEASUREMENT_ROUTINE_ALREADY_RUNNING))
        else:
            threading.Thread.__init__(self)
            self.start()

    def stop(self):
        self.running = False
        self.join()
        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []
        self.state = CURRENT_MONITOR_HALTED
        self.ina226.disable_buffer()

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
        if any(value is None for argument, value in arguments.items()):
            missing_arguments = [argument for argument in arguments.keys() if arguments[argument] is None]
            bottle.response.node_status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(missing_arguments)
            # issue the command
        try:
            self.commands[command](**arguments)
            bottle.response.node_status = m_common.REST_REQUEST_FULFILLED
            # return the node node_status
            return self.status()
        except m_common.LocationException as e:
            bottle.response.node_status = m_common.REST_REQUEST_ERROR
            return m_common.ERROR_CONFIGURATION_FAIL.format(e.message)

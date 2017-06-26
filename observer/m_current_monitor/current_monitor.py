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
import struct
from   select import poll, POLLIN
from pydispatch import dispatcher
from datetime import datetime
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
AVERAGE_NUMBER = 'average_number' #[1 4 16 64 128 256 512 1024]
SHUNT_VOLTAGE_INTEGRATION_TIME = 'shunt_voltage_integration_time' #[0.000140 0.000204 0.000332 0.000588 0.001100 0.002116 0.004156 0.008244] [seconds]
BUS_VOLTAGE_INTEGRATION_TIME = 'bus_voltage_integration_time' #[0.000140 0.000204 0.000332 0.000588 0.001100 0.002116 0.004156 0.008244] [seconds]
OPERATING_MODE = 'operating_mode' #[0,1,2,3,4,5,6,7] (cf datasheet)
CHANNEL_BUS_VOLTAGE_ENABLED = 'channel_bus_voltage_enabled'
CHANNEL_SHUNT_VOLTAGE_ENABLED = 'channel_shunt_voltage_enabled'
CHANNEL_TIMESTAMP_ENABLED = 'channel_timestamp_enabled'
CHANNEL_CURRENT_ENABLED = 'channel_current_enabled'
CHANNEL_POWER_ENABLED = 'channel_power_enabled'

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [CALIBRE, BUFFER_LENGTH, AVERAGE_NUMBER, SHUNT_VOLTAGE_INTEGRATION_TIME, BUS_VOLTAGE_INTEGRATION_TIME, OPERATING_MODE, CHANNEL_BUS_VOLTAGE_ENABLED, CHANNEL_SHUNT_VOLTAGE_ENABLED, CHANNEL_TIMESTAMP_ENABLED, CHANNEL_CURRENT_ENABLED, CHANNEL_POWER_ENABLED]}
}

CURRENT_UNDEFINED = 'current undefined'
SHUNT_VOLTAGE_UNDEFINED = 'shunt voltage undefined'
BUS_VOLTAGE_UNDEFINED = 'bus voltage undefined'
POWER_UNDEFINED = 'power undefined'
TIMESTAMP_UNDEFINED = 'time stamp undefined'
CALIBRE_UNDEFINED = 'calibre undefined'
BUFFER_LENGTH_UNDEFINED = ' buffer length undefined'
AVERAGE_NUMBER_UNDEFINED = 'average number undefined'
SHUNT_VOLTAGE_INTEGRATION_TIME_UNDEFINED = 'shunt voltage integration time undefined'
BUS_VOLTAGE_INTEGRATION_TIME_UNDEFINED = 'bus voltage integration time undefined'
OPERATING_MODE_UNDEFINED = 'operating mode undefined'
SAMPLING_PERIOD_UNDEFINE = 'sampling period undefined'
REAL_SAMPLING_PERIOD_UNDEFINE = 'real sampling period undefined'

CALIBRATION = 0x0847
###
SHUNT_VOLTAGE_OFFSET = 3
CURRENT_OFFSET = 3
###
SHUNT_VOLTAGE_LSB= 0.0000025 #[V/bit]
BUS_VOLTAGE_LSB = 0.00125    #[V/bit]
DEVICE = '/sys/bus/i2c/devices/1-0040/iio:device0/'
DEVICE_PATH = "/dev/iio:device0"

# exception messages
CURRENT_MEASUREMENT_ROUTINE_ALREADY_RUNNING = 'current measurement routine already running'
#Other exception? exemple no channel enabled

###
def timestamp_to_date(timestamp_nano):
    dt = datetime.fromtimestamp(timestamp_nano // 1000000000)
    output = dt.strftime('%Y-%m-%d %H:%M:%S')
    output += '.' + str(int(timestamp_nano % 1000000000)).zfill(9)

    return output
###

###
def start(self):
    self.threadlock = threading.Lock()
    threading.Thread(target=self.run)
###

class CurrentMonitor(threading.Thread):
    
    def __init__(self):
       
        threading.Thread.__init__(self)
        self.running = False
        self.state = CURRENT_MONITOR_UNDEFINED
        self.reader_running = False
        self.reader_thread = None
        self.ina226 = m_ina226.ina226(DEVICE)
        self.device_path = DEVICE_PATH
 
        self.calibre = None
        self.buffer_length = None
        self.average_number = None
        self.shunt_voltage_integration_time = None
        self.bus_voltage_integration_time = None
        self.operating_mode = None
        self.channel_bus_voltage_enabled = None
        self.channel_shunt_voltage_enabled = None
        self.channel_timestamp_enabled = None
        self.channel_current_enabled = None
        self.channel_power_enabled = None

        self.calibration = CALIBRATION
        self.shunt_voltage_offset = SHUNT_VOLTAGE_OFFSET
        self.current_offset = CURRENT_OFFSET
        self.current_LSB = None
        self.shunt_voltage_LSB = SHUNT_VOLTAGE_LSB
        self.bus_voltage_LSB = BUS_VOLTAGE_LSB
        self.power_LSB = None
        self.sampling_period = None
        self.sampling_period_real = None

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

    def setup(self,calibre,buffer_length,average_number,shunt_voltage_integration_time,bus_voltage_integration_time,operating_mode,channel_bus_voltage_enabled,channel_shunt_voltage_enabled,channel_timestamp_enabled,channel_current_enabled,channel_power_enabled):
		
        if self.running:
            self.stop()
       
        self.state = CURRENT_MONITOR_HALTED
        self.calibre = float(calibre)
        self.buffer_length = int(buffer_length)
        self.average_number = int(average_number)
        self.shunt_voltage_integration_time = float(shunt_voltage_integration_time)
        self.bus_voltage_integration_time = float(bus_voltage_integration_time)
        self.operating_mode = int(operating_mode)

        self.channel_bus_voltage_enabled = bool(int(channel_bus_voltage_enabled))
        self.channel_shunt_voltage_enabled = bool(int(channel_shunt_voltage_enabled))
        self.channel_timestamp_enabled = bool(int(channel_timestamp_enabled))
        self.channel_current_enabled = bool(int(channel_current_enabled))
        self.channel_power_enabled = bool(int(channel_power_enabled))

        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []

        if self.operating_mode == 1 or self.operating_mode == 5:
            self.sampling_period = self.shunt_voltage_integration_time*self.average_number
        elif self.operating_mode == 2 or self.operating_mode == 6:
            self.sampling_period = self.bus_voltage_integration_time*self.average_number
        elif self.operating_mode == 3 or self.operating_mode == 7:
            self.sampling_period = (self.shunt_voltage_integration_time + self.bus_voltage_integration_time)*self.average_number
        else:
            self.sampling_period = 0

        self.current_LSB = self.calibre/pow(2,15)
        self.power_LSB = self.current_LSB*25
        
        #disable buffer in case it is enabled
        self.ina226.disable_buffer()
        #configure ina226
        self.ina226.set_calibration(self.calibration)
        self.ina226.set_buffer_length(self.buffer_length)
        self.ina226.set_average(self.average_number)
        self.ina226.set_shunt_voltage_integration_time(self.shunt_voltage_integration_time)
        self.ina226.set_bus_voltage_integration_time(self.bus_voltage_integration_time)
        self.ina226.set_operating_mode(self.operating_mode)
        #Enabling/disabling channels
        if self.channel_bus_voltage_enabled:
            self.ina226.enable_channel_bus_voltage()
        else:
            self.ina226.disable_channel_bus_voltage()
        if self.channel_shunt_voltage_enabled:
            self.ina226.enable_channel_shunt_voltage()
        else:
            self.ina226.disable_channel_shunt_voltage()
        if self.channel_timestamp_enabled:
            self.ina226.enable_channel_timestamp()
        else:
            self.ina226.disable_channel_timestamp()
        if self.channel_current_enabled:
            self.ina226.enable_channel_current()
        else:
            self.ina226.disable_channel_current()
        if self.channel_power_enabled:
            self.ina226.enable_channel_power()
        else:
            self.ina226.disable_channel_power()

    def run(self):   
        self.running = True
        self.state = CURRENT_MONITOR_RUNNING

        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []
        
        try:
            #enable buffer 
            self.ina226.enable_buffer()
            buffer_ina226 = open(self.device_path, "rb")
            
            cnt = 0
            prev_cnt = 0
            nBytes = 0
            unpackFormat = ""
            
            if self.channel_shunt_voltage_enabled:
                unpackFormat += "h"
            if self.channel_bus_voltage_enabled:
                unpackFormat += "h"
            if self.channel_power_enabled:
                unpackFormat += "h"
            if self.channel_current_enabled:
                unpackFormat += "h"
            if self.channel_timestamp_enabled:
                unpackFormat += "Q"
            
            nBytes = struct.calcsize(unpackFormat)

            p = poll()
            p.register(buffer_ina226.fileno(), POLLIN)

            t = time.time()
            while self.running:
                
                events = p.poll(int(self.sampling_period*1000*self.buffer_length))       #OK????    /!\ Tsampling >1??   
                for e in events:
                    data = buffer_ina226.read(nBytes)
                    data_raw = struct.unpack(unpackFormat,data) 
                    data_raw_list = [x for x in data_raw] #data_raw is a tuple. to use pop() method we need a list
                    
                    if self.channel_timestamp_enabled: #WARNING:Timestamp in nanoseconds
                        self.timestamp.append(data_raw_list.pop())
                    if self.channel_current_enabled:
                        self.current.append((data_raw_list.pop()-self.current_offset)*self.current_LSB)
                    if self.channel_power_enabled:
                        self.power.append(data_raw_list.pop()*self.power_LSB)
                    if self.channel_bus_voltage_enabled:
                        self.bus_voltage.append(data_raw_list.pop()*self.bus_voltage_LSB)
                    if self.channel_shunt_voltage_enabled:
                        self.shunt_voltage.append((data_raw_list.pop()-self.shunt_voltage_offset)*self.shunt_voltage_LSB)
                    
                    cnt += 1

                if ((time.time()-t) >= 20):  #One update every 20 seconds
                    self.sampling_period_real = (time.time() - t)/(cnt-prev_cnt)
                    t = time.time()
                    prev_cnt = cnt
                    
                    dispatcher.send(
                        signal = m_common.CURRENT_MONITOR_UPDATE,
                        sender = self,
                        shunt_voltage  = self.shunt_voltage,
                        bus_voltage = self.bus_voltage,
                        current = self.current,
                        power = self.power,
                        timestamp = self.timestamp,
                                           
                    )

                    self.shunt_voltage = []
                    self.bus_voltage = []
                    self.current = []
                    self.power = []
                    self.timestamp = [] 
                               
            buffer_ina226.close                     
            
        except Exception as e:
            self.running = False

    def status(self):
            
        return {                  
            'State': CURRENT_MONITOR_STATES[self.state],
            'Calibre [A]': self.calibre if self.calibre else CALIBRE_UNDEFINED,
            'Buffer length': self.buffer_length if self.buffer_length else BUFFER_LENGTH_UNDEFINED,
            'Average number': self.average_number if self.average_number else AVERAGE_NUMBER_UNDEFINED,
            'Shunt voltage integration time [s]': self.shunt_voltage_integration_time if self.shunt_voltage_integration_time else  SHUNT_VOLTAGE_INTEGRATION_TIME_UNDEFINED,
            'Bus voltage integration time [s]': self.bus_voltage_integration_time if self.bus_voltage_integration_time else BUS_VOLTAGE_INTEGRATION_TIME_UNDEFINED,
            'Operating Mode': self.operating_mode if self.operating_mode else OPERATING_MODE_UNDEFINED,
            'Shunt voltage offset [V]': self.shunt_voltage_offset*self.shunt_voltage_LSB, 
            'Current offset [A]':self.current_offset*self.current_LSB,  
            'Sampling period [s]': self.sampling_period if self.sampling_period else SAMPLING_PERIOD_UNDEFINE,
            'approximation of the real sampling period [s]': self.sampling_period_real if self.sampling_period_real else REAL_SAMPLING_PERIOD_UNDEFINE,
            'channel bus voltage enabled': self.channel_bus_voltage_enabled,
            'channel shunt voltage enabled': self.channel_shunt_voltage_enabled,
            'channel timestamp enabled': self.channel_timestamp_enabled,
            'channel current enabled': self.channel_current_enabled,
            'channel power enabled': self.channel_power_enabled,
            'Current': self.current if self.current else CURRENT_UNDEFINED,
            'Shunt voltage': self.shunt_voltage if self.shunt_voltage else SHUNT_VOLTAGE_UNDEFINED,
            'Bus voltage': self.bus_voltage if self.bus_voltage else BUS_VOLTAGE_UNDEFINED,
            'Power': self.power if self.power else POWER_UNDEFINED,
            'Time stamp': self.timestamp if self.timestamp else TIMESTAMP_UNDEFINED,
            
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

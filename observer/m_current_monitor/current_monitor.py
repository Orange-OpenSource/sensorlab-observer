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
import subprocess
import os
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

#Measurement mode:
MODE_OSCILLOSCOPE_FAST = 0
MODE_LOW_FREQUENCY = 1
MODE_OSCILLOSCOPE = 2
MODE_UNDEFINED = 3
MODE_LIST = ('oscilloscope 1,7kHz - current', 'Low frequency 0,9 Hz', 'oscilloscope 0,9 kHz - current, shunt voltage, bus voltage','undefined')

#Measurement channel:
MEASUREMENT_CHANNEL_TERMINAL = 0
MEASUREMENT_CHANNEL_USB = 1
MEASUREMENT_CHANNEL_UNDEFINED =2
MEASUREMENT_CHANNEL_LIST = ('Terminal', 'USB', 'undefined')

# POST request arguments
MODE = "mode" #Choose between [0,1,2] 0: Oscilloscope 1,7kHz current only - 1: Low frequency 0.9 Hz current only - 2: Oscilloscope 0.9 kHz current,shunt and bus voltage
CALIBRE = 'calibre' #choose between [0.05,0.1,0.2] depending on solder jump connextion 
MEASUREMENT_CHANNEL = 'measurement_channel' #Choose between [0,1] 0: Terminal, 1:USB

# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [MODE, CALIBRE, MEASUREMENT_CHANNEL]}
}

#undefined
CALIBRE_UNDEFINED = 'calibre undefined'
SAMPLING_PERIOD_UNDEFINE = 'sampling period undefined'

SHUNT_VOLTAGE_OFFSET_TERMINAL = 2
CURRENT_OFFSET_TERMINAL = 2
SHUNT_VOLTAGE_OFFSET_USB = 0
CURRENT_OFFSET_USB = 0

CALIBRATION = 0x0847
SHUNT_VOLTAGE_LSB= 0.0000025 #[V/bit]
BUS_VOLTAGE_LSB = 0.00125    #[V/bit]

DEVICE_TERMINAL = '/sys/bus/i2c/devices/1-0040/iio:device0/'
DEVICE_USB = '/sys/bus/i2c/devices/1-0045/iio:device0/'
DEVICE_PATH = "/dev/iio:device0"

CURRENT_MEASUREMENT_ROUTINE_ALREADY_RUNNING = 'current measurement routine already running'



def bash_command(cmd):
    subprocess.Popen(['/bin/bash', '-c', cmd])

def start(self):
    self.threadlock = threading.Lock()
    threading.Thread(target=self.run)

class CurrentMonitor(threading.Thread):
    
    def __init__(self):
       
        threading.Thread.__init__(self)
        self.running = False
        self.state = CURRENT_MONITOR_UNDEFINED
        self.reader_running = False
        self.reader_thread = None

        #Device path
        self.ina226 =  None
        self.device_path = DEVICE_PATH

        #Channel USB or terminal
        self.measurement_channel = MEASUREMENT_CHANNEL_UNDEFINED
        
        #Measurement mode
        self.mode = MODE_UNDEFINED 

        #INA226 Configuration
        self.calibre = None
        self.buffer_length = None
        self.average_number = None
        self.shunt_voltage_integration_time = None
        self.bus_voltage_integration_time = None
        self.operating_mode = None
        self.channel_bus_voltage_enabled = False    
        self.channel_shunt_voltage_enabled = False
        self.channel_timestamp_enabled = False
        self.channel_current_enabled = False
        self.channel_power_enabled = False      
        self.calibration = CALIBRATION
        self.shunt_voltage_offset_terminal = SHUNT_VOLTAGE_OFFSET_TERMINAL
        self.current_offset_terminal = CURRENT_OFFSET_TERMINAL
        self.shunt_voltage_offset_usb = SHUNT_VOLTAGE_OFFSET_USB
        self.current_offset_usb = CURRENT_OFFSET_USB
        self.current_LSB = None
        self.shunt_voltage_LSB = SHUNT_VOLTAGE_LSB
        self.bus_voltage_LSB = BUS_VOLTAGE_LSB
        self.power_LSB = None
        self.sampling_period = None
        

        #Experiment variables
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

    def setup(self, mode, calibre, measurement_channel):
		#Send a "current monitor setup" event to the database???

        #, buffer_length, average_number,shunt_voltage_integration_time,bus_voltage_integration_time,operating_mode,channel_timestamp_enabled,channel_bus_voltage_enabled, channel_shunt_voltage_enabled, channel_current_enabled ,channel_power_enabled
        if self.running:
            self.stop()
       
        self.state = CURRENT_MONITOR_HALTED
        
        #Instantiate one of the two INA226 available depending on the measurement channel selected (USB or Terminal)
        self.measurement_channel = int(measurement_channel)

        #INA 226 device instanciation
        #delete device in case they've been previously instanciated...
        if os.path.exists("/sys/bus/i2c/devices/1-0045"):
            bash_command('echo 0x45 > /sys/bus/i2c/devices/i2c-1/delete_device') 
            time.sleep(0.5) 
        if os.path.exists("/sys/bus/i2c/devices/1-0040"):
            bash_command('echo 0x40 > /sys/bus/i2c/devices/i2c-1/delete_device')
            time.sleep(0.5)
        
        #If module loaded??
        bash_command('rmmod ina226-i2c')
        time.sleep(0.5)

        if bool(self.measurement_channel):
            bash_command('modprobe -v ina226-i2c alert_pin_on_rpi2=20')  
            time.sleep(0.5)
            bash_command('echo ina226-i2c 0x45 > /sys/bus/i2c/devices/i2c-1/new_device')  
            self.ina226 =  m_ina226.ina226(DEVICE_USB)
        else:
            bash_command('modprobe -v ina226-i2c alert_pin_on_rpi2=21')  
            time.sleep(0.5)
            bash_command('echo ina226-i2c 0x40 > /sys/bus/i2c/devices/i2c-1/new_device')
            self.ina226 =  m_ina226.ina226(DEVICE_TERMINAL)
        time.sleep(0.5)

        self.mode = int(mode)
        if self.mode == 0: #Oscilloscope fast mode 1,7 kHz:
            self.buffer_length = 300
            self.average_number = 1
            self.shunt_voltage_integration_time = 0.000558
            self.bus_voltage_integration_time = 0.000558 #INUTILE?
            self.operating_mode = 5
            self.channel_bus_voltage_enabled = False
            self.channel_shunt_voltage_enabled = False
            self.channel_current_enabled = True
            self.channel_power_enabled = False
            self.channel_timestamp_enabled = True
            
        if self.mode == 1: #Low frequency mode 0,89 Hz
            self.buffer_length = 100
            self.average_number = 1024
            self.shunt_voltage_integration_time = 0.001100
            self.bus_voltage_integration_time = 0.001100 #INUTILE?
            self.operating_mode = 5
            self.channel_bus_voltage_enabled = False
            self.channel_shunt_voltage_enabled = False
            self.channel_current_enabled = True
            self.channel_power_enabled = False
            self.channel_timestamp_enabled = True

        if self.mode == 2: #Ocsilloscope mode 0,89 kHz
            self.buffer_length = 100
            self.average_number = 1
            self.shunt_voltage_integration_time = 0.000558
            self.bus_voltage_integration_time = 0.000558 #INUTILE?
            self.operating_mode = 7
            self.channel_bus_voltage_enabled = True
            self.channel_shunt_voltage_enabled = True
            self.channel_current_enabled = True
            self.channel_power_enabled = False
            self.channel_timestamp_enabled = True

        

        self.calibre = float(calibre)

        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []

        #A modifier
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
        #WARNING: need a setup before start
        #Send a "current monitor start" event to the database???

        self.running = True
        self.state = CURRENT_MONITOR_RUNNING

        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []

        if bool(self.measurement_channel):
            current_offset = self.current_offset_usb
            shunt_voltage_offset = self.shunt_voltage_offset_usb
        else:
            current_offset = self.current_offset_terminal
            shunt_voltage_offset = self.shunt_voltage_offset_terminal
        
        try:
            #enable buffer 
            self.ina226.enable_buffer()

            buffer_ina226 = open(self.device_path, "rb")

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

            if self.sampling_period >= 1:
                t_update = self.sampling_period
            else:
                t_update = 1

            while self.running:

                events = p.poll(int(self.sampling_period*1000*self.buffer_length))       #OK????    /!\ Tsampling >1??   
                for e in events:

                    data = buffer_ina226.read(nBytes)
                    data_raw = struct.unpack(unpackFormat,data) 
                    data_raw_list = [x for x in data_raw] #data_raw is a tuple. to use pop() method we need a list
                    
                    if self.channel_timestamp_enabled: #Timestamp in seconds
                        self.timestamp.append(data_raw_list.pop()/1E9)
                    if self.channel_current_enabled: #Current in mA
                        self.current.append((data_raw_list.pop()-current_offset)*self.current_LSB*1E3)
                    if self.channel_power_enabled:   #Power in mW
                        self.power.append(data_raw_list.pop()*self.power_LSB*1E3)
                    if self.channel_bus_voltage_enabled: #Bus voltage in V
                        self.bus_voltage.append(data_raw_list.pop()*self.bus_voltage_LSB)
                    if self.channel_shunt_voltage_enabled: #Shunt voltage in mV
                        self.shunt_voltage.append((data_raw_list.pop()-shunt_voltage_offset)*self.shunt_voltage_LSB*1E3)
                    
                    #Filtrage data???
                    
                if ((time.time()-t) >= t_update):  #One update every "t_update" seconds 
                    t = time.time()
                                        
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
            'state': CURRENT_MONITOR_STATES[self.state],
            'calibre': self.calibre if self.calibre else CALIBRE_UNDEFINED,
            'mode': MODE_LIST[self.mode],
            'sampling_period': self.sampling_period if self.sampling_period else SAMPLING_PERIOD_UNDEFINE,
            'measurement_channel': MEASUREMENT_CHANNEL_LIST[self.measurement_channel]
            }
        ###WARNING: verifier que status fonctionne meme avant setup
        
    def start_proxy(self):
        if self.running:
            raise m_common.CurrentMonitorException(
                m_common.ERROR_COMMAND_FORBIDDEN.format(m_common.COMMAND_START, CURRENT_MEASUREMENT_ROUTINE_ALREADY_RUNNING))
        else:
            threading.Thread.__init__(self)
            self.start()

    def stop(self):
        #Send a "current monitor stop" event to the database???
        self.running = False
        self.join()
        self.current = []
        self.shunt_voltage = []
        self.bus_voltage = []
        self.power = []
        self.timestamp = []
        self.state = CURRENT_MONITOR_HALTED
        self.ina226.disable_buffer()

        #delete device...
        if os.path.exists("/sys/bus/i2c/devices/1-0045"):
            bash_command('echo 0x45 > /sys/bus/i2c/devices/i2c-1/delete_device') 
            time.sleep(0.5) 
        if os.path.exists("/sys/bus/i2c/devices/1-0040"):
            bash_command('echo 0x40 > /sys/bus/i2c/devices/i2c-1/delete_device')
            time.sleep(0.5)

        bash_command('rmmod ina226-i2c')

        #Probleme: oblige de relancer un setup avant un start... (?)

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

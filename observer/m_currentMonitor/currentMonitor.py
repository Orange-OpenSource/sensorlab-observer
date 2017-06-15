# -*- coding: utf-8 -*-

"""
Current monitoring module.

`author`    :   Guillaume LARUE <guillaume.larue@orange.com>
`license`   :   MPL
`date`      :   2017/15/06
Copyright 2017 Orange

"""

from .. import m_common
from   select import poll, POLLIN
from pydispatch import dispatcher
import sys
#import os
#import time
import threading
import bottle

# experiment states

CURRENT_MONITOR_HALTED = 0
CURRENT_MONITOR_RUNNING = 1
CURRENT_MONITOR_UNDEFINED = 2
CURRENT_MONITOR_STATES = ('halted', 'running','undefined')

# node_commands
GET_COMMANDS = [m_common.COMMAND_STATUS, m_common.COMMAND_START, m_common.COMMAND_STOP]
POST_COMMANDS = [m_common.COMMAND_SETUP]

# POST request arguments
#
LATITUDE = 'latitude'
LONGITUDE = 'longitude'
#
# mandatory configuration arguments
REQUIRED_ARGUMENTS = {
    m_common.COMMAND_SETUP: {'files': [], 'forms': [LATITUDE, LONGITUDE]}
}

#
CURRENT_UNDEFINED = 'current undefined'
SHUNT_VOLTAGE_UNDEFINED = 'shunt voltage undefined'
BUS_VOLTAGE_UNDEFINED = 'bus voltage undefined'
POWER_UNDEFINED = 'power undefined'
#
# exception messages
#
EXCEPTION_CONFIGURATION_ATTEMPT_WHILE_RUNNING='configuration can`t occur while running!'
EXCEPTION_ALREADY_RUNNING='current monitor already running!'
EXCEPTION_ALREADY_HALTED='current monitor already halted!'
#
class ina226:
	def __init__(self, device_config_path):
		self.device_config_path = device_config_path

		
	def __set_config ( self, config_path, value):
		try:
			print('Set ', config_path, ' to ' , value)
			f = open(config_path, 'w')
			f.write(str(value))  
			f.close()
			print('=> OK')
		except:
			print ("Configuring ", config_path, "with " , value, " error: ", sys.exc_info()[0])
			raise
			
	def __get_config ( self, config_path):
		try:
			print('Get ', config_path)
			f = open(config_path, 'r')
			data = f.read()  
			f.close()
			print('data \n=> OK')
			return data
		except:
			print ("Configuring ", config_path, "with " , value, " error: ", sys.exc_info()[0])
			raise
		
	def set_calibration(self, calibration):
		self.__set_config(self.device_config_path + "in_calibration", calibration)
		
	def get_calibration(self):
		return self.__get_config(self.device_config_path + "in_calibration")
		
	def set_shunt_voltage_integration_time(self, time_s):
		self.__set_config(self.device_config_path + "in_voltage0_integration_time", time_s)
		
	def get_shunt_voltage_integration_time(self):
		return self.__get_config(self.device_config_path + "in_voltage0_integration_time")
		
	def set_bus_voltage_integration_time(self, time_s):
		self.__set_config(self.device_config_path + "in_voltage1_integration_time", time_s)
		
	def get_bus_voltage_integration_time(self):
		return self.__get_config(self.device_config_path + "in_voltage1_integration_time")
		
	def set_operating_mode(self, mode):
		self.__set_config(self.device_config_path + "in_operating_mode", mode)
		
	def get_operating_mode(self):
		return self.__get_config(self.device_config_path + "in_operating_mode")
		
	def set_average(self, average):
		self.__set_config(self.device_config_path + "in_average", average)
		
	def get_average(self):
		return self.__get_config(self.device_config_path + "in_average")
		
	def enable_channel_bus_voltage(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_voltage1_en', 1)
		
	def disable_channel_bus_voltage(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_voltage1_en', 0)
		
	def enable_channel_shunt_voltage(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_voltage0_en', 1)
		
	def disable_channel_shunt_voltage(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_voltage0_en', 0)
		
	def enable_channel_power(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_power2_en', 1)
		
	def disable_channel_power(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_power2_en', 0)
		
	def enable_channel_current(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_current3_en', 1)
		
	def disable_channel_current(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_current3_en', 0)		
		
	def enable_channel_timestamp(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_timestamp_en', 1)
		
	def disable_channel_timestamp(self):
		self.__set_config(self.device_config_path + 'scan_elements/in_timestamp_en', 0)
		
	def set_buffer_length(self, length):
		self.__set_config(self.device_config_path + 'buffer/length', length)
		
	def get_bus_voltage(self):
		return self.__get_config(self.device_config_path + "in_voltage1_raw")
		
	def get_shunt_voltage(self):
		return self.__get_config(self.device_config_path + "in_voltage0_raw")
		
	def get_power(self):
		return self.__get_config(self.device_config_path + "in_power2_raw")
		
	def get_current(self):
		return self.__get_config(self.device_config_path + "in_current3_raw")
		
	def enable_buffer(self):
		self.__set_config(self.device_config_path + 'buffer/enable', 1)	
	
	def disable_buffer(self):
		self.__set_config(self.device_config_path + 'buffer/enable', 0)


class CurrentMonitorException(Exception):
	def __init__(self, message):
		self.message = message
		super(Exception, self).__init__(message)

def start(self):
        self.threadlock = threading.Lock()
        threading.Thread(target=self.run)

class CurrentMonitor(threading.Thread):
	def __init__(self):
		self.state = UNDEFINED
        #
		self.reader_running = False
		self.reader_thread = None
        #
		self.ina226 = ina226('/sys/bus/i2c/devices/1-0040/iio:device0/')
		self.device_path = "/dev/iio:device0"
		self.output_file_path = "/tmp/ina226_output.txt"

        # link node_commands to instance methods
        self.commands = {
            m_common.COMMAND_STATUS: self.status,
            m_common.COMMAND_SETUP: self.setup,
            m_common.COMMAND_START: self.start_proxy,
            m_common.COMMAND_STOP: self.stop,
        }

	def setup(self,calibration,bufferLength,averageNumber,shuntVoltageIntegrationTime,busVoltageIntgrationTime,operatingMode):
		
        if self.running:
            self.stop()
        if self.state != HALTED:
			raise CurrentMonitorException(EXCEPTION_CONFIGURATION_ATTEMPT_WHILE_RUNNING)

            
		#disable buffer in case it is enabled
		self.ina226.disable_buffer()
		#configure ina226
		self.ina226.set_calibration(int(calibration))
		self.ina226.set_buffer_length(int(bufferLength))
		self.ina226.disable_channel_bus_voltage()
		self.ina226.enable_channel_shunt_voltage()
		self.ina226.enable_channel_timestamp()
		self.ina226.disable_channel_current()
		self.ina226.disable_channel_power()
		self.ina226.set_average(int(averageNumber))
		self.ina226.set_shunt_voltage_integration_time(float(shuntVoltageIntegrationTime))
		self.ina226.set_bus_voltage_integration_time(float(busVoltageIntgrationTime))
		self.ina226.set_operating_mode(int(operatingMode)
		
	def read(self):
		try:
			#enable buffer 
			self.ina226.enable_buffer()
			cnt = 0
			buffer_ina226 = open(self.device_path, "rb")
			output_file = open(self.output_file_path, "wt")

			p = poll()
			p.register(buffer_ina226.fileno(), POLLIN)

			print("Capture in progress")
			
			while self.reader_running:

				events = p.poll(1000)
				for e in events:
					#read 16 bytes, only 2 channels are enabled (0 and 1), but timestamp channel is enable, so data for channel 2 and 3 are available but not reliable
					data = buffer_ina226.read(16)
					voltage0 = (0xFFFF) & (data[0] | data[1] << 8)
					volatge1 = (0xFFFF) & (data[2] | data[3] << 8)
					power2 =   (0xFFFF) & (data[4] | data[5] << 8)
					current3 = (0xFFFF) & (data[6] | data[7] << 8)
					timestamp = (0xFFFFFFFFFFFFFFFF) & (data[8] | data[9] << 8 | data[10] << 16 | data[11] << 24 | data[12] << 32 | data[13] << 40 | data[14] << 48 | data[15] << 56 )
					output_file.write(str(timestamp) + " " + str(voltage0) + " " +str(volatge1) + " " +str(power2) + " "  +str(current3) + "\n")
					cnt = cnt + 1
					if  cnt%1000 == 0 :
						print(str(cnt) + " data written\r")

			output_file.close
			buffer_ina226.close
						
			print(str(cnt) + " data written in file " + self.output_file_path)

		except Exception as e:
			self.reader_running = False

	def __start_reader(self):
		if self.state != HALTED:
			raise CurrentMonitorException(EXCEPTION_ALREADY_RUNNING)
		self.reader_running = True
		self.state = RUNNING
		self.reader_thread = threading.Thread(target=self.read)
		self.reader_thread.setDaemon(True)
		self.reader_thread.start()

	def __stop_reader(self):
		if self.state != RUNNING:
			raise CurrentMonitorException(EXCEPTION_ALREADY_HALTED)
		self.state = HALTED
		self.reader_running = False
		self.reader_thread.join()

    # public API

	def configure(self, configuration):
		self.configure_ina226(configuration)

	def start(self):
		self.__start_reader()

	def stop(self):
		self.__stop_reader()


def main():
	try:
		current_monitor = CurrentMonitor('/sys/bus/i2c/devices/1-0040/iio:device0/',  "/dev/iio:device0", "/tmp/ina226_output.txt")
		current_monitor.start()
		while True:
			time.sleep(5)
	except CurrentMonitorException as exception:
		print(exception.message)
	except KeyboardInterrupt:
		print("\ninterrupt received, stopping…")
	finally:
		current_monitor.stop()


if __name__ == '__main__':
	main()

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
        self.start()
        # link node_commands to instance methods
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
                self.state = GPS_ONLINE
                self.latitude = self.gpsd.fix.latitude
                self.longitude = self.gpsd.fix.longitude
                self.altitude = self.gpsd.fix.altitude
                self.speed = self.gpsd.fix.speed
                self.error_estimate_longitude = self.gpsd.fix.epx
                self.error_estimate_latitude = self.gpsd.fix.epy
                self.error_estimate_altitude = self.gpsd.fix.epv
                self.satellites = self.gpsd.satellites

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
            elif self.gpsd.fix.mode == m_gpsd.MODE_NO_FIX:
                self.state = GPS_OFFLINE
                self.satellites = self.gpsd.satellites

    def status(self):
        return {
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

# -*- coding: utf-8 -*-
"""

`author`	:	Alexandre Maréchal <alexandre.marechal@orange.com>
`license`	:	MPL
`date`		:	2017/06/09
Copyright 2017 Orange

"""
import sys

class ina226:
	def __init__(self, device_config_path):
		self.device_config_path = device_config_path
	
	def __set_config ( self, config_path, value):
		try:
			#print('Set ', config_path, ' to ' , value)
			f = open(config_path, 'w')
			f.write(str(value))  
			f.close()
			#print('=> OK')
		except:
			#print ("Configuring ", config_path, "with " , value, " error: ", sys.exc_info()[0])
			raise
			
	def __get_config ( self, config_path):
		try:
			#print('Get ', config_path)
			f = open(config_path, 'r')
			data = f.read()  
			f.close()
			#print('data \n=> OK')
			return data
		except:
			#print ("Configuring ", config_path, "with " , value, " error: ", sys.exc_info()[0])
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


#!/home/pi/MotorController_app/bin/python3
##!/usr/bin/python3

# this is the library used by MotorController_app.py
#
# Uses the pySerial library to send and receive data from a
# Simple Motor Controller G2.
#
# NOTE: The Simple Motor Controller's input mode must be "Serial/USB".
# NOTE: You might need to change the "port_name =" line below to specify the
#   right serial port.
 
import serial
import time,sys
import os
import datetime
import signal
#import json
#import psutil
#import pika  #for rabbitMQ
#import logging



response_codes = ["No problems setting the limit.",
                  "Unable to set forward limit to the specified value because of hard motor limit settings.",
                  "Unable to set reverse limit to the specified value because of hard motor limit settings.",
                  "Unable to set forward and reverse limits to the specified value because of hard motor limit settings."]

 
class SmcG2Serial(object):
  def __init__(self, port, device_number=None):
    self.port = port
    self.device_number = device_number
 
  def send_command(self, cmd, *data_bytes):
    if self.device_number == None:
      header = [cmd]  # Compact protocol
    else:
      header = [0xAA, device_number, cmd & 0x7F]  # Pololu protocol
      
    try:
      self.port.write(bytes(header + list(data_bytes)))
    except:
      print("Could not send_command: " + str(cmd))
      
 
  # Sends the Exit Safe Start command, which is required to drive the motor.
  def exit_safe_start(self):
    try:
      self.send_command(0x83)
    except:
      print("Could not exit_safe_start.")
      return False
    return True
 
  # Sets the SMC's target speed (-3200 to 3200).
  def set_target_speed(self, speed):
    cmd = 0x85  # Motor forward
    if speed < 0:
      cmd = 0x86  # Motor reverse
      speed = -speed
    try:
      self.send_command(cmd, speed & 0x1F, speed >> 5 & 0x7F)
    except:
      print("Could not set_target_speed.")
      return False
    return True
 
  # Gets the specified variable as an unsigned value.
  def get_variable(self, id):
    self.send_command(0xA1, id)
    result = self.port.read(2)
    if len(result) != 2:
      raise RuntimeError("Expected to read 2 bytes, got {}."
        .format(len(result)))
    b = bytearray(result)
    return b[0] + 256 * b[1]
 
  # Gets the specified variable as a signed value.
  def get_variable_signed(self, id):
    try:
      value = self.get_variable(id)
      if value >= 0x8000:
        value -= 0x10000
      return value
    except:
      print("Could not get_variable.")
      return False


  def stop_motor(self):
    try:
      self.send_command(0xE0)
    except:
      print("could not stop_motor.")
      return False
    return True

  def set_motor_brake(self, value):
    # value of 0 is coasting
    # value of 32 is full braking
    #value = value & 0x1F
    print("Motor Brake Value = " + str(value))
    #print("Brake = " + str(brake))
    try:
      self.send_command(0x92, value)
    except:
      print("Could not set_motor_brake.")
      return False
    return True


  def get_brake_amount(self):
    return self.get_variable(22)
  
  
  def set_motor_limit(self, id, value): #not tested yet
    #max_acceleration for both foward and reverse is id = 1
    limit_byte1 = value & 0x7F
    limit_byte2 = value >> 7
    self.send_command(0xA2, id, limit_byte1, limit_byte2)
    result = self.port.read(1) #this is a byte
    if len(result) != 1:
      raise RuntimeError("Expected to read 1 bytes, got {}."
        .format(len(result)))
    print(result)
    #b = bytearray(result)
    return int.from_bytes(result, "big")
    
 
  # Gets the target speed (-3200 to 3200).
  def get_target_speed(self):
    return self.get_variable_signed(20)

  # Gets the current speed (-3200 to 3200).
  def get_current_speed(self):
    return self.get_variable_signed(21)
  
 
  # Gets a number where each bit represents a different error, and the
  # bit is 1 if the error is currently active.
  # See the user's guide for definitions of the different error bits.
  def get_error_status(self):
    return self.get_variable(0)


  def reset_error_status(self):
    return self.get_variable(1)

  
  def get_temp(self):
    temp = self.get_variable(24)
    temp = str(temp) #make temp a string for easy processing
    temp_len = len(str(temp))
    left = temp[0:(temp_len-1)]
    right = temp[(temp_len-1):]
    temp = str(left) + '.' + str(right)
    return float(temp)
  

  def swap_nibbles(self, x):
    #Takes an int and swaps the most and least significant nibbles
    # probably not the most elegant, but it works.
    bin_string = bin(x)
  
    nibble1 = bin_string[2:6] #don't want the leading 0b
    nibble2 = bin_string[6:]
    #print("Nibble1: " + str(nibble1))
    #print("Nibble2: " + str(nibble2))

    swap_bin_string = nibble2 + nibble1
    return int(swap_bin_string,2)
  
  
  def get_firmware_version(self):
    self.send_command(0xC2)
    result = self.port.read(4)
    if len(result) != 4:
      raise RuntimeError("Expected to read 4 bytes, got {}."
        .format(len(result)))
    b = bytearray(result)
    #print(b[0])
    #print(b[1])
    product_id = b[1] + b[0]
    #product_id = int(product_id, 16)
    #print("product_id: " + hex(product_id))
    major_version = b[3]
    minor_version = b[2]
    #print("Major:" + str(major_version))
    #print("Minor:" + str(minor_version))
    #return b[0] + 256 * b[1]
    return("MotorController: " + str(product_id) + " Version: " + str(major_version) + "." + str(minor_version))
    

  def get_current(self):
    current = self.get_variable(44)
    return current

  def get_input_voltage(self):
    vin = self.get_variable(23)
    return vin

  def health_check(self):
    value = self.get_firmware_version()
    if value.startswith("MotorController"):
      #print("GOOD")
      return True
    else:
      print("BAD")
      #return False
    
  
def decode_error_code(error_code):
  b = format(error_code, '016b')
  #print(b)
  
  '''
  lsb = b[0:8] #don't want the leading 0b
  msb = b[8:]
  print("Byte1: " + str(lsb))
  print("Byte2: " + str(msb))
  new_bytes = msb + lsb
  new_bytes = b
  #print("New_bytes: " + new_bytes)
  '''
  
  bit_list = list(b)

  error_list = list()
  
  if(bit_list[15] == '1'):
    error_list.append("Safe start violation")
  if(bit_list[14] == '1'):
    error_list.append("Required channel invalid")
  if(bit_list[13] is '1'):
    error_list.append("Serial error")
  if(bit_list[12] is '1'):
    error_list.append("Command timeout")
  if(bit_list[11] is '1'):
    error_list.append("Limit/kill switch")
  if(bit_list[10] is '1'):
    error_list.append("Low VIN")
  if(bit_list[9] is '1'):
    error_list.append("High VIN")
  if(bit_list[8] is '1'):
    error_list.append("Over temperature")
  if(bit_list[7] is '1'):
    error_list.append("Motor driver error")
  if(bit_list[6] is '1'):
    error_list.append("ERR line is high")
  
  return error_list


def get_serial_device():
  port_name = "/dev/ttyACM0"
  baud_rate = 9600
  device_number = None

  # Timeout needed to be adjusted for slower RPi
  try:
    port = serial.Serial(port_name, baud_rate, timeout=2, write_timeout=0.1)
  except ValueError as e:
    print("Error connecting to serial port: " + str(e))

  try:
    smc = SmcG2Serial(port, device_number)
  except ValueError as e:
    print("Cannot create serial device: " + str(e))
    sys.exit(1)
    return False

  return smc
          
  
##################################################
# below are examples for testing
##################################################
if __name__ == "__main__":


  # Choose the serial port name.
  # Linux USB example:  "/dev/ttyACM0"  (see also: /dev/serial/by-id)
  # macOS USB example:  "/dev/cu.usbmodem001234562"
  # Windows example:    "COM6"
  port_name = "/dev/ttyACM0"
   
  # Choose the baud rate (bits per second).  This does not matter if you are
  # connecting to the SMC over USB.  If you are connecting via the TX and RX
  # lines, this should match the baud rate in the SMC's serial settings.
  baud_rate = 9600
   
  # Change this to a number between 0 and 127 that matches the device number of
  # your SMC if there are multiple serial devices on the line and you want to
  # use the Pololu Protocol.
  device_number = None
   
  #port = serial.Serial(port_name, baud_rate, timeout=0.1, write_timeout=0.1)

  # Timeout needed to be adjusted for slower RPi
  try:
    port = serial.Serial(port_name, baud_rate, timeout=2, write_timeout=0.1)
  except ValueError as e:
    print("Error connecting to serial port: " + str(e))

  try:
    smc = SmcG2Serial(port, device_number)
  except ValueError as e:
    print("Cannot create serial device: " + str(e))
    sys.exit(1)
  




  smc.exit_safe_start()

  '''
  error_status = smc.get_error_status()
  print("Error status: 0x{:04X}".format(error_status))
   
  target_speed = smc.get_target_speed()
  print("Target speed is {}.".format(target_speed))
   
  new_speed = 3200 if target_speed <= 0 else -3200
  print("Setting target speed to {}.\n".format(new_speed));
  smc.set_target_speed(new_speed)
  '''

  print ("Running G2 tests.")


  firmware_version = smc.get_firmware_version()
  print(str(firmware_version))


  smc.set_motor_brake(0) #coasting
  print("Brake amount: " + str(smc.get_brake_amount()))

  result = smc.set_motor_limit(1,5) #limit acceleration, 5 times slower than default
  print("result = " + str(result))
  print(response_codes[result])

  print("Current speed: " + str(smc.get_current_speed()))

  temp = smc.get_temp()
  #print("Type: " + str(type(temp)))
  #print("Temp: 0x{:04X}".format(temp))
  print("Temp: {}".format(temp))

  error_status = smc.get_error_status()
  #print(error_status)
  print("Error status: 0x{:04X}".format(error_status))
  #print(type(error_status))
  errors = decode_error_code(error_status)
  print("Errors: " + str(errors))

  #result = smc.reset_error_status()
  #print("Result= " + str(result))

  current = smc.get_current()
  print("Current: " + str(current) + " mA")

  vin = smc.get_input_voltage()
  print("Input voltage: " + str(vin) + " mV")

  target_speed = smc.get_target_speed()
  print("Target speed is {}.".format(target_speed))

  new_speed = 3200 if target_speed <= 0 else -3200
  print("Setting target speed to {}.\n".format(new_speed));
  smc.set_target_speed(new_speed)


  time.sleep(5)

  print("Stopping motor.")
  smc.stop_motor()

#!/home/mrrad/MotorController_app/bin/python3
##!/usr/bin/python3

# Uses the pySerial library to send and receive data from a
# Simple Motor Controller G2.
#
# NOTE: The Simple Motor Controller's input mode must be "Serial/USB".
# NOTE: You might need to change the "port_name =" line below to specify the
#   right serial port.
 
import serial  #this is pyserial
import time
import sys
import os
import datetime
import signal
import json
import psutil
import pika  #for rabbitMQ
import logging
from threading import Thread
import threading
import subprocess
import serial.tools.list_ports
import MotorController as mc


DEBUG = 0

HEALTH_CHECK_TIME = 60

LOGFILENAME = '/var/log/MotorController_app.log'


#rabbitmq_pid_file = "/var/run/rabbitmq/pid"
#rabbitmq_pid_file = "/var/lib/rabbitmq/mnesia/rabbit@raspberrypi-train.pid"

ERROR_CODE = -1


def output(output_string='') :
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    output_string = str(timestamp) + ':' + str(output_string)
    
    if DEBUG :   
        print("%s" % output_string)
        logging.debug(str(output_string))
    else :
        logging.info(str(output_string))
        
    return 0


def check_request(body):
    try:
        command_json = str(body.decode("utf-8","strict"))
    except:
        output("body is not a byte code: %s\n" % (str(body)))
        return ERROR_CODE

    
    output("check_request command = %s\n" % (command_json))

    try:
        #wrap this all in a "Try" for error checking!
        parsed_json = json.loads(command_json)
        #output("JSON=%s\n" % (parsed_json))
    except:
        output("JSON Loads failed=%s\n" % (str(parsed_json)))
        return ERROR_CODE

    #print(type(parsed_json), repr(parsed_json))
    #try:
        #for key in parsed_json:
            #print("Key:%s\n" % (key))
        #for k, v in parsed_json.items():
            #temp = [key, value]
            #dictlist.append(temp)
            #print("Key=%s  Value=%s \n" % (str(k),str(v)))
    #except:
        #output("Error with dict to list")
        #return ERROR_CODE
        
    #first_command = parsed_json[0]
    #output("First_command = %s\n" % (first_command))
    
    try:
        my_command = parsed_json['command']
        output("Command received = %s" % (my_command))
    except:
        output("No command given in JSON: %s\n" % (str(parsed_json)))
        return ERROR_CODE

    
    # status is the current speed setting
    if my_command == "status":
        output("check_request getting status.")
        result = smc.get_target_speed()
        
        #speed = smc.get_target_speed()
        #voltage = smc.get_input_voltage()
        #current = smc.get_current()
        
        #output(speed)
        #output(type(speed))
        
        #result_line  = "{\"speed\":" +str(speed) + "," + "\"voltage\":" + str(voltage) + "\"current\":" + str(current)  "}"
        #output(result_line)
        
        return result

    if my_command == "config":
        try:
            result = get_motor_config(gertbot_board,gertbot_channel)
        except:
            return False
        return result

    if my_command == "version":
        result = smc.get_firmware_version()
        return result
    
    if my_command == "read_error":
        result = smc.get_error_status()
        return result

    if my_command == "voltage":
        result = smc.get_input_voltage()
        result = str(result)
        return result

    if my_command == "current":
        result = smc.get_current()
        result = str(result)
        return result

    if (my_command == "temp" or my_command == "temperature"):
        result = smc.get_temp()
        return result
        
    if my_command == "info":
        temp = str(smc.get_temp())
        voltage = str(smc.get_input_voltage()) 
        current = str(smc.get_current())
        #info_string = temp + ',' + voltage + ',' + current 
        result_dict = {"temp": temp, "voltage": voltage, "current": current}
        #response_dict = result_dict["response"]
        #output(response_dict)
        #result_json = json.dumps(result_dict, sort_keys=True)
        return result_dict
    
    if (my_command == "start_a" or my_command == "reverse"): #reverse
        output("check_request start_a")
        smc.exit_safe_start() #needed before restarting
        target_speed = smc.get_target_speed()
        #new_speed = 3200 if target_speed <= 0 else -3200
        #result = smc.set_target_speed(new_speed)
        #ramp up
        #ramp_values = [-1280, -1920, -2560, -3200] #4 steps, NEGATIVE for reverse!
        ramp_values = [-1900, -2000, -2560, -3200] #4 steps, NEGATIVE for reverse!
        ramp_sleep = 1 #1 seconds
        for ramp_value in ramp_values:
            output("RAMP: " + str(ramp_value))
            result = smc.set_target_speed(ramp_value)
            time.sleep(ramp_sleep)
        return result

    if (my_command == "start_b" or my_command == "forward"): #forward
        smc.exit_safe_start() #needed before restarting
        target_speed = smc.get_target_speed()
        #new_speed = 3200 if target_speed <= 0 else -3200
        #result = smc.set_target_speed(new_speed)

        #ramp up
        #ramp_values = [640, 1280, 1920, 2560, 3200] #5 steps
        #ramp_values = [1280, 1920, 2560, 3200] #4 steps
        ramp_values = [1900, 2000, 2560, 3200] # 4 steps
        #ramp_value = [1900, 2000, 2560, 3200] # 4 steps
        ramp_sleep = 1 #1 seconds
        for ramp_value in ramp_values:
            #output("RAMP: " + str(ramp_value))
            result = smc.set_target_speed(ramp_value)
            time.sleep(ramp_sleep)
        return result
    
    if my_command == "stop":
        #result = stop_pwm_brushed(gertbot_board,gertbot_channel)
        result = smc.stop_motor()
        return result

    if my_command == "emergency_stop":
        result = gb.emergency_stop()
        return result
    
    return ERROR_CODE



def on_request(ch, method, props, body):
    #body should be a byte code 
    #print(type(body), repr(body))

    response = check_request(body)

    #response needs to be in JSON format
    #response = json.dumps({"response" : response}, sort_keys=True) #original
    response = json.dumps(response, sort_keys=True) #new
    
    #timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    #output("%s Response=%s  ID:%s\n" % (str(timestamp), str(response), str(props.correlation_id)) )
    output("Response=%s  ID:%s\n" % (str(response), str(props.correlation_id)) )

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=str(response))
    ch.basic_ack(delivery_tag = method.delivery_tag)




def exit_gracefully(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S") 
    output("Exiting at %s\n" % (str(timestamp)))
    #gb.stop_all()
    sys.exit(1)
    return 0


def find_serial_port():
	ports = list(serial.tools.list_ports.comports())
	for p in ports:
		print(p)
		#print(type(p))
		#print(p.description)
		
		if 'Pololu' in p.description:
			print("Found Pololu at " + str(p.device))
			return p.device
		
		
	return 0
	
	
def get_serial_device():
  port_name = "/dev/ttyACM0" #default value
  baud_rate = 9600
  device_number = None

  output("in get_serial_device")
  
  port_name = find_serial_port()
  
  print("Connecting to serial port %s" % str(port_name))
  
  # Timeout needed to be adjusted for slower RPi
  '''
  try:
    print("here0")
    port = serial.Serial(port_name, baud_rate, timeout=2, write_timeout=0.1)
    print("here")
  except ValueError as e:
    output("Error connecting to serial port")
    print("Error connecting to serial port: " + str(e))
'''
  port = serial.Serial(port_name, baud_rate, timeout=2, write_timeout=0.1)

  #output("HERE")
  
  
  try:
    smc = mc.SmcG2Serial(port, device_number)
  except ValueError as e:
    output("Cannot create serial device: " + str(e))
    print("Cannot create serial device")
    sys.exit(1)
    return False

  #output("GOOD")
  
  return smc


def health_check(smc):
    while True:
        if smc.health_check() is False:
            output("MotorController cannot be reached.")
            sys.exit(1) #systemd will hopefully restart this process
        time.sleep(HEALTH_CHECK_TIME)



def join_all_threads():
	main_thread = threading.current_thread()
	for t in threading.enumerate():
		if t is main_thread:
			continue
		thread_name = t.name
		#print("Thread name = %s" % thread_name, file=sys.stderr)
		if thread_name.startswith('Dummy'):
                        continue
		#print("Joining %s" % (t.name), file=sys.stderr)
		logging.debug("Joining %s", t.name)
		t.join(1.0)
		
def exit_gracefully():
    STOP = 1
    join_all_threads()
    sys.exit(0)
    
    
##########################################################################################
##########################################################################################
##########################################################################################

### Initialize ######


#original_sigint = signal.getsignal(signal.SIGINT)
#signal.signal(signal.SIGINT, exit_gracefully)

# enable logging

if DEBUG :
    log_level = 'DEBUG'
else :
    log_level = 'INFO';


#translate string log level to a numeric log level
numeric_level = getattr(logging, log_level.upper(), 10)


try:
    #logging.basicConfig(filename=log_filename, level=logging.DEBUG)
    logging.basicConfig(filename=LOGFILENAME, level=numeric_level)
except IOError:
    print("Could not open log file:", log_filename, file=sys.stderr)
    print("Exiting.", file=sys.stderr)
    sys.exit()

#logging.debug("Test")


output("Starting MotorController_app")

try:
    smc = get_serial_device()
except:
    output("Could not open serial device, exiting.")
    sys.exit()



health_check_thread = Thread(target = health_check, args = (smc,))
#health_check_thread.setDaemon(True)
health_check_thread.daemon = True
health_check_thread.start()


firmware_version = smc.get_firmware_version()
print(str(firmware_version))

# Make sure that RabbitMQ is running!
try:
	stat = subprocess.call(["systemctl", "is-active", "--quiet", "rabbitmq-server"])
except ValueError as e:
        msg = "{'type': 'ERROR', 'value': " + str(e) + "}"
        output(str(msg))
        print("Error getting status of rabbitmq-server: %s" % str(e)) 

if stat == 0: #this is good
        e = "'rabbitmq-server is running'"
        msg = "{'type': 'rabbitmq-server_status', 'value': " + str(e) + "}"
        output(str(msg))
else:
        #rabbitmq-server is NOT running
        e = "'rabbitmq-server is NOT running!'"
        msg = "{'type': 'ERROR', 'value': " + str(e) + "}"
        output(str(msg))
        print("rabbitmq-server is NOT running!")
        e = "'rabbitmq-server is NOT running'"
        msg = "{'type': 'rabbotmq-server', 'value': " + str(e) + "}"
        output(str(msg))
        sys.exit()
        #attempt restart?



# Configure RabbitMQ event loop
connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))

channel = connection.channel()

#channel.queue_declare(queue='motorcontroller_queue')
channel.queue_declare(queue='motorcontroller_queue', durable=True, exclusive=False, auto_delete=False)

channel.basic_qos(prefetch_count=1)
#channel.basic_consume(on_request, queue='motorcontroller_queue')
channel.basic_consume('motorcontroller_queue', on_request)


# Start RabbitMQ event loop
print(" [x] Awaiting RPC requests")

# Reduce pika logging
logging.getLogger("pika").setLevel(logging.WARNING)
    
try:
    channel.start_consuming()
except KeyboardInterrupt:
    channel.stop_consuming()

connection.close()    
exit_gracefully()





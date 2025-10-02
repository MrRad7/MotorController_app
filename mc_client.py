#!/home/mrrad/MotorController_app/bin/python3
import sys
import pika
import uuid
import json
import argparse
import MotorController as mc

command_list = ["version", "config", "status", "start_b", "forward", "reverse", "read_error", "stop", "info", "temp", "voltage", "current"] 


class MotorControllerRpcClient(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                host='localhost'))

        self.channel = self.connection.channel()

        #result = self.channel.queue_declare(exclusive=True)
        result = self.channel.queue_declare(queue='motorcontroller_queue',durable=True, exclusive=False, auto_delete=False)
        
        self.callback_queue = result.method.queue

        #self.channel.basic_consume(self.on_response, no_ack=True,
        #                           queue=self.callback_queue)

        self.channel.basic_consume(self.callback_queue, self.on_response, auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = str(body.decode("utf-8","strict"))

    def close(self):
        self.connection.close()

    def call(self, n):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(exchange='',
                                   routing_key='motorcontroller_queue',
                                   properties=pika.BasicProperties(
                                         reply_to = self.callback_queue,
                                         correlation_id = self.corr_id,
                                         ),
                                   body=str(n))
        while self.response is None:
            self.connection.process_data_events()
        return str(self.response)
    

################################################################

parser = argparse.ArgumentParser()
help_line = "Valid commands are:  " + str(command_list)
parser.add_argument("command", help=help_line)
args = parser.parse_args()


command = str(args.command)
print("Command=",command)

if command not in command_list:
    print("Command not found.")
    print(help_line)
    sys.exit(1)
    
motorcontroller_rpc = MotorControllerRpcClient()

print(f" [x] Requesting MotorController({command})")



command_json = json.dumps({"command" : command}, sort_keys=True)

print("CommandJSON=",command_json)


response = motorcontroller_rpc.call(command_json)
#response = str(response,('utf-8'))
#print(type(response), repr(response))

if command == "read_error":
    #print("Reading error")
    response_dict = json.loads(response)
    #print(response_dict)
    error_code = response_dict["response"]
    #print(error_code)
    value = mc.decode_error_code(error_code)
    value = str(error_code) + " = " + str(value)
    print(value)
    
print(" [.] Got %s" % response)


exit()


for item in command_list:
    command_json = json.dumps({"command" : item}, sort_keys=True)
    print("CommandJSON=",command_json)
    response = motorcontroller_rpc.call(command_json)
    print(" [.] Got %s" % response)

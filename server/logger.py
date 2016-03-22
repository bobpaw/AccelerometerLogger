#!/bin/python

import SocketServer
import socket
import time
from threading import Thread
#from multiprocessing import Process

HOST, CONTROL_PORT, DATA_PORT = "192.168.0.101", 9999, 9998

STATE_DISCONNECTED = "DISCONNECTED";
STATE_CONNECTED = "CONNECTED";
STATE_RUNNING = "RUNNING";
STATE_STOPPED = "STOPPED";

OPCODE_CONFIGURE = 'r'
OPCODE_START = 's'
OPCODE_HALT = 'h'
OPCODE_KEEPALIVE = 'k'

quit = False
samplerate = "g"
samplerange = "b"
streamingData = False

dividers = { "a" : 16380, "b" : 8192, "c" : 4096, "d" : 2048 }
rates = { "a" : "1 Hz", "b" : "10 Hz", "c" : "25 Hz", "d" : "50 Hz", "e" : "100 Hz", "f" : "200 Hz", "g": "400 Hz" }
ranges = { "a" : "2G", "b" : "4G", "c" : "8G" , "d" : "16G" }

class AccelerometerClient(object):
    def __init__(self, socket):
        self.state = STATE_CONNECTED
        self.events = list()
        self.socket = socket
        self.ip = socket.getpeername()[0]
    def addEvent(self, timestamp, x, y, z):
        event = { "timestamp" : timestamp, "x" : x, "y" : y, "z": z }
        self.events.append(event)

clients = dict()

def chunk(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

class DataStreamHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        client = clients[self.client_address[0]]
        client.events.extend(chunk(data.split(' '), 5))

class AccelerometerHandler(SocketServer.BaseRequestHandler):
  def setup(self):
    if not (self.request.getpeername()[0] in clients):
        self.client = AccelerometerClient(self.request)
        clients[self.client.ip] = self.client
        print "New client: " + str(self.client.ip)
        try:
            self.request.sendall(str(OPCODE_CONFIGURE + samplerate + samplerange))
        except Exception:
            print "Error configuring new client"
    else:
        self.client = clients[self.request.getpeername()[0]]
        self.client.state = STATE_CONNECTED
        self.client.socket = self.request
        print "Client reconnected: " + str(self.client.ip)
        try:
            self.request.sendall(str(OPCODE_CONFIGURE + samplerate + samplerange))
        except Exception:
            print "Error reconfiguring client upon reconnect"

  def handle(self):
    disconnected = False
    numTimeouts = 0
    self.request.settimeout(2)
    while not quit and not disconnected:
        try:
            self.data = self.request.recv(1024).strip()
            if self.data == OPCODE_KEEPALIVE:
                # print "Keep alive"
                self.data = None
                numTimeouts = 0
        except Exception as e:
            if not streamingData:
                if isinstance(e, socket.timeout):
                    numTimeouts = numTimeouts + 1
                    disconnected = numTimeouts > 5
                else:
                    disconnected = True
  def finish(self):
      if self.client.ip in clients:
          print str(self.client.ip) + " disconnected"
          self.client.state = STATE_DISCONNECTED
          self.request.close()

def broadcast(command, newstate=None):
    for key in clients:
        try:
            client = clients[key]
            client.socket.sendall(command)
            if not newstate is None:
                client.state = newstate
        except Exception:
            print "Error sending command to " + str(client.ip)

def print_menu():
    print "(a) configure accelerometers"
    print "(b) print status"
    print "(c) start data collection"
    print "(d) halt data collection"
    print "(e) write data to disk"
    print "(q) quit"

def configure():
    global samplerate
    global samplerange
    print "Choose a sample rate:"
    print "(a) 1 Hz"
    print "(b) 10 Hz"
    print "(c) 25 Hz"
    print "(d) 50 Hz"
    print "(e) 100 Hz"
    print "(f) 200 Hz"
    print "(g) 400 Hz"
    samplerate = raw_input("Sample rate selection: ").lower()
    print "Choose a sample range:"
    print "(a) 2G"
    print "(b) 4G"
    print "(c) 8G"
    print "(d) 16G"
    samplerange = raw_input("Sample range selection: ").lower()
    pass
    cmdstring = OPCODE_CONFIGURE + samplerate + samplerange
    broadcast(cmdstring)

def print_status():
    print "Accelerometer settings - " + ranges[samplerange] + " sampling range at " + rates[samplerate]
    if streamingData:
        print "Currently receiving data"
    else:
        print "Not currently receiving data"
    for key in clients:
        client = clients[key]
        print str(client.ip) + ": " + client.state + " (" + str(len(client.events)) + " events recorded)"
    pass

def signal_start():
    broadcast(OPCODE_START, STATE_RUNNING)
    global streamingData
    streamingData = True
    print "Started data collection"
    pass

def halt_data_collection():
    broadcast(OPCODE_HALT, STATE_CONNECTED)
    global streamingData
    streamingData = False
    print "Halted data collection"
    pass

def write_data():
    filename = raw_input("Enter a filename for the data: ")
    if filename.find('.csv') <= -1:
        filename = filename.trim() + '.csv'
    f = open(filename, 'w')
    for key in clients:
        client = clients[key]
        for event in client.events:
            event[0] = str(client.ip)
            event[2] = float(event[2]) / dividers[samplerange]
            event[3] = float(event[3]) / dividers[samplerange]
            event[4] = float(event[4]) / dividers[samplerange]
            for item in event:
                f.write(str(item))
                f.write(',')
            f.write('\n')
        client.events = list()
    f.flush()
    f.close()
    print "Data written to " + filename
    pass

if __name__ == "__main__":
  controlServer = SocketServer.TCPServer((HOST, CONTROL_PORT), AccelerometerHandler)
  controlThread = Thread (target=controlServer.serve_forever)
  controlThread.start()
  dataServer = SocketServer.UDPServer((HOST, DATA_PORT), DataStreamHandler)
  dataThread = Thread(target=dataServer.serve_forever)
  dataThread.start()
  quit = False
  try:
    while not quit:
      print_menu()
      choice = raw_input("Enter choice letter: ").lower()
      if choice == 'a':
        configure()
      elif choice == 'b':
        print_status()
      elif choice == 'c':
        signal_start()
      elif choice == 'd':
        halt_data_collection()
      elif choice == 'e':
        write_data()
      elif choice == 'q':
        quit = True
    print "Calling server shutdown"
    controlServer.shutdown()
    dataServer.shutdown()
    print "Joining thread"
    controlThread.join()
    dataThread.join()
    print "Goodbye!"
    raise KeyboardInterrupt()
  except KeyboardInterrupt:
    quit = True
    controlServer.shutdown()
    dataServer.shutdown()
    controlThread.join()
    dataThread.join()
    print "Goodbye!"

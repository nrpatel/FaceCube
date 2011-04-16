#!/usr/bin/env python

import sys
import math
import numpy
import scipy
import scipy.ndimage
import pygame
from pygame.locals import *
import OSC
import threading
import Queue
import RepRapArduinoSerialSender

class GCodeGenerator(object):
    def __init__(self):
        self.q = Queue.Queue()
        self.running = True
        self.sendqueue = threading.Thread(target=self.send_move)
        self.sender = RepRapArduinoSerialSender.RepRapArduinoSerialSender("/dev/ttyUSB0", 115200, True)
        self.sender.reset()
        self.feedrate = 4200
        self.base_feedrate = 2100
        self.z_feedrate = 128
        self.layer_height = 0.35
        self.z = self.layer_height
        self.center = (90.0, 100.0)
        self.layer = 1 # start at 1 for since starting height is 0.35
        self.filament_diameter = 1.75
        self.extruded_width = 0.35*1.5
        self.extrusion_area = self.extruded_width*self.layer_height*0.9
        self.filament_area = math.pi*((self.filament_diameter/2)**2)
        self.e_per_mm = self.extrusion_area/self.filament_area
        self.e = 0.0
        self.current_layer = []
    
    def connect(self):
        self.sendqueue.start()
        self.start_sequence()
    
    def start_sequence(self):
        self.q.put('G1 X-200 F%.1f' % self.base_feedrate)
        self.q.put('G92 X0')        
        self.q.put('G1 Y-200 F%.1f' % self.base_feedrate)
        self.q.put('G92 Y0')
        self.q.put('G1 Z-100 F%.1f' % self.z_feedrate)
        self.q.put('G92 Z0')
        self.q.put('G92 E0') # reset E distance
        self.q.put('G90')    # use absolute movement
        self.q.put('M140 S70.0')  # set the bed to 70C
        self.q.put('M104 S210.0') # set the extruder to 210C
        self.q.put('G1 X0.0 Y0.0 Z0.0 F%.1f' % self.base_feedrate)
        self.q.put('M109') # wait for the temperature to reach what it should
        self.q.put('G1 Z%.2f F%.1f' % (self.z, self.z_feedrate))
        self.q.put('G1 X%.2f Y%.2f F%.1f' % (self.center[0], self.center[1], self.feedrate))
        
    def add_move(self, start, end, extruding):
        f = self.feedrate
        if self.layer == 1:
            f = self.base_feedrate
        move = 'G1 X%.2f Y%.2f Z%.2f F%.1f' % (end[0], end[1], self.z, f)
        if extruding:
            distance = math.sqrt((end[0]-start[0])**2+(end[1]-start[1])**2)
            self.e += self.e_per_mm * distance
            move = move + ' E%.4f' % self.e
        self.q.put(move)
        self.current_layer.append((end[0],end[1],self.e))
    
    def reset_layer(self):
        self.layer += 1
        self.z += self.layer_height
        move = 'G1 Z%.2f F%.1f' % (self.z, self.z_feedrate)
        self.q.put(move)
        self.q.put('G92 E0') # reset E to 0 for new layer
        self.e = 0.0
        
    def duplicate_layer(self):
        self.reset_layer()
        for m in self.current_layer:
            move = 'G1 X%.2f Y%.2f Z%.2f F%.1f E%.4f' % (m[0], m[1], self.z, self.feedrate,m[2])
            self.q.put(move)
        
    def new_layer(self, point):
        if self.layer == 1:
            self.q.put('M104 S190') # extruder to 190C after first layer
        self.duplicate_layer()
        self.duplicate_layer()
        self.current_layer = []
        self.reset_layer()
        
        
    def send_move(self):
        while self.running or not self.q.empty():
            move = self.q.get()
            print move
            self.sender.write(move)
            # TODO: retract when the queue runs dry
            self.q.task_done()
            
    def disconnect(self):
        self.q.put('G1 X0.0 Y0.0 F%.1f' % self.base_feedrate)
        self.q.put('M104 S0')
        self.q.put('M140 S0')
        self.q.put('M84')
        self.running = False
        print 'Disconnecting. %d moves left' % self.q.qsize()
        self.q.join()
        

class HandClient(object):
    def __init__(self):
        self.server = OSC.OSCServer(('127.0.0.1', 7110))
        print self.server
        print self.server.address()
        self.server.addMsgHandler("/new_user", self.new_hand)
        self.server.addMsgHandler("/lost_user", self.lost_hand)
        self.server.addMsgHandler("/joint", self.update_hand)
        self.server.addMsgHandler("default", self.null_callback)
        self.server.timeout = 1
        self.hand = None
        
    def pos(self):
        return self.hand
    
    def new_hand(self, addr, tags, args, source):
        print "new hand"
        self.hand = None
    
    def lost_hand(self, addr, tags, args, source):
        print "lost hand"
        self.hand = None
        
    def update_hand(self, addr, tags, args, source):
        self.hand = (args[2],args[3],args[4])
        
    def null_callback(self, addr, tags, args, source):
        pass
    
    def update(self):
        self.server.handle_request()


class GesturePrinter(object):
    IDLE = 0
    EXTRUDING = 1
    RAISING = 2

    def __init__(self):
        pygame.init()
        self.size = (800, 600)
        self.printsize = (80, 60)
        self.printcenter = (90, 100)
        # rough approximation of the width of a printed line
        self.brushsize = int(0.65*(self.size[0]/self.printsize[0]))
        self.display = pygame.display.set_mode(self.size, 0)
        self.layer = pygame.surface.Surface(self.size)
        self.hand = HandClient()
        self.generator = GCodeGenerator()
        self.generator.connect()
        self.last_point = None
        self.point = None
        self.moving = False
        self.state = self.IDLE
        self.center = None
        self.extrude_color = (255,127,127)
        self.move_color = (127,255,127)
        self.raise_color = (127,127,255)
        self.extrude_threshold = 12
        self.raise_threshold = 30
        self.start_threshold = 20

    def camera_to_display(self, point):
        if point == None or self.center == None:
            return None
        
        x = (point[0]-self.center[0])*self.size[0]+self.size[0]/2
        y = (point[1]-self.center[1])*self.size[1]+self.size[1]/2
        z = max(4,self.start_threshold-(self.center[2]-self.point[2])*100)
        return (int(x),int(y),int(z))

    def camera_to_printer(self, point):
        if point == None or self.center == None:
            return None
            
        x = (point[0]-self.center[0])*self.printsize[0]+self.printcenter[0]
        y = (point[1]-self.center[1])*self.printsize[1]+self.printcenter[1]
        return (x,y)

    def draw(self):
        d = self.camera_to_display(self.point)
        
        if self.moving and (self.state == self.EXTRUDING):
            ld = self.camera_to_display(self.last_point)
        
            # pygame likes ints for drawing
            pygame.draw.line(self.layer,(255,255,63),(ld[0],ld[1]),(d[0],d[1]),self.brushsize)
            
        self.display.blit(self.layer,(0,0))
            
        if d != None:
            if self.state == self.EXTRUDING:
                color = self.extrude_color
            elif self.state == self.RAISING:
                color = self.raise_color
            else:
                color = self.move_color
        
            pygame.draw.circle(self.display,color,(d[0],d[1]),d[2],2)
            pygame.draw.circle(self.display,self.extrude_color,(d[0],d[1]),self.extrude_threshold,1)
            pygame.draw.circle(self.display,self.raise_color,(d[0],d[1]),self.raise_threshold,1)
            pygame.draw.circle(self.display,self.move_color,(d[0],d[1]),4,int(not self.moving))
            
        pygame.display.flip()

    def update(self):
        self.hand.update()
        if self.moving or self.last_point == None:
            self.last_point = self.point
            
        self.point = self.hand.pos()
        
        if self.point != None and self.last_point == None:
            # starting with a new hand
            self.center = self.point
        elif self.point == None:
            # hand is lost
            self.center = None
            self.last_point = None
            self.moving = False
            self.state = self.IDLE
        else:
            depth = self.start_threshold-(self.center[2]-self.point[2])*100
            if depth < self.extrude_threshold:
                self.state = self.EXTRUDING
            elif depth > self.raise_threshold:
                if self.state != self.RAISING:
                    self.state = self.RAISING
                    self.new_layer()
            else:
                self.state = self.IDLE
            
        # We're only moving if there is a decent distance moved
        if self.last_point and self.point:
            dist =  math.sqrt((self.point[0]-self.last_point[0])**2+(self.point[1]-self.last_point[1])**2)
#            print dist
            if dist > 0.003:
                self.moving = True
            else:
                self.moving = False
           
    def send(self): 
        if self.moving:    
            self.generator.add_move(self.camera_to_printer(self.last_point),
              self.camera_to_printer(self.point),self.state == self.EXTRUDING)
        
    def new_layer(self):
        self.generator.new_layer(self.camera_to_printer(self.last_point))
        # fade to black
        self.layer.fill((180,180,180),special_flags=BLEND_MULT)

    def run(self):
        going = True
        
        while going:
            events = pygame.event.get()
            for e in events:
                if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                    self.generator.disconnect()
                    going = False
            
            self.update()
            self.send()
            self.draw()

            
if __name__ == '__main__':
    gesture = GesturePrinter()
    gesture.run()

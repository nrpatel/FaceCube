#!/usr/bin/env python

import sys
import math
import freenect
import numpy
import scipy
import scipy.ndimage
import pygame
from pygame.locals import *
import OSC
import threading
import Queue

class GCodeGenerator(object):
    def __init__(self):
        self.q = Queue.Queue()
        self.running = True
        self.sender = threading.Thread(target=self.send_move)
        self.feedrate = 4200
        self.base_feedrate = 2100
    
    def connect(self):
        self.sender.start()
        
    def add_move(self, start, end, extruding):
        self.q.put((start,end,extruding))
        
    def send_move(self):
        while self.running:
            move = self.q.get()
            print move
            
    def disconnect(self):
        self.running = False
        

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
        self.size = (640, 480)
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
        self.extrude_threshold = 13
        self.raise_threshold = 27
        self.start_threshold = 20

    def camera_to_display(self, point):
        if point == None or self.center == None:
            return None
        
        x = (point[0]-self.center[0])*self.size[0]+self.size[0]/2
        y = (point[1]-self.center[1])*self.size[1]+self.size[1]/2
        z = max(4,self.start_threshold-(self.center[2]-self.point[2])*100)
        return (int(x),int(y),int(z))

    def draw(self):
        d = self.camera_to_display(self.point)
        
        if self.moving and (self.state == self.EXTRUDING):
            ld = self.camera_to_display(self.last_point)
        
            # pygame likes ints for drawing
            pygame.draw.line(self.layer,(255,255,63),(ld[0],ld[1]),(d[0],d[1]),3)
            
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
            
        if self.moving:    
            self.generator.add_move(self.last_point,self.point,self.state == self.EXTRUDING)
        
    def new_layer(self):
        # fade to black
        self.layer.fill((180,180,180),special_flags=BLEND_MULT)

    def run(self):
        going = True
        
        while going:
            events = pygame.event.get()
            for e in events:
                if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                    going = False
            
            self.update()
            self.draw()
            
if __name__ == '__main__':
    gesture = GesturePrinter()
    gesture.run()

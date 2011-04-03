#!/usr/bin/env python

import sys
import math
import freenect
import numpy
import scipy
import scipy.ndimage
import pygame
from pygame.locals import *
import facecube

class FingerTracker(facecube.FaceCube):
    def finger_count(self):
        pass
    
    def centroid(self):
        point = scipy.ndimage.measurements.center_of_mass(self.threshold)
        depth = scipy.ndimage.measurements.mean(self.threshold)
        return (point,depth)

class GesturePrinter(object):
    def __init__(self):
        pygame.init()
        self.size = (640, 480)
        self.display = pygame.display.set_mode(self.size, 0)
        self.layer = pygame.surface.Surface(self.size)
        self.capture = FingerTracker()
        self.last_point = None
        self.point = None
        self.moving = False

    def draw(self):
        if self.moving:
            # pygame likes ints for drawing
            pygame.draw.line(self.layer,(255,255,63),
                (int(self.last_point[0]),int(self.last_point[1])),
                (int(self.point[0]),int(self.point[1])),3)
            
        self.display.blit(self.layer,(0,0))
        self.display.blit(pygame.surfarray.make_surface(self.capture.get_array()),(0,0))
            
        if self.point:
            pygame.draw.circle(self.display,(127,255,127),(int(self.point[0]),int(self.point[1])),4,int(not self.moving))
            
        pygame.display.flip()

    def update(self):
        self.capture.update()
        self.capture.generate_threshold(2.5)
        if self.moving or self.last_point == None:
            self.last_point = self.point
        self.point,depth = self.capture.centroid()
        # We're only moving if there is a decent distance moved
        if self.last_point and self.point:
            dist =  math.sqrt((self.point[0]-self.last_point[0])**2+(self.point[1]-self.last_point[1])**2)
            print dist
            if dist > 5.0:
                self.moving = True
        
    def new_layer(self):
        # fade to black
        self.layer.fill((64,64,64),special_flags=BLEND_ADD)

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

#!/usr/bin/env python

import freenect
import numpy
import pygame
from pygame.locals import *

class FaceCube(object):
    def __init__(self, face_depth):
        self.depth, timestamp = freenect.sync_get_depth()
        self.face_depth = face_depth
        pass
    
    def update(self):
        self.depth, timestamp = freenect.sync_get_depth()
        self.generate_threshold()
        
    def generate_threshold(self):
        # the image breaks down when you get too close, so cap it at around 60cm
        self.depth = self.depth + 2047 * (self.depth <= 544)
        closest = numpy.amin(self.depth)
        closest_cm = 100.0/(-0.00307 * closest + 3.33) # approximation from ROS
        farthest = (100/(closest_cm + self.face_depth) - 3.33)/-0.00307
        hist, bins = numpy.histogram(self.depth)
        self.threshold = self.depth * (self.depth <= farthest)
    
    def find_connected_component(self):
        pass
        
    def hole_fill(self):
        pass
    
    def get_surface(self):
        return pygame.surfarray.make_surface(self.threshold.transpose())
        
if __name__ == '__main__':
    size = (640, 480)
    pygame.init()
    display = pygame.display.set_mode(size, 0)
    facecube = FaceCube(10.0)
    going = True
    
    while going:
        events = pygame.event.get()
        for e in events:
            if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                going = False
        
        facecube.update()
        display.blit(facecube.get_surface(),(0,0))
        pygame.display.flip()

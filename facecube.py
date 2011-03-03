#!/usr/bin/env python

import freenect
import numpy
import scipy
import pygame
from pygame.locals import *

class FaceCube(object):
    def __init__(self):
        self.depth, timestamp = freenect.sync_get_depth()
        self.threshold = None
        self.segmented = None
        self.selected_segment = None
        pass
    
    def update(self):
        self.depth, timestamp = freenect.sync_get_depth()
        
    def generate_threshold(self, face_depth):
        # the image breaks down when you get too close, so cap it at around 60cm
        self.depth = self.depth + 2047 * (self.depth <= 544)
        closest = numpy.amin(self.depth)
        closest_cm = 100.0/(-0.00307 * closest + 3.33) # approximation from ROS
        farthest = (100/(closest_cm + face_depth) - 3.33)/-0.00307
        hist, bins = numpy.histogram(self.depth)
        self.threshold = self.depth * (self.depth <= farthest)
    
    def select_segment(self,point)
        segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
        selected = segments[point[1],point[0]]
        
        if selected:
            self.selected_segment = (point[1],point[0])
    
    def segment(self):
        if self.selected_segment:
            segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
            selected = segments[self.selected_segment]
            if selected:
                self.segmented = self.threshold * (segments == selected)
            else:
                self.segmented = None
        
    def hole_fill(self):
        pass
    
    def get_surface(self):
        if self.segmented:
            return pygame.surfarray.make_surface(self.segmented.transpose())
        else:
            return pygame.surfarray.make_surface(self.threshold.transpose())
        
if __name__ == '__main__':
    size = (640, 480)
    pygame.init()
    display = pygame.display.set_mode(size, 0)
    face_depth = 10.0
    facecube = FaceCube()
    going = True
    capturing = True
    changing_depth = 0.0
    
    while going:
        events = pygame.event.get()
        for e in events:
            if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                going = False
            elif e.type == KEYDOWN:
                if e.key == K_UP:
                    changing_depth = 1.0
                elif e.key == K_DOWN:
                    changing_depth = -1.0
                elif e.key == K_SPACE:
                    capturing = not capturing
            elif e.type == KEYUP:
                if changing_depth != 0.0:
                    changing_depth = 0.0
                    print "Getting closest %d cm" % face_depth
            elif e.type == MOUSEBUTTONDOWN
                facecube.select_segment(pygame.mouse.get_pos())
                
        if capturing:
            facecube.update()
        
        face_depth = min(max(0.0,face_depth + changing_depth),2047.0)
        
        facecube.generate_threshold(face_depth)
        facecube.segment()
        display.blit(facecube.get_surface(),(0,0))
        pygame.display.flip()

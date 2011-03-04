""" FaceCube: Copy objects using a Kinect and RepRap

Copyright (c) 2011, Nirav Patel <http://eclecti.cc>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

This script allows you to capture whatever your Kinect is pointing at as a 
point cloud to be formed into a solid STL in MeshLab.  Specific objects can
be thresholded, segmented out, and hole filled.

PlyWriter - Saves a numpy array of a point cloud as a PLY file
FaceCube - Does the actual capture, thresholding, and segmentation
'main' - Pygame loop that displays the capture and accepts key and mouse input
"""

#!/usr/bin/env python

import sys
import freenect
import numpy
import scipy
import scipy.ndimage

class PlyWriter(object):
    """Writes out the point cloud in the PLY file format
    http://en.wikipedia.org/wiki/PLY_%28file_format%29"""
       
    def __init__(self,name):
        self.name =  name
        
    def save(self,array):
        points = []
        
        farthest = numpy.amax(array)
        farthest_mm = 1000.0/(-0.00307 * farthest + 3.33)

        points.extend(self.outline_points(array,farthest))
        points.extend(self.back_points(array,farthest))
        points.extend(self.mesh_points(array))
        
        f = open(self.name,'w')
        
        self.write_header(f,points)
        self.write_points(f,points,farthest_mm)
        
        f.close()
        
    # inspired by, but not based on http://borglabs.com/blog/create-point-clouds-from-kinect
    def mesh_points(self,array):
        points = []
        
        # depth approximation from ROS, in mm
        array = (array != 0) * 1000.0/(-0.00307 * array + 3.33)
        
        dims = array.shape
        minDistance = -100
        scaleFactor = 0.0021
        ratio = float(dims[0])/float(dims[1])
        
        for i in range(0,dims[0]):
            for j in range(0,dims[1]):
                z = array[i,j]
                if z:
                    # from http://openkinect.org/wiki/Imaging_Information
                    x = float(i - dims[0] / 2) * float(z + minDistance) * scaleFactor * ratio
                    y = float(j - dims[1] / 2) * float(z + minDistance) * scaleFactor
                    points.append((x,y,z))
                    
        return points
        
    def outline_points(self,array,depth):
        """Adds an outline going back to the farthest depth to give MeshLab an
        easier point cloud to turn into a solid"""
        points = []
        
        mask = array != 0
        outline = array * (mask - scipy.ndimage.morphology.binary_erosion(mask))
        
        dims = array.shape
        minDistance = -100
        scaleFactor = 0.0021
        ratio = float(dims[0])/float(dims[1])
        
        for i in range(0,dims[0]):
            for j in range(0,dims[1]):
                z = outline[i,j]
                if z:
                    z += 1
                    while z < depth:
                        z_mm = 1000.0/(-0.00307 * z + 3.33)
                        x = float(i - dims[0] / 2) * float(z_mm + minDistance) * scaleFactor * ratio
                        y = float(j - dims[1] / 2) * float(z_mm + minDistance) * scaleFactor
                        points.append((x,y,z_mm))
                        z += 1
        
        return points
        
    def back_points(self,array,depth):
        """Adds a plane of points at the maximum depth to make it easier for MeshLab
        to mesh a solid"""
        array = depth * (array != 0)
        
        return self.mesh_points(array)
        
    def write_header(self,f,points):
        f.write('ply\n')
        f.write('format ascii 1.0\n')
        f.write('element vertex %d\n' % len(points))
        f.write('property float x\n')
        f.write('property float y\n')
        f.write('property float z\n')
        f.write('end_header\n')
        
    def write_points(self,f,points,farthest):
        """writes out the points with z starting at 0"""
        for point in points:
            f.write('%f %f %f\n' % (point[0],point[1],farthest-point[2]))
        

class FaceCube(object):
    def __init__(self):
        self.depth, timestamp = freenect.sync_get_depth()
        self.threshold = None
        self.segmented = None
        self.selected_segment = None
        pass
    
    def update(self):
        """grabs a new frame from the Kinect"""
        self.depth, timestamp = freenect.sync_get_depth()
        
    def generate_threshold(self, face_depth):
        """thresholds out the closest face_depth cm of stuff"""
        # the image breaks down when you get too close, so cap it at around 60cm
        self.depth = self.depth + 2047 * (self.depth <= 544)
        closest = numpy.amin(self.depth)
        closest_cm = 100.0/(-0.00307 * closest + 3.33)
        farthest = (100/(closest_cm + face_depth) - 3.33)/-0.00307
        self.threshold = self.depth * (self.depth <= farthest)
    
    def select_segment(self,point):
        """picks a segment at a specific point.  if there is no segment there,
        it resets to just show everything within the thresholded image"""
        segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
        selected = segments[point[1],point[0]]
        
        if selected:
            self.selected_segment = (point[1],point[0])
        else:
            self.selected_segment = None
            self.segmented = None
    
    def segment(self):
        """does the actual segmenting"""
        if self.selected_segment != None:
            segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
            selected = segments[self.selected_segment]
            if selected:
                self.segmented = self.threshold * (segments == selected)
            else:
                self.segmented = None
        
    def hole_fill(self,window):
        """fills holes in the object with an adjustable window size
        bigger windows fill bigger holes, but will start to alias the object"""
        if self.segmented != None:
            self.segmented = scipy.ndimage.morphology.grey_closing(self.segmented,size=(window,window))
            
    def get_array(self):
        if self.segmented != None:
            return self.segmented
        else:
            return self.threshold
        
def facecube_usage():
    print 'This script allows you to capture whatever your Kinect is pointing at as a'
    print 'point cloud to be formed into a solid STL in MeshLab.  Specific objects can'
    print 'be thresholded, segmented out, and hole filled.'
    print 'Usage: python facecube.py filename'
    print ' '
    print 'Up/Down      Adjusts the depth of the threshold closer or deeper'
    print '             (can still be used while paused)'
    print 'Spacebar     Pauses or unpauses capture'
    print 'Mouse Click  Click on an object to choose it and hide everything else.'
    print '             Click elsewhere to clear the selection.'
    print 'H/G          After choosing an object, H increases hole filling, G decreases'
    print 'S            Saves the currently chosen object as a filename.ply'
    print 'P            Saves a screenshot as filename.png'
        
if __name__ == '__main__':
    import pygame
    from pygame.locals import *

    facecube_usage()
    size = (640, 480)
    pygame.init()
    display = pygame.display.set_mode(size, 0)
    face_depth = 10.0
    facecube = FaceCube()
    going = True
    capturing = True
    hole_filling = 0
    changing_depth = 0.0
    filename = 'facecube_test'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
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
                elif e.key == K_h:
                    hole_filling += 1
                    print "Hole filling window set to %d" % hole_filling
                elif e.key == K_g:
                    hole_filling = max(0,hole_filling-1)
                    print "Hole filling window set to %d" % hole_filling
                elif e.key == K_s:
                    print "Saving array as %s.ply..." % filename
                    writer = PlyWriter(filename + '.ply')
                    writer.save(facecube.get_array())
                    print "done"
                elif e.key == K_p:
                    screenshot = pygame.surfarray.make_surface(facecube.get_array().transpose())
                    pygame.image.save(screenshot,filename + '.png')
                    
            elif e.type == KEYUP:
                if changing_depth != 0.0:
                    changing_depth = 0.0
                    print "Getting closest %d cm" % face_depth
                    
            elif e.type == MOUSEBUTTONDOWN:
                facecube.select_segment(pygame.mouse.get_pos())
                
        if capturing:
            facecube.update()
        
        face_depth = min(max(0.0,face_depth + changing_depth),2047.0)
        
        facecube.generate_threshold(face_depth)
        facecube.segment()
        if hole_filling:
            facecube.hole_fill(hole_filling)
        
        # this is not actually correct, but it sure does look cool!
        display.blit(pygame.surfarray.make_surface(facecube.get_array().transpose()),(0,0))
        pygame.display.flip()

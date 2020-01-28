# -*- coding: utf-8 -*-
"""
Created on Thu Dec 12 20:42:45 2019

@author: nagarajanj2
"""
import javabridge as jutil
import bioformats
import os
import glob
import numpy as np
import pandas as pd
from skimage import measure
from skimage.measure import label
from scipy.stats import skew,kurtosis,mode
from scipy import stats
from operator import itemgetter
import math


class ConvertImage(object):
    
    def __init__(self, inpDir, segDir):
        self.img_list_actual = []
        self.msk_list = []
        self.maskimg =[]
        self.input_dir = inpDir
        self.mask_dir = segDir
        
    def labeling(self, msk_list):
        all_labels = label(msk_list)
        return all_labels
        
    def convert_tiled_tiff(self,boxSize, angleStart, angleStop, pixelDistance):
        
      
        df_feature = pd.DataFrame([])
        df = pd.DataFrame([])
        os.chdir(self.input_dir)
        #Read all the files(.ome.tif) in the directory
        filenames = glob.glob("*.ome.tif")
        
        os.chdir(self.mask_dir)
        #Read all the files(.ome.tif) in the directory
        filenames1 = glob.glob("*.ome.tif")
        
        # Import javabridge and start the vm
        jutil.start_vm(class_path=bioformats.JARS)      
        
        index=0
                
        for file_names,file_names1 in zip(filenames,filenames1):
            print('Processing Image - ',file_names)
            #Read metadata from the intensity image
            os.chdir(self.input_dir)
            xmlstr = bioformats.get_omexml_metadata(file_names)    
            ome = bioformats.OMEXML(xmlstr)
            del xmlstr
            iome = ome.image(0)
            del ome
            pixel_iomes = iome.Pixels.get_SizeZ()
            del iome
            reader = bioformats.ImageReader(file_names)
            
            #Read metadata from the segmented image
            os.chdir(self.mask_dir)
            xmlstr1 = bioformats.get_omexml_metadata(file_names1)
            ome1 = bioformats.OMEXML(xmlstr1)
            del xmlstr1
            iome1 = ome1.image(0)
            del ome1
            pixel_iomes1 = iome1.Pixels.get_SizeZ()
            del iome1
            reader1 = bioformats.ImageReader(file_names1)
            
            
            for z_img, z_msk in zip(range(pixel_iomes),range(pixel_iomes1)):
                img_list_actual =[]
                maskimg =[]
                img_file= reader.read(z=z_img, series=0,rescale=False)
                msk_file= reader1.read(z=z_msk, series=0,rescale=False)
                label_img= self.labeling(msk_file)
                img_list_actual.append(img_file)
                maskimg.append(label_img)
                del label_img
                intensity_image =  np.asarray(img_list_actual)
                del img_list_actual
                label_image =  np.asarray(maskimg)
                del maskimg
            analysis = Analysis(intensity_image, label_image, filenames, boxSize, angleStart, angleStop, pixelDistance)
            df = analysis.feature_extraction()
            title = filenames[index]
            df.insert(0, 'Image', title)
            del img_file
            del msk_file         
            del intensity_image
            del label_image
            del reader
            del reader1
            del pixel_iomes1
            del pixel_iomes
            df_feature = df_feature.append(df)
            index+=1
            print("Number of images processed-",index)

        jutil.kill_vm()
        return(df_feature,filenames)
        
      
class Analysis(ConvertImage):
    
    def __init__(self, intensity_image, label_image, filenames, boxSize, angleStart, angleStop, pixelDistance):
        self.objneighbors = []
        self.numneighbors = []
        self.labels = []
        self.uniqueindices_list=[]
        self.meanind_list=[]
        self.rot_position =[]
        self.rot_list =[]
        self.sub_rot_list=[]
        self.feretdiam=[]
        self.area_list=[]
        self.perim_list=[]
        self.df2 = pd.DataFrame([])
        self.boxsize = boxSize
        self.thetastart = angleStart
        self.thetastop = angleStop
        self.pixeldistance = pixelDistance
        
        if self.pixeldistance is None:
            self.pixeldistance = 1
        else:
            self.pixeldistance = pixelDistance
            
        if self.boxsize is None:
            self.boxsize = 3
        else:
            self.boxsize = boxSize
            
        if self.thetastart is None:
            self.thetastart = 1
        else:
            self.thetastart = angleStart
            
        if self.thetastop is None:
            self.thetastop = 181
        else:
            self.thetastop = angleStop
        
        
        self.label_image = label_image
        del label_image
        
        self.intensity_image = intensity_image
        del intensity_image
        
        self.filenames = filenames
        
    def properties(self,label_image,intensity_image):
        region_properties = measure.regionprops(label_image,intensity_image)
        return region_properties
    
    def box_border_search(self, label_image, boxSize):
    #Get image shape values
        height, width = label_image.shape

    #Get boxsize values
        floor_offset = math.floor(self.boxsize/2)
        ceil_offset = math.ceil(self.boxsize/2)

    #Create the integral image
        int_image = np.zeros((height+1, width+1))
        int_image[1:,1:] = np.cumsum(np.cumsum(np.double(label_image),0),1)
        int_image_transpose = int_image.T
        del int_image
        int_image_int = int_image_transpose.astype(int)
        del int_image_transpose

    #Create indices for the original image
        height_sequence = height-(self.boxsize-1)
        width_sequence = width-(self.boxsize-1)
        width_boxsize = np.linspace(0, width-self.boxsize, height_sequence)
        del height_sequence
        height_boxsize = np.linspace(0, height-self.boxsize, width_sequence)
        del width_sequence
        columns, rows = np.meshgrid(width_boxsize, height_boxsize)
        del width_boxsize
        del height_boxsize
        columns_flat = columns.flatten(order = 'F')
        del columns
        columns_reshape = columns_flat.reshape(-1,1)
        del columns_flat
        rows_flat = rows.flatten(order = 'F')
        del rows
        rows_reshape = rows_flat.reshape(-1,1)
        del rows_flat
        upper_left = (height+1)*columns_reshape+rows_reshape
        del columns_reshape
        del rows_reshape
        upper_left_int = upper_left.astype(int)
        upper_right = upper_left_int+(self.boxsize)*(height+1)
        upper_right_int = upper_right.astype(int)
        del upper_right 
        lower_left = upper_left+self.boxsize
        del upper_left
        lower_left_int = lower_left.astype(int)
        del lower_left
        lower_right = upper_right_int+self.boxsize
        lower_right_int = lower_right.astype(int)
        del lower_right
    
    #Get the sum of local neighborhood defined by boxSize
        int_image_flat = int_image_int.flatten(order = 'F')
        del int_image_int
        int_image_flat_transpose = int_image_flat.T
        del int_image_flat
        neighborvals = (int_image_flat_transpose[upper_left_int]
                        + int_image_flat_transpose[lower_right_int] 
                        - int_image_flat_transpose[upper_right_int] 
                        - int_image_flat_transpose[lower_left_int])
        del lower_left_int
        del lower_right_int
        del upper_right_int
        del upper_left_int
        del int_image_flat_transpose
    #Divide the pixel averages by the pixel value
        reshape_vals = np.reshape(neighborvals, (height-2*floor_offset, width-2*floor_offset))
        del neighborvals
        #label_image = self.mask1
        double_image = label_image[ceil_offset-1: -floor_offset,ceil_offset-1: -floor_offset]
        pix_mask = reshape_vals / double_image
        del reshape_vals
        del ceil_offset
        del double_image
        pad = np.pad(pix_mask, ((floor_offset, floor_offset), (floor_offset, floor_offset)), mode='constant')
        del pix_mask
        del floor_offset
        thresh = self.boxsize*self.boxsize
    #Get perimeter of the object    
        pad_array = np.array(pad)
        del pad
        pad_flat = pad_array.flatten(order = 'F')
        del pad_array
        perimeter_indices = np.where(pad_flat!=thresh)
        del pad_flat
        del thresh
        perimeter_indices_array = np.asarray(perimeter_indices)
        del perimeter_indices
        perimeter_indices_reshape = perimeter_indices_array.reshape(-1,1)
        del perimeter_indices_array
        perimeter_zeros = np.zeros(label_image.shape)
        perimeter_int = perimeter_zeros.astype(int)
        del perimeter_zeros
        perimeter_flat = perimeter_int.flatten(order = 'F')
        del perimeter_int
        image_flat = label_image.flatten(order = 'F')
        perimeter_flat[perimeter_indices_reshape] = image_flat[perimeter_indices_reshape]
        del image_flat
        del perimeter_indices_reshape
        perimeter_reshape = perimeter_flat.reshape(height, width)
        del perimeter_flat
        del height
        del width
        perimeter_transpose = perimeter_reshape.T
        del perimeter_reshape
        return perimeter_transpose

    def neighbors(self,perimeter_transpose,pixelDistance):
        
        obj_edges = self.box_border_search(perimeter_transpose, self.boxsize)
    #Get the height and width of the labeled image
        height,width = obj_edges.shape

    #Generate number of samples for creating numeric sequence
        num_sequence = (2*self.pixeldistance)+1    
        pixel_distance_range = np.linspace(-self.pixeldistance,self.pixeldistance,num_sequence)
        del num_sequence
        
    #Create a rectangular grid out of an array of pixel_distance_range and an array of pixel_distance_range1 values
        column_index,row_index = np.meshgrid(pixel_distance_range,pixel_distance_range)
        del pixel_distance_range
        
    #Convert to single column vector
        column_index_transpose = column_index.T
        row_index_transpose = row_index.T
        del column_index
        del row_index
        column_index_reshape =  column_index_transpose.reshape(-1,1)
        row_index_reshape = row_index_transpose.reshape(-1,1)
        column_index_int = column_index_reshape.astype(int)
        row_index_int = row_index_reshape.astype(int)
        del column_index_transpose
        del row_index_transpose
        del column_index_reshape
        del row_index_reshape
        
    #Generate pixel neighborhood reference
        neighboroffsets = column_index_int*height+row_index_int
        neighboroffsets = neighboroffsets[neighboroffsets != 0]
        neighboroffsets = neighboroffsets.reshape(-1,1)
        del column_index_int
        del row_index_int
        
    #Get inscribed image linear indices:    
        width_sequence = width-(2*self.pixeldistance)
        height_sequence = height-(2*self.pixeldistance)
        columns_range = np.linspace(self.pixeldistance,width-self.pixeldistance-1,width_sequence)
        rows_range = np.linspace(self.pixeldistance,height-self.pixeldistance-1,height_sequence)
        del width_sequence
        del height_sequence
        columns,rows = np.meshgrid(columns_range,rows_range)
        del columns_range
        del rows_range
        columns_flat = columns.flatten(order = 'F')
        del columns
        del width
        columns_reshape = columns_flat.reshape(-1,1)
        del columns_flat 
        rows_flat = rows.flatten(order = 'F')
        del rows
        rows_reshape = rows_flat.reshape(-1,1)
        del rows_flat
        linear_index = height*columns_reshape+rows_reshape
        del height
        del columns_reshape
        del rows_reshape
        linear_index_int = linear_index.astype(int)
        del linear_index
        
    #Consider indices that contain objects 
        image_flatten = obj_edges.flatten(order = 'F')
        mask = image_flatten[linear_index_int]>0
        linear_index_mask = linear_index_int[mask]
        del linear_index_int
        del mask
        linear_index_reshape = linear_index_mask.reshape(-1,1)
   #Get indices of neighbor pixels
        neighbor_index = (neighboroffsets+linear_index_reshape.T)
        del neighboroffsets
        del linear_index_reshape

    #Get values of neighbor pixels
       
        neighborvals = image_flatten[neighbor_index]
        del neighbor_index   
        
    #Sort pixels by object    
        objnum = image_flatten[linear_index_mask]
        del image_flatten
        del linear_index_mask
        objnum_reshape = objnum.reshape(-1,1)
        index = list(range(len(objnum_reshape)))
        del objnum_reshape
        index = np.asarray(index).reshape(objnum.shape)
        stack_index_objnum= np.column_stack((index,objnum))
        del objnum
        sort_index_objnum = sorted(stack_index_objnum, key = itemgetter(1))
        del stack_index_objnum
        index_objnum_array = np.asarray(sort_index_objnum)
        del sort_index_objnum 
        index_split = index_objnum_array[:,0]
        objnum_split = index_objnum_array[:,1]
        del index_objnum_array
        index_reshape = np.asarray(index_split).reshape(-1,1)
        del index_split 
        objnum_reshape = np.asarray(objnum_split).reshape(-1,1)
        del objnum_split 
        del index
        
    #Find object index boundaries
        difference_objnum = np.diff(objnum_reshape,axis=0)
        del objnum_reshape
        stack_objnum = np.vstack((1,difference_objnum,1))
        del difference_objnum
        objbounds = np.where(stack_objnum)
        del stack_objnum
        objbounds_array = np.asarray(objbounds)
        del objbounds
        objbounds_split = objbounds_array[0,:]
        del objbounds_array
        objbounds_reshape = objbounds_split.reshape(-1,1)
        del objbounds_split 
        self.objneighbors = []
       
    #Get border objects  
        for obj in range(len(objbounds_reshape)-1):
            allvals = neighborvals[:, index_reshape[np.arange(objbounds_reshape[obj],objbounds_reshape[obj+1])]]
            sortedvals = np.sort(allvals.ravel())
            del allvals
            sortedvals_reshape = sortedvals.reshape(-1,1)
            del sortedvals
            difference_sortedvals = np.diff(sortedvals_reshape,axis=0)
            difference_sortedvals_flat = difference_sortedvals.flatten(order = 'C')
            del difference_sortedvals
            difference_sortedvals_stack = np.hstack((1,difference_sortedvals_flat))
            del difference_sortedvals_flat
            uniqueindices = np.where(difference_sortedvals_stack)
            del difference_sortedvals_stack
            uniqueindices_array = np.asarray(uniqueindices)
            del uniqueindices
            uniqueindices_transpose = uniqueindices_array.T
            del uniqueindices_array
            obj_neighbor = sortedvals_reshape[uniqueindices_transpose]
            del uniqueindices_transpose
            obj_neighbor_flat = obj_neighbor.flatten(order = 'C')
            del obj_neighbor
            self.objneighbors.append(obj_neighbor_flat)
            del obj_neighbor_flat
        objneighbors_array = np.asarray(self.objneighbors)
        del objbounds_reshape
        del neighborvals
        del index_reshape
        
        self.numneighbors = []
        self.objneighbors = []
    #Get the number of neighbor objects and its label
        for neigh in objneighbors_array:
            len_neighbor = len(neigh)-1
            self.numneighbors.append(len_neighbor)
            del len_neighbor
            del neigh
        del objneighbors_array
        numneighbors_arr = np.asarray(self.numneighbors)
        del self.numneighbors
        numneighbors_array = numneighbors_arr.reshape(-1,1)
        del numneighbors_arr
        self.labels =[]
        return numneighbors_array



    def feret_diameter(self, perimeter_transpose, angleStart, angleStop):
        counts_scalar_copy=None

    #Convert to radians
        theta = np.arange(self.thetastart,self.thetastop)
        theta = np.asarray(theta)
        theta = np.radians(theta)

    #Get border of objects
        obj_edges = self.box_border_search(perimeter_transpose, self.boxsize)

    #Get indices and label of all pixels
        obj_edges_flat = obj_edges.flatten(order = 'F')
        obj_edges_reshape = obj_edges_flat.reshape(-1,1)
        del obj_edges_flat
        objnum = obj_edges_reshape[obj_edges_reshape!=0]
        del obj_edges_reshape
        obj_edges_transpose = obj_edges.T
        del obj_edges
        positionx = np.where(obj_edges_transpose)[0]
        positionx_reshape = positionx.reshape(-1,1)
        del positionx
        positiony = np.where(obj_edges_transpose)[1]
        del obj_edges_transpose
        positiony_reshape = positiony.reshape(-1,1)
        del positiony
        index = list(range(len(objnum)))
        index = np.asarray(index).reshape(objnum.shape)
        stack_index_objnum = np.column_stack((index,objnum))
        del objnum
        del index
        
    #Sort pixels by label
        sort_index_objnum = sorted(stack_index_objnum, key=itemgetter(1))
        index_objnum_array = np.asarray(sort_index_objnum)
        del stack_index_objnum
        del sort_index_objnum
        index_split = index_objnum_array[:,0]
        objnum_split = index_objnum_array[:,1]
        del index_objnum_array
        positionx_index = positionx_reshape[index_split]
        del positionx_reshape
        positiony_index = positiony_reshape[index_split]
        del positiony_reshape
        del index_split
   #Get number of pixels for each object    
        objnum_reshape = np.asarray(objnum_split).reshape(-1,1)
        del objnum_split
        difference_objnum = np.diff(objnum_reshape,axis=0)
        stack_objnum = np.vstack((1,difference_objnum,1))
        del difference_objnum
        objbounds = np.where(stack_objnum)
        del stack_objnum
        objbounds_array = np.asarray(objbounds)
        del objbounds
        objbounds_split = objbounds_array[0,:]
        del objbounds_array
        objbounds_reshape = objbounds_split.reshape(-1,1)
        del objbounds_split
        objbounds_counts = objbounds_reshape[1:]-objbounds_reshape[:-1]
        del objnum_reshape
        del objbounds_reshape
         
        self.uniqueindices_list = [] # Clear#
    #Create cell with x, y positions of each objects border
        for counts in objbounds_counts:
            counts_scalar = np.asscalar(counts)
            if counts_scalar == objbounds_counts[0]:
                uniqueindices_x = positionx_index[:counts_scalar]
                uniqueindices_y = positiony_index[:counts_scalar]
                counts_scalar_copy = counts_scalar
            if counts_scalar != objbounds_counts[0]:
                index_range = counts_scalar_copy+counts_scalar
                uniqueindices_x = positionx_index[counts_scalar_copy: index_range]
                uniqueindices_y = positiony_index[counts_scalar_copy: index_range]
                counts_scalar_copy = index_range
            uniqueindices_x_reshape = uniqueindices_x.reshape(-1,1)
            del uniqueindices_x
            uniqueindices_y_reshape = uniqueindices_y.reshape(-1,1)
            del uniqueindices_y
            uniqueindices_concate = np.concatenate((uniqueindices_x_reshape, uniqueindices_y_reshape),axis=1)
            del uniqueindices_x_reshape 
            del uniqueindices_y_reshape
            self.uniqueindices_list.append(uniqueindices_concate)
            del uniqueindices_concate
            
    #Center points based on object centroid    
        uniqueindices_array = np.asarray(self.uniqueindices_list)
        self.meanind_list = [] # Clear#
        for indices in uniqueindices_array:
            #length = indices.shape[0]
            repitations= (len(indices),2)
            sum_indices0 = np.sum(indices[:, 0])
            sum_indices1 = np.sum(indices[:, 1])
            length_indices0 =(sum_indices0/len(indices))
            length_indices1 =(sum_indices1/len(indices))
            del sum_indices0
            del sum_indices1
            mean_tile0 = np.tile(length_indices0, repitations)
            del length_indices0
            sub_mean0_indices = np.subtract(indices, mean_tile0)
            del mean_tile0
            sub_mean0_indices = sub_mean0_indices[:,0]
            mean_tile1 = np.tile(length_indices1, repitations)
            del repitations
            del length_indices1
            sub_mean1_indices = np.subtract(indices, mean_tile1)
            del indices
            del mean_tile1
            sub_mean1_indices = sub_mean1_indices[:,1]
            meanind0_reshape = sub_mean0_indices.reshape(-1,1)
            del sub_mean0_indices
            meanind1_reshape = sub_mean1_indices.reshape(-1,1)
            del sub_mean1_indices
            meanind_concate = np.concatenate((meanind0_reshape, meanind1_reshape),axis=1)
            del meanind0_reshape
            del meanind1_reshape
            self.meanind_list.append(meanind_concate)
            del meanind_concate
        del uniqueindices_array    
        center_point = np.asarray(self.meanind_list)

    #Create transformation matrix
        rot_trans = np.array((np.cos(theta), -np.sin(theta)))
        rot_trans = rot_trans.T
        self.rot_list = [] # Clear#
        
    #Calculate rotation positions
        for point in center_point:
            self.rot_position.clear()
            for rotation in rot_trans:
                rot_mul = np.multiply(rotation,point)
                del rotation
                rot_add = np.add(rot_mul[:,0],rot_mul[:,1])#, out = aaa)
                del rot_mul
                self.rot_position.append(rot_add)
                del rot_add
            rot_array = np.asarray(self.rot_position)
            self.rot_list.append(rot_array)
            del rot_array
        del center_point
        del self.rot_position
        del point

        self.feretdiam = []    # Clear#
    #Get Ferets diameter  
        for rot in self.rot_list:
            self.sub_rot_list.clear()
            for rt,trans in zip(rot,rot_trans):
                sub_rot = np.subtract(np.max(rt),np.min(rt))
                del rt
                sub_rot_add = np.add(sub_rot, np.sum(abs(trans)))
                del sub_rot
                del trans
                self.sub_rot_list.append(sub_rot_add)
                del sub_rot_add
            convert_array = np.asarray(self.sub_rot_list)
            convert_reshape = convert_array.reshape(-1,1)
            del convert_array
            self.feretdiam.append(convert_reshape)
            del convert_reshape
        del self.sub_rot_list
        del self.rot_list
        del theta
        del rot
        feret_diameter = np.asarray(self.feretdiam)
        del self.feretdiam
         
        return feret_diameter
    
    def polygonality_hexagonality(self,area, perimeter, neighbors, solidity, maxferet, minferet):

        self.area_list=[]
        self.perim_list=[]
        
        #Calculate area hull
        area_hull = area/solidity

        #Calculate Perimeter hull
        perim_hull = 6*math.sqrt(area_hull/(1.5*math.sqrt(3)))

        if neighbors == 0:
            perimeter_neighbors = float("NAN")
        elif neighbors > 0:
            perimeter_neighbors = perimeter/neighbors

        #Polygonality metrics calculated based on the number of sides of the polygon
        if neighbors > 2:
            poly_size_ratio = 1-math.sqrt((1-(perimeter_neighbors/(math.sqrt((4*area)/(neighbors*(1/(math.tan(math.pi/neighbors))))))))*(1-(perimeter_neighbors/(math.sqrt((4*area)/(neighbors*(1/(math.tan(math.pi/neighbors)))))))))
            poly_area_ratio = 1-math.sqrt((1-(area/(0.25*neighbors*perimeter_neighbors*perimeter_neighbors*(1/(math.tan(math.pi/neighbors))))))*(1-(area/(0.25*neighbors*perimeter_neighbors*perimeter_neighbors*(1/(math.tan(math.pi/neighbors)))))))

        #Calculate Polygonality Score
            poly_ave = 10*(poly_size_ratio+poly_area_ratio)/2

        #Hexagonality metrics calculated based on a convex, regular, hexagon    
            apoth1 = math.sqrt(3)*perimeter/12
            apoth2 = math.sqrt(3)*maxferet/4
            apoth3 = minferet/2
            side1 = perimeter/6
            side2 = maxferet/2
            side3 = minferet/math.sqrt(3)
            side4 = perim_hull/6

        #Unique area calculations from the derived and primary measures above        
            area1 = 0.5*(3*math.sqrt(3))*side1*side1
            area2 = 0.5*(3*math.sqrt(3))*side2*side2
            area3 = 0.5*(3*math.sqrt(3))*side3*side3
            area4 = 3*side1*apoth2
            area5 = 3*side1*apoth3
            area6 = 3*side2*apoth3
            area7 = 3*side4*apoth1
            area8 = 3*side4*apoth2
            area9 = 3*side4*apoth3
            area10 = area_hull
            area11 = area
            
        #Create an array of all unique areas
            list_area=[area1, area2, area3, area4, area5, area6, area7, area8, area9, area10, area11]
            area_uniq = np.asarray(list_area,dtype= float)
            del list_area

        #Create an array of the ratio of all areas to eachother   
            for ib in range (0,len(area_uniq)):
                for ic in range (ib+1,len(area_uniq)):
                    area_ratio = 1-math.sqrt((1-(area_uniq[ib]/area_uniq[ic]))*(1-(area_uniq[ib]/area_uniq[ic])))
                    self.area_list.append (area_ratio)
                    del area_ratio
            area_array = np.asarray(self.area_list)
            del self.area_list
            stat_value_area=stats.describe(area_array)
            del area_array
            del area_uniq

        #Create Summary statistics of all array ratios     
            #area_ratio_min = stat_value_area.minmax[0]
            #area_ratio_max = stat_value_area.minmax[1]
            area_ratio_ave = stat_value_area.mean
            area_ratio_sd = math.sqrt(stat_value_area.variance)

        #Set the hexagon area ratio equal to the average Area Ratio
            hex_area_ratio = area_ratio_ave

        # Perimeter Ratio Calculations
        # Two extra apothems are now useful                 
            apoth4 = math.sqrt(3)*perim_hull/12
            apoth5 = math.sqrt(4*area_hull/(4.5*math.sqrt(3)))

            perim1 = math.sqrt(24*area/math.sqrt(3))
            perim2 = math.sqrt(24*area_hull/math.sqrt(3))
            perim3 = perimeter
            perim4 = perim_hull
            perim5 = 3*maxferet
            perim6 = 6*minferet/math.sqrt(3)
            perim7 = 2*area/(apoth1)
            perim8 = 2*area/(apoth2)
            perim9 = 2*area/(apoth3)
            perim10 = 2*area/(apoth4)
            perim11 = 2*area/(apoth5)
            perim12 = 2*area_hull/(apoth1)
            perim13 = 2*area_hull/(apoth2)
            perim14 = 2*area_hull/(apoth3)

        #Create an array of all unique Perimeters
            list_perim=[perim1,perim2,perim3,perim4,perim5,perim6,perim7,perim8,perim9,perim10,perim11,perim12,perim13,perim14]
            perim_uniq = np.asarray(list_perim,dtype= float)
            del list_perim

        #Create an array of the ratio of all Perimeters to eachother    
            for ib in range (0,len(perim_uniq)):
                for ic in range (ib+1,len(perim_uniq)):
                    perim_ratio = 1-math.sqrt((1-(perim_uniq[ib]/perim_uniq[ic]))*(1-(perim_uniq[ib]/perim_uniq[ic])))
                    self.perim_list.append (perim_ratio)
                    del perim_ratio
            perim_array = np.asarray(self.perim_list)
            del self.perim_list
            stat_value_perim=stats.describe(perim_array)
            del perim_array
            del perim_uniq

        #Create Summary statistics of all array ratios    
            #perim_ratio_min = stat_value_perim.minmax[0]
            #perim_ratio_max = stat_value_perim.minmax[1]
            perim_ratio_ave = stat_value_perim.mean
            perim_ratio_sd = math.sqrt(stat_value_perim.variance)

        #Set the HSR equal to the average Perimeter Ratio    
            hex_size_ratio = perim_ratio_ave
            hex_sd = np.sqrt((area_ratio_sd**2+perim_ratio_sd**2)/2)

        # Calculate Hexagonality score
            hex_ave = 10*(hex_area_ratio+hex_size_ratio)/2

        if neighbors < 3:
            poly_size_ratio = float("NAN")
            poly_area_ratio = float("NAN")
            poly_ave = float("NAN")
            hex_size_ratio = float("NAN")
            hex_area_ratio = float("NAN")
            hex_ave = float("NAN")
            hex_sd=float("NAN")
 
        return(poly_ave, hex_ave,hex_sd)
     
    def feature_extraction(self):
       
        for l,i in zip(self.label_image,self.intensity_image):
            
            regions = self.properties(l,i)
            
            #Calculate Perimeter to consider border pixels
            edges= self.box_border_search(l, self.boxsize)
            
            #Calculate Neighbor
            neighbor = self.neighbors(edges, self.pixeldistance)
            
            #Calculate Ferte Diameter
            feretdiam = self.feret_diameter(edges,self.thetastart, self.thetastop)
            
            
            for region, neigh, feret in zip(regions, neighbor, feretdiam):
                label = region.label
                area = region.area
                convex_areaa = region.convex_area
                perimeter = region.perimeter
                orientation = region.orientation
                centroid = str(region.centroid)
                centroidx,centroidy = centroid.split(',')
                centroidx = centroidx.replace('(','')
                centroidy = centroidy.replace(')','')
                eccentricity = region.eccentricity
                equivalent_diameter = region.equivalent_diameter
                euler_number = region.euler_number
                major_axis_length = region.major_axis_length
                minor_axis_length = region.minor_axis_length
                solidity = region.solidity
                neighbor_metric = neigh
                maxferet = np.max(feret)
                minferet = np.min(feret)
                poly_hex= self.polygonality_hexagonality(area, perimeter, neighbor_metric, solidity, maxferet, minferet)
                polygonality_score = poly_hex[0]
                hexagonality_score = poly_hex[1]
                hexagonality_sd = poly_hex[2]
                intensity_image = region.intensity_image
                img = region.image
                mean_intensity =  int((region.mean_intensity))
                max_intensity = int((region.max_intensity))
                min_intensity = int((region.min_intensity))
                median =int((np.median(intensity_image[img])))
                modes = mode(intensity_image[img])[0]
                sd = (np.std(intensity_image[img]))
                skewness= skew(intensity_image[img], axis=0, bias=True)
                hist_dd = np.histogramdd(np.ravel(intensity_image[img]), bins = 256)[0]/intensity_image[img].size
                hist_greater_zero = list(filter(lambda p: p > 0, np.ravel(hist_dd)))
                entropy = -np.sum(np.multiply(hist_greater_zero, np.log2(hist_greater_zero)))
                kurtosiss = kurtosis(intensity_image[img],axis=0,fisher=False, bias=True)
                df = pd.DataFrame({'Label':label,'Area':  area,'Perimeter':perimeter,'Neighbor_metric' : neighbor_metric,'Orientation': orientation,'Solidity': solidity,'MinFeret':minferet, 'MaxFeret': maxferet,'Hexagonality score':hexagonality_score,'Polygonality score': polygonality_score,'Hexagonality SD':hexagonality_sd, 'CentroidX': centroidx,'CentroidY': centroidy,'Convex Area': convex_areaa, 'Eccentricity': eccentricity,'Equivalent diameter': equivalent_diameter,'Euler Number':euler_number,'Major Axis Length':major_axis_length,'Minor Axis Length': minor_axis_length,'Mean_intensity': mean_intensity,'Maximum intensity':max_intensity,'Minimum intensity': min_intensity, 'Median': median, 'Mode': modes, 'Standard Deviation': sd, 'Skewness':skewness,'Kurtosis': kurtosiss, 'Entropy': entropy}, index=[0])
                self.df2=self.df2.append(df)
                del df
                del region
                del neigh
                del feret
                del area
                del convex_areaa
                del perimeter
                del orientation
                del centroidx
                del eccentricity
                del equivalent_diameter
                del euler_number
                del major_axis_length
                del minor_axis_length
                del solidity
                del neighbor_metric
                del maxferet
                del minferet
                del poly_hex
                del polygonality_score 
                del hexagonality_score 
                del hexagonality_sd 
                del intensity_image 
                del img
                del mean_intensity
                del max_intensity
                del min_intensity
                del median
                del modes
                del sd
                del skewness
                del hist_dd
                del hist_greater_zero
                del entropy
                del kurtosiss
            del regions
            del neighbor
            del edges
            del feretdiam
        df3 = self.df2
        del self.df2
        return df3
    
class Df_Csv(Analysis):
    def __init__(self,df3, output_dir):
        self.df3 = df3
        self.output_dir = output_dir

    def csvfile(self):
        os.chdir(self.output_dir)
        df4 = self.df3
        del self.df3
        #Export to csv
        export_csv = df4.to_csv (r'Feature_Extraction.csv', index = None, header=True)
        del df4
        del export_csv

                
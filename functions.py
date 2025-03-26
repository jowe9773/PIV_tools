#functions.py
"""This file holds all of the important tools needed to post process piv data. This means data that is exported from PIVLAB as a text file (with metadata?)"""

#import packages and modules
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog
import geopandas as gpd
from shapely.geometry import Point
from osgeo import gdal,osr

class File_Functions():
    '''Class containing methods for user handling of files.'''

    def __init__(self):
        print("Initialized File_Funtions")

    def load_dn(self, purpose):
        """this function opens a tkinter GUI for selecting a 
        directory and returns the full path to the directory 
        once selected
        
        'purpose' -- provides expanatory text in the GUI
        that tells the user what directory to select"""

        root = tk.Tk()
        root.withdraw()
        directory_name = filedialog.askdirectory(title = purpose)

        return directory_name

    def load_fn(self, purpose):
        """this function opens a tkinter GUI for selecting a 
        file and returns the full path to the file 
        once selected
        
        'purpose' -- provides expanatory text in the GUI
        that tells the user what file to select"""

        root = tk.Tk()
        root.withdraw()
        filename = filedialog.askopenfilename(title = purpose)

        return filename

class PIVProcessingTools():
    """Class containing PIV processing tools"""

    def __init__(self):
        print("Initialized PIV Processing Tools")

    def load_metadata(self, filename):
        """This module extracts metadata from a PIV data file saved as a .txt. 
        Will extract cell size, dimensions of grid, starting location grid center, and grid size."""

        # Read the CSV file into a DataFrame
        df = pd.read_csv(filename, skiprows=2)

        #find the number of rows of data (how many cells in the y direction)
        #instantiate counter variables
        y_num = None
        rows_before_change = 0
        previous_value = df.iloc[0, 0]

        #count number of rows before change in x value
        for index, row in df.iterrows():
            current_value = row[df.columns[0]]
            
            # Check if the value in the target column has changed
            if current_value != previous_value:
                break
            
            rows_before_change += 1
            previous_value = current_value

        # count the number of columns of data (how many cells in the x direction)
        #initialze counter variables
        y_num = None
        previous_value = None
        change_count = 0

        #count number of changes in x value
        for index, row in df.iterrows():
            current_value = row[df.columns[0]]
            
            # Check if the value in the target column has changed
            if current_value != previous_value:
                change_count += 1
            
            previous_value = current_value

        #Now lets define the metadata variables that we are interested in
        #origin is the x,y coordinate of the first datapoint
        x_origin = df.iloc[0, 0]
        y_origin = df.iloc[0, 1]

        #number is the number of rows/columns
        x_num = change_count
        y_num = rows_before_change

        #size is the distance between data points. For tif exports this will also be the cell size
        x_size = df.iloc[rows_before_change, 0] - df.iloc[0, 0]
        y_size = df.iloc[1, 1] - df.iloc[0, 1]

        #dim is the real world distances between the smallest and largest x coordinates and the smallest and largest y coordinates
        # basically it is the real world size of the grid of data points
        x_dim = x_size * x_num
        y_dim = y_size * y_num

        print("X origin: ", x_origin)
        print("Y origin: ", y_origin)
        print("x_num: ", x_num)
        print("y_num: ", y_num)
        print("x_size: ", x_size)
        print("y_size: ", y_size)
        print("x_dim: ", x_dim)
        print("y_dim: ", y_dim)

        metadata = [x_origin, y_origin, x_num, y_num, x_size, y_size]

        return metadata
    
    def load_txt_to_numpy(self, filename, x_num, y_num):

        # Read the CSV file into a DataFrame
        df = pd.read_csv(filename, skiprows=2)

        #Extract values from the 3rd column (Column3)
        u_values = df.iloc[:, 2].values
        v_values = df.iloc[:, 3].values

        # Reshape the values into a 2D NumPy array
        u_array_2d = u_values.reshape(x_num, y_num)
        u_array_2d = np.transpose(u_array_2d)
        v_array_2d = v_values.reshape(x_num, y_num)
        v_array_2d = np.transpose(v_array_2d)

        return u_array_2d, v_array_2d
    
    def export_PIV_as_geotiff(self, out_array, projection_num, directory, top_right_AOI, metadata):

        #this defines the distance btween the corner of the top left (first) cell and the edge of the top left corner of the AOI 
        x_border_offset = metadata[0] - (metadata[4]/2)
        y_border_offset = metadata[1] - (metadata[5]/2)
        
        #geotransorm parameters
        geotransform = [
        top_right_AOI[0] + (x_border_offset*1000),                  # top left x
        metadata[4]*1000,                                           # w-e pixel resolution
        0.0,                                                        # rotation, 0 if image is "north up"
        top_right_AOI[1] - (y_border_offset*1000),                              # top left y
        0.0,                                                        # rotation, 0 if image is "north up"
        -metadata[5]*1000                                           # n-s pixel resolution (negative value for north-up images)
]

        #instantiate tools for spatial reference
        proj = osr.SpatialReference()

        #import projection information
        proj.ImportFromEPSG(projection_num)

        #remove extra dimensions (dimensions that are only 1 long)
        datout = np.squeeze(out_array)

        #set nodata value to -9999
        datout[np.isnan(datout)] = -9999

        #set driver to export geotiff
        driver = gdal.GetDriverByName('GTiff')

        
        cols,rows = np.shape(datout)

        #list the output filename
        output_filename = directory + "/out_array.tif"

        #create geotiff, fill with data from output array
        ds = driver.Create(output_filename, rows, cols, 1, gdal.GDT_Float32, [ 'COMPRESS=LZW' ] )
        if proj is not None:
            ds.SetProjection(proj.ExportToWkt())

        ds.SetGeoTransform(geotransform)
        ss_band = ds.GetRasterBand(1)
        ss_band.WriteArray(datout)
        ss_band.SetNoDataValue(-9999)
        ss_band.FlushCache()
        ss_band.ComputeStatistics(False)
        ss_band.SetUnitType('m')

    def export_PIV_as_shp(self, out_array, projection_num, directory, top_right_AOI, metadata):

        # Unpack the start coordinates
        x_start = top_right_AOI[0] + metadata[0] * 1000
        y_start = top_right_AOI[1] - metadata[1] * 1000
        
        # Get the dimensions of the array
        rows, cols, attribute_num = out_array.shape
        
        # Create a list to store the point geometries and their attributes
        points = []

        # Iterate over the array to create points and attributes
        for i in range(rows):
            
            for j in range(cols):
                # Calculate the coordinates of the current point
                x = x_start + j * metadata[4] * 1000
                y = y_start - i * metadata[5] * 1000

                # Create a Point object
                point = Point(x, y)

                # Extract the attributes for the current point
                attributes = out_array[i, j, :]

                # Append the point and attributes to the list
                points.append((point, *attributes))

        # Create a GeoDataFrame from the list of points and attributes
        attribute_names = ["u_mean", "v_mean", "magnitude"]
        columns = ['geometry'] + attribute_names

        gdf = gpd.GeoDataFrame(points, columns=columns)

        # Set the CRS
        gdf.set_crs(epsg=projection_num, inplace=True)

        # Save the GeoDataFrame to a shapefile
        gdf.to_file(directory + "/out_array.shp")
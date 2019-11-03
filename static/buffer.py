
import arcpy
from arcpy import env

# Set environment settings
env.workspace = r"C:/Users/sherb/Documents/ArcGIS/Projects/MyProject/MyProject.gdb"
in_features = 'CEEC_NSW'
out_features = 'CEEC_buff90'
buffer_distance_or_field = "300 Meters"
arcpy.Buffer_analysis(in_features, out_features, buffer_distance_or_field)
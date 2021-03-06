#!/usr/bin/python3
# GVF Source: Analytics Vidhya
# generateBins.py
#
# This script generates the bins that need to be run to determine the beta values
import os
import sys

from pathlib import Path
import json
#import rasterio
from jenkspy import jenks
import jenkspy
import numpy as np
#import matplotlib.pyplot as plt
#plt.style.use('seaborn-poster')
#%matplotlib inline


# Import our libraries
sys.path.append(os.path.join(os.path.dirname(__file__), "include"))

from ascFile import *
from calibrationLib import *


# TODO Still need a good way of supplying these
PFPR_FILE       = "rwa_pfpr2to10.asc"
POPULATION_FILE = "rwa_population.asc"


# TODO Determine the bins computationally
# Following bins are for Rwanda
POPULATION_BINS = [2125, 5640, 8989, 12108, 15577, 20289, 27629, 49378, 95262, 286928]

# getting data ready for binning
# data should be 1-dimensional array, python list or iterable
myArray  = np.loadtxt("GIS\\rwa_population.asc", skiprows = 6)
print (type(myArray))
print(myArray.ndim)
print(myArray.shape)
print(myArray.size)
array_1d = myArray.flatten()
print (array_1d)
print(array_1d.ndim)
print(array_1d.shape)
print(array_1d.size)
#gvf = 0.0
#nclasses = 20

def goodness_of_variance_fit(array, classes):
    # get the break points
    classes = jenkspy.jenks_breaks(array, classes)

    # do the actual classification
    classified = np.array([classify(i, classes) for i in array])

    # max value of zones
    maxz = max(classified)

    # nested list of zone indices
    zone_indices = [[idx for idx, val in enumerate(classified) if zone + 1 == val] for zone in range(maxz)]

    # sum of squared deviations from array mean
    sdam = np.sum((array - array.mean()) ** 2)

    # sorted polygon stats
    array_sort = [np.array([array[index] for index in zone]) for zone in zone_indices]

    # sum of squared deviations of class means
    sdcm = sum([np.sum((classified - classified.mean()) ** 2) for classified in array_sort])

    # goodness of variance fit
    gvf = (sdam - sdcm) / sdam

    return gvf


def process(configuration, gisPath = ""):
    # Load the configuration
    cfg = load_configuration(configuration)

    # TODO Add the stuff for the population bins!

    # Get the access to treatments rate
    [treatments, needsBinning] = get_treatments_list(cfg, gisPath)
    if treatments == -1:
        print("Unable to load determine the treatments in the configuration.")
        exit(1)
    
    # TODO Add stuff for binning the treatments as needed!
    if needsBinning:
        print("Treatments need binning, not currently supported")
        exit(1)

    # Load the climate and treatment rasters
    climate = get_climate_zones(cfg, gisPath)
    treatment = get_treatments_raster(cfg, gisPath)

    # Load the relevent data
    filename = os.path.join(gisPath, PFPR_FILE)
    [ ascHeader, pfpr ] = load_asc(filename)
    filename = os.path.join(gisPath, POPULATION_FILE)
    [ ascHeader, population ] = load_asc(filename)

    # Prepare our results
    pfprRanges = {}
    zoneTreatments = {}

    # Process the data
    for row in range(0, ascHeader['nrows']):
        for col in range(0, ascHeader['ncols']):

            # Press on if there is nothing to do
            zone = climate[row][col]
            if zone == ascHeader['nodata']: continue

            # Note the bins
            popBin = int(get_bin(population[row][col], POPULATION_BINS))
            treatBin = get_bin(treatment[row][col], treatments)

            # Add to the dictionary as needed
            if zone not in pfprRanges:
                pfprRanges[zone] = {}            
            if popBin not in pfprRanges[zone]:
                pfprRanges[zone][popBin] = []
            if zone not in zoneTreatments:
                zoneTreatments[zone] = []
            
            # Add to our data sets
            pfprRanges[zone][popBin].append(pfpr[row][col])
            if treatBin not in zoneTreatments[zone]:
                zoneTreatments[zone].append(treatBin)

    return [ pfprRanges, zoneTreatments ]

def classify(value, breaks):
    for i in range(1, len(breaks)):
        if value < breaks[i]:
            return i
    return len(breaks) - 1

def save(pfpr, treatments, filename, username):
    with open(filename, 'w') as script:
        # Print the front matter
        script.write("#!/bin/bash\n")
        script.write("source ./calibrationLib.sh\n\n")

        # Print the ASC file generation commands
        script.write("generateAsc \"\\\"{}\\\"\"\n".format(
            " ".join([str(x) for x in sorted(POPULATION_BINS)])))
        script.write("generateZoneAsc \"\\\"{}\\\"\"\n\n".format(
            " ".join([str(x) for x in sorted(pfpr.keys())])))

        # Print the zone matter
        for zone in pfpr.keys():
            script.write("run {} \"\\\"{}\\\"\" \"\\\"{}\\\"\" {}".format(
                zone, 
                " ".join([str(x) for x in sorted(POPULATION_BINS)]), 
                " ".join([str(x) for x in sorted(treatments[zone])]), 
                username))


if __name__ == '__main__':


    if len(sys.argv) < 3:
        print("Usage: ./generateBins.py [configuration] [username] [gis]")

        print("configuration - the configuration file to be loaded")
        print("gis - the directory that GIS file can be found in")
        print("username - the user who will be running the calibration on the cluster")
        exit(0)


    # Parse the parameters
    configuration = str(sys.argv[1])
    gisPath = str(sys.argv[2])
    username = str(sys.argv[3])
    
    # Process and print the relevent ranges for the user
    [ pfpr, treatments ] = process( configuration, gisPath)
    for zone in pfpr.keys():
        print("Climate Zone {}".format(zone))
        print("Treatments: {}".format(sorted(treatments[zone])))
        print("Populations: {}".format(sorted(pfpr[zone].keys())))
        for popBin in sorted(pfpr[zone].keys()):
            print("{} - {} to {} PfPR".format(popBin, min(pfpr[zone][popBin]), max(pfpr[zone][popBin])))
        #print

    # Save the basic script
    if not os.path.isdir('out'): os.mkdir('out')
    save(pfpr, treatments, 'out/calibration.sh', username)

    # GVF Implementation
    gvf = 0.0
    nclasses = 20
    while gvf < 0.8:
        gvf = goodness_of_variance_fit(array_1d, nclasses)
        nclasses += 1
    print("The value of Goodness of Variance fit is:", gvf)
    if (gvf < 0.7):
        print("Warning: GVF too low")
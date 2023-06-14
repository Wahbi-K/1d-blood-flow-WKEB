# !/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Simulate all variations of the BraVa.
"""
import sys
from os.path import dirname, realpath
import shutil
import multiprocessing as mp
import traceback
import logging

# sys.path.append(realpath(dirname(__file__)))
from datetime import datetime
import os
from distutils.dir_util import copy_tree
import matplotlib.pyplot as plt

from Blood_Flow_1D import Metadata, GenerateBloodflowFiles


# make dir for Brava (with brava vtpm files)
# make two empty dir: Output, Clustering_Lib

def run_sim(name):
    patient_folder = Folder + name + "/"
    try:
        # os.mkdir(Folder + name)
        copy_tree(Main_folder + "/DefaultPatient_new_mesh", patient_folder)
    except OSError:
        print("Creation of the directory %s failed" % name)
    else:
        print("Successfully created the directory %s " % name)

    # Update CoW config in model_parameters.txt
    model_parameters = Metadata.ModelParameter()
    model_parameters.LoadModelParameters(patient_folder + "/bf_sim/Model_parameters.txt")
    model_parameters["NewPatientFiles"] = True
    model_parameters["UsingPatientSegmentation"] = False
    model_parameters["Donor_Network"] = name + ".vtp"
    model_parameters["Circle_of_Willis"] = "CoW_Complete"
    model_parameters["NewBravaSet"] = False
    model_parameters["ClotFile"] = "Clots"
    model_parameters["UsingPAfile"] = False
    model_parameters["ClusteringCompute"] = True
    model_parameters["brain_mesh"] = 'new'
    model_parameters.WriteModelParameters(patient_folder + "/bf_sim/Model_parameters.txt")

    # run the simulations
    try:
        GenerateBloodflowFiles.generatebloodflowfiles(patient_folder)
        # BloodFlowSimulator.blood_flow_script("", patient_folder, "True")
        # ContrastModel.runModel(patient_folder, True, 30)
    except OSError as err:
        print("OS error: {0}".format(err))
    except ValueError:
        print("Could not convert data to an integer.")
    except:
        print("Unexpected error:", sys.exc_info()[0])

    f.write(patient_folder + "\n")
    f.flush()
    plt.close('all')

    try:  # remove distance matrix after generation
        os.remove(patient_folder + "/bf_sim/Distancemat.npy")
    except:
        pass
    try:  # move files
        output_folder = Main_folder + "/Clustering_Lib/" + name + "/"
        try:
            os.mkdir(output_folder)
        except OSError:
            print("Creation of the directory %s failed" % output_folder)
        else:
            print("Successfully created the directory %s " % output_folder)

        clustercsv = patient_folder + "/bf_sim/Clusters.csv"
        clustervtp = patient_folder + "/bf_sim/Clustering.vtp"
        shutil.copy(clustercsv, output_folder)
        shutil.copy(clustervtp, output_folder)
    except:
        pass


if __name__ == '__main__':
    start_time = datetime.now()

    Main_folder = "/media/raymond/429D-D132/Simulations/Updated_new_mesh/"

    Folder = Main_folder + "/Output/"
    BravaFolder = Main_folder + "/Brava/"
    BraVa = [f.split(".vtp")[0] for f in os.listdir(BravaFolder) if
             os.path.isfile(os.path.join(BravaFolder, f)) and f[-3:] == "vtp"]

    f = open(Folder + "Completed.txt", "w")

    pool = mp.Pool(4)
    results = [pool.apply_async(run_sim, (name,)) for name in
               BraVa]  # async execution (switch to apply for sync)
    _ = [p.get() for p in results]
    pool.close()

    time_elapsed = datetime.now() - start_time
    print('Time elapsed (hh:mm:ss.ms) {}'.format(time_elapsed))
    f.close()

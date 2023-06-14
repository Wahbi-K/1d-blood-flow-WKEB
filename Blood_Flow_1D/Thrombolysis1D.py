#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Thrombolysis Simulator

Script to run a simulation of the 1D BF model with changing clot length.
Input argument is the patient folder with a folder for input files and a folder for modelling files
The input folder contains patient data.
The modelling file folder contains files for the models such as the parameters and the surface mesh.

Usage:
  tavernaBloodFlow.py <patient_folder>
  tavernaBloodFlow.py (-h | --help)

Options:
  -h --help     Show this screen.
"""

import contextlib
import math
from datetime import datetime

import numpy as np
from scipy.integrate import quad
from tqdm import tqdm

from Blood_Flow_1D import GeneralFunctions, Collaterals, Patient, \
    docopt, transcript, CollateralsSimulation


def change_clot_length(time, tpa_concentration, dp, c_fibrin):
    # time in s
    t = time * 60
    # dp in Pa
    # conc in ng/mL
    beta = 9e-11  # m^2/kg
    dl = beta * (tpa_concentration / c_fibrin) * dp * (t * t)  # m
    return 1e3 * dl  # mm
    # return 0.1

# The recommended total dose is 0.9 mg/kg (not to exceed 90 mg total dose)
# infused over 60 minutes with 10% {(0.09 mg/kg (max 9 mg)} of the total
# dose administered as an initial intravenous bolus over 1 minute.
# https://www.allinahealth.org/for-medical-professionals/-/media/allina-health/files/for-medical-professionals/emergency-protocols/allina-health-alteplase-dosage-administration.pdf
weight = 75 # kg
bloodvolume = 5000  # mL
dose = 0.9 * weight  # mg
bolus_conc = 0.1 * dose * 1e6/bloodvolume  # ng/mL
injection_duration = 60  # minutes
injection_concentration_rate = 0.9 * dose * 1e6/(bloodvolume*60)  # ng/mL/min
k = np.log(2) / 5  # decay constant (half-life: 5 minutes)

def injection_rate(time,injection_duration, injection_concentration_rate): # ng/mL/min
    return injection_concentration_rate * (1 - np.heaviside(time - injection_duration, 0))

# from scipy integrate
# Be aware that pulse shapes and other sharp features as compared to the size
# of the integration interval may not be integrated correctly using this method.

def tpa_concentration_function(time,injection_duration, injection_concentration_rate,k,bolus_conc):
    # tpa injection conc at time t
    # constant for an hour
    # return 13.3 * (1-np.heaviside(time-60, 1))  # ng/mL
    # return 13.3  # ng/mL
    return np.exp(-k * time) * (quad(lambda x: np.exp(k * x) * injection_rate(x, injection_duration, injection_concentration_rate), 0, min(time, injection_duration * 100))[0] + bolus_conc)

def concentration_profile(injection_duration, injection_concentration_rate,k,bolus_conc):
    time = np.linspace(0, 240, num=241, endpoint=True)
    profile = [tpa_concentration_function(t, injection_duration, injection_concentration_rate, k, bolus_conc) for t in time]
    return profile


def permeability_simulation(patient_folder):
    """
    Run the 1D model with data from patient_folder

    Parameters
    ----------
    patient_folder : str
        Patient folder location

    Returns
    -------
    """
    start_time = datetime.now()
    transcript.start(patient_folder + 'logfile.log')

    # Load files
    patient = Patient.Patient(patient_folder)
    patient.LoadBFSimFiles()
    patient.LoadPositions()

    dt = 1
    end_time = 240  # minutes
    maxiter = math.ceil(end_time / dt) + 2
    c_fibrin = 4e6  # ng/ml
    time_steps = range(0, maxiter)

    # BF Simulation initiation
    patient.Initiate1DSteadyStateModel()
    patient.Topology.NodeVesselDict()  # todo update clot output to store vessel as well

    for clot in patient.Topology.Clots:
        proximal_node = min(clot[0], key=lambda item: item.Number)
        distal_node = max(clot[0], key=lambda item: item.Number)
        length_clot = distal_node.LengthAlongVessel - proximal_node.LengthAlongVessel
        clot.append(length_clot)
        clot.append(patient.Topology.NodeDict[proximal_node])
        # todo replace this function by outputting this value to clots.txt directly

    # Thrombolysis simulation
    filename = patient.Folders.ModellingFolder + "Thrombolysis1D.csv"
    with open(filename, "w") as f:
        f.write("Time [m],Length [mm],Pressure drop [pa],Flow rate [mL/s],tPA [ng/ml]\n")
    clotfile = open(filename, "a")

    for current_time in tqdm(time_steps):
        # print(f"Current time:{current_time}")

        with contextlib.redirect_stdout(None):
            if patient.ModelParameters["UsingPAfile"] == "True" and GeneralFunctions.is_non_zero_file(
                    patient.Folders.ModellingFolder + "PAmapping.csv"):
                Collaterals.ImportPAnodes(patient)
                # if PAnode are present, run the model with the autoregulation method.
                CollateralsSimulation.collateral_simulation(patient, clot_active=False)
            else:
                patient.Run1DSteadyStateModel(model="Linear", tol=1e-12, clotactive=True, PressureInlets=True,
                                              FlowRateOutlets=False, coarseCollaterals=False,
                                              frictionconstant=patient.ModelParameters["FRICTION_C"],
                                              scale_resistance=True)
                # todo replace with coupled model eventually

        for clot in patient.Topology.Clots:
            proximal_node = min(clot[0], key=lambda item: item.Number)
            distal_node = max(clot[0], key=lambda item: item.Number)
            dp = proximal_node.Pressure - distal_node.Pressure

            # get concentration of tPA
            tpa_conc = tpa_concentration_function(current_time, injection_duration, injection_concentration_rate, k, bolus_conc)
            changed_length = change_clot_length(current_time, tpa_conc, dp, c_fibrin)
            # todo update for thrombolysis at both ends?

            # update clot length
            current_length = clot[3]
            new_length = current_length - changed_length
            # output current data
            clotfile.write("%d,%.10f,%.10f,%.10f,%.10f\n" % (current_time, current_length, dp,
                                                             distal_node.FlowRate, tpa_conc))

            # start at proximal end, shorten clot
            current_nodes = []
            for node in clot[0]:
                new_pos = node.LengthAlongVessel + changed_length
                if distal_node.LengthAlongVessel - new_pos < 1e-3 and not (node is distal_node):
                    # update connections
                    list(node.Connections)[0].AddConnection(list(node.Connections)[1])
                    list(node.Connections)[1].AddConnection(list(node.Connections)[0])
                    list(node.Connections)[0].RemoveConnection(node)
                    list(node.Connections)[1].RemoveConnection(node)
                    # remove from vessel
                    vessel = patient.Topology.NodeDict[node]
                    vessel.Nodes.remove(node)
                else:
                    node.LengthAlongVessel = min(distal_node.LengthAlongVessel, new_pos)
                    current_nodes.append(node)

            clot[0] = current_nodes
            clot[3] = new_length

        patient.Topology.Clots = [clot for clot in patient.Topology.Clots if len(clot[0]) >= 2]
        # patient.Topology.UpdateTopology()
    clotfile.close()
    time_elapsed = datetime.now() - start_time
    print('Time elapsed (hh:mm:ss.ms) {}'.format(time_elapsed))
    transcript.stop()


if __name__ == '__main__':
    arguments = docopt.docopt(__doc__, version='0.1')
    input_patient_folder = arguments["<patient_folder>"]
    # input_patient_folder = "/home/raymond/Desktop/thrombolysis/"
    permeability_simulation(input_patient_folder)

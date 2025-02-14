##########################################################################

# Titre: main.py
# Author: Christopher Sicotte (SICC2201)
# last modified: 26/03/2024

##########################################################################
'''
# Description: 

C'est ce fichier qui sera lancé par l'utilisateur pour lancer l'algorithme.

'''

###########################################################################

# IMPORTS

###########################################################################
import os
import time

# Custom libraries
import IBMQ_credentials
import Quantum_chemistry as qchem
import Utils

###########################################################################

# MAIN

###########################################################################


def main():
    # start_time = time.time()

    ibmq_token = "put your token here"
    backend_name = "ibmq_qasm_simulator"
    directory_path = "BSQ101_projects/Projet3/project_code/h2_mo_integrals"
    file_paths = [os.path.join(directory_path, file_path) for file_path in os.listdir(directory_path)]

    ####  uncomment if this is the first time you connect to your IBMQ account  ##########

    # IBMQ_credentials.ibmq_connexion(ibmq_token)

    #################################################################################

    #_, backend = IBMQ_credentials.ibmq_provider(backend_name)

    backend = IBMQ_credentials.get_local_simulator()
    execute_opts = {'shots': 512}

    h2_orbitals = 4

    distances, estimated_energy_from_minimizer, exact_energy, repulsion_energy = qchem.get_dissociation_curve_parameters(file_paths, h2_orbitals, backend, execute_opts)

    # end_time = time.time()
    # print('Runtime: ', end_time-start_time, 'sec')

    estimated_energy = [result['fun'] for result in estimated_energy_from_minimizer]
    estimated_dissociation_curve = qchem.add_repulsion_energy(estimated_energy, repulsion_energy)
    Utils.plot_results(distances, estimated_dissociation_curve, 'Estimated dissociation curve')
    print('minimal energy: ', min(estimated_dissociation_curve))

    exact_dissociation_curve = qchem.add_repulsion_energy(exact_energy, repulsion_energy)
    Utils.plot_results(distances, exact_dissociation_curve, 'Exact dissociation curve')
    print('minimal exact energy: ', min(exact_dissociation_curve))

    error = Utils.validate_results(estimated_dissociation_curve, exact_dissociation_curve)
    print('MSE: ', error)
    return 0


if __name__ == "__main__":
    main()
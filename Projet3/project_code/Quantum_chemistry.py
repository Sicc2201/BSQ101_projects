
##########################################################################

# Titre: Quantum_chemistry.py
# Author: Christopher Sicotte (SICC2201)
# last modified: 26/03/2024

##########################################################################
'''
# Description: 

Ce fichier contient toutes fonctions qui gèrent le processus de chimie quantique.

'''

###########################################################################

# IMPORTS

###########################################################################
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.providers.backend import Backend
from qiskit.quantum_info import PauliList, SparsePauliOp
import numpy as np
from numpy.typing import NDArray, ArrayLike
from typing import List, Callable, Union
from scipy.optimize import OptimizeResult, minimize

#custom library
import Utils
import Pauli_operations as po

###########################################################################

# METHODS

###########################################################################

def get_dissociation_curve_parameters(
data_file_Paths: List[str],
num_orbitals: int,
backend: Backend,
execute_opts : dict = dict()) -> Union[NDArray[np.float32], ArrayLike, NDArray[np.float32], NDArray[np.float32]]:
    """
    Manage the structure of the dissociation curve.
    Args:
    data_file_paths (NList[str]): File path that contains the data.
    num_orbitals (int): The number of orbitals spins of the molecule.
    backend (Backend): The backend to execute the circuit.
    execute_opts (dict): Dictionnary of execution options.
 
    Returns:
    NDArray[np.float32]: The interatomic distances
    NDArray[OptimizedResults]: The optimized results from the minimizer
    NDArray[np.float32]: The exact eigenvalues of the hamiltonians
    NDArray[np.float32]: The nuclear repulsion energy
    """
    
    state_circuit = create_initial_quantum_circuit(num_orbitals)
    
    annihilators = annihilation_operators_with_jordan_wigner(num_orbitals)

    return calculate_hamiltonian_energy(data_file_Paths, annihilators, state_circuit, backend, execute_opts)

def add_repulsion_energy(original_system: NDArray[np.float32], repulsion_energy_list: NDArray[np.float32]) -> NDArray[np.float32]:
    """
    Add the nuclear repulsion energy to the minimal electronic energy.
    Args:
    original_system (NDArray[np.float32]): The minimal electronic energy
    repulsion_energy_list (NDArray[np.float32]): The nuclear energy to add.
 
    Returns:
    NDArray[np.float32]: minimal molecular energy

    """   
    return np.add(original_system, repulsion_energy_list)

def calculate_hamiltonian_energy(data_file_Paths: str, annihilators: List[SparsePauliOp], state_circuit: QuantumCircuit, backend: Backend, execute_opts: dict):
    """
    Calculate the minimal energy of hamiltonians for every files.
    Args:
    data_file_paths (NList[str]): File paths that contains the data.
    annihilators (List[SparsePauliOp]): list of all the annihilator operators.
    state_circuit (QuantumCircuit): The quantum circuit that describe the occupation states of the electrons.
    backend (Backend): The backend to execute the circuit.
    execute_opts (dict): Dictionnary of execution options.
 
    Returns:
    NDArray[np.float32]: The interatomic distances
    NDArray[OptimizedResults]: The optimized results from the minimizer
    NDArray[np.float32]: The exact eigenvalues of the hamiltonians
    NDArray[np.float32]: The nuclear repulsion energy
    """
    distances = np.empty(len(data_file_Paths), dtype=float)
    repulsions = np.empty(len(data_file_Paths), dtype=float)
    optimized_results = np.empty(len(data_file_Paths), dtype=object)
    minimal_exact_eigenvalues = np.empty(len(data_file_Paths), dtype=float)
    creators = [op.adjoint() for op in annihilators]
    for index, file in enumerate(data_file_Paths):
        
        print('processing file: ', index + 1, ' of ', len(data_file_Paths))
        distance, one_body, two_body, repulsion_energy = Utils.extract_data(file)
        hamiltonian = build_qubit_hamiltonian(one_body, two_body, annihilators, creators)
        #print(hamiltonian.paulis)
        minimized_result = minimize_expectation_value(hamiltonian, state_circuit, [0], backend, minimize, execute_opts)
        distances[index] = float(distance)
        repulsions[index] = float(repulsion_energy)
        optimized_results[index] = minimized_result

        minimal_exact_eigenvalues[index] = exact_minimal_eigenvalue(hamiltonian)

    return distances, optimized_results, minimal_exact_eigenvalues, repulsions

def create_initial_quantum_circuit(num_qubits : int) -> QuantumCircuit:
    '''
    Build a quantum circuit.
    Args:
    num_qubits (int): the number of qubits (number of orbitals) to build the circuit
    Returns:
    QuantumCircuit: The quantum circuit reprensenting the electrons occupation states

    '''
    qc = QuantumCircuit(num_qubits)
    ry_param = Parameter("theta")
    qc.ry(ry_param, 1)
    qc.x(1)
    qc.cx(1, 0)
    qc.x(1)
    qc.cx(0, 2)
    qc.cx(1, 3)

    print(qc)

    return qc

def annihilation_operators_with_jordan_wigner(num_states: int) -> List[SparsePauliOp]:
    """
    Builds the annihilation operators as sum of two Pauli Strings for given number offermionic
    states using the Jordan Wigner mapping.
    Args:
    num_states (int): Number of fermionic states.
    Returns:
    List[SparsePauliOp]: The annihilation operators
    """

    annihilation_operators = []

    z1_bits = np.tri(num_states, num_states, -1)
    z2_bits = np.tri(num_states, num_states, 0)

    x_bits = np.eye(num_states, num_states, 0)

    for z1, z2, x in zip(z1_bits, z2_bits, x_bits): 
        paulis = PauliList.from_symplectic([z1, z2], [x, x])
        annihilation_operators.append(SparsePauliOp(paulis, [0.5, 0.5j]))

    return annihilation_operators

def build_qubit_hamiltonian(
one_body: NDArray[np.complex_],
two_body: NDArray[np.complex_],
annihilation_operators: List[SparsePauliOp],
creation_operators: List[SparsePauliOp],
) -> SparsePauliOp:
    """
    Build a qubit Hamiltonian from the one body and two body fermionic Hamiltonians.
    Args:
    one_body (NDArray[np.complex_]): The matrix for the one body Hamiltonian
    two_body (NDArray[np.complex_]): The array for the two body Hamiltonian
    annihilation_operators (List[SparsePauliOp]): List of sums of two Pauli strings
    creation_operators (List[SparsePauliOp]): List of sums of two Pauli strings (adjoint of
    annihilation_operators)
    Returns:
    SparsePauliOp: The total Hamiltonian as a sum of Pauli strings
    """
    qubit_hamiltonian = 0
    one_body_sum = 0
    two_body_sum = 0

    for i in range(len(annihilation_operators)):
        for j in range(len(annihilation_operators)):
            one_body_sum += one_body[i][j]*creation_operators[i].compose(annihilation_operators[j])
            a_ij = creation_operators[i].compose(creation_operators[j])
            for k in range(len(annihilation_operators)):
                for l in range(len(annihilation_operators)): 
                    a_kl = annihilation_operators[k].compose(annihilation_operators[l])
                    two_body_sum += two_body[i][j][k][l]*a_ij.compose(a_kl)

    qubit_hamiltonian = one_body_sum + 0.5*two_body_sum
    simplified_qubit_hamiltonian = qubit_hamiltonian.simplify()
    
    return simplified_qubit_hamiltonian

def minimize_expectation_value(
observable: SparsePauliOp,
ansatz: QuantumCircuit,
starting_params: list,
backend: Backend,
minimizer: Callable,
execute_opts: dict = {},
) -> OptimizeResult:
    """
    Uses the minimizer to search for the minimal expection value of the observable for the
    state that the ansatz produces given some parameters.
    Args:
    observable (SparsePauliOp): The observable which the expectation value will be
    minimized.
    ansatz (QuantumCircuit): A paramtrized quantum circuit used to produce quantum state.
    starting_params (list): The initial parameter of the circuit used to start the
    minimization.
    backend (Backend): A Qiskit backend on which the cirucit will be executed.
    minimizer (Callable): A callable function, based on scipy.optimize.minimize which only
    takes a function and starting params as inputs.
    execute_opts (dict, optional): Options to be passed to the Qsikit execute function.
    Returns:
    OptimizeResult: The result of the optimization
    """
    
    def cost_function(params):
        estimated_values = po.estimate_expectation_values(observable.paulis, ansatz.bind_parameters(params), backend, execute_opts)
        estimated_energy = np.dot(observable.coeffs, estimated_values)
        return estimated_energy

    return minimizer(cost_function, starting_params, method='COBYLA')

def exact_minimal_eigenvalue(observable: SparsePauliOp) -> float:
    """
    Computes the minimal eigenvalue of an observable.
    Args:
    observable (SparsePauliOp): The observable to diagonalize.
    Returns:
    float: The minimal eigenvalue of the observable.
    """

    eigenvalues, eigenvector = np.linalg.eigh(observable.to_matrix())

    return min(eigenvalues)
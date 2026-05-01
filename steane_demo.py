"""
Steane QEC demo 7/1/3 code - Adhyantha Chandrasekaran
Quantum algo final project

Circuit layout (10 qubits totally):
  data[0..6]  - 7 data qubits (logical qubit lives here)
  anc[0]      - ancilla for Z-stabilizer syndrome (detects X errors)
  anc[1]      - ancilla for X-stabilizer syndrome (detects Z errors)

Steane code parity-check matrix H (columns = qubits 0..6):
  Z-stabilizers (measured to detect X-errors):
    S1: qubits 0,2,4,6   (column pattern 1010101)
    S2: qubits 1,2,5,6   (column pattern 0110011)
    S3: qubits 3,4,5,6   (column pattern 0001111)

  Encoding |0>_L = (1/sqrt(8)) * sum of all even-weight codewords
  Encoding |1>_L = (1/sqrt(8)) * sum of all odd-weight codewords

Usage:
    python steane_demo.py --demo          # run all 4 demonstration cases
    python steane_demo.py --error X --qubit 3   # single case
    python steane_demo.py --selftest      # verify all 21 single-qubit errors
"""

from __future__ import annotations
import argparse
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.quantum_info import Statevector, random_unitary
from qiskit_aer import AerSimulator


# ---------------------------------------------------------------------------
# Steane code parameters
# ---------------------------------------------------------------------------
# Each stabilizer generator is a list of qubit indices it acts on.
# These match Mermin Ch.7 / standard [7,1,3] parity-check columns 1-7.
#
# The parity-check columns (1..7 in binary):
#   qubit 0 -> column 001
#   qubit 1 -> column 010
#   qubit 2 -> column 011
#   qubit 3 -> column 100
#   qubit 4 -> column 101
#   qubit 5 -> column 110
#   qubit 6 -> column 111
#
# Stabilizer S_k acts on qubits whose column has bit k set:
#   S0 (bit 0): qubits 0,2,4,6  (columns 001,011,101,111)
#   S1 (bit 1): qubits 1,2,5,6  (columns 010,011,110,111)
#   S2 (bit 2): qubits 3,4,5,6  (columns 100,101,110,111)

STABILIZER_QUBITS = [
    [0, 2, 4, 6],   # S0
    [1, 2, 5, 6],   # S1
    [3, 4, 5, 6],   # S2
]

# Syndrome lookup: syndrome bits (s2,s1,s0) as integer -> qubit index with error
# syndrome == qubit column index (1-indexed), so qubit = syndrome - 1
# syndrome 0 = no error
SYNDROME_TABLE = {s: s - 1 for s in range(1, 8)}


# ---------------------------------------------------------------------------
# Encoding circuit (explicit CNOTs, Mermin style)
# ---------------------------------------------------------------------------
def steane_encode(qc: QuantumCircuit, data) -> None:
    """
    Encode data[0] into logical qubit across data[0..6].

    Protocol (Mermin Ch.7):
    1. Apply H to data[0], data[1], data[3] (these parity bits become the
       |+> superpositions that generate the code space)
    2. Apply CNOTs from each 'check' qubit to every data qubit in its
       stabilizer group to spread the state.

    Logical |0> maps to equal superposition of all even-parity codewords.
    Logical |1> maps to equal superposition of all odd-parity codewords.
    """
    # Move logical input from data[0] to data[2] (data bit)
    qc.swap(data[0], data[2])
    
    # Put parity qubits into |+>
    qc.h(data[0])
    qc.h(data[1])
    qc.h(data[3])

    # CNOTs to entangle parity bits with data bits (building the Steane code)
    # For S0: parity q0 -> data q2, q4, q6
    qc.cx(data[0], data[2])
    qc.cx(data[0], data[4])
    qc.cx(data[0], data[6])

    # For S1: parity q1 -> data q2, q5, q6
    qc.cx(data[1], data[2])
    qc.cx(data[1], data[5])
    qc.cx(data[1], data[6])

    # For S2: parity q3 -> data q4, q5, q6
    qc.cx(data[3], data[4])
    qc.cx(data[3], data[5])
    qc.cx(data[3], data[6])


def steane_decode(qc: QuantumCircuit, data) -> None:
    """Decode: inverse of encoding (reverse CNOT order, same targets)."""
    # Exact inverse
    qc.cx(data[3], data[6])
    qc.cx(data[3], data[5])
    qc.cx(data[3], data[4])

    qc.cx(data[1], data[6])
    qc.cx(data[1], data[5])
    qc.cx(data[1], data[2])

    qc.cx(data[0], data[6])
    qc.cx(data[0], data[4])
    qc.cx(data[0], data[2])

    qc.h(data[3])
    qc.h(data[1])
    qc.h(data[0])
    
    qc.swap(data[0], data[2])


# ---------------------------------------------------------------------------
# Syndrome extraction (ancilla-based)
# ---------------------------------------------------------------------------
def extract_syndrome(qc: QuantumCircuit, data, anc, syn_x, syn_z) -> None:
    """
    Extract X-error syndrome and Z-error syndrome using 2 ancilla qubits.
    anc[0] measures Z-stabilizers to find X errors.
    anc[1] measures X-stabilizers to find Z errors.
    """
    for k, qubits in enumerate(STABILIZER_QUBITS):
        # 1. Measure Z-stabilizer using anc[0] (detects X errors)
        qc.reset(anc[0])
        for q in qubits:
            qc.cx(data[q], anc[0])
        qc.measure(anc[0], syn_x[k])
        
        # 2. Measure X-stabilizer using anc[1] (detects Z errors)
        qc.reset(anc[1])
        qc.h(anc[1])
        for q in qubits:
            qc.cx(anc[1], data[q])
        qc.h(anc[1])
        qc.measure(anc[1], syn_z[k])


# ---------------------------------------------------------------------------
# Main simulation (statevector, no measurement noise)
# ---------------------------------------------------------------------------

def syndrome_from_error_analytic(error_type: str, target: int):
    """Compute syndrome bits analytically for a known error (for verification)."""
    col = target + 1  # column index is qubit+1
    # X errors -> Z-stabilizer syndrome (bit pattern of column)
    # Z errors -> X-stabilizer syndrome
    x_syn = col if error_type in ("X", "Y") else 0
    z_syn = col if error_type in ("Z", "Y") else 0
    return x_syn, z_syn


def decode_syndrome(syndrome: int) -> int:
    """Syndrome integer -> qubit index. 0 means no error."""
    if syndrome == 0:
        return -1
    return syndrome - 1


def run_case(
    initial: str,
    error_type: str,
    target_qubit: int,
    apply_random_unitary: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Full demo circuit: prepare -> [random U] -> encode -> error -> syndrome ->
    correct -> decode -> [U†] -> measure.
    """
    data = QuantumRegister(7, "data")
    anc  = QuantumRegister(2, "anc")
    syn_x = ClassicalRegister(3, "syn_x")
    syn_z = ClassicalRegister(3, "syn_z")
    result_cr = ClassicalRegister(1, "out")

    # Order of registers matters for AerSimulator counts parsing.
    qc = QuantumCircuit(data, anc, syn_x, syn_z, result_cr)

    # ---- 1. PREPARE logical |0> ----
    steane_encode(qc, data)
    qc.barrier(label="encode_0")

    # ---- 2. INITIAL STATE TRANSVERSAL PREPARATION ----
    # Steane code allows transversal H and X
    if initial == "1":
        for i in range(7): qc.x(data[i])
    elif initial == "+":
        for i in range(7): qc.h(data[i])
    
    qc.barrier(label="logical_state")

    # ---- 3. INJECT ERROR ----
    # A random unitary on a single qubit acts as a continuous superposition of I, X, Y, Z errors.
    # QEC will discretize and correct this!
    if apply_random_unitary:
        U = random_unitary(2, seed=42)
        U_gate = U.to_instruction()
        U_gate.label = "U_error"
        qc.append(U_gate, [data[target_qubit]])
    else:
        if error_type == "X":
            qc.x(data[target_qubit])
        elif error_type == "Z":
            qc.z(data[target_qubit])
        elif error_type == "Y":
            qc.y(data[target_qubit])

    qc.barrier(label="error_injected")

    # ---- 4. SYNDROME EXTRACTION (Ancilla-based Mid-circuit measurement) ----
    extract_syndrome(qc, data, anc, syn_x, syn_z)
    
    # ---- 5. CORRECTION (Classical Feedforward) ----
    for syn_val in range(1, 8):
        err_qubit = decode_syndrome(syn_val)
        # Fix X errors based on syn_x measurement
        with qc.if_test((syn_x, syn_val)):
            qc.x(data[err_qubit])
        # Fix Z errors based on syn_z measurement
        with qc.if_test((syn_z, syn_val)):
            qc.z(data[err_qubit])

    qc.barrier(label="correct")

    # ---- 6. DECODE ----
    steane_decode(qc, data)
    qc.barrier(label="decode")

    # ---- 7. MEASURE data[0] (logical qubit readout) ----
    qc.measure(data[0], result_cr[0])

    # ---- Simulate with AerSimulator ----
    simulator = AerSimulator()
    compiled_qc = transpile(qc, simulator)
    job = simulator.run(compiled_qc, shots=1000)
    result = job.result()
    counts = result.get_counts(compiled_qc)
    
    # Qiskit get_counts() returns strings separated by spaces for each register.
    # Order matches how we added them: syn_x, syn_z, out.
    # So "out syn_z syn_x" is the format.
    # The leftmost token is result_cr (out).
    data0_prob_0 = sum(v for k, v in counts.items() if k.split()[0] == "0") / 1000.0
    data0_prob_1 = sum(v for k, v in counts.items() if k.split()[0] == "1") / 1000.0

    expected_data0 = "1" if initial == "1" else "0"
    
    if verbose:
        print(f"\n{'='*55}")
        print(f"  Initial: |{initial}>   Error: {error_type} on qubit {target_qubit}")
        print(f"  Random U applied: {apply_random_unitary}")
        
        # We can extract the syndrome that actually occurred from the counts.
        # Since it's deterministic (error is fixed), we just look at the highest count key.
        most_frequent = max(counts, key=counts.get).split()
        syn_z_val = int(most_frequent[1], 2)
        syn_x_val = int(most_frequent[2], 2)
        
        print(f"  Measured X-syndrome (finds X-err): {syn_x_val:03b}  -> qubit {decode_syndrome(syn_x_val)}")
        print(f"  Measured Z-syndrome (finds Z-err): {syn_z_val:03b}  -> qubit {decode_syndrome(syn_z_val)}")
        
        if initial == "+":
            correct = (abs(data0_prob_0 - 0.5) < 0.1) and (abs(data0_prob_1 - 0.5) < 0.1)
        elif initial == "1":
            correct = (abs(data0_prob_1 - 1.0) < 1e-6)
        else:
            correct = (abs(data0_prob_0 - 1.0) < 1e-6)
        print(f"  data[0] prob |0>: {data0_prob_0:.6f}  |1>: {data0_prob_1:.6f}")
        print(f"  Correction {'PASSED' if correct else 'FAILED'}")

    # Make sure we extract syndromes even if not verbose
    most_frequent = max(counts, key=counts.get).split()
    syn_z_val = int(most_frequent[1], 2)
    syn_x_val = int(most_frequent[2], 2)
    
    # Calculate correctness without printing
    if initial == "+":
        correct = (abs(data0_prob_0 - 0.5) < 0.1) and (abs(data0_prob_1 - 0.5) < 0.1)
    elif initial == "1":
        correct = (abs(data0_prob_1 - 1.0) < 1e-6)
    else:
        correct = (abs(data0_prob_0 - 1.0) < 1e-6)

    return {
        "circuit": qc,
        "counts": counts,
        "data0_prob_0": data0_prob_0,
        "data0_prob_1": data0_prob_1,
        "syn_x_val": syn_x_val,
        "syn_z_val": syn_z_val,
        "correct": correct
    }


# ---------------------------------------------------------------------------
# Self-test: all 21 single-qubit Pauli errors x {|0>,|1>,|+>}
# ---------------------------------------------------------------------------
def run_selftest():
    passed = 0
    failed = 0
    for initial in ("0", "1", "+"):
        for error in ("None", "X", "Y", "Z"):
            targets = [0] if error == "None" else range(7)
            for t in targets:
                result = run_case(initial, error, t, verbose=False)
                expected_bit = "1" if initial == "1" else "0"
                if initial == "+":
                    ok = abs(result["data0_prob_0"] - 0.5) < 0.1 and abs(result["data0_prob_1"] - 0.5) < 0.1
                else:
                    if initial == "0":
                        ok = abs(result["data0_prob_0"] - 1.0) < 1e-5
                    else:
                        ok = abs(result["data0_prob_1"] - 1.0) < 1e-5
                        
                if ok:
                    passed += 1
                else:
                    print(f"FAIL: initial={initial} error={error} qubit={t} probs={result['data0_prob_0'], result['data0_prob_1']}")
                    failed += 1
    print(f"\nSelf-test: {passed} passed, {failed} failed.")


# ---------------------------------------------------------------------------
# Demo: the 4 cases to show in your presentation
# ---------------------------------------------------------------------------
def run_demo():
    print("=" * 55)
    print("  STEANE [[7,1,3]] ERROR CORRECTION DEMO")
    print("=" * 55)

    print("\n[Case 1] No error -- should recover |0>")
    run_case("0", "None", 0)

    print("\n[Case 2] X error on qubit 3 -- bit flip correction")
    run_case("0", "X", 3)

    print("\n[Case 3] Z error on qubit 5 -- phase flip correction")
    run_case("0", "Z", 5)

    print("\n[Case 4] Continuous Random Unitary Error on qubit 2")
    print("         (Demonstrates measurement collapse discretizing a continuous error!)")
    run_case("0", "None", 2, apply_random_unitary=True)

    print("\n[Case 5] |1> logical state + Y error (X+Z)")
    run_case("1", "Y", 6)

    print()


# ---------------------------------------------------------------------------
# Draw circuits
# ---------------------------------------------------------------------------
def draw_circuits():
    """Save circuit diagrams for use in slides."""
    result = run_case("0", "X", 3, verbose=False)
    qc = result["circuit"]

    # Save to file so user can include in presentation
    try:
        import matplotlib.pyplot as plt
        qc.draw(output="mpl", filename="steane_circuit.png", fold=120)
        print("\n[+] Circuit diagram saved as steane_circuit.png")
    except ImportError:
        print("\n[!] Could not generate image (matplotlib/pylatexenc not installed).")

    # Text diagram
    print("\n--- FULL CIRCUIT (text) ---")
    print(qc.draw(output="text", fold=120))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Steane [[7,1,3]] QEC demo")
    p.add_argument("--demo",       action="store_true", help="Run presentation demo cases")
    p.add_argument("--selftest",   action="store_true", help="Test all 21 single-qubit errors")
    p.add_argument("--draw",       action="store_true", help="Print circuit diagram")
    p.add_argument("--initial",    choices=("0","1","+"), default="0")
    p.add_argument("--error",      choices=("None","X","Y","Z"), default="X")
    p.add_argument("--qubit",      type=int, default=0)
    p.add_argument("--random-u",   action="store_true", help="Apply random unitary before error")
    return p.parse_args()


def main():
    args = parse_args()
    if args.selftest:
        run_selftest()
    elif args.demo:
        run_demo()
    elif args.draw:
        draw_circuits()
    else:
        run_case(args.initial, args.error, args.qubit,
                 apply_random_unitary=args.random_u)


if __name__ == "__main__":
    main()
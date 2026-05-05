"""
Steane QEC demo 7/1/3 code - Adhyantha Chandrasekaran
Quantum algo final project

Usage:
    python steane_demo.py --demo
    python steane_demo.py --error X --qubit 3
"""

from __future__ import annotations
import argparse
import matplotlib
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.quantum_info import random_unitary
from qiskit_aer import AerSimulator

matplotlib.use("Agg")

# ----- Parameters for Steane's code ----- #
STABILIZER_QUBITS = [
    [0, 2, 4, 6],
    [1, 2, 5, 6],
    [3, 4, 5, 6],
]


def steane_encode(qc: QuantumCircuit, data) -> None:
    # switch logical input from parity to next available message bit, from Hamming code
    qc.swap(data[0], data[2])

    # applying superposition on three parity bits
    qc.h(data[0])
    qc.h(data[1])
    qc.h(data[3])

    for q in (0, 1, 3, 4, 5):
        qc.cx(data[2], data[q])

    # CNOT gates put the parity bits in entanglement with the other data bits
    qc.cx(data[0], data[2])
    qc.cx(data[0], data[4])
    qc.cx(data[0], data[6])

    qc.cx(data[1], data[2])
    qc.cx(data[1], data[5])
    qc.cx(data[1], data[6])

    qc.cx(data[3], data[4])
    qc.cx(data[3], data[5])
    qc.cx(data[3], data[6])


def steane_decode(qc: QuantumCircuit, data) -> None:
    # exact opposite of encoding, to make sure we reverse all the operations performed before measurement
    qc.cx(data[3], data[6])
    qc.cx(data[3], data[5])
    qc.cx(data[3], data[4])

    qc.cx(data[1], data[6])
    qc.cx(data[1], data[5])
    qc.cx(data[1], data[2])

    qc.cx(data[0], data[6])
    qc.cx(data[0], data[4])
    qc.cx(data[0], data[2])

    for q in (5, 4, 3, 1, 0):
        qc.cx(data[2], data[q])

    qc.h(data[3])
    qc.h(data[1])
    qc.h(data[0])

    qc.swap(data[0], data[2]) # move decoded message back into data[0] for measurement


def get_syndrome(qc: QuantumCircuit, data, ancilla, xsyn, zsyn) -> None:
    # This part detects X errors (bit flips) by measuring Z-parity
    for bob, qubits in enumerate(STABILIZER_QUBITS):
        qc.reset(ancilla[0])
        for steane in qubits:
            qc.cx(data[steane], ancilla[0])
        qc.measure(ancilla[0], xsyn[bob])

        # This part detects Z errors (phase flips) by measuring X-parity
        qc.reset(ancilla[1])
        qc.h(ancilla[1]) # Place ancilla in |+> state
        for shor in qubits:
            qc.cx(ancilla[1], data[shor])
        qc.h(ancilla[1]) # Return ancilla to Z-basis for measurement
        qc.measure(ancilla[1], zsyn[bob])


def decode_syndrome(syndrome: int) -> int:
    if syndrome == 0: # no error
        return -1
    return syndrome - 1 # find error qubit


def run_case(
    initial: str,
    error_type: str,
    target_qubit: int,
    apply_random_unitary: bool = False,
    verbose: bool = True,
) -> dict:
    if target_qubit < 0 or target_qubit > 6:
        raise ValueError("target_qubit must be between 0 and 6")

    # Creating multiple registers like quantum hardware engineer :)
    data = QuantumRegister(7, "data")
    ancilla = QuantumRegister(2, "anc")
    xsyn = ClassicalRegister(3, "xsyn")
    zsyn = ClassicalRegister(3, "zsyn")
    out = ClassicalRegister(1, "out")
    qc = QuantumCircuit(data, ancilla, xsyn, zsyn, out)

    if initial == "1": # user inputs 1
        qc.x(data[0]) # use X-flip to get 1 from 0
    elif initial == "+":
        qc.h(data[0]) # use hadamard to place in superposition

    steane_encode(qc, data) # encode to logical qubit after setting the initial state
    qc.barrier(label="encode")

    # Error injection
    if apply_random_unitary:
        U = random_unitary(2).to_instruction()
        U.label = "U_error"
        qc.append(U, [data[target_qubit]])
    else:
        if error_type == "X":
            qc.x(data[target_qubit])
        elif error_type == "Z":
            qc.z(data[target_qubit])
        elif error_type == "Y":
            qc.y(data[target_qubit])

    qc.barrier(label="error_injected")

    # extracting the symptoms!
    get_syndrome(qc, data, ancilla, xsyn, zsyn)

    # Correcting error (FINALLY!) totally writing 14 conditional rules (7 for X and 7 for Z)
    for syn_int in range(1, 8):
        err_qubit = decode_syndrome(syn_int)

        with qc.if_test((xsyn, syn_int)):
            qc.x(data[err_qubit])

        with qc.if_test((zsyn, syn_int)):
            qc.z(data[err_qubit])

    qc.barrier(label="correct")

    # decode
    steane_decode(qc, data)
    qc.barrier(label="decode")

    # measure final state
    if initial == "+":
        qc.h(data[0])
    qc.measure(data[0], out[0])

    # simulations yay!
    sim = AerSimulator()
    qc_transpiled = transpile(qc, sim)
    result = sim.run(qc_transpiled, shots=1000).result()
    counts = result.get_counts(qc_transpiled)

    # qiskit mashes xsyn, zsyn, out together so we need to extract string
    most_frequent_str = max(counts, key=counts.get)
    parts = most_frequent_str.split()

    x_syndrome_val = int(parts[2], 2)
    z_syndrome_val = int(parts[1], 2)

    total_shots = sum(counts.values())
    prob_0 = sum(v for k, v in counts.items() if k.split()[0] == "0") / total_shots
    prob_1 = sum(v for k, v in counts.items() if k.split()[0] == "1") / total_shots
    syndrome_distribution = {}

    for bit_string, shots in counts.items():
        bit_parts = bit_string.split()
        x_val = int(bit_parts[2], 2)
        z_val = int(bit_parts[1], 2)
        syndrome_distribution[(x_val, z_val)] = syndrome_distribution.get((x_val, z_val), 0) + shots

    if initial == "+":
        correct = (abs(prob_0 - 1.0) < 1e-6)
    elif initial == "1":
        correct = (abs(prob_1 - 1.0) < 1e-6)
    else:
        correct = (abs(prob_0 - 1.0) < 1e-6)

    if verbose:
        print(f"  Initial State: |{initial}>")
        print(f"  Injected Error: {'Continuous Random Unitary' if apply_random_unitary else error_type} on data[{target_qubit}]")
        print(f"  Measured X-syndrome (finds X-err): {x_syndrome_val:03b}  -> corrected qubit {decode_syndrome(x_syndrome_val)}")
        print(f"  Measured Z-syndrome (finds Z-err): {z_syndrome_val:03b}  -> corrected qubit {decode_syndrome(z_syndrome_val)}")
        if apply_random_unitary:
            print("  Random U syndrome branches:")
            for (x_val, z_val), shots in sorted(syndrome_distribution.items(), key=lambda item: item[1], reverse=True):
                print(f"    X={x_val:03b}, Z={z_val:03b}: {shots / total_shots:.3f}")
        print(f"  data[0] probabilities -> |0>: {prob_0:.3f}  |1>: {prob_1:.3f}")
        print(f"  Status: {'PASSED' if correct else 'FAILED'}")

    return {
        "circuit": qc,
        "counts": counts,
        "data0_prob_0": prob_0,
        "data0_prob_1": prob_1,
        "syn_x_val": x_syndrome_val,
        "syn_z_val": z_syndrome_val,
        "syndrome_distribution": syndrome_distribution,
        "correct": correct,
    }


def run_demo():
    print("Demo 0: No error")
    run_case("0", "None", 2)

    print("\nDemo 1: X error (bit flip)")
    run_case("0", "X", 5)

    print("\nDemo 2: Z error (phase flip)")
    run_case("+", "Z", 6)

    print("\nDemo 3: Y error on superposition")
    run_case("+", "Y", 2)

    print("\nDemo 4: Random unitary noise")
    run_case("1", "None", 1, apply_random_unitary=True)


def draw_circuits():
    result = run_case("0", "X", 3, verbose=False)
    qc = result["circuit"]

    try:
        import matplotlib.pyplot as plt
        qc.draw(output="mpl", filename="steane_circuit.png", fold=-1)
        print("\n[+] Circuit diagram saved as steane_circuit.png")
    except ImportError:
        print("\n[!] Could not generate image (matplotlib/pylatexenc not installed).")

    print("\nFULL CIRCUIT")
    print(qc.draw(output="text", fold=-1))


def parse_args():
    p = argparse.ArgumentParser(description="Steane [[7,1,3]] QEC demo")
    p.add_argument("--demo",       action="store_true", help="Run presentation demo cases")
    p.add_argument("--draw",       action="store_true", help="Print circuit diagram")
    p.add_argument("--initial",    choices=("0","1","+"), default="0")
    p.add_argument("--error",      choices=("None","X","Y","Z"), default="X")
    p.add_argument("--qubit",      type=int, default=0)
    p.add_argument("--random-u",   action="store_true", help="Apply random unitary before error")
    return p.parse_args()


def main():
    args = parse_args()
    if args.qubit < 0 or args.qubit > 6:
        raise SystemExit("qubit must be between 0 and 6")

    if args.demo:
        run_demo()
    elif args.draw:
        draw_circuits()
    else:
        run_case(args.initial, args.error, args.qubit, apply_random_unitary=args.random_u)


if __name__ == "__main__":
    main()

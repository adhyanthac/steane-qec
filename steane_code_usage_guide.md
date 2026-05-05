# Steane [[7,1,3]] Code Simulator: Usage Guide

This guide explains how to operate the Steane Quantum Error Correction (QEC) simulator. You can run it from the notebook, from the command line, or through the GUI.

## 1. Using the Graphical User Interface (GUI)

The GUI provides an interactive, visual way to experiment with the code during your presentation without needing to type commands.

### How to Launch
Open your terminal (in VS Code or standard Windows Terminal) and ensure you are in your project directory:
```powershell
python steane_gui.py
```

### Navigating the GUI
1. **Initial Logical State:** Select the logical state you want to prepare before encoding. You can choose $|0\rangle_L$, $|1\rangle_L$, or $|+\rangle_L$.
2. **Injected Pauli Error:** Choose the discrete Pauli error ($X$, $Y$, or $Z$) to inject into the circuit, or select `None` to run a clean circuit.
3. **Target Data Qubit (0-6):** Use the slider to pick which physical qubit (0 through 6) will be hit by the error. 
4. **Apply Continuous Random Unitary:** Checking this box applies a fresh random single-qubit unitary error to the selected physical data qubit instead of the Pauli error. The syndrome measurement can land in different Pauli-like branches, so the GUI reports the branch probabilities.
5. **Run Simulation:** Click this button to execute the circuit via Qiskit's `AerSimulator`. 
6. **Results Panel:** Once complete, the right-side text panel will display exactly what syndromes were measured, which qubits were corrected, and the final restored state probability.
7. **Circuit Diagram:** A visual representation of the generated quantum circuit will automatically render at the bottom right.

## 2. Using the Command-Line Interface (CLI)

The CLI (`steane_demo.py`) is excellent for running automated tests, generating diagrams for slides, or executing predefined presentation scenarios.

### How to Launch
Run the primary script directly from your terminal:
```powershell
python steane_demo.py [OPTIONS]
```

### Available Command-Line Arguments

You can mix and match these arguments to build specific test cases:

| Argument | Options | Description |
| :--- | :--- | :--- |
| `--initial` | `0`, `1`, `+` | Sets the initial logical state to encode. (Default: `0`) |
| `--error` | `None`, `X`, `Y`, `Z` | Sets the discrete Pauli error to inject. (Default: `X`) |
| `--qubit` | `0` to `6` | Selects which physical data qubit receives the error. (Default: `0`) |
| `--random-u` | *(Flag)* | Applies a fresh random unitary error on the selected physical data qubit instead of the Pauli error. |
| `--demo` | *(Flag)* | Automatically runs through 5 predefined presentation cases. |
| `--draw` | *(Flag)* | Generates a high-quality image of the circuit (`steane_circuit.png`) and prints an ASCII version to the terminal. |

## 3. Example Terminal Commands

Here are some useful commands you might want to run or show during your presentation:

**Run a single custom error case:**
*(Encodes $|1\rangle_L$, applies a Phase-Flip ($Z$) error on Qubit 4, and corrects it)*
```powershell
python steane_demo.py --initial 1 --error Z --qubit 4
```

**Demonstrate a random unitary error:**
*(Applies a random single-qubit unitary error on Qubit 2 and shows the syndrome branches)*
```powershell
python steane_demo.py --error X --qubit 2 --random-u
```

**Generate a circuit diagram image for your slides:**
*(Saves `steane_circuit.png` to your folder based on an X error on Qubit 3)*
```powershell
python steane_demo.py --draw
```

**Run the automated presentation demo sequence:**
*(Runs 5 distinct cases, explaining the output for each)*
```powershell
python steane_demo.py --demo
```

**Run the notebook demo:**
*(Use this version when you want a quick presentation walkthrough.)*
```powershell
jupyter notebook steane_qec.ipynb
```

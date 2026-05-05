import customtkinter as ctk
from PIL import Image
import os
import shutil

# GUI implementation polished with assistance from Anthropic.

# Ensure matplotlib backend doesn't try to open a window
import matplotlib
matplotlib.use('Agg')

from steane_demo import run_case, decode_syndrome

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SteaneApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Steane [[7,1,3]] Quantum Error Correction Simulator")
        self.geometry("1200x800")
        
        # Grid layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Steane [[7,1,3]]", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))
        
        # Initial State
        self.initial_label = ctk.CTkLabel(self.sidebar_frame, text="Initial Logical State:", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.initial_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.initial_var = ctk.StringVar(value="0")
        self.initial_dropdown = ctk.CTkSegmentedButton(self.sidebar_frame, variable=self.initial_var, values=["0", "1", "+"])
        self.initial_dropdown.grid(row=2, column=0, padx=20, pady=(5, 20), sticky="ew")
        
        # Error Type
        self.error_label = ctk.CTkLabel(self.sidebar_frame, text="Injected Pauli Error:", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.error_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.error_var = ctk.StringVar(value="X")
        self.error_dropdown = ctk.CTkSegmentedButton(self.sidebar_frame, variable=self.error_var, values=["None", "X", "Y", "Z"])
        self.error_dropdown.grid(row=4, column=0, padx=20, pady=(5, 20), sticky="ew")
        
        # Target Qubit
        self.qubit_label = ctk.CTkLabel(self.sidebar_frame, text="Target Data Qubit (0-6):", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.qubit_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
        self.qubit_var = ctk.IntVar(value=3)
        self.qubit_slider = ctk.CTkSlider(self.sidebar_frame, from_=0, to=6, number_of_steps=6, variable=self.qubit_var)
        self.qubit_slider.grid(row=6, column=0, padx=20, pady=(5, 5), sticky="ew")
        self.qubit_display = ctk.CTkLabel(self.sidebar_frame, textvariable=self.qubit_var)
        self.qubit_display.grid(row=7, column=0, padx=20, pady=(0, 20))
        
        # Continuous Error Checkbox
        self.rand_u_var = ctk.BooleanVar(value=False)
        self.rand_u_checkbox = ctk.CTkCheckBox(
            self.sidebar_frame, 
            text="Apply Continuous Random\nUnitary (Instead of Pauli)", 
            variable=self.rand_u_var,
            command=self.toggle_random_unitary,
            font=ctk.CTkFont(weight="bold")
        )
        self.rand_u_checkbox.grid(row=8, column=0, padx=20, pady=20, sticky="w")
        
        # Run Button
        self.run_button = ctk.CTkButton(self.sidebar_frame, text="Run Simulation", command=self.run_simulation, font=ctk.CTkFont(size=16, weight="bold"), height=40)
        self.run_button.grid(row=10, column=0, padx=20, pady=20, sticky="ew")
        
        # Save Button
        self.save_button = ctk.CTkButton(self.sidebar_frame, text="Save Circuit Image As...", command=self.save_image, font=ctk.CTkFont(size=14, weight="bold"), height=35, fg_color="#2b7b51", hover_color="#1f5a3b")
        self.save_button.grid(row=11, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.save_button.configure(state="disabled")
        
        # Main Area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Results Text
        self.results_textbox = ctk.CTkTextbox(self.main_frame, height=220, font=ctk.CTkFont(family="Consolas", size=16))
        self.results_textbox.grid(row=0, column=0, sticky="new", padx=10, pady=10)
        self.results_textbox.insert("0.0", "Ready.\n\nConfigure parameters on the left and click 'Run Simulation'.\n\nQiskit AerSimulator will execute the circuit with mid-circuit\nmeasurements and classical feedforward error correction.")
        self.results_textbox.configure(state="disabled")
        
        # Image Display (Scrollable frame for large circuits)
        self.image_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="Generated Circuit Diagram")
        self.image_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.image_label = ctk.CTkLabel(self.image_frame, text="")
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)

    def toggle_random_unitary(self):
        if self.rand_u_var.get():
            self.error_dropdown.configure(state="disabled")
        else:
            self.error_dropdown.configure(state="normal")

    def run_simulation(self):
        # Disable button while running
        self.run_button.configure(state="disabled", text="Running...")
        self.update()
        
        try:
            initial = self.initial_var.get()
            error = self.error_var.get()
            qubit = self.qubit_var.get()
            rand_u = self.rand_u_var.get()
            
            # Execute the simulation
            result = run_case(initial, error, qubit, apply_random_unitary=rand_u, verbose=False)
            
            # Extract values
            data0_0 = result["data0_prob_0"]
            data0_1 = result["data0_prob_1"]
            syn_x = result["syn_x_val"]
            syn_z = result["syn_z_val"]
            syndrome_distribution = result["syndrome_distribution"]
            correct = result["correct"]
            qc = result["circuit"]
            
            # Save circuit drawing with a smaller fold and larger scale for better visibility
            img_path = "gui_circuit.png"
            qc.draw(output="mpl", filename=img_path, fold=60, scale=1.2)
            
            # Enable the save button
            self.save_button.configure(state="normal")
            
            # Display Image
            if os.path.exists(img_path):
                img = Image.open(img_path)
                # Resize dynamically to fit the width of the frame so we don't need horizontal scrolling
                width, height = img.size
                
                # Target width is roughly the width of the main frame (around 800px)
                target_width = 800
                ratio = target_width / float(width)
                new_size = (int(width * ratio), int(height * ratio))
                
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=new_size)
                self.image_label.configure(image=ctk_img)
                self.image_label.image = ctk_img  # Keep reference
            
            # Format text output
            status = "PASSED \u2713" if correct else "FAILED \u2717"
            q_x = decode_syndrome(syn_x)
            q_z = decode_syndrome(syn_z)
            
            msg = f"RESULTS\n"
            msg += f"Initial Logical State: |{initial}>\n"
            msg += f"Injected Error       : {'Continuous Random Unitary' if rand_u else error} on data[{qubit}]\n\n"
            msg += f"Measured X-Syndrome (detects X-errors): {syn_x:03b}  -->  Corrected qubit {q_x if q_x >= 0 else 'None'}\n"
            msg += f"Measured Z-Syndrome (detects Z-errors): {syn_z:03b}  -->  Corrected qubit {q_z if q_z >= 0 else 'None'}\n\n"
            if rand_u:
                msg += "Random unitary syndrome branches:\n"
                total_branch_shots = sum(syndrome_distribution.values())
                for (x_val, z_val), shots in sorted(syndrome_distribution.items(), key=lambda item: item[1], reverse=True):
                    msg += f"  X={x_val:03b}, Z={z_val:03b}: {shots / total_branch_shots:.3f}\n"
                msg += "\n"
            msg += f"Final decoded data[0] probabilities:  P(|0>) = {data0_0:.4f}  |  P(|1>) = {data0_1:.4f}\n\n"
            msg += f"Error Correction Status: {status}"
            
            self.results_textbox.configure(state="normal")
            self.results_textbox.delete("0.0", "end")
            self.results_textbox.insert("0.0", msg)
            self.results_textbox.configure(state="disabled")
            
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            self.results_textbox.configure(state="normal")
            self.results_textbox.delete("0.0", "end")
            self.results_textbox.insert("0.0", f"Error running simulation:\n{err_msg}")
            self.results_textbox.configure(state="disabled")
            
        # Re-enable button
        self.run_button.configure(state="normal", text="Run Simulation")

    def save_image(self):
        if not os.path.exists("gui_circuit.png"):
            return
        
        filepath = ctk.filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Save Circuit Diagram As..."
        )
        if filepath:
            try:
                shutil.copy("gui_circuit.png", filepath)
                self.results_textbox.configure(state="normal")
                self.results_textbox.insert("0.0", f"--> Image successfully saved to:\n{filepath}\n\n")
                self.results_textbox.configure(state="disabled")
            except Exception as e:
                self.results_textbox.configure(state="normal")
                self.results_textbox.insert("0.0", f"--> Error saving image: {str(e)}\n\n")
                self.results_textbox.configure(state="disabled")


if __name__ == "__main__":
    app = SteaneApp()
    app.mainloop()

import socket
import random
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog
import logging
import json
import os

# Configuration defaults
XPLANE_IP = '127.0.0.1'
XPLANE_PORT = 49000
FAILURE_PROBABILITY = 0.001
CHECK_INTERVAL = 300
FAILURES_FILE = 'failures.json'

FAILURE_TYPES = ['HYDRAULIC', 'ELECTRICAL', 'AVIONICS', 'FUEL']

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class FailureInjectorApp:
    def __init__(self, master, registration):
        self.master = master
        self.master.title("Failure Injector")
        self.registration = registration

        # Load failures
        self.failures_dict = self.load_failures()

        # Variables for auto fail
        self.auto_fail_var = tk.BooleanVar(value=True)
        self.probability_var = tk.DoubleVar(value=FAILURE_PROBABILITY)
        self.interval_var = tk.DoubleVar(value=CHECK_INTERVAL)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=True, fill='both')

        # Create pages
        self.create_failure_page()
        self.create_settings_page()
        self.create_readme_page()
        self.create_failure_log_page()  # New tab for all failures

        # Thread control
        self.running = False
        self.thread = None

        # Handle close
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_failure_page(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Failure Controls")

        # Start/Stop button
        self.start_button = ttk.Button(frame, text="Start", command=self.toggle_injection)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        # Manual failure buttons
        manual_frame = ttk.LabelFrame(frame, text="Manual Failures")
        manual_frame.grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        for i, ft in enumerate(FAILURE_TYPES):
            btn = ttk.Button(manual_frame, text=f"Manual {ft}", command=lambda ft=ft: self.manual_failure(ft))
            btn.grid(row=0, column=i, padx=2, pady=2)

        # Clear failures button
        self.clear_button = ttk.Button(frame, text="Clear Failures", command=self.clear_failures)
        self.clear_button.grid(row=2, column=0, padx=5, pady=5)

        # Log area
        self.log_area = scrolledtext.ScrolledText(frame, width=80, height=15, state='disabled')
        self.log_area.grid(row=3, column=0, padx=5, pady=5)

    def create_settings_page(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Settings")

        # Auto Fail checkbox
        ttk.Checkbutton(frame, text="Auto Fail", variable=self.auto_fail_var).grid(row=0, column=0, sticky='w', padx=5, pady=5)

        # Failure probability
        ttk.Label(frame, text="Failure Probability (0-1):").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        prob_entry = ttk.Spinbox(frame, from_=0.0, to=1.0, increment=0.001, textvariable=self.probability_var, width=10)
        prob_entry.grid(row=1, column=1, padx=5, pady=2)

        # Check interval
        ttk.Label(frame, text="Check Interval (sec):").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        interval_entry = ttk.Spinbox(frame, from_=1, to=3600, increment=1, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=2, column=1, padx=5, pady=2)

        # Recommended settings label
        ttk.Label(frame, text="Recommended failure rate 0.001 and check rate 300 seconds").grid(row=4, column=0, columnspan=2, padx=5, pady=10)
        
        # Save settings button
        save_button = ttk.Button(frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=5, column=0, columnspan=2, pady=10)

    def create_readme_page(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="ReadMe")
        text = (
            "Failure Injector Application\n"
            "This tool injects failure commands into the simulation environment.\n"
            "Features:\n"
            "- Auto failure with configurable probability and interval.\n"
            "- Manual trigger for different failure types.\n"
            "- Persistently remembers failures per registration.\n"
            "- Modern GUI with tabs.\n"
        )
        label = ttk.Label(frame, text=text, justify='left')
        label.pack(padx=10, pady=10)

    def create_failure_log_page(self):
        # New tab for all triggered failures
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Failure Log")
        self.failure_log_text = scrolledtext.ScrolledText(frame, width=80, height=15, state='disabled')
        self.failure_log_text.pack(padx=5, pady=5)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        logging.info(message)

    def record_failure_triggered(self, failure_type):
        # Record and display in failure log tab
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} - {failure_type}"
        self.failure_log_text.config(state='normal')
        self.failure_log_text.insert(tk.END, entry + "\n")
        self.failure_log_text.see(tk.END)
        self.failure_log_text.config(state='disabled')

        # Also update failures dict
        reg = self.registration
        if reg not in self.failures_dict:
            self.failures_dict[reg] = set()
        self.failures_dict[reg].add(failure_type)

        # Save to json
        self.save_failures()

    def toggle_injection(self):
        if not self.running:
            # get user settings
            try:
                # Use the variables directly
                prob = float(self.probability_var.get())
                interval = float(self.interval_var.get())
                if not (0 <= prob <= 1):
                    raise ValueError("Probability must be between 0 and 1")
                global FAILURE_PROBABILITY, CHECK_INTERVAL
                FAILURE_PROBABILITY = prob
                CHECK_INTERVAL = interval
            except Exception as e:
                self.log(f"Invalid settings: {e}")
                return
            self.running = True
            self.start_button.config(text="Stop")
            self.thread = threading.Thread(target=self.run_injection, daemon=True)
            self.thread.start()
            self.log("Failure injection started.")
        else:
            self.running = False
            self.start_button.config(text="Start")
            self.log("Failure injection stopped.")

    def run_injection(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self.running:
            if self.auto_fail_var.get():
                if random.random() < FAILURE_PROBABILITY:
                    failure = random.choice(FAILURE_TYPES)
                    self.send_failure(failure, sock)
            time.sleep(CHECK_INTERVAL)
        sock.close()

    def send_failure(self, failure_type, sock=None):
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_created = True
        else:
            sock_created = False
        message = f"FAIL:{failure_type}"
        try:
            sock.sendto(message.encode(), (XPLANE_IP, XPLANE_PORT))
            self.log(f"{self.registration}: Sent failure: {message}")
            # Record this triggered failure
            self.record_failure_triggered(failure_type)
        except Exception as e:
            self.log(f"Error sending failure: {e}")
        if sock_created:
            sock.close()

    def manual_failure(self, failure_type):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_failure(failure_type, sock)

    def change_registration(self):
        new_reg = simpledialog.askstring("Change Registration", "Enter new registration code:", initialvalue=self.registration)
        if new_reg:
            self.registration = new_reg
            if new_reg not in self.failures_dict:
                self.failures_dict[new_reg] = set()
            self.log(f"Registration changed to: {self.registration}")

    def clear_failures(self):
        self.failures_dict[self.registration] = set()
        self.log(f"Cleared all failures for registration '{self.registration}'.")
        self.save_failures()

    def save_settings(self):
        self.log("Settings saved.")
        # Save settings if needed

    def load_failures(self):
        if os.path.exists(FAILURES_FILE):
            try:
                with open(FAILURES_FILE, 'r') as f:
                    data = json.load(f)
                return {reg: set(fails) for reg, fails in data.items()}
            except Exception as e:
                self.log(f"Error loading failures: {e}")
                return {}
        return {}

    def save_failures(self):
        try:
            with open(FAILURES_FILE, 'w') as f:
                json.dump({reg: list(fails) for reg, fails in self.failures_dict.items()}, f)
        except Exception as e:
            self.log(f"Error saving failures: {e}")

    def on_close(self):
        self.save_failures()
        self.running = False
        self.master.destroy()

# Main
def prompt_registration():
    root = tk.Tk()
    root.withdraw()
    reg = simpledialog.askstring("Registration Input", "Please enter your registration code:")
    root.destroy()
    return reg or "2-CUTE"

if __name__ == "__main__":
    reg_code = prompt_registration()
    root = tk.Tk()
    app = FailureInjectorApp(root, reg_code)
    root.mainloop()

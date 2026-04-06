import socket
import random
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog
import logging

# Configuration defaults
XPLANE_IP = '127.0.0.1'
XPLANE_PORT = 49000
FAILURE_PROBABILITY = 0.001
CHECK_INTERVAL = 300

FAILURE_TYPES = ['HYDRAULIC', 'ELECTRICAL', 'AVIONICS', 'FUEL']

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class FailureInjectorApp:
    def __init__(self, master, registration):
        self.master = master
        self.master.title("Failure Injector")
        self.running = False
        self.thread = None
        self.registration = registration

        # Dictionary to store failures per registration
        self.failures_dict = {self.registration: set()}

        # GUI Elements
        self.start_button = tk.Button(master, text="Start", command=self.toggle_injection)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.auto_var = tk.BooleanVar(value=True)
        self.auto_check = tk.Checkbutton(master, text="Auto Fail", variable=self.auto_var)
        self.auto_check.grid(row=0, column=1, padx=5, pady=5)

        # Probability input
        tk.Label(master, text="Failure Probability (0-1):").grid(row=1, column=0, padx=5, pady=5)
        self.prob_entry = tk.Entry(master)
        self.prob_entry.insert(0, str(FAILURE_PROBABILITY))
        self.prob_entry.grid(row=1, column=1, padx=5, pady=5)

        # Interval input
        tk.Label(master, text="Check Interval (sec):").grid(row=2, column=0, padx=5, pady=5)
        self.interval_entry = tk.Entry(master)
        self.interval_entry.insert(0, str(CHECK_INTERVAL))
        self.interval_entry.grid(row=2, column=1, padx=5, pady=5)

        # Registration display and change button
        self.reg_label = tk.Label(master, text=f"Registration: {self.registration}")
        self.reg_label.grid(row=3, column=0, padx=5, pady=5)
        self.change_reg_button = tk.Button(master, text="Change Registration", command=self.change_registration)
        self.change_reg_button.grid(row=3, column=1, padx=5, pady=5)

        # Manual failure buttons
        manual_frame = tk.Frame(master)
        manual_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
        for i, ft in enumerate(FAILURE_TYPES):
            btn = tk.Button(manual_frame, text=f"Manual {ft}", command=lambda ft=ft: self.manual_failure(ft))
            btn.grid(row=0, column=i, padx=2, pady=2)

        # Clear failures button
        self.clear_button = tk.Button(master, text="Clear Failures", command=self.clear_failures)
        self.clear_button.grid(row=5, column=0, columnspan=2, padx=5, pady=5)

        # Log display
        self.log_area = scrolledtext.ScrolledText(master, width=60, height=15, state='disabled')
        self.log_area.grid(row=6, column=0, columnspan=2, padx=5, pady=5)

        # Close event
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        logging.info(message)

    def toggle_injection(self):
        if not self.running:
            try:
                # Read user inputs
                prob = float(self.prob_entry.get())
                interval = float(self.interval_entry.get())
                if not (0 <= prob <= 1):
                    raise ValueError("Probability must be between 0 and 1")
                global FAILURE_PROBABILITY, CHECK_INTERVAL
                FAILURE_PROBABILITY = prob
                CHECK_INTERVAL = interval
            except ValueError as e:
                self.log(f"Invalid input: {e}")
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
            if self.auto_var.get():
                if random.random() < FAILURE_PROBABILITY:
                    failure = random.choice(FAILURE_TYPES)
                    self.send_failure(failure, sock)
            time.sleep(CHECK_INTERVAL)
        sock.close()

    def send_failure(self, failure_type, sock=None):
        """Send failure command and log with registration."""
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_created = True
        else:
            sock_created = False
        message = f"FAIL:{failure_type}"
        try:
            sock.sendto(message.encode(), (XPLANE_IP, XPLANE_PORT))
            self.log(f"{self.registration}: Sent failure command: {message}")
        except Exception as e:
            self.log(f"Error sending failure: {e}")
        if sock_created:
            sock.close()

    def manual_failure(self, failure_type):
        """Trigger manual failure and remember it."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_failure(failure_type, sock)
        # Remember this failure for the current registration
        reg = self.registration
        if reg not in self.failures_dict:
            self.failures_dict[reg] = set()
        self.failures_dict[reg].add(failure_type)
        self.log(f"Recorded failure '{failure_type}' for registration '{reg}'.")

    def change_registration(self):
        """Prompt user to change registration."""
        new_reg = simpledialog.askstring("Change Registration", "Enter new registration code:", initialvalue=self.registration)
        if new_reg:
            self.registration = new_reg
            if new_reg not in self.failures_dict:
                self.failures_dict[new_reg] = set()
            self.reg_label.config(text=f"Registration: {self.registration}")
            self.log(f"Registration changed to: {self.registration}")

    def clear_failures(self):
        """Clear stored failures for current registration."""
        reg = self.registration
        self.failures_dict[reg] = set()
        self.log(f"Cleared all failures for registration '{reg}'.")

    def on_close(self):
        self.running = False
        self.master.destroy()

def prompt_registration():
    root = tk.Tk()
    root.withdraw()  # Hide root window
    reg = simpledialog.askstring("Registration Input", "Please enter your registration code:")
    root.destroy()
    if reg:
        return reg
    else:
        return "2-CUTE"  # Default if user cancels or enters nothing

if __name__ == "__main__":
    registration_code = prompt_registration()
    main_root = tk.Tk()
    # Removed iconbitmap line
    app = FailureInjectorApp(main_root, registration_code)
    main_root.mainloop()

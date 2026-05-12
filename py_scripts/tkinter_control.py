import tkinter as tk
from tkinter import messagebox
import serial
import time

ESP_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200

class DofbotController:
    def __init__(self, master):
        self.master = master
        self.master.title("Dofbot Master Controller")
        self.master.geometry("500x550")
        self.master.resizable(False, False)

        # --- Serial Setup ---
        self.esp32 = None
        self.connect_serial()

        # --- UI Header ---
        tk.Label(master, text="Dofbot Kinematic Control", font=("Arial", 16, "bold")).pack(pady=10)

        # --- Sliders (Scales) ---
        self.sliders = []
        # Format: (Label, Min Angle, Max Angle, Default Angle)
        slider_info = [
            ("Joint 1 (Base)", 0, 180, 90),
            ("Joint 2 (Shoulder)", 0, 180, 90),
            ("Joint 3 (Elbow)", 0, 180, 90),
            ("Joint 4 (Wrist Pitch)", 0, 180, 90),
            ("Joint 5 (Wrist Roll) - motor is not there", 0, 270, 90), # S5 is the 270-degree servo
            ("Joint 6 (Gripper) - motor is not there", 0, 180, 90)
        ]

        for label_text, min_val, max_val, default_val in slider_info:
            frame = tk.Frame(master)
            frame.pack(fill=tk.X, padx=20, pady=5)

            label = tk.Label(frame, text=label_text, width=18, anchor='w')
            label.pack(side=tk.LEFT)

            slider = tk.Scale(frame, from_=min_val, to=max_val, orient=tk.HORIZONTAL)
            slider.set(default_val)
            slider.pack(side=tk.LEFT, expand=True, fill=tk.X)
            self.sliders.append(slider)

        # --- Movement Time Slider ---
        time_frame = tk.Frame(master)
        time_frame.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(time_frame, text="Move Time (ms)", width=18, anchor='w', fg="blue").pack(side=tk.LEFT)
        self.time_slider = tk.Scale(time_frame, from_=500, to=4000, resolution=100, orient=tk.HORIZONTAL)
        self.time_slider.set(1500) # Default to 1.5 seconds
        self.time_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # --- Control Buttons ---
        btn_frame = tk.Frame(master)
        btn_frame.pack(pady=10)

        self.send_btn = tk.Button(btn_frame, text="SEND TO ARM", command=self.send_movement, 
                                  bg="darkgreen", fg="white", font=("Arial", 12, "bold"), width=15)
        self.send_btn.pack(side=tk.LEFT, padx=10)

        self.buzzer_btn = tk.Button(btn_frame, text="Test Buzzer", command=self.test_buzzer, width=12)
        self.buzzer_btn.pack(side=tk.LEFT, padx=10)

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_var.set("Ready." if self.esp32 else "ESP32 Not Connected!")
        self.status_label = tk.Label(master, textvariable=self.status_var, fg="red" if not self.esp32 else "green")
        self.status_label.pack(side=tk.BOTTOM, pady=10)

    def connect_serial(self):
        try:
            print(f"Connecting to {ESP_PORT}...")
            self.esp32 = serial.Serial(ESP_PORT, BAUD_RATE, timeout=1)
            time.sleep(2) # Wait for hardware reboot
            self.esp32.reset_input_buffer() # Flush the bootloader garbage
            print("Connected and buffered cleared!")
        except serial.SerialException as e:
            messagebox.showerror("Hardware Error", f"Cannot connect to ESP32 on {ESP_PORT}.\n\nIs it plugged in? Are permissions set?")

    def send_movement(self):
        if not self.esp32:
            self.status_var.set("Error: Cannot send, ESP32 offline.")
            return

        # Gather all 6 slider values and the time value
        s_vals = [int(slider.get()) for slider in self.sliders]
        move_time = int(self.time_slider.get())
        s_vals[4] = 0
        s_vals[5] = 0
        # Format the command exactly as the ESP32 expects it
        command_str = f"MOVE {s_vals[0]} {s_vals[1]} {s_vals[2]} {s_vals[3]} {s_vals[4]} {s_vals[5]} {move_time}"
        
        try:
            self.esp32.reset_input_buffer() # Clear old ACKs
            self.esp32.write(f"{command_str}\n".encode('utf-8'))
            response = self.esp32.readline().decode('utf-8', errors='replace').strip()
            self.status_var.set(f"Last status: {response}")
            print(f"PC Sent: {command_str} | ESP32 Reply: {response}")
            
        except Exception as e:
            self.status_var.set(f"Serial Write Error: {e}")

    def test_buzzer(self):
        if not self.esp32: return
        try:
            self.esp32.write(b"BUZZER_ON\n")
            # Tell tkinter to turn it off after 300ms without freezing the UI
            self.master.after(300, lambda: self.esp32.write(b"BUZZER_OFF\n"))
        except Exception as e:
            print(f"Buzzer error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DofbotController(root)
    root.mainloop()
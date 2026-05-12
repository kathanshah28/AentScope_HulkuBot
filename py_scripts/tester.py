import serial
import time

ESP_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200

def send_command(esp32, cmd_str):
    """Sends a string command to the ESP32 and waits for the ACK"""
    esp32.write(f"{cmd_str}\n".encode('utf-8'))
    
    # Adding errors='replace' prevents crashes if a random garbage byte sneaks in
    response = esp32.readline().decode('utf-8', errors='replace').strip()
    print(f"ESP32 says: {response}")

def main():
    try:
        print(f"Connecting to {ESP_PORT}...")
        esp32 = serial.Serial(ESP_PORT, BAUD_RATE, timeout=1)
        
        # Wait for the ESP32 to finish its hardware reboot
        time.sleep(2) 
        
        # CRITICAL FIX: Throw away all the garbled bootloader messages sitting in the buffer
        esp32.reset_input_buffer() 
        
        print("Connected and buffer cleared! Sending initial position command...")

        # FORMAT: MOVE <s1> <s2> <s3> <s4> <s5> <s6> <time_ms>
        # Moving all servos to 90 degrees
        send_command(esp32, "MOVE 90 90 90 90 90 90 2000")
        
        # Wait for the physical movement to finish
        time.sleep(2.5) 

        print("Sending secondary position command...")
        send_command(esp32, "MOVE 90 45 45 90 90 90 1500")

        esp32.close()
        print("Test Complete.")

    except serial.SerialException as e:
        print(f"\nSerial Error: {e}")

if __name__ == "__main__":
    main()
# Goal

Create a native C++ `ros2_control` Hardware Interface plugin for the `hulku_bot`, utilizing a high-speed binary (hex) protocol instead of strings, and enabling true closed-loop feedback by reading the servo encoders.

## User Review Required

> [!IMPORTANT]
> Since we are switching to a binary protocol and adding the ability to read from the arm, the Arduino code must be updated. I have provided the proposed Arduino code in the section below. **Please review it to ensure you are comfortable flashing this to your board.**

## Proposed Changes

---

### The Binary Protocol (ESP32 <-> PC)

To make communication blazing fast and avoid slow `String` parsing, we will use a raw byte protocol.

**Write Command (PC to ESP32):**
- Byte 0-1: Header `0x55, 0xAA`
- Byte 2: Command `0x01` (Move Arm)
- Byte 3-4: Time in ms (High, Low)
- Byte 5-16: 6 Servos * 2 bytes each (Pulse width 900-3100)
*Total: 17 bytes*

**Read Command (PC to ESP32):**
- Byte 0-1: Header `0x55, 0xAA`
- Byte 2: Command `0x02` (Request Angles)

**Read Response (ESP32 to PC):**
- Byte 0-1: Header `0x55, 0xAA`
- Byte 2-13: 6 Servos * 2 bytes each (Pulse width 900-3100)

---

### 1. Updated Arduino Code
Here is the updated Arduino code you will flash to your ESP32. It replaces the `String` logic with raw `Serial.readBytes()`, does the I2C writing, and includes a stub for reading the I2C registers (assuming standard DOF board read registers).

```cpp
#include <Wire.h>

#define DOF_BOARD_ADDR 0x15 
#define BUZZER_REG 0x06     
#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  // Use a very high baud rate for minimum latency in MoveIt
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN); 
}

void loop() {
  if (Serial.available() >= 3) {
    // Check for header 0x55 0xAA
    if (Serial.read() == 0x55) {
      if (Serial.read() == 0xAA) {
        uint8_t cmd = Serial.read();

        // COMMAND 1: MOVE
        if (cmd == 0x01) {
          uint8_t buf[14];
          Serial.readBytes(buf, 14); // Read time(2) + 6*pos(12)
          
          int time_ms = (buf[0] << 8) | buf[1];
          
          // Send Time Array
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(0x1E);
          Wire.write(buf[0]); // Time High
          Wire.write(buf[1]); // Time Low
          Wire.endTransmission();

          // Send Position Array (Pulse widths passed directly from C++)
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(0x1D);
          for(int i=2; i<14; i++) {
            Wire.write(buf[i]);
          }
          Wire.endTransmission();
        }

        // COMMAND 2: READ
        else if (cmd == 0x02) {
          // Assuming the DOF board allows reading 12 bytes of current pulse widths from register 0x15
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(0x15); // Adjust this to the actual read register of your board
          Wire.endTransmission();
          
          Wire.requestFrom(DOF_BOARD_ADDR, 12);
          
          uint8_t resp[14];
          resp[0] = 0x55;
          resp[1] = 0xAA;
          
          int idx = 2;
          while(Wire.available() && idx < 14) {
             resp[idx++] = Wire.read();
          }
          
          // Send back to PC
          Serial.write(resp, 14);
        }
      }
    }
  }
}
```

---

### 2. `hulku_hardware` C++ Plugin

#### [NEW] `src/hulku_hardware_interface.cpp`
The core plugin overriding `hardware_interface::SystemInterface`.
- **`on_activate()`**: Opens `/dev/ttyUSB0` with termios (raw binary mode, `B115200`).
- **`read()`**: 
  1. Sends `[0x55, 0xAA, 0x02]` over serial.
  2. Waits for and reads the 14-byte response.
  3. Re-maps the pulse widths (900-3100) back to Radians (-π/2 to π/2).
  4. Stores them in the `state_interfaces` array so MoveIt knows exactly where the arm is.
- **`write()`**: 
  1. Reads the `command_interfaces` array (Radians).
  2. Re-maps Radians to pulse widths (900-3100) in C++, applying your physical inversion rules.
  3. Sends `[0x55, 0xAA, 0x01, ...]` to the ESP32.

#### [NEW] `include/hulku_hardware/hulku_hardware_interface.hpp`
Defines the C++ class, serial file descriptor, and mapping functions.

#### [NEW] `hulku_hardware_plugin.xml` & `CMakeLists.txt`
Exports the plugin and links `rclcpp` and `hardware_interface`.

---

### 3. `arm_moveit_config`

#### [MODIFY] `config/robot.ros2_control.xacro`
Replaces the `FakeSystem` with:
```xml
<plugin>hulku_hardware/HulkuHardwareInterface</plugin>
<param name="port">/dev/ttyUSB0</param>
```

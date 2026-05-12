#include <Wire.h>

#define ADDR 0x15
#define SDA_PIN 21
#define SCL_PIN 22

unsigned long last_telemetry_time = 0;
const int TELEMETRY_INTERVAL = 20; // 20ms = 50Hz

void setup() {
  Serial.begin(115200);
  while (!Serial); 
  delay(500);

  Wire.begin(SDA_PIN, SCL_PIN, 100000); 
  
  Serial.println("\n========================================");
  Serial.println("  DOFBOT ESP32 BRIDGE - ROS2 READY");
  Serial.println("========================================\n");

  // ==========================================
  // INITIALIZATION SEQUENCE
  // ==========================================
  Serial.println("[1/4] Starting Diagnostics...");
  
  // 1. Dual beep (starts)
  dualBeep();

  // 2. RGB check (Red -> Green -> Blue)
  Serial.println("[2/4] Testing RGB...");
  setRGB(255, 0, 0); delay(200);
  setRGB(0, 255, 0); delay(200);
  setRGB(0, 0, 255); delay(200);
  setRGB(0, 0, 0);   delay(200);

  // 3. Dual beep (RGB okay)
  dualBeep();

  // 4. Set torque 1 and move to 90 degrees while blinking
  Serial.println("[3/4] Locking Torque & Moving to Home (90 deg)...");
  setTorque(1);
  moveArm(90, 90, 90, 90, 90, 90, 1000); // 1-second move
  
  // Blink Yellow while moving (5 loops of 200ms = 1000ms)
  for (int i = 0; i < 5; i++) {
    setRGB(255, 255, 0); // Yellow
    delay(100);
    setRGB(0, 0, 0);
    delay(100);
  }
  delay(200); // Small buffer to let physical servos settle

  // 5. Check encoder values (Error should be < 2 degrees)
  Serial.println("[4/4] Verifying Encoder Accuracy...");
  bool pass = true;
  for (int i = 1; i <= 6; i++) {
    int pos = readJointPos(i);
    int error = abs(pos - 90);
    Serial.print("  -> Joint "); Serial.print(i); 
    Serial.print(" Position: "); Serial.print(pos);
    Serial.print(" (Error: "); Serial.print(error); Serial.println(")");
    
    if (error > 2) {
      pass = false;
    }
  }

  if (pass) {
    Serial.println(">>> DIAGNOSTIC PASSED <<<");
    setRGB(0, 255, 0); // Solid Green for success
  } else {
    Serial.println("!!! WARNING: ENCODER ERROR DETECTED !!!");
    setRGB(255, 0, 0); // Solid Red for warning
  }
  
  Serial.println("\n--- ENTERING 50Hz TELEMETRY MODE ---");
}

// ---------------------------------------------------------
// HARDWARE HELPER FUNCTIONS
// ---------------------------------------------------------

void controlBuzzer(uint8_t state) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x06);
  Wire.write(state);
  Wire.endTransmission();
}

void dualBeep() {
  controlBuzzer(0xFF); delay(100); controlBuzzer(0x00); delay(100);
  controlBuzzer(0xFF); delay(100); controlBuzzer(0x00);
}

void setTorque(uint8_t state) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x1A);
  Wire.write(state); 
  Wire.endTransmission();
}

void setRGB(uint8_t r, uint8_t g, uint8_t b) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x02);
  Wire.write(r); Wire.write(g); Wire.write(b);
  Wire.endTransmission();
}

void moveArm(int s1, int s2, int s3, int s4, int s5, int s6, int t) {
  int pos[6];
  pos[0] = map(s1, 0, 180, 900, 3100);
  pos[1] = map(180 - s2, 0, 180, 900, 3100);
  pos[2] = map(180 - s3, 0, 180, 900, 3100);
  pos[3] = map(180 - s4, 0, 180, 900, 3100);
  pos[4] = map(s5, 0, 270, 380, 3700); 
  pos[5] = map(s6, 0, 180, 900, 3100);

  Wire.beginTransmission(ADDR);
  Wire.write(0x1E);
  Wire.write((t >> 8) & 0xFF); 
  Wire.write(t & 0xFF);
  Wire.endTransmission();

  Wire.beginTransmission(ADDR);
  Wire.write(0x1D);
  for(int i=0; i<6; i++) {
    Wire.write((pos[i] >> 8) & 0xFF); 
    Wire.write(pos[i] & 0xFF);
  }
  Wire.endTransmission();
}

int readJointPos(uint8_t id) {
  if (id < 1 || id > 6) return -1;

  Wire.beginTransmission(ADDR);
  Wire.write(0x30 + id);
  Wire.write(0x00); 
  Wire.endTransmission();

  delay(3); // Crucial 3ms delay

  Wire.requestFrom((int)ADDR, (int)2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read(); 
    uint8_t lsb = Wire.read();
    uint16_t pos = (msb << 8) | lsb; 

    if (pos == 0) return -1; 

    int angle = 0;
    if (id == 5) {
      angle = (int)((270.0 - 0) * (pos - 380.0) / (3700.0 - 380.0));
      if (angle > 270 || angle < 0) return -1;
    } else {
      angle = (int)((180.0 - 0) * (pos - 900.0) / (3100.0 - 900.0));
      if (angle > 180 || angle < 0) return -1;
      if (id == 2 || id == 3 || id == 4) {
        angle = 180 - angle;
      }
    }
    return angle;
  }
  return -1; 
}

// ---------------------------------------------------------
// 50Hz MAIN LOOP & SERIAL PARSER
// ---------------------------------------------------------

void loop() {
  unsigned long current_time = millis();

  // 1. 50Hz Encoder Transmission Loop
  if (current_time - last_telemetry_time >= TELEMETRY_INTERVAL) {
    last_telemetry_time = current_time;
    
    // Read all 6 joints
    int j1 = readJointPos(1);
    int j2 = readJointPos(2);
    int j3 = readJointPos(3);
    int j4 = readJointPos(4);
    int j5 = readJointPos(5);
    int j6 = readJointPos(6);

    // Print in a compact, easily parsed string format: ENC j1 j2 j3 j4 j5 j6
    Serial.print("ENC ");
    Serial.print(j1); Serial.print(" ");
    Serial.print(j2); Serial.print(" ");
    Serial.print(j3); Serial.print(" ");
    Serial.print(j4); Serial.print(" ");
    Serial.print(j5); Serial.print(" ");
    Serial.println(j6);
  }

  // 2. Incoming Command Parser (Non-blocking)
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("BUZZ ")) {
      int state = cmd.substring(5).toInt();
      controlBuzzer(state == 1 ? 0xFF : 0x00);
    }
    else if (cmd.startsWith("TORQUE ")) {
      int state = cmd.substring(7).toInt();
      setTorque(state);
    }
    else if (cmd.startsWith("RGB ")) {
      int r, g, b;
      if (sscanf(cmd.c_str(), "RGB %d %d %d", &r, &g, &b) == 3) {
        setRGB(r, g, b);
      }
    }
    else if (cmd.startsWith("MOVE ")) {
      int s1, s2, s3, s4, s5, s6, t;
      if (sscanf(cmd.c_str(), "MOVE %d %d %d %d %d %d %d", &s1, &s2, &s3, &s4, &s5, &s6, &t) == 7) {
        moveArm(s1, s2, s3, s4, s5, s6, t);
      }
    }
  }
}
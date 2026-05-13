// includes class definitions for our hulku hardware interface include->.hpp
#include "hulku_hardware/hulku_hardware_interface.hpp"

#include <chrono>    //for handling time duration
#include <cmath>     //Math functions
#include <fcntl.h>   //File control: - for serial port read/write permission
#include <iostream>  //standard input/output
#include <limits>    //To get the limits of data types
#include <memory>    //For smart pointers management
#include <termios.h> //POSIX terminal interface asynchronous port management
#include <unistd.h> //POSIX standard os APIs provides read etc., for serialport, write etc.,
#include <vector> //array container

// ROS 2 libraries for harware interface and program
#include "hardware_interface/types/hardware_interface_type_values.hpp" //Provides standard string constants like HW_IF_POSITION ("position")
#include "rclcpp/rclcpp.hpp" //Provides here rclcpp logger class and others

// The actual sequence of method calls see link: -
// https://design.ros2.org/img/node_lifecycle/life_cycle_sm.png

// on_init() (It is for static setup like initializing parameters) ->
// on_configure() (It is for readying the data and also resetting variables) ->

// Defining all in hulku_hardware interface
namespace hulku_hardware {

// This on_init() method is called first on each first load
// CallbackReturn is a type alias which provides return type like SUCCESS,
// FAILURE, ERROR.
// hardware_interface::HardwareInfo provides info about urdf<ros2_control> you
// are using and populate on info_  (HardwareInfo is a structure name, type,
// hardware_parameters, joints, sensors and gpios)

hardware_interface::CallbackReturn
HulkuHardwareInterface::on_init(const hardware_interface::HardwareInfo &info) {
  // Checks if info exits and give status success then procceed otherwise throw
  // error
  if (hardware_interface::SystemInterface::on_init(info) !=
      hardware_interface::CallbackReturn::SUCCESS) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // Allocate memory for states and commands size is set according joints found
  // in info_.joints.size() and we fill them with NaN
  hw_states_.resize(info_.joints.size(),
                    std::numeric_limits<double>::quiet_NaN());
  hw_commands_.resize(info_.joints.size(),
                      std::numeric_limits<double>::quiet_NaN());

  // Get parameters port from urdf and if not set default
  port_ = info_.hardware_parameters["port"];
  if (port_.empty()) {
    port_ = "/dev/ttyUSB0";
  }

  // Get baud_rate from urdf and if not set default
  std::string baud_rate_str = info_.hardware_parameters["baud_rate"];
  if (baud_rate_str.empty()) {
    baud_rate_ = 115200;
  } else {
    baud_rate_ = std::stoi(baud_rate_str); // std::stoi converts string to int
  }

  // Validating joints configuration
  // ComponentInfo is a structure that stores the configuration data for each
  // joint (name, command_interfaces, state_interfaces, etc.)
  for (const hardware_interface::ComponentInfo &joint : info_.joints) {
    // Check 1 - if the joint contains defined number of command interfaces
    // (here 1) (RCLCPP_FATAL prints big red error)
    if (joint.command_interfaces.size() != 1) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' has %zu command interfaces found. 1 expected.",
                   joint.name.c_str(), joint.command_interfaces.size());
      return hardware_interface::CallbackReturn::ERROR;
    }

    // Check 2 - Check command interface type
    // (here checks for position) HW_IF_POSITION is just a string constant
    // "position"
    if (joint.command_interfaces[0].name !=
        hardware_interface::HW_IF_POSITION) {
      RCLCPP_FATAL(
          rclcpp::get_logger("HulkuHardwareInterface"),
          "Joint '%s' have %s command interfaces found. '%s' expected.",
          joint.name.c_str(), joint.command_interfaces[0].name.c_str(),
          hardware_interface::HW_IF_POSITION);
      return hardware_interface::CallbackReturn::ERROR;
    }

    // Check 3 - Check state interface size (here 1)
    if (joint.state_interfaces.size() != 1) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' has %zu state interface. 1 expected.",
                   joint.name.c_str(), joint.state_interfaces.size());
      return hardware_interface::CallbackReturn::ERROR;
    }

    // Check 4 - Check state interface type (here position)
    if (joint.state_interfaces[0].name != hardware_interface::HW_IF_POSITION) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' have %s state interface. '%s' expected.",
                   joint.name.c_str(), joint.state_interfaces[0].name.c_str(),
                   hardware_interface::HW_IF_POSITION);
      return hardware_interface::CallbackReturn::ERROR;
    }
  }

  // Initialize GPIO command arrays to zero
  for (size_t i = 0; i < GPIO_COUNT; i++) {
    gpio_commands_[i] = 0.0;
    gpio_states_[i] = 0.0;
    gpio_prev_[i] = 0.0;
  }

  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "GPIO controller initialized: buzzer, torque, rgb_r, rgb_g, rgb_b");

  // if all checks go well return success
  return hardware_interface::CallbackReturn::SUCCESS;
}

// This method setup-ups internal data strctures (variables, constant etc.,) and
// prepare the system for communication
// here commenting out of previous_state varibale is for preventing compiler
// warnings for unused variable
// it is used to get the previous state of the system but here we are not using
// Here states might be Unconfigured, Active, Inactive etc.,
hardware_interface::CallbackReturn HulkuHardwareInterface::on_configure(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Configuring ...please wait...");
  // here setting up all the joints values with 0.0 to prevent math errors
  for (uint i = 0; i < hw_states_.size(); i++) {
    hw_states_[i] = 0.0;
    hw_commands_[i] = 0.0;
  }

  // here print success message
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully configured!");

  // return success if everything goes well
  return hardware_interface::CallbackReturn::SUCCESS;
}

// It undo's whatever does so far including done in on_configure meaning put in
// uncofgured state currently we are doing nothing return only success and
// logging
hardware_interface::CallbackReturn HulkuHardwareInterface::on_cleanup(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"), "Cleaning up ...");
  return hardware_interface::CallbackReturn::SUCCESS;
}

// It is used to actually making robot live and do the needful connections
// For commented previous_state -> check on_configure comments
hardware_interface::CallbackReturn HulkuHardwareInterface::on_activate(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Activating ...please wait...");

  // It opens up serial connection and set configs using the handler function
  // in case fail to open serial port it log error and retun error message
  if (setup_serial(port_, baud_rate_) < 0) {
    RCLCPP_ERROR(rclcpp::get_logger("HulkuHardwareInterface"),
                 "Failed to open serial port %s", port_.c_str());
    return hardware_interface::CallbackReturn::ERROR;
  }

  // print success message
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully activated! GPIO managed by ros2_control.");

  // return success if everything goes well
  return hardware_interface::CallbackReturn::SUCCESS;
}

// It deactivates the robot closes the serial connection and other action needed
// to done for closing the robot connection and system
hardware_interface::CallbackReturn HulkuHardwareInterface::on_deactivate(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Deactivating ...please wait...");

  // closes the serial connection
  close_serial();

  // prints success message
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully deactivated!");

  // return success if everything goes well
  return hardware_interface::CallbackReturn::SUCCESS;
}

// This function is used to tell ros2_controllers where to look for joint values
// in the memory of the system (states interfaces are read only link)
// It exports state_interface
//  returns a list of interface objects
std::vector<hardware_interface::StateInterface>
HulkuHardwareInterface::export_state_interfaces() {
  std::vector<hardware_interface::StateInterface> state_interfaces;

  // Joint state interfaces
  for (uint i = 0; i < info_.joints.size(); i++) {
    state_interfaces.emplace_back(hardware_interface::StateInterface(
        info_.joints[i].name, hardware_interface::HW_IF_POSITION,
        &hw_states_[i]));
  }

  return state_interfaces;
}

// It export command interfaces to the ros2_controlers
// it is used to send commands to the robot joints
// return list of commandInterface
std::vector<hardware_interface::CommandInterface>
HulkuHardwareInterface::export_command_interfaces() {
  std::vector<hardware_interface::CommandInterface> command_interfaces;

  // Joint command interfaces
  for (uint i = 0; i < info_.joints.size(); i++) {
    command_interfaces.emplace_back(hardware_interface::CommandInterface(
        info_.joints[i].name, hardware_interface::HW_IF_POSITION,
        &hw_commands_[i]));
  }

  // GPIO command interfaces
  for (const auto & gpio : info_.gpios) {
    size_t gpio_idx = 0;
    if (gpio.name == "buzzer_trigger") gpio_idx = 0;
    else if (gpio.name == "torque_enable") gpio_idx = 1;
    else if (gpio.name == "led_r") gpio_idx = 2;
    else if (gpio.name == "led_g") gpio_idx = 3;
    else if (gpio.name == "led_b") gpio_idx = 4;
    else continue;

    for (size_t i = 0; i < gpio.command_interfaces.size(); i++) {
      if (gpio.command_interfaces[i].name == "command") {
        command_interfaces.emplace_back(hardware_interface::CommandInterface(
            gpio.name, "command", &gpio_commands_[gpio_idx]));
        RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                    "Exported GPIO command: %s/command (index %zu)",
                    gpio.name.c_str(), gpio_idx);
      }
    }
  }

  return command_interfaces;
}

// Convert Pulse Width back to Radians
// is_270  does motor rotates 270 degree or standard 180 degree
double pulse_to_rad(uint16_t pulse, bool invert, bool is_270) {
  // safety check to handle 0 pulse width
  if (pulse == 0)
    return 0.0; // Prevent wild angle jumps if a servo is unplugged (returns 0)

  // formula to convert pulse width to degrees based in the servo type selected
  double deg;
  if (is_270) {
    // standard mapping formula (Value - Min) / (Max - Min) * Range
    deg = (pulse - 380.0) / (3700.0 - 380.0) * 270.0;
  } else {
    deg = (pulse - 900.0) / (3100.0 - 900.0) * 180.0;
  }

  // invert the angle if needed
  if (invert) {
    deg = 180.0 - deg;
  }

  // (deg - 90) It makes range -90 to 90 degree with 0 as the middle
  // (deg * M_PI / 180) converting the range from degrees to radians
  return (deg - 90.0) * (M_PI / 180.0);
}

// This is the eye of the robotic system
// This function calls the hardware to read the states of the joints and provide
// the reading to the computer memory where the controllers can access it
// Here we are running read loop at 100Hz but actually just asking the hardware
// state updates at 20Hz 5 times a second because of bus overload and traffic of
// commands being sent out
// motor takes 4ms time the conversion takes 1ms (laptop-nodemcu) + 1ms (nodemcu
// process) + 1ms (nodemcu-STM32 I2C) + 4ms (motor refresh rate)
hardware_interface::return_type
HulkuHardwareInterface::read(const rclcpp::Time & /*time*/,
                             const rclcpp::Duration & /*period*/) {

  // This is a safety check:  if serial port not open or hw_states is empty(no
  // states defined) then this check simply exits this loop safely without
  // breaking flow
  if (serial_fd_ < 0 || hw_states_.empty())
    return hardware_interface::return_type::OK;

  std::lock_guard<std::mutex> lock(serial_mutex_);

  // This variable is used to count the number of loops
  static int loop_counter = 0;
  loop_counter++;

  // 1. Request data only at 20Hz (every 5 loops) to prevent overwhelming the
  // Arduino's I2C bus The Arduino takes ~18ms to read 6 servos, so 100Hz
  // polling crashes it!
  if (loop_counter % 5 == 0) {
    // This commands 0x55 0xAA 0x02 is a handshake code for asking position
    uint8_t req[3] = {0x55, 0xAA, 0x02};
    // :: directly tells compiler that check for write function in the global
    // space and it is actually defined in the <unistd.h> library
    // so this write function is used to send the data over the
    // port(filedescriptor)
    ::write(serial_fd_, req, 3);
  }

  // 2. Read all available bytes from serial into a persistent buffer
  // Serial data arrives in "bits and pieces"
  // Data arrives in chunks so it is a buffer which stores data as it arrives
  // and wait for gets a full message
  uint8_t buf[256];
  int n = ::read(serial_fd_, buf, sizeof(buf));

  // rx_buffer to store this incoming pieces of data a whole
  static std::vector<uint8_t> rx_buffer;
  if (n > 0) {
    // This is a permanent storage area for a whole message
    rx_buffer.insert(rx_buffer.end(), buf, buf + n);
  }

  // Safety clear if buffer gets too large due to garbage
  if (rx_buffer.size() > 1000)
    rx_buffer.clear();

  static int read_fails = 0;
  bool parsed = false;

  // 3. Search the buffer for a complete 15-byte packet and erase after the
  // cmpleter read to eliminate false reads
  while (rx_buffer.size() >= 15) {
    // Checks for first 3 byte to be the 0x55 0xAA 0x02 code to confirm it is a
    // valid packet
    if (rx_buffer[0] == 0x55 && rx_buffer[1] == 0xAA && rx_buffer[2] == 0x02) {
      uint16_t pulses[6];
      for (int i = 0; i < 6; i++) {
        // reconstruct the 16 bit motor position integer from 8 bit sets because
        // normally serial bus sents 8 bit (1 byte) at a time
        // (rx_buffer[3 + i * 2] << 8) => 3 + i * 2 This is for getting msb byte
        // standing at all odd positions from 3
        // left shift by 8 to make it 16 bit 0x05 from 0x0005
        // (rx_buffer[4 + i * 2]) => 4 + i * 2 This is for getting lsb byte
        // standing at all even positions from 4
        pulses[i] = (rx_buffer[3 + i * 2] << 8) | rx_buffer[4 + i * 2];
      }

      // If the pulses are NOT zero, the I2C read was successful
      // updating reads in the hw_states_ variable
      if (pulses[0] != 0 || pulses[1] != 0 || pulses[2] != 0) {
        read_fails = 0;
        if (hw_states_.size() > 0)
          hw_states_[0] = pulse_to_rad(pulses[0], false, false);
        if (hw_states_.size() > 1)
          hw_states_[1] = pulse_to_rad(pulses[1], true, false);
        if (hw_states_.size() > 2)
          hw_states_[2] = pulse_to_rad(pulses[2], true, false);
        if (hw_states_.size() > 3)
          hw_states_[3] = pulse_to_rad(pulses[3], true, false);
        if (hw_states_.size() > 4)
          hw_states_[4] = pulse_to_rad(pulses[4], false, true); // 270 deg
        if (hw_states_.size() > 5)
          hw_states_[5] = pulse_to_rad(pulses[5], false, false);
        parsed = true;
      }

      // Remove the parsed 15 bytes
      rx_buffer.erase(rx_buffer.begin(), rx_buffer.begin() + 15);
    } else {
      // Not a valid header, pop 1 byte and search again
      rx_buffer.erase(rx_buffer.begin());
    }
  }

  if (!parsed) {
    read_fails++;
    // If we haven't received valid hardware state for 200ms (20 loops),
    // fallback to open-loop to prevent MoveIt from aborting.
    if (read_fails > 20) {
      for (uint i = 0; i < hw_states_.size(); i++) {
        if (!std::isnan(hw_commands_[i])) {
          hw_states_[i] = hw_commands_[i];
        }
      }
    }
  }

  // Initialize NaN states to 0.0 on the very first loop
  for (uint i = 0; i < hw_states_.size(); i++) {
    if (std::isnan(hw_states_[i]))
      hw_states_[i] = 0.0;
  }

  // return ok to indicate successfull read and move controllers to the next
  // loop
  return hardware_interface::return_type::OK;
}

// Convert Radians to Pulse Width
uint16_t rad_to_pulse(double rad, bool invert, bool is_270) {
  if (std::isnan(rad)) {
    // Return center position if command is NaN
    return (is_270) ? 2040 : 2000;
  }
  // Converts radians back into degrees // Shifts the range to 0-180 instead of
  // -90-90
  double deg = rad * (180.0 / M_PI) + 90.0;
  if (invert) {
    deg = 180.0 - deg;
  }
  if (is_270) {
    // map 0..270 to 380..3700
    double p = 380 + (deg / 270.0) * (3700 - 380);
    if (p < 380)
      p = 380;
    if (p > 3700)
      p = 3700;
    return (uint16_t)p;
  } else {
    // map 0..180 to 900..3100
    double p = 900 + (deg / 180.0) * (3100 - 900);
    if (p < 900)
      p = 900;
    if (p > 3100)
      p = 3100;
    return (uint16_t)p;
  }
}

hardware_interface::return_type
HulkuHardwareInterface::write(const rclcpp::Time & /*time*/,
                              const rclcpp::Duration & /*period*/) {
  // if serial ports not open or no commands are there to be executed then just
  // simply return from this loop
  if (serial_fd_ < 0 || hw_commands_.empty())
    return hardware_interface::return_type::OK;

  std::lock_guard<std::mutex> lock(serial_mutex_);

  // assigning the commands to variables
  // If hw_commands vector is not empty then take the joint values or fill with
  // NaN to keep things working
  double c1 = (hw_commands_.size() > 0)
                  ? hw_commands_[0]
                  : std::numeric_limits<double>::quiet_NaN();
  double c2 = (hw_commands_.size() > 1)
                  ? hw_commands_[1]
                  : std::numeric_limits<double>::quiet_NaN();
  double c3 = (hw_commands_.size() > 2)
                  ? hw_commands_[2]
                  : std::numeric_limits<double>::quiet_NaN();
  double c4 = (hw_commands_.size() > 3)
                  ? hw_commands_[3]
                  : std::numeric_limits<double>::quiet_NaN();
  double c5 = (hw_commands_.size() > 4)
                  ? hw_commands_[4]
                  : std::numeric_limits<double>::quiet_NaN();
  double c6 = (hw_commands_.size() > 5)
                  ? hw_commands_[5]
                  : std::numeric_limits<double>::quiet_NaN();

  // Convert commands
  uint16_t pos1 = rad_to_pulse(c1, false, false);
  uint16_t pos2 = rad_to_pulse(c2, true, false);
  uint16_t pos3 = rad_to_pulse(c3, true, false);
  uint16_t pos4 = rad_to_pulse(c4, true, false);
  uint16_t pos5 = rad_to_pulse(c5, false, true); // 270 deg
  uint16_t pos6 = rad_to_pulse(c6, false, false);

  // Tells motor how fast the transition should happen
  uint16_t time_ms = 10; // Change to 10ms. 0ms might cause Divide By Zero on
                         // Arduino interpolation!

  static int print_count = 0;
  if (print_count++ % 100 == 0) {
    RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                "SENDING -> CMD(rad): [%.2f, %.2f, %.2f, %.2f, %.2f, %.2f] | "
                "PULSE: [%d, %d, %d, %d, %d, %d]",
                c1, c2, c3, c4, c5, c6, pos1, pos2, pos3, pos4, pos5, pos6);
  }

  uint8_t msg[17];
  msg[0] = 0x55;
  msg[1] = 0xAA;
  msg[2] = 0x01; // Command values which points to which command to send

  // which tells the system in how much time the position process should happen
  msg[3] = (time_ms >> 8) & 0xFF; // time_ms msb bit
  msg[4] = time_ms & 0xFF;        // time_ms lsb bit

  msg[5] = (pos1 >> 8) & 0xFF; // first motor msb bit
  msg[6] = pos1 & 0xFF;        // first motor lsb bit

  msg[7] = (pos2 >> 8) & 0xFF; // second motor msb bit
  msg[8] = pos2 & 0xFF;        // second motor lsb bit

  msg[9] = (pos3 >> 8) & 0xFF; // third motor msb bit
  msg[10] = pos3 & 0xFF;       // third motor lsb bit

  msg[11] = (pos4 >> 8) & 0xFF; // fourth motor msb bit
  msg[12] = pos4 & 0xFF;        // fourth motor lsb bit

  msg[13] = (pos5 >> 8) & 0xFF; // fifth motor msb bit
  msg[14] = pos5 & 0xFF;        // fifth motor lsb bit

  msg[15] = (pos6 >> 8) & 0xFF; // sixth motor msb bit //gripper
  msg[16] = pos6 & 0xFF;        // sixth motor lsb bit

  ::write(serial_fd_, msg, 17); // write all 17 bytes to the serial port

  // ===== GPIO Dispatch (send-on-change) =====
  // Index: 0=buzzer, 1=torque, 2=rgb_r, 3=rgb_g, 4=rgb_b

  // Buzzer (MCU register 0x06)
  if (gpio_commands_[0] != gpio_prev_[0]) {
    uint8_t val = static_cast<uint8_t>(gpio_commands_[0]);
    uint8_t buzzer_msg[4] = {0x55, 0xAA, 0x03, val};
    for (int i = 0; i < 3; i++) {
      ::write(serial_fd_, buzzer_msg, 4);
      usleep(3000);
    }
    RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                "[GPIO] Buzzer -> 0x%02X", val);
    gpio_prev_[0] = gpio_commands_[0];
    gpio_states_[0] = gpio_commands_[0];
  }

  // Torque (MCU register 0x1A)
  if (gpio_commands_[1] != gpio_prev_[1]) {
    uint8_t val = (gpio_commands_[1] > 0.5) ? 0x01 : 0x00;
    uint8_t torque_msg[4] = {0x55, 0xAA, 0x04, val};
    for (int i = 0; i < 3; i++) {
      ::write(serial_fd_, torque_msg, 4);
      usleep(3000);
    }
    RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                "[GPIO] Torque -> %s", val ? "ON (Hold)" : "OFF (Drag)");
    gpio_prev_[1] = gpio_commands_[1];
    gpio_states_[1] = gpio_commands_[1];
  }

  // RGB (MCU register 0x02)
  if (gpio_commands_[2] != gpio_prev_[2] ||
      gpio_commands_[3] != gpio_prev_[3] ||
      gpio_commands_[4] != gpio_prev_[4]) {
    uint8_t r = static_cast<uint8_t>(gpio_commands_[2]);
    uint8_t g = static_cast<uint8_t>(gpio_commands_[3]);
    uint8_t b = static_cast<uint8_t>(gpio_commands_[4]);
    uint8_t rgb_msg[6] = {0x55, 0xAA, 0x05, r, g, b};
    for (int i = 0; i < 3; i++) {
      ::write(serial_fd_, rgb_msg, 6);
      usleep(3000);
    }
    RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                "[GPIO] RGB -> R:%d G:%d B:%d", r, g, b);
    gpio_prev_[2] = gpio_commands_[2];
    gpio_prev_[3] = gpio_commands_[3];
    gpio_prev_[4] = gpio_commands_[4];
    gpio_states_[2] = gpio_commands_[2];
    gpio_states_[3] = gpio_commands_[3];
    gpio_states_[4] = gpio_commands_[4];
  }

  // return ok if everything goes well
  return hardware_interface::return_type::OK;
}

// It is a helper function to configure serial port and help in establish
// connection to hardware (micro-controller)
int HulkuHardwareInterface::setup_serial(const std::string &port,
                                         int baud_rate) {
  // in linux port is defined as a "file" like /dev/ttyUSB0
  // Open() is the linux system call
  // o_RDWR : - opens for read and write both
  // o_NoCTTY : - tells do not let it control our program or system
  // o_NDELAY : - open port in non-blocking mode means it will not wait for port
  // to open if found busy
  serial_fd_ = open(port.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
  if (serial_fd_ == -1) {
    // return -1 if port or file doesn't exist
    return -1;
  }

  // terminos is a standard structure who holds all config for a port
  struct termios options;
  // this function reads all configuration of the port we provided and saves it
  // in options variable
  tcgetattr(serial_fd_, &options);

  speed_t baud; // this varibale stores the baud_rate speed of communication
  // This switch statement maps the baud_rate integer to a special linux
  // constant like B115200
  switch (baud_rate) {
  case 9600:
    baud = B9600;
    break;
  case 19200:
    baud = B19200;
    break;
  case 38400:
    baud = B38400;
    break;
  case 57600:
    baud = B57600;
    break;
  case 115200:
    baud = B115200;
    break;
  default:
    baud = B115200;
    break;
  }

  // sets the input and outpur baud rate in the configuration
  cfsetispeed(&options, baud); // sets input speed in the configuration
  cfsetospeed(&options, baud); // sets output speed in the configuration

  // below is "8-N-1" configuration. it is standard grammer for serial
  // communication it tells how many bits make up one letter or number
  options.c_cflag |= (CLOCAL | CREAD); // Ignore modem lines, enable reciever
  options.c_cflag &= ~PARENB;          // Disable(No) parity bit
  options.c_cflag &= ~CSTOPB;          // 1 Stop bit
  options.c_cflag &= ~CSIZE;           // Clear size mask (bits)
  options.c_cflag |= CS8;              // 8 data bits (standard)

  options.c_cflag &= ~CRTSCTS; // Disable harware flow control

  // Enable Raw mode (tells linux not to touch the data just give the raw bytes
  // directly)
  // ICANON (canonical mode)- Enable non-technical mode which let the
  // data arrive to the read function instantly without the need of pressing the
  // enter key.
  // ECHO - ECHO (echoing)- Disable echo which let the data flow stop
  // from sending motors packet back to motor to avoid collision and getting
  // firmware crash
  // ECHOE (echo erase)- remove backspace key processing
  // ISIG (Signals) - It prevents the serial driver from interpreting any byte
  // of data as a control signal to prevent ros2_control kill itself if any
  // motor signal containing data which maps to ctrl-c or that kind of commands
  options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
  // It insures raw output from computer to motor being sent otherwise the smart
  // feature changes the bytes if needed like appending \n with \r and being
  // sent 0x0D with 0x0A
  options.c_oflag &= ~OPOST;
  // It Enable bits control for input data which is coming from the motors to
  // the computer and pass the raw bytes directly
  // ---------- Flow control ----------
  // IXON/IXOFF (XON/XOFF) - Enable software flow control which means it stops
  // thinking that motor is full when got 0x11 or 0x13
  // IXANY - It disable any charatcter to restart after a pause which prevents
  // random bytes from accidently triggering resume signals
  //---------- Break and error group : - handles what happens if the electric
  // signal is brokern or corrupted----------
  // IGNBRK and BRKINT -not setting is off It kill ros2 node if a 0 signal
  // persist for a long time to prevent this we set it off makes this treated as
  // null bytes or ignored
  // PARMRK - This flag off tells linux not add extra byte to mark error happen
  // by parity error which will ruin motor packet's
  // ISTRIP - Disabling this make sure that the linux system want strip 8th bit
  // off every byte which could destroy the main data
  //---------- Newline Translation ----------
  // INLCR - translates newline to carriage return on input
  // IGNCR - Discards all CR characters
  // ICRNL - translates cr to nl on input
  // Disabling this will make sure data and position values won't come dirty
  // In summary this bits disanle terminal to change any bit of data coming from
  // motors

  options.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK | BRKINT | PARMRK |
                       ISTRIP | INLCR | IGNCR | ICRNL);

  // Non-blocking read behavior
  // VMIN -Minimum number of characters to read and should present in the serial
  // buffer
  // VTIME - Time to wait for characters to arrive in seconds before giving up
  // Return immediately because setted 0 it ignores timers intirely and size
  options.c_cc[VMIN] = 0;
  options.c_cc[VTIME] = 0;

  // Set and applies the chnages in the attributes to the actual hardware
  // (serial port config file)
  // TCSANOW - it applies changes immediately
  tcsetattr(serial_fd_, TCSANOW, &options);

  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Serial port opened. Waiting 2 seconds for Arduino to boot...");
  sleep(2); // Wait for Arduino to reset

  // Flush any pending garbage data from the boot process
  // TCIFLUSH : discards all waiting input data
  // TCOFLUSH : discards all pending output data
  // TCIOFLUSH : discards both input and output data
  tcflush(serial_fd_, TCIOFLUSH);

  // return 0 if serial port is opened successfully, -1 otherwise
  return 0;
}

void HulkuHardwareInterface::close_serial() {
  if (serial_fd_ >= 0) {
    // The linux system call which tells system to release the port we assigned
    close(serial_fd_);
    // It is a safety check which makes the other accidentl program stop to use
    // that port again
    serial_fd_ = -1;
  }
}

// Service callbacks removed — GPIO is now managed by ros2_control gpio_controller.
// Commands arrive via ForwardCommandController -> gpio_commands_[] -> write() dispatch.

} // namespace hulku_hardware

#include "pluginlib/class_list_macros.hpp"

PLUGINLIB_EXPORT_CLASS(hulku_hardware::HulkuHardwareInterface,
                       hardware_interface::SystemInterface)

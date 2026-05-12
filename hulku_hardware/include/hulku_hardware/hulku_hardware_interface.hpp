#ifndef HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_
#define HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_

#include <atomic>
#include <memory>
#include <string>
#include <mutex>
#include <thread>
#include <vector>

#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"

namespace hulku_hardware {

class HulkuHardwareInterface : public hardware_interface::SystemInterface {
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(HulkuHardwareInterface)

  hardware_interface::CallbackReturn
  on_init(const hardware_interface::HardwareInfo &info) override;

  hardware_interface::CallbackReturn
  on_configure(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_cleanup(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_activate(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_deactivate(const rclcpp_lifecycle::State &previous_state) override;

  std::vector<hardware_interface::StateInterface>
  export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface>
  export_command_interfaces() override;

  hardware_interface::return_type read(const rclcpp::Time &time,
                                       const rclcpp::Duration &period) override;

  hardware_interface::return_type
  write(const rclcpp::Time &time, const rclcpp::Duration &period) override;

private:
  int setup_serial(const std::string &port, int baud_rate);
  void close_serial();

  // Communication handles
  std::string port_;
  int baud_rate_;
  int serial_fd_ = -1;
  std::mutex serial_mutex_;

  // Joint commands and states
  std::vector<double> hw_commands_;
  std::vector<double> hw_states_;

  // GPIO command values
  // Indexes: 0=buzzer, 1=torque, 2=rgb_r, 3=rgb_g, 4=rgb_b
  static constexpr size_t GPIO_COUNT = 5;
  double gpio_commands_[GPIO_COUNT];
  double gpio_states_[GPIO_COUNT];
  double gpio_prev_[GPIO_COUNT] = {0.0};
};

} // namespace hulku_hardware

#endif // HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_

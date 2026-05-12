cmake_minimum_required(VERSION 3.8)
project(hulku_hardware)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)

add_library(hulku_hardware SHARED
  src/hulku_hardware_interface.cpp
)

target_include_directories(hulku_hardware
  PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(hulku_hardware
  rclcpp
  hardware_interface
  pluginlib
)

pluginlib_export_plugin_description_file(hardware_interface hulku_hardware_plugin.xml)

install(
  TARGETS hulku_hardware
  EXPORT export_hulku_hardware
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(
  DIRECTORY include/
  DESTINATION include
)

ament_export_targets(export_hulku_hardware HAS_LIBRARY_TARGET)
ament_export_dependencies(rclcpp hardware_interface pluginlib)

ament_package()

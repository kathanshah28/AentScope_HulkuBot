import sys
from unittest.mock import MagicMock

# Mock ROS 2 modules so tests can run without ROS sourced
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.action'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['moveit_msgs'] = MagicMock()
sys.modules['moveit_msgs.srv'] = MagicMock()
sys.modules['moveit_msgs.action'] = MagicMock()
sys.modules['moveit_msgs.msg'] = MagicMock()
sys.modules['custom_interfaces'] = MagicMock()
sys.modules['custom_interfaces.action'] = MagicMock()
sys.modules['ament_index_python'] = MagicMock()
sys.modules['ament_index_python.packages'] = MagicMock()

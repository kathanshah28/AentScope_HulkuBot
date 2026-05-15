import sys
from unittest.mock import MagicMock

sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.action'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['custom_interfaces'] = MagicMock()
sys.modules['custom_interfaces.action'] = MagicMock()
sys.modules['custom_interfaces.msg'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()
sys.modules['moveit_msgs'] = MagicMock()
sys.modules['moveit_msgs.srv'] = MagicMock()
sys.modules['control_msgs'] = MagicMock()
sys.modules['control_msgs.action'] = MagicMock()

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import serial
import math

# --- Configuration ---
ESP_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
MOVE_TIME = 200  # ms - low value for "real-time" streaming feel

class DofbotBridge(Node):
    def __init__(self):
        super().__init__('dofbot_bridge')
        
        # 1. Serial Connection Setup
        try:
            self.ser = serial.Serial(ESP_PORT, BAUD_RATE, timeout=0.1)
            self.get_logger().info(f"Connected to ESP32 on {ESP_PORT}")
        except Exception as e:
            self.get_logger().error(f"Serial Error: {e}")
            exit()

        # 2. Subscription to Joint States
        # This topic is where RViz/MoveIt/Joint_State_Publisher send data
        self.subscription = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10)
        
        # Map your URDF joint names to the servo order (adjust names if different)
        self.joint_order = [
            'link_1_joint', 'link_2_joint', 'link_3_joint', 
            'link_4_joint', 'link_5_joint', 'link_6_joint'
        ]
        
        self.get_logger().info("Dofbot Bridge Node Started. Listening for JointStates...")

    def rad_to_deg(self, rad):
        """Converts ROS radians to Servo degrees (0-180)."""
        # Adjust offsets if your '0' radian position isn't 90 degrees
        return int(math.degrees(rad) + 90)

    def joint_state_callback(self, msg):
        # Create a dictionary for easy lookup of incoming joint values
        joint_map = dict(zip(msg.name, msg.position))
        
        try:
            # Extract values based on our fixed order
            angles = []
            for name in self.joint_order:
                if name in joint_map:
                    angles.append(self.rad_to_deg(joint_map[name]))
                else:
                    angles.append(90) # Default if joint not found

            # Format the command for your ESP32 script
            # MOVE S1 S2 S3 S4 S5 S6 TIME
            command = f"MOVE {angles[0]} {angles[1]} {angles[2]} {angles[3]} {angles[4]} {angles[5]} {MOVE_TIME}\n"
            print(command)
            # Send to hardware
            self.ser.write(command.encode('utf-8'))
            
            # Optional: Log to terminal (comment out for performance)
            # self.get_logger().info(f"Sent: {command.strip()}")

        except Exception as e:
            self.get_logger().warn(f"Bridge Error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = DofbotBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.ser.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

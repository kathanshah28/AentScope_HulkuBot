#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

class GPIOCommandPublisher(Node):
    def __init__(self):
        super().__init__('gpio_command_publisher')
        self.publisher_ = self.create_publisher(Float64MultiArray, '/gpio_controller/commands', 10)
        self.timer = self.create_timer(2.0, self.timer_callback)
        self.toggle = False

    def timer_callback(self):
        msg = Float64MultiArray()
        # Interface names from yaml: led_r, led_g, led_b, torque_enable, buzzer_trigger

        if self.toggle:
            # Turn buzzer ON, torque ON, LED Red
            msg.data = [255.0, 0.0, 0.0, 1.0, 1.0] # Red=255, Torque=1, Buzzer=1
            self.get_logger().info('Sending: Red LED, Torque ON, Buzzer ON')
        else:
            # Turn buzzer OFF, torque OFF, LED Blue
            msg.data = [0.0, 0.0, 255.0, 0.0, 0.0] # Blue=255, Torque=0, Buzzer=0
            self.get_logger().info('Sending: Blue LED, Torque OFF, Buzzer OFF')

        self.publisher_.publish(msg)
        self.toggle = not self.toggle

def main(args=None):
    rclpy.init(args=args)
    node = GPIOCommandPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

class TestRGB(Node):
    def __init__(self):
        super().__init__('test_rgb')
        self.publisher_ = self.create_publisher(Float64MultiArray, '/gpio_controller/commands', 10)
        self.timer = self.create_timer(1.5, self.timer_callback)
        self.state = 0

    def timer_callback(self):
        msg = Float64MultiArray()
        # The correct order defined in yaml is: buzzer, torque, led_r, led_g, led_b
        if self.state == 0:
            msg.data = [0.0, 0.0, 255.0, 0.0, 0.0] 
            self.get_logger().info('Sending: Red LED')
        elif self.state == 1:
            msg.data = [0.0, 0.0, 0.0, 255.0, 0.0] 
            self.get_logger().info('Sending: Green LED')
        elif self.state == 2:
            msg.data = [0.0, 0.0, 0.0, 0.0, 255.0] 
            self.get_logger().info('Sending: Blue LED')
        else:
            msg.data = [0.0, 0.0, 0.0, 0.0, 0.0] 
            self.get_logger().info('Sending: LEDs OFF')

        self.publisher_.publish(msg)
        self.state = (self.state + 1) % 4

def main(args=None):
    rclpy.init(args=args)
    node = TestRGB()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

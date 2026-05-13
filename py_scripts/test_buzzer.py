#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

class TestBuzzer(Node):
    def __init__(self):
        super().__init__('test_buzzer')
        self.publisher_ = self.create_publisher(Float64MultiArray, '/gpio_controller/commands', 10)
        self.timer = self.create_timer(2.0, self.timer_callback)
        self.toggle = False

    def timer_callback(self):
        msg = Float64MultiArray()
        # The correct order defined in yaml is: buzzer, torque, led_r, led_g, led_b
        if self.toggle:
            msg.data = [1.0, 0.0, 0.0, 0.0, 0.0] 
            self.get_logger().info('Sending: Buzzer ON')
        else:
            msg.data = [0.0, 0.0, 0.0, 0.0, 0.0] 
            self.get_logger().info('Sending: Buzzer OFF')

        self.publisher_.publish(msg)
        self.toggle = not self.toggle

def main(args=None):
    rclpy.init(args=args)
    node = TestBuzzer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

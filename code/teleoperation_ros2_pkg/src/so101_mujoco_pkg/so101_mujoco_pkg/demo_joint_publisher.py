import math
import time

import rclpy
from rclpy.node import Node
from so101_interfaces.msg import SequencedJointState


DEFAULT_JOINT_STATES_TOPIC = 'master/joint_states'
DEFAULT_JOINT_NAMES = [
    'shoulder_pan',
    'shoulder_lift',
    'elbow_flex',
    'wrist_flex',
    'wrist_roll',
    'gripper',
]


class DemoJointPublisher(Node):
    def __init__(self) -> None:
        super().__init__('demo_joint_publisher')

        self.declare_parameter('joint_states_topic', DEFAULT_JOINT_STATES_TOPIC)
        self.declare_parameter('joint_names', DEFAULT_JOINT_NAMES)
        self.declare_parameter('publish_rate', 30.0)
        self.declare_parameter('amplitude', 0.35)
        self.declare_parameter('period', 4.0)

        self.joint_states_topic = str(self.get_parameter('joint_states_topic').value)
        self.joint_names = list(self.get_parameter('joint_names').value)
        self.joint_count = max(1, len(self.joint_names))
        self.publish_rate = max(1.0, float(self.get_parameter('publish_rate').value))
        self.amplitude = float(self.get_parameter('amplitude').value)
        self.period = max(0.1, float(self.get_parameter('period').value))

        self.publisher = self.create_publisher(SequencedJointState, self.joint_states_topic, 10)
        self._start_time = time.monotonic()
        self._message_seq = 0
        self._timer = self.create_timer(1.0 / self.publish_rate, self._timer_callback)

        self.get_logger().info(
            f'Publishing demo joint targets to {self.joint_states_topic} '
            f'({self.joint_count} joints @ {self.publish_rate:.1f} Hz).'
        )

    def _timer_callback(self) -> None:
        elapsed = time.monotonic() - self._start_time
        phase = (2.0 * math.pi * elapsed) / self.period
        positions = [
            self.amplitude * math.sin(phase + index * 0.4)
            for index in range(self.joint_count)
        ]

        msg = SequencedJointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.seq = self._message_seq
        self._message_seq += 1
        msg.name = self.joint_names
        msg.position = positions
        self.publisher.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DemoJointPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

from collections import deque
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from so101_interfaces.msg import SequencedJointState

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode


DEFAULT_SERIAL_PORT = '/dev/ttyACM0'
DEFAULT_PUBLISH_RATE = 60.0
DEFAULT_JOINT_STATES_TOPIC = 'master/joint_states'
DEFAULT_PUBLISH_DELAY_MS = 0.0
DEFAULT_MOTOR_NAMES = [
    'shoulder_pan',
    'shoulder_lift',
    'elbow_flex',
    'wrist_flex',
    'wrist_roll',
    'gripper',
]
DEFAULT_OFFSETS = [0.064, -0.882, 0.864, 1.0165, 0.003, 0.7925]
DEFAULT_SCALES = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
DEFAULT_INVERTS = [False, False, False, False, False, False]


class SO101MasterNode(Node):
    def __init__(self) -> None:
        super().__init__('so101_master_node')

        # Parameters (aligned with config/motors.yaml)
        self.declare_parameter('serial_port', DEFAULT_SERIAL_PORT)
        self.declare_parameter('publish_rate', DEFAULT_PUBLISH_RATE)
        self.declare_parameter('joint_states_topic', DEFAULT_JOINT_STATES_TOPIC)
        self.declare_parameter('publish_delay_ms', DEFAULT_PUBLISH_DELAY_MS)
        self.declare_parameter('motor_names', DEFAULT_MOTOR_NAMES)
        self.declare_parameter('offsets', DEFAULT_OFFSETS)
        self.declare_parameter('scales', DEFAULT_SCALES)
        self.declare_parameter('inverts', DEFAULT_INVERTS)

        self.serial_port = self.get_parameter('serial_port').value
        self.publish_rate = float(self.get_parameter('publish_rate').value)
        self.joint_states_topic = str(self.get_parameter('joint_states_topic').value)
        self.publish_delay_ms = max(0.0, float(self.get_parameter('publish_delay_ms').value))
        self.publish_delay_sec = self.publish_delay_ms / 1000.0
        self.motor_names = list(self.get_parameter('motor_names').value)
        self.offsets = np.array(self.get_parameter('offsets').value, dtype=float)
        self.scales = np.array(self.get_parameter('scales').value, dtype=float)
        self.inverts = np.array(self.get_parameter('inverts').value, dtype=bool)
        self._message_seq = 0
        self._pending_messages = deque()
        self._pending_lock = threading.Lock()

        motors_config = {
            'shoulder_pan': Motor(id=1, model='sts3215', norm_mode=MotorNormMode.DEGREES),
            'shoulder_lift': Motor(id=2, model='sts3215', norm_mode=MotorNormMode.DEGREES),
            'elbow_flex': Motor(id=3, model='sts3215', norm_mode=MotorNormMode.DEGREES),
            'wrist_flex': Motor(id=4, model='sts3215', norm_mode=MotorNormMode.DEGREES),
            'wrist_roll': Motor(id=5, model='sts3215', norm_mode=MotorNormMode.DEGREES),
            'gripper': Motor(id=6, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        }

        try:
            self.so101_arm = FeetechMotorsBus(port=self.serial_port, motors=motors_config)
            if not self.so101_arm.is_connected:
                self.so101_arm.connect()
            # Disable torque for manual teaching
            self.so101_arm.disable_torque()
            self._log_torque_state()
        except Exception as exc:
            self.get_logger().error(f'Failed to connect to SO101 master: {exc}')
            raise

        self.joint_state_pub = self.create_publisher(
            SequencedJointState,
            self.joint_states_topic,
            10,
        )

        rate = self.publish_rate if self.publish_rate > 0.0 else 30.0
        self.timer = self.create_timer(1.0 / rate, self.timer_callback)
        self.delay_timer = None
        if self.publish_delay_sec > 0.0:
            self.delay_timer = self.create_timer(0.001, self._publish_ready_messages)

        self.get_logger().info(
            f'Publishing master joint states to {self.joint_states_topic} '
            f'@ {rate:.1f} Hz with publish_delay_ms={self.publish_delay_ms:.3f}.'
        )

    def _log_torque_state(self) -> None:
        try:
            torque_state = self.so101_arm.sync_read(
                'Torque_Enable',
                self.motor_names,
                normalize=False,
                num_retry=1,
            )
        except Exception as exc:
            self.get_logger().warn(
                'SO101 master connected and torque disable command sent, '
                f'but Torque_Enable readback failed: {exc}'
            )
            return

        still_enabled = [
            name for name in self.motor_names if int(torque_state.get(name, 1)) != 0
        ]
        if still_enabled:
            self.get_logger().warn(
                'SO101 master connected, but torque is still enabled for joints '
                f'{still_enabled}. Readback={torque_state}'
            )
        else:
            self.get_logger().info(
                f'SO101 master connected. Torque disable verified. Readback={torque_state}'
            )

    def timer_callback(self) -> None:
        try:
            present_pos_dict = self.so101_arm.sync_read('Present_Position', normalize=False)
            ordered_values = [float(present_pos_dict[name]) for name in self.motor_names]
            pos_array = np.array(ordered_values, dtype=float)

            # 0~4096 -> radians
            pos_array = (pos_array / 2048.0 - 1.0) * np.pi

            if (
                len(self.offsets) != len(self.motor_names)
                or len(self.scales) != len(self.motor_names)
                or len(self.inverts) != len(self.motor_names)
            ):
                self.get_logger().warn('offsets/scales/inverts length mismatch; skip compensation')
                final_pos = pos_array
            else:
                signs = np.where(self.inverts, -1.0, 1.0)
                final_pos = pos_array * signs * self.scales + self.offsets

            js_msg = SequencedJointState()
            js_msg.header.stamp = self.get_clock().now().to_msg()
            js_msg.name = self.motor_names
            js_msg.position = final_pos.tolist()
            js_msg.seq = self._message_seq
            self._message_seq += 1
            self._queue_or_publish(js_msg)
        except Exception as exc:
            self.get_logger().warn(f'Read skipped: {exc}')

    def _queue_or_publish(self, msg: SequencedJointState) -> None:
        if self.publish_delay_sec <= 0.0:
            self.joint_state_pub.publish(msg)
            return

        publish_at = time.monotonic() + self.publish_delay_sec
        with self._pending_lock:
            self._pending_messages.append((publish_at, msg))
        self._publish_ready_messages()

    def _publish_ready_messages(self) -> None:
        now = time.monotonic()
        ready_messages = []
        with self._pending_lock:
            while self._pending_messages and self._pending_messages[0][0] <= now:
                _, msg = self._pending_messages.popleft()
                ready_messages.append(msg)

        for msg in ready_messages:
            self.joint_state_pub.publish(msg)

    def destroy_node(self) -> None:
        self._publish_ready_messages()
        self.so101_arm.disconnect()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SO101MasterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

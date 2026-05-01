import time
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from so101_interfaces.msg import SequencedJointState

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode


DEFAULT_MOTOR_NAMES = [
    'shoulder_pan',
    'shoulder_lift',
    'elbow_flex',
    'wrist_flex',
    'wrist_roll',
    'gripper',
]
DEFAULT_SERIAL_PORT = '/dev/ttyACM1'
DEFAULT_INPUT_TOPIC = 'master/joint_states'
DEFAULT_FEEDBACK_TOPIC = 'follower/joint_states'
DEFAULT_OFFSETS = [0.064, -0.882, 0.864, 1.0165, 0.003, 0.7925]
DEFAULT_INVERTS = [False, False, False, False, False, False]


class SO101FollowerNode(Node):
    def __init__(self) -> None:
        super().__init__('so101_follower_node')

        self.declare_parameter('serial_port', DEFAULT_SERIAL_PORT)
        self.declare_parameter('input_topic', DEFAULT_INPUT_TOPIC)
        self.declare_parameter('write_rate', 30.0)
        self.declare_parameter('readback_rate', 15.0)
        self.declare_parameter('command_timeout_sec', 0.5)
        self.declare_parameter('motor_names', DEFAULT_MOTOR_NAMES)
        self.declare_parameter('motor_ids', [1, 2, 3, 4, 5, 6])
        self.declare_parameter('motor_model', 'sts3215')
        self.declare_parameter('offsets', DEFAULT_OFFSETS)
        self.declare_parameter('inverts', DEFAULT_INVERTS)
        self.declare_parameter('enable_torque_on_start', True)
        self.declare_parameter('disable_torque_on_shutdown', True)
        self.declare_parameter('publish_readback', True)
        self.declare_parameter('joint_states_topic', DEFAULT_FEEDBACK_TOPIC)

        self.serial_port = str(self.get_parameter('serial_port').value).strip()
        self.input_topic = str(self.get_parameter('input_topic').value)
        self.write_rate = float(self.get_parameter('write_rate').value)
        self.readback_rate = float(self.get_parameter('readback_rate').value)
        self.command_timeout_sec = float(self.get_parameter('command_timeout_sec').value)
        self.motor_names = list(self.get_parameter('motor_names').value)
        self.motor_ids = [int(value) for value in self.get_parameter('motor_ids').value]
        self.motor_model = str(self.get_parameter('motor_model').value)
        self.offsets = np.array(self.get_parameter('offsets').value, dtype=float)
        self.inverts = np.array(self.get_parameter('inverts').value, dtype=bool)
        self.enable_torque_on_start = bool(self.get_parameter('enable_torque_on_start').value)
        self.disable_torque_on_shutdown = bool(
            self.get_parameter('disable_torque_on_shutdown').value
        )
        self.publish_readback = bool(self.get_parameter('publish_readback').value)
        self.joint_states_topic = str(self.get_parameter('joint_states_topic').value)
        self._feedback_seq = 0

        self._validate_parameters()

        self._motor_count = len(self.motor_names)
        self._signs = np.where(self.inverts, -1.0, 1.0)
        self._latest_target: Optional[np.ndarray] = None
        self._last_msg_monotonic: Optional[float] = None
        self._warned_length_mismatch = False
        self._warned_timeout = False
        self._warned_clipping = False
        self._warned_missing_joints = False
        self._warned_invalid_joint_state = False
        self.follower_arm: Optional[FeetechMotorsBus] = None

        motors_config = {
            name: Motor(id=motor_id, model=self.motor_model, norm_mode=MotorNormMode.DEGREES)
            for name, motor_id in zip(self.motor_names, self.motor_ids, strict=True)
        }

        try:
            self.follower_arm = FeetechMotorsBus(port=self.serial_port, motors=motors_config)
            if not self.follower_arm.is_connected:
                self.follower_arm.connect()
            if self.enable_torque_on_start:
                self.follower_arm.enable_torque(num_retry=3)
            self.get_logger().info(
                f'SO101 follower connected on {self.serial_port}. '
                f'Subscribing to {self.input_topic}.'
            )
        except Exception as exc:
            self.get_logger().error(f'Failed to connect to follower arm: {exc}')
            raise

        self.create_subscription(SequencedJointState, self.input_topic, self._on_joint_state, 10)

        write_period = 1.0 / self.write_rate
        self.write_timer = self.create_timer(write_period, self._write_latest_command)

        self.joint_state_pub = None
        self.readback_timer = None
        if self.publish_readback:
            self.joint_state_pub = self.create_publisher(
                SequencedJointState,
                self.joint_states_topic,
                10,
            )
            if self.readback_rate > 0.0:
                readback_period = 1.0 / self.readback_rate
                self.readback_timer = self.create_timer(readback_period, self._publish_readback)

    def _validate_parameters(self) -> None:
        if not self.serial_port:
            raise ValueError(
                "Parameter 'serial_port' must not be empty. "
                "Set it in src/so101_follower_pkg/config/follower_motors.yaml or via launch."
            )
        if self.write_rate <= 0.0:
            raise ValueError("Parameter 'write_rate' must be > 0.")
        if self.readback_rate < 0.0:
            raise ValueError("Parameter 'readback_rate' must be >= 0.")
        if self.command_timeout_sec < 0.0:
            raise ValueError("Parameter 'command_timeout_sec' must be >= 0.")
        if len(self.motor_names) != len(self.motor_ids):
            raise ValueError('motor_names and motor_ids must have the same length.')
        if len(self.offsets) == 0 or len(self.inverts) == 0:
            raise ValueError(
                "Parameters 'offsets' and 'inverts' must not be empty."
            )
        if len(self.offsets) != len(self.motor_names):
            raise ValueError('offsets and motor_names must have the same length.')
        if len(self.inverts) != len(self.motor_names):
            raise ValueError('inverts and motor_names must have the same length.')
        if len(set(self.motor_ids)) != len(self.motor_ids):
            raise ValueError('motor_ids must be unique.')

    def _extract_target_positions(self, msg: SequencedJointState) -> Optional[np.ndarray]:
        if len(msg.name) != 0 and len(msg.name) != len(msg.position):
            if not self._warned_invalid_joint_state:
                self.get_logger().warn(
                    'Received SequencedJointState with mismatched name/position lengths; message will be ignored.'
                )
                self._warned_invalid_joint_state = True
            return None

        if len(msg.name) == 0:
            return np.array(msg.position, dtype=float)

        positions_by_name = {
            name: float(position)
            for name, position in zip(msg.name, msg.position, strict=True)
        }
        missing_joints = [name for name in self.motor_names if name not in positions_by_name]
        if missing_joints:
            if not self._warned_missing_joints:
                self.get_logger().warn(
                    f'Received SequencedJointState missing required joints {missing_joints}; message will be ignored.'
                )
                self._warned_missing_joints = True
            return None

        return np.array([positions_by_name[name] for name in self.motor_names], dtype=float)

    def _on_joint_state(self, msg: SequencedJointState) -> None:
        target_positions = self._extract_target_positions(msg)
        if target_positions is None:
            return

        self._latest_target = target_positions
        self._last_msg_monotonic = time.monotonic()
        self._warned_timeout = False

    def _fit_target(self, target: np.ndarray) -> np.ndarray:
        if target.shape[0] == self._motor_count:
            return target

        if not self._warned_length_mismatch:
            self.get_logger().warn(
                f'Joint length mismatch: got {target.shape[0]}, expected {self._motor_count}. '
                'Will pad or truncate.'
            )
            self._warned_length_mismatch = True

        if target.shape[0] > self._motor_count:
            return target[: self._motor_count]

        padded = np.zeros(self._motor_count, dtype=float)
        padded[: target.shape[0]] = target
        return padded

    def _target_positions_to_raw_steps(self, target_positions: np.ndarray) -> dict[str, int]:
        fitted = self._fit_target(target_positions)
        motor_radians = (fitted - self.offsets) / self._signs
        raw_steps = np.rint((motor_radians / np.pi + 1.0) * 2048.0).astype(int)
        clipped = np.clip(raw_steps, 0, 4095)

        if not self._warned_clipping and np.any(clipped != raw_steps):
            clipped_names = [
                name
                for name, raw_value, clipped_value in zip(
                    self.motor_names, raw_steps, clipped, strict=True
                )
                if raw_value != clipped_value
            ]
            self.get_logger().warn(
                f'Goal_Position exceeded raw range for joints {clipped_names}; values were clipped.'
            )
            self._warned_clipping = True

        return {
            name: int(value)
            for name, value in zip(self.motor_names, clipped.tolist(), strict=True)
        }

    def _raw_steps_to_joint_positions(self, raw_positions: dict[str, float]) -> np.ndarray:
        ordered_values = [float(raw_positions[name]) for name in self.motor_names]
        pos_array = np.array(ordered_values, dtype=float)
        pos_array = (pos_array / 2048.0 - 1.0) * np.pi
        return pos_array * self._signs + self.offsets

    def _write_latest_command(self) -> None:
        if self.follower_arm is None or self._latest_target is None:
            return

        if self.command_timeout_sec > 0.0 and self._last_msg_monotonic is not None:
            age = time.monotonic() - self._last_msg_monotonic
            if age > self.command_timeout_sec:
                if not self._warned_timeout:
                    self.get_logger().warn(
                        f'No command received for {age:.3f}s; holding last motor goal.'
                    )
                    self._warned_timeout = True
                return

        try:
            raw_steps = self._target_positions_to_raw_steps(self._latest_target)
            self.follower_arm.sync_write('Goal_Position', raw_steps, normalize=False, num_retry=1)
        except Exception as exc:
            self.get_logger().warn(f'Follower write skipped: {exc}')

    def _publish_readback(self) -> None:
        if self.follower_arm is None or self.joint_state_pub is None:
            return

        try:
            raw_positions = self.follower_arm.sync_read(
                'Present_Position',
                self.motor_names,
                normalize=False,
                num_retry=1,
            )
            joint_positions = self._raw_steps_to_joint_positions(raw_positions)

            joint_state_msg = SequencedJointState()
            joint_state_msg.header.stamp = self.get_clock().now().to_msg()
            joint_state_msg.seq = self._feedback_seq
            self._feedback_seq += 1
            joint_state_msg.name = self.motor_names
            joint_state_msg.position = joint_positions.tolist()
            self.joint_state_pub.publish(joint_state_msg)
        except Exception as exc:
            self.get_logger().warn(f'Follower readback skipped: {exc}')

    def destroy_node(self) -> None:
        if self.follower_arm is not None and self.follower_arm.is_connected:
            self.follower_arm.disconnect(disable_torque=self.disable_torque_on_shutdown)
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SO101FollowerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

from collections import deque
import os
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from so101_interfaces.msg import SequencedJointState


DEFAULT_JOINT_STATES_TOPIC = 'master/joint_states'
DEFAULT_INPUT_OFFSETS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
DEFAULT_INPUT_SCALES = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
DEFAULT_INPUT_DELAY_MS = 0.0


def _find_default_xml() -> str:
    base = os.path.abspath(os.path.dirname(__file__))
    rel_candidates = (
        os.path.join('src', 'so101_6dof', 'push_cube_loop.xml'),
        os.path.join('so101_6dof', 'push_cube_loop.xml'),
        os.path.join('src', 'so101_6dof', 'so101_new_calib.xml'),
        os.path.join('so101_6dof', 'so101_new_calib.xml'),
    )
    for _ in range(8):
        for rel in rel_candidates:
            candidate = os.path.join(base, rel)
            if os.path.exists(candidate):
                return candidate
        base = os.path.dirname(base)
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'so101_6dof', 'push_cube_loop.xml')
    )


def _load_simulation_dependencies():
    try:
        import mujoco
        import mujoco.viewer
    except ImportError as exc:
        raise RuntimeError(
            'MuJoCo dependencies are missing. Install with '
            '`scripts/install_deps.sh --with-mujoco` or `pip install -e ".[hardware,sim]"`.'
        ) from exc

    try:
        from youzi_robot.interface.simulated_robot import SimulatedRobot
    except ImportError as exc:
        raise RuntimeError(
            'youzi-robot (module: gym_lowcostrobot) is missing. Install with '
            '`scripts/install_deps.sh --with-mujoco` or `pip install -e ".[hardware,sim]"`.'
        ) from exc

    return mujoco, SimulatedRobot


class SO101MujocoNode(Node):
    def __init__(self):
        super().__init__('so101_mujoco_node')

        default_xml = _find_default_xml()

        self.declare_parameter('joint_states_topic', DEFAULT_JOINT_STATES_TOPIC)
        self.declare_parameter('xml_path', default_xml)
        self.declare_parameter('wait_for_first_msg', True)
        self.declare_parameter('input_offsets', DEFAULT_INPUT_OFFSETS)
        self.declare_parameter('input_scales', DEFAULT_INPUT_SCALES)
        self.declare_parameter('clip_to_ctrlrange', True)
        self.declare_parameter('input_delay_ms', DEFAULT_INPUT_DELAY_MS)

        self.joint_states_topic = str(self.get_parameter('joint_states_topic').value)
        self.xml_path = self.get_parameter('xml_path').value
        if (not self.xml_path) or str(self.xml_path).lower() == 'auto':
            self.xml_path = _find_default_xml()
        self.wait_for_first_msg = bool(self.get_parameter('wait_for_first_msg').value)
        self.input_offsets = np.array(self.get_parameter('input_offsets').value, dtype=float)
        self.input_scales = np.array(self.get_parameter('input_scales').value, dtype=float)
        self.clip_to_ctrlrange = bool(self.get_parameter('clip_to_ctrlrange').value)
        self.input_delay_ms = max(0.0, float(self.get_parameter('input_delay_ms').value))
        self.input_delay_sec = self.input_delay_ms / 1000.0

        self._lock = threading.Lock()
        self._latest_qpos = None
        self._qpos_buffer = deque()
        self._delayed_qpos = None
        self._stop_event = threading.Event()
        self._warned_len = False
        self._warned_calib_len = False

        self.create_subscription(
            SequencedJointState,
            self.joint_states_topic,
            self._on_joint_state,
            10,
        )

        self._thread = threading.Thread(target=self._run_mujoco, daemon=True)
        self._thread.start()

    def _on_joint_state(self, msg: SequencedJointState):
        data = np.array(msg.position, dtype=float)
        received_at = time.monotonic()
        with self._lock:
            self._latest_qpos = data
            if self.input_delay_sec <= 0.0:
                self._delayed_qpos = data
                self._qpos_buffer.clear()
            else:
                self._qpos_buffer.append((received_at, data))

    def _get_target_qpos(self):
        if self.input_delay_sec <= 0.0:
            with self._lock:
                return None if self._latest_qpos is None else self._latest_qpos.copy()

        ready_before = time.monotonic() - self.input_delay_sec
        with self._lock:
            while self._qpos_buffer and self._qpos_buffer[0][0] <= ready_before:
                _, qpos = self._qpos_buffer.popleft()
                self._delayed_qpos = qpos
            return None if self._delayed_qpos is None else self._delayed_qpos.copy()

    def _fit_qpos(self, qpos: np.ndarray, expected_len: int) -> np.ndarray:
        if qpos.shape[0] == expected_len:
            return qpos
        if not self._warned_len:
            self.get_logger().warn(
                f'Joint length mismatch: got {qpos.shape[0]}, expected {expected_len}. '
                'Will pad/truncate.'
            )
            self._warned_len = True
        if qpos.shape[0] > expected_len:
            return qpos[:expected_len]
        padded = np.zeros(expected_len, dtype=float)
        padded[:qpos.shape[0]] = qpos
        return padded

    def _apply_input_calibration(self, qpos: np.ndarray) -> np.ndarray:
        if (
            self.input_offsets.shape[0] != qpos.shape[0]
            or self.input_scales.shape[0] != qpos.shape[0]
        ):
            if not self._warned_calib_len:
                self.get_logger().warn(
                    f'Input calibration length mismatch: got offsets={self.input_offsets.shape[0]}, '
                    f'scales={self.input_scales.shape[0]}, expected={qpos.shape[0]}. '
                    'Skipping input calibration.'
                )
                self._warned_calib_len = True
            return qpos
        return qpos * self.input_scales + self.input_offsets

    def _run_mujoco(self):
        if not os.path.exists(self.xml_path):
            self.get_logger().error(f'XML not found: {self.xml_path}')
            return

        try:
            mujoco, simulated_robot_cls = _load_simulation_dependencies()
            model = mujoco.MjModel.from_xml_path(self.xml_path)
            data = mujoco.MjData(model)
            sim_robot = simulated_robot_cls(model, data)
        except Exception as exc:
            self.get_logger().error(f'Failed to load MuJoCo model: {exc}')
            return

        if self.wait_for_first_msg:
            self.get_logger().info('Waiting for first joint message...')
            while rclpy.ok() and not self._stop_event.is_set():
                with self._lock:
                    ready = self._latest_qpos is not None
                if ready:
                    break
                time.sleep(0.01)

        self.get_logger().info('Starting MuJoCo viewer...')
        self.get_logger().info(
            f'Using XML: {self.xml_path}; input_offsets={self.input_offsets.tolist()}; '
            f'input_scales={self.input_scales.tolist()}; '
            f'input_delay_ms={self.input_delay_ms:.3f}'
        )
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running() and rclpy.ok() and not self._stop_event.is_set():
                step_start = time.time()
                qpos = self._get_target_qpos()
                if qpos is None:
                    qpos = np.zeros(model.nu, dtype=float)
                qpos = self._fit_qpos(qpos, model.nu)
                qpos = self._apply_input_calibration(qpos)
                if self.clip_to_ctrlrange:
                    qpos = np.clip(
                        qpos,
                        model.actuator_ctrlrange[:, 0],
                        model.actuator_ctrlrange[:, 1],
                    )
                sim_robot.set_target_qpos(qpos)
                mujoco.mj_step(model, data)
                viewer.sync()

                time_until_next_step = model.opt.timestep - (time.time() - step_start)
                if time_until_next_step > 0:
                    time.sleep(time_until_next_step)

    def destroy_node(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SO101MujocoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

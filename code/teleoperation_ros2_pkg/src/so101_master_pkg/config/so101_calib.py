import os
import threading
import time

import mujoco
import mujoco.viewer
import numpy as np

from youzi_robot.interface.simulated_robot import SimulatedRobot
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..', '..'))

MOTOR_NAMES = [
    'shoulder_pan',
    'shoulder_lift',
    'elbow_flex',
    'wrist_flex',
    'wrist_roll',
    'gripper',
]
OFFSETS = np.array([0.064, -0.882, 0.864, 1.0165, 0.003, 0.3196109799], dtype=float)
SCALES = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0502528322], dtype=float)

target_pos = np.zeros(len(MOTOR_NAMES), dtype=float)
so101_arm = None


def read_so101_arm_position() -> None:
    """Read SO101 joint positions in a background thread."""
    global target_pos

    while True:
        try:
            present_pos_dict = so101_arm.sync_read('Present_Position', normalize=False)
            ordered_values = [present_pos_dict[name] for name in MOTOR_NAMES]
            target_pos = np.array(ordered_values, dtype=float)
            target_pos = (target_pos / 2048.0 - 1.0) * 3.14
            target_pos = target_pos * SCALES + OFFSETS
            time.sleep(0.005)
        except Exception as exc:
            print(f'读取数据出错: {exc}')
            break


if __name__ == '__main__':
    motors_config = {
        'shoulder_pan': Motor(id=1, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        'shoulder_lift': Motor(id=2, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        'elbow_flex': Motor(id=3, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        'wrist_flex': Motor(id=4, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        'wrist_roll': Motor(id=5, model='sts3215', norm_mode=MotorNormMode.DEGREES),
        'gripper': Motor(id=6, model='sts3215', norm_mode=MotorNormMode.DEGREES),
    }

    so101_arm = FeetechMotorsBus(
        port='/dev/ttyACM0',
        motors=motors_config,
    )

    if not so101_arm.is_connected:
        so101_arm.connect()
        print('✅ 机械臂已连接')

    so101_arm.disable_torque()
    try:
        torque_state = so101_arm.sync_read(
            'Torque_Enable',
            MOTOR_NAMES,
            normalize=False,
            num_retry=1,
        )
        still_enabled = [name for name in MOTOR_NAMES if int(torque_state.get(name, 1)) != 0]
        if still_enabled:
            print(f'⚠️ 已发送关扭矩命令，但以下关节读回仍非 0: {still_enabled}, readback={torque_state}')
        else:
            print(f'🔓 扭矩已关闭并读回确认: {torque_state}')
    except Exception as exc:
        print(f'⚠️ 已发送关扭矩命令，但 Torque_Enable 读回失败: {exc}')

    try:
        xml_path = os.path.join(_WS_DIR, 'src', 'so101_6dof', 'push_cube_loop.xml')
        model = mujoco.MjModel.from_xml_path(xml_path)
        data = mujoco.MjData(model)
        sim_robot = SimulatedRobot(model, data)
    except Exception as exc:
        print(f'MuJoCo 模型加载失败: {exc}')
        print(f"请确保 {os.path.join(_WS_DIR, 'src', 'so101_6dof', 'push_cube_loop.xml')} 存在")
        so101_arm.disconnect()
        raise SystemExit(1) from exc

    so101_arm_thread = threading.Thread(target=read_so101_arm_position, daemon=True)
    so101_arm_thread.start()

    print('🚀 仿真开始...')
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            step_start = time.time()

            target_pos_local = target_pos.copy()
            sim_robot.set_target_qpos(target_pos_local)
            mujoco.mj_step(model, data)
            viewer.sync()

            time_until_next_step = model.opt.timestep - (time.time() - step_start)
            if time_until_next_step > 0:
                time.sleep(time_until_next_step)

    so101_arm.disconnect()
    print('仿真结束，连接已断开')

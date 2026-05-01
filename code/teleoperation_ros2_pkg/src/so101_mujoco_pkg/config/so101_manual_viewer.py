import argparse
import os
import time

import mujoco
import mujoco.viewer
import numpy as np


def _find_default_xml() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    ws_dir = os.path.abspath(os.path.join(here, '..', '..', '..'))
    candidates = [
        os.path.join(ws_dir, 'src', 'so101_6dof', 'push_cube_loop.xml'),
        os.path.join(ws_dir, 'src', 'so101_6dof', 'so101_new_calib.xml'),
        os.path.join(ws_dir, 'so101_6dof', 'push_cube_loop.xml'),
        os.path.join(ws_dir, 'so101_6dof', 'so101_new_calib.xml'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Fallback: walk up a few levels from this file
    base = here
    for _ in range(6):
        candidate = os.path.join(base, 'src', 'so101_6dof', 'push_cube_loop.xml')
        if os.path.exists(candidate):
            return candidate
        base = os.path.dirname(base)
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description='SO101 manual MuJoCo viewer (no external control).'
    )
    parser.add_argument('--xml', default='auto', help='Path to MuJoCo XML (or "auto").')
    parser.add_argument(
        '--mode',
        choices=('joint', 'control'),
        default='joint',
        help=(
            'joint: drag Joint sliders (kinematic, no dynamics); '
            'control: use Control sliders (actuated).'
        ),
    )
    parser.add_argument('--print', action='store_true', help='Print joint qpos periodically.')
    parser.add_argument(
        '--print-interval',
        type=float,
        default=1.0,
        help='Seconds between prints.',
    )
    args = parser.parse_args()

    xml_path = _find_default_xml() if args.xml == 'auto' else args.xml
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f'XML not found: {xml_path}')

    model = mujoco.MjModel.from_xml_path(xml_path)
    data = mujoco.MjData(model)

    print('MuJoCo viewer started.')
    if args.mode == 'joint':
        print('Mode: joint (use the Joint panel sliders).')
        model.opt.disableflags |= mujoco.mjtDisableBit.mjDISABLE_ACTUATION
    else:
        print('Mode: control (use the Control panel sliders).')
    print(f'XML: {xml_path}')

    last_print = time.time()
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            step_start = time.time()

            if args.mode == 'joint':
                mujoco.mj_forward(model, data)
            else:
                mujoco.mj_step(model, data)
            viewer.sync()

            if args.print and (time.time() - last_print) >= args.print_interval:
                qpos = data.qpos.copy()
                n_show = min(6, qpos.shape[0])
                print('qpos[0:6]=', np.array2string(qpos[:n_show], precision=4, separator=', '))
                last_print = time.time()

            time_until_next_step = model.opt.timestep - (time.time() - step_start)
            if time_until_next_step > 0:
                time.sleep(time_until_next_step)


if __name__ == '__main__':
    main()

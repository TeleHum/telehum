# Installation

These instructions use placeholder paths and do not assume the authors' machines.

## Software Dependencies

- Ubuntu 22.04 for ROS 2 nodes and gNB/UE-side scripts.
- ROS 2 Humble, including `rclpy`, `sensor_msgs`, `std_msgs`, `launch`, `launch_ros`, `rosbag2`, and `colcon`.
- Python 3.10 for ROS 2 workspaces and utility scripts.
- `rosdep` for ROS dependency resolution.
- Optional MuJoCo Python package for software-only SO101 simulation.
- Optional `rmw_zenoh_cpp` for the distributed 5G teleoperation setup.
- OpenAirInterface build environment for live gNB KPI capture.
- Docker for OAI 5G core-network deployment if reproducing the full system.

## Hardware Dependencies

The software-only review path does not require hardware. Full-system reproduction requires:

- SO101-compatible leader/follower robot hardware and serial access to the motor controllers.
- A 5G UE module, for example an RM520N_GL-class terminal module.
- A gNB host with a compatible CPU and USRP hardware, for example a B210-class device.
- UHD drivers and libraries for the USRP.
- A core-network or edge-server host configured for the OAI 5G core.
- Clock synchronization across participating machines, for example with `chrony`.

## Python Environment

```bash
cd /path/to/anonymized_artifact
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas numpy matplotlib scipy pyyaml
```

`scipy` is optional for some statistical analysis scripts. If it is unavailable, basic parsing and CSV inspection can still be performed.

## Teleoperation ROS 2 Workspace

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/teleoperation_ros2_pkg
rosdep install --from-paths src --ignore-src -r -y
python -m pip install -e ".[sim,test]"
colcon build --symlink-install
source install/setup.bash
```

Software-only MuJoCo demo:

```bash
ros2 launch so101_mujoco_pkg sim_demo.launch.py
```

For hardware runs, configure serial devices through local YAML files or launch arguments. Do not commit local serial paths, hostnames, or lab-specific calibration notes to the review artifact.

## ROS 2 KPI Toolkit

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
python -m pip install -e ".[dev]"
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Example KPI pipeline:

```bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  csv_output_path:=./output/kpi_metrics.csv
```

## OAI gNB KPI Recorder

The artifact includes a modified OAI source tree and helper scripts under `code/oai_gnb_kpi_recorder/`. It does not install OAI system dependencies automatically.

Use the deployment notes in `code/oai_gnb_kpi_recorder/README.md` and the OAI documentation under `code/oai_gnb_kpi_recorder/oai_custom/doc/` inside an existing OAI-capable environment. Keep local radio parameters, SIM details, IP addresses, and machine-specific paths outside the public artifact.

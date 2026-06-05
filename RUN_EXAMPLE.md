# Run Example

Run commands from the artifact root unless noted otherwise.

## Software-Only Path

This path does not require robot hardware or 5G radio equipment.

```bash
cd /path/to/anonymized_artifact
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas numpy pyyaml
```

Inspect the run-level dataset sample:

```bash
python - <<'PY'
from pathlib import Path
root = Path("networked_teleoperation_dataset/dataset")
runs = sorted(root.glob("delay*/user*"))
print("run_count", len(runs))
print("first_run", runs[0])
print("has_gnb_kpi", (runs[0] / "gnb_kpi.csv").exists())
print("has_rosbag_metadata", (runs[0] / "behavior_rosbag" / "metadata.yaml").exists())
PY
```

Build the ROS 2 workspaces if ROS 2 Humble is installed:

```bash
source /opt/ros/humble/setup.bash

cd /path/to/anonymized_artifact/code/teleoperation_ros2_pkg
colcon build --symlink-install

cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
colcon build --symlink-install
```

Optional simulation-only teleoperation demo:

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/teleoperation_ros2_pkg
source install/setup.bash
ros2 launch so101_mujoco_pkg sim_demo.launch.py
```

## Full-System Run Path

This path requires the physical teleoperation and 5G setup.

1. Prepare all machines with ROS 2 Humble and synchronized clocks.

```bash
sudo systemctl restart chrony
chronyc tracking
chronyc sources -v
```

2. Start the OAI core network and gNB using local, non-submitted configuration.

```bash
cd /path/to/anonymized_artifact/code/oai_gnb_kpi_recorder/oai_custom
source oaienv
cd cmake_targets
./build_oai -I
./build_oai -w USRP --gNB --ninja -c
```

Run the gNB from the built OAI tree using a local radio configuration file:

```bash
sudo ./nr-softmodem -O /path/to/local/gnb.conf --sa -E
```

3. Start the ROS 2 transport for the distributed run, for example Zenoh RMW.

```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run rmw_zenoh_cpp rmw_zenohd
```

4. Start teleoperation and KPI collection.

```bash
cd /path/to/anonymized_artifact/code/teleoperation_ros2_pkg
source install/setup.bash
ros2 launch so101_follower_pkg leader_follower.launch.py
```

```bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  csv_output_path:=./output/kpi_metrics.csv
```

5. Record ROS behavior bags and gNB KPI CSV files into a run directory matching the dataset schema:

```text
networked_teleoperation_dataset/dataset/
  delay<delay_ms>/
    user<id>/
      gnb_kpi.csv
      behavior_rosbag/
        metadata.yaml
        behavior_rosbag_0.db3
```

Store local IP addresses, SIM information, hostnames, and device paths outside this artifact.

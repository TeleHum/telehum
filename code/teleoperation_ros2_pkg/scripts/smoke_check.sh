#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

python3 -m compileall src/so101_mujoco_pkg src/so101_master_pkg src/so101_follower_pkg

if [[ -n "${ROS_DISTRO-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u
elif [[ -f "/opt/ros/humble/setup.bash" ]]; then
  set +u
  # shellcheck disable=SC1091
  source "/opt/ros/humble/setup.bash"
  set -u
fi

colcon list --base-paths src
python3 -m pytest tests

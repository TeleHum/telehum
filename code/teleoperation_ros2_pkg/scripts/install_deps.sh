#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
USE_VENV=1
USE_CONDA=0
CONDA_ENV="so101_mujoco_pkg"
PY_VER="3.10"
WITH_MUJOCO=0
WITH_TEST=0

usage() {
  cat <<'USAGE'
Usage: scripts/install_deps.sh [options]

Install Python dependencies from the workspace root `pyproject.toml`.
ROS 2 dependencies are still installed separately via `rosdep`.

Options:
  --system         Install into system Python (no venv)
  --conda [NAME]   Install into a conda env (default: so101_mujoco_pkg)
  --python VER     Python version for conda env (default: 3.10)
  --with-mujoco    Install MuJoCo + youzi-robot (sim/calib scripts)
  --with-test      Install test deps (pytest)
  -h, --help       Show this help

Examples:
  scripts/install_deps.sh
  scripts/install_deps.sh --with-mujoco
  scripts/install_deps.sh --system --with-mujoco
  scripts/install_deps.sh --conda
  scripts/install_deps.sh --conda myenv --python 3.9
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) USE_VENV=0; shift ;;
    --conda)
      USE_CONDA=1
      USE_VENV=0
      if [[ -n "${2-}" && "${2-}" != "--"* ]]; then
        CONDA_ENV="$2"
        shift 2
      else
        shift
      fi
      ;;
    --python)
      PY_VER="$2"
      shift 2
      ;;
    --with-mujoco) WITH_MUJOCO=1; shift ;;
    --with-test) WITH_TEST=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

PY=(python3)
PIP=(pip3)

ensure_conda() {
  if command -v conda >/dev/null 2>&1; then
    return 0
  fi
  # Try to load conda from common install locations
  if [[ -n "${CONDA_EXE-}" && -f "${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1090
    source "${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
  elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  fi
  command -v conda >/dev/null 2>&1
}

if [[ $USE_CONDA -eq 1 ]]; then
  if ! ensure_conda; then
    echo "conda not found. Please install Miniconda/Anaconda and retry." >&2
    exit 1
  fi
  if ! conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
    conda create -y -n "$CONDA_ENV" "python=${PY_VER}"
  fi
  PY=(conda run -n "$CONDA_ENV" python)
  PIP=(conda run -n "$CONDA_ENV" python -m pip)
else
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Please install Python 3 first." >&2
    exit 1
  fi
  if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found. Please install python3-pip first." >&2
    exit 1
  fi
fi

if [[ $USE_VENV -eq 1 ]]; then
  if [[ ! -d "$VENV_DIR" ]]; then
    "${PY[@]}" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  PY=(python)
  PIP=(pip)
fi

"${PIP[@]}" install --upgrade pip setuptools

EXTRAS=(hardware)
if [[ $WITH_MUJOCO -eq 1 ]]; then
  EXTRAS+=(sim)
fi
if [[ $WITH_TEST -eq 1 ]]; then
  EXTRAS+=(test)
fi

EXTRAS_CSV="$(IFS=,; echo "${EXTRAS[*]}")"
(cd "$ROOT_DIR" && "${PIP[@]}" install -e ".[${EXTRAS_CSV}]")

echo "Done."
echo "Installed Python dependencies from pyproject extras: ${EXTRAS_CSV}"
echo "ROS 2 packages are still built with: colcon build --symlink-install"
if [[ $USE_VENV -eq 1 ]]; then
  echo "Activated venv: $VENV_DIR"
  echo "To use it later: source \"$VENV_DIR/bin/activate\""
fi

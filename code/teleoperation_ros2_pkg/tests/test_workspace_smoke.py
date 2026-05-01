from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PACKAGES = {"so101_mujoco_pkg", "so101_master_pkg", "so101_follower_pkg"}


def test_key_paths_exist() -> None:
    expected_paths = [
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "scripts" / "install_deps.sh",
        ROOT / "scripts" / "smoke_check.sh",
        ROOT / "src" / "so101_mujoco_pkg" / "launch" / "sim_demo.launch.py",
        ROOT / "src" / "so101_follower_pkg" / "launch" / "leader_follower.launch.py",
        ROOT / "src" / "so101_6dof" / "push_cube_loop.xml",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing expected path: {path}"


def test_install_deps_help() -> None:
    result = subprocess.run(
        ["bash", "scripts/install_deps.sh", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--with-mujoco" in result.stdout
    assert "--with-test" in result.stdout


def test_package_metadata_has_no_todo() -> None:
    for package_xml in ROOT.glob("src/*/package.xml"):
        package = ET.parse(package_xml).getroot()
        text_blob = " ".join(node.text or "" for node in package.iter())
        assert "TODO" not in text_blob, f"Found TODO in {package_xml}"


def test_python_dependencies_are_not_declared_in_package_xml() -> None:
    disallowed = {"python3-numpy"}

    for package_xml in ROOT.glob("src/*/package.xml"):
        package = ET.parse(package_xml).getroot()
        depends = {node.text for node in package.iter() if node.text}
        assert disallowed.isdisjoint(depends), (
            f"Found runtime Python dependency in {package_xml}; keep it in pyproject.toml"
        )


def test_so101_mujoco_pkg_does_not_duplicate_master_node() -> None:
    duplicate_node = ROOT / "src" / "so101_mujoco_pkg" / "so101_mujoco_pkg" / "so101_master_node.py"
    assert not duplicate_node.exists(), "Duplicate master node should live only in so101_master_pkg"


def test_calibration_script_has_single_home() -> None:
    duplicated_calib = ROOT / "src" / "so101_mujoco_pkg" / "config" / "so101_calib.py"
    canonical_calib = ROOT / "src" / "so101_master_pkg" / "config" / "so101_calib.py"

    assert not duplicated_calib.exists(), "Calibration script should live only in so101_master_pkg"
    assert canonical_calib.exists(), "Canonical calibration script is missing"


def test_colcon_lists_expected_packages() -> None:
    result = subprocess.run(
        ["colcon", "list", "--base-paths", "src"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    found = {
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip()
    }
    assert EXPECTED_PACKAGES.issubset(found)

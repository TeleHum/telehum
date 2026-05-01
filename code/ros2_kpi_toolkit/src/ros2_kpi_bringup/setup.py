from glob import glob

from setuptools import find_packages, setup

package_name = "ros2_kpi_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anonymous Authors",
    maintainer_email="anonymous@example.com",
    description="Bringup package for the ROS 2 KPI toolkit.",
    license="Apache-2.0",
    tests_require=["pytest"],
)


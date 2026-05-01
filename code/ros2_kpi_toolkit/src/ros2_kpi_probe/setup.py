from setuptools import find_packages, setup

package_name = "ros2_kpi_probe"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anonymous Authors",
    maintainer_email="anonymous@example.com",
    description="Probe publisher and subscriber nodes for ROS 2 KPI measurement.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "probe_publisher = ros2_kpi_probe.probe_publisher:main",
            "probe_subscriber = ros2_kpi_probe.probe_subscriber:main",
            "topic_monitor = ros2_kpi_probe.topic_monitor:main",
        ],
    },
)

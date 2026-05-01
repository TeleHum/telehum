from setuptools import find_packages, setup

package_name = "ros2_kpi_collector"

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
    description="Collector node that aggregates ROS 2 KPI samples.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "metrics_node = ros2_kpi_collector.metrics_node:main",
        ],
    },
)


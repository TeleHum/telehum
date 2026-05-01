from setuptools import find_packages, setup

package_name = "ros2_kpi_exporter"

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
    description="CSV exporter for ROS 2 KPI window statistics.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "csv_exporter = ros2_kpi_exporter.csv_exporter:main",
        ],
    },
)


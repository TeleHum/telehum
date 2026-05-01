import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'so101_mujoco_pkg'


def glob_files(pattern):
    return [path for path in glob(pattern) if os.path.isfile(path)]


setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob_files('config/*')),
        ('share/' + package_name + '/launch', glob_files('launch/*.py')),
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Anonymous Authors',
    maintainer_email='anonymous@example.com',
    description=(
        'ROS 2 MuJoCo visualization and demo nodes for the SO101 workspace.'
    ),
    license='MIT',
    entry_points={
        'console_scripts': [
            'so101_mujoco_node = so101_mujoco_pkg.so101_mujoco_node:main',
            'demo_joint_publisher = so101_mujoco_pkg.demo_joint_publisher:main',
        ],
    },
)

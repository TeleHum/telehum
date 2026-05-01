from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare('so101_master_pkg')

    params_file = LaunchConfiguration('params_file')
    publish_delay_ms = LaunchConfiguration('publish_delay_ms')

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'params_file',
                default_value=PathJoinSubstitution([pkg_share, 'config', 'motors.yaml']),
                description='Path to the YAML file with motor and master parameters.',
            ),
            DeclareLaunchArgument(
                'publish_delay_ms',
                default_value='0.0',
                description='Delay, in milliseconds, before publishing sampled master joint data.',
            ),
            Node(
                package='so101_master_pkg',
                executable='so101_master_node',
                name='so101_master_node',
                output='screen',
                parameters=[params_file, {'publish_delay_ms': publish_delay_ms}],
            ),
        ]
    )

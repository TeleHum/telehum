from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    master_pkg_share = FindPackageShare('so101_master_pkg')
    follower_pkg_share = FindPackageShare('so101_follower_pkg')

    master_params_file = LaunchConfiguration('master_params_file')
    follower_params_file = LaunchConfiguration('follower_params_file')
    master_topic = LaunchConfiguration('master_topic')
    follower_topic = LaunchConfiguration('follower_topic')
    master_publish_delay_ms = LaunchConfiguration('master_publish_delay_ms')

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'master_params_file',
                default_value=PathJoinSubstitution([master_pkg_share, 'config', 'motors.yaml']),
                description='Path to the YAML file with master hardware parameters.',
            ),
            DeclareLaunchArgument(
                'follower_params_file',
                default_value=PathJoinSubstitution(
                    [follower_pkg_share, 'config', 'follower_motors.yaml']
                ),
                description='Path to the YAML file with follower hardware parameters.',
            ),
            DeclareLaunchArgument(
                'master_topic',
                default_value='master/joint_states',
                description='SequencedJointState topic published by the master arm.',
            ),
            DeclareLaunchArgument(
                'follower_topic',
                default_value='follower/joint_states',
                description='SequencedJointState topic published as follower feedback.',
            ),
            DeclareLaunchArgument(
                'master_publish_delay_ms',
                default_value='0.0',
                description='Delay, in milliseconds, before publishing sampled master joint data.',
            ),
            Node(
                package='so101_master_pkg',
                executable='so101_master_node',
                name='so101_master_node',
                output='screen',
                parameters=[
                    master_params_file,
                    {
                        'joint_states_topic': master_topic,
                        'publish_delay_ms': master_publish_delay_ms,
                    },
                ],
            ),
            Node(
                package='so101_follower_pkg',
                executable='so101_follower_node',
                name='so101_follower_node',
                output='screen',
                parameters=[
                    follower_params_file,
                    {
                        'input_topic': master_topic,
                        'joint_states_topic': follower_topic,
                    },
                ],
            ),
        ]
    )

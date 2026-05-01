from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare('so101_follower_pkg')

    params_file = LaunchConfiguration('params_file')
    input_topic = LaunchConfiguration('input_topic')
    feedback_topic = LaunchConfiguration('feedback_topic')

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'params_file',
                default_value=PathJoinSubstitution([pkg_share, 'config', 'follower_motors.yaml']),
                description='Path to the YAML file with follower hardware parameters.',
            ),
            DeclareLaunchArgument(
                'input_topic',
                default_value='master/joint_states',
                description='SequencedJointState topic to subscribe for master commands.',
            ),
            DeclareLaunchArgument(
                'feedback_topic',
                default_value='follower/joint_states',
                description='SequencedJointState topic to publish follower feedback.',
            ),
            Node(
                package='so101_follower_pkg',
                executable='so101_follower_node',
                name='so101_follower_node',
                output='screen',
                parameters=[
                    params_file,
                    {
                        'input_topic': input_topic,
                        'joint_states_topic': feedback_topic,
                    },
                ],
            ),
        ]
    )

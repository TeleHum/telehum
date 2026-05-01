from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    master_pkg_share = FindPackageShare('so101_master_pkg')

    params_file = LaunchConfiguration('params_file')
    xml_path = LaunchConfiguration('xml_path')
    joint_states_topic = LaunchConfiguration('joint_states_topic')
    wait_for_first_msg = LaunchConfiguration('wait_for_first_msg')
    input_delay_ms = LaunchConfiguration('input_delay_ms')
    publish_delay_ms = LaunchConfiguration('publish_delay_ms')

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'params_file',
                default_value=PathJoinSubstitution([master_pkg_share, 'config', 'motors.yaml']),
                description='Path to the YAML file with master hardware parameters.',
            ),
            DeclareLaunchArgument(
                'xml_path',
                default_value='auto',
                description='Path to the MuJoCo XML model (use auto to search workspace).',
            ),
            DeclareLaunchArgument(
                'joint_states_topic',
                default_value='master/joint_states',
                description='SequencedJointState topic consumed by the MuJoCo node.',
            ),
            DeclareLaunchArgument(
                'wait_for_first_msg',
                default_value='true',
                description='Wait for first joint message before opening viewer.',
            ),
            DeclareLaunchArgument(
                'input_delay_ms',
                default_value='0.0',
                description='Artificial delay, in milliseconds, before MuJoCo applies received joint data.',
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
                parameters=[
                    params_file,
                    {
                        'joint_states_topic': joint_states_topic,
                        'publish_delay_ms': publish_delay_ms,
                    },
                ],
            ),
            Node(
                package='so101_mujoco_pkg',
                executable='so101_mujoco_node',
                name='so101_mujoco_node',
                output='screen',
                parameters=[
                    {
                        'joint_states_topic': joint_states_topic,
                        'xml_path': xml_path,
                        'wait_for_first_msg': wait_for_first_msg,
                        'input_delay_ms': input_delay_ms,
                        'input_offsets': [0.0, 0.0, 0.0, 0.0, 0.0, -0.5727143896],
                        'input_scales': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0502528322],
                    }
                ],
            ),
        ]
    )

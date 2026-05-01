from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    xml_path = LaunchConfiguration('xml_path')
    joint_states_topic = LaunchConfiguration('joint_states_topic')
    amplitude = LaunchConfiguration('amplitude')
    period = LaunchConfiguration('period')
    wait_for_first_msg = LaunchConfiguration('wait_for_first_msg')
    input_delay_ms = LaunchConfiguration('input_delay_ms')

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'xml_path',
                default_value='auto',
                description='Path to the MuJoCo XML model (use auto to search workspace).',
            ),
            DeclareLaunchArgument(
                'joint_states_topic',
                default_value='master/joint_states',
                description='SequencedJointState topic shared between demo publisher and MuJoCo.',
            ),
            DeclareLaunchArgument(
                'amplitude',
                default_value='0.35',
                description='Sine-wave amplitude in radians for the demo publisher.',
            ),
            DeclareLaunchArgument(
                'period',
                default_value='4.0',
                description='Sine-wave period in seconds for the demo publisher.',
            ),
            DeclareLaunchArgument(
                'wait_for_first_msg',
                default_value='false',
                description='Wait for the first joint message before opening the viewer.',
            ),
            DeclareLaunchArgument(
                'input_delay_ms',
                default_value='0.0',
                description='Artificial delay, in milliseconds, before MuJoCo applies received joint data.',
            ),
            Node(
                package='so101_mujoco_pkg',
                executable='demo_joint_publisher',
                name='demo_joint_publisher',
                output='screen',
                parameters=[
                    {
                        'joint_states_topic': joint_states_topic,
                        'joint_names': [
                            'shoulder_pan',
                            'shoulder_lift',
                            'elbow_flex',
                            'wrist_flex',
                            'wrist_roll',
                            'gripper',
                        ],
                        'publish_rate': 30.0,
                        'amplitude': amplitude,
                        'period': period,
                    }
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
                    }
                ],
            ),
        ]
    )

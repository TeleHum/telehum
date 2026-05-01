from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    topic_type = LaunchConfiguration("topic_type")
    window_size_sec = LaunchConfiguration("window_size_sec")
    metrics_publish_period_sec = LaunchConfiguration("metrics_publish_period_sec")
    csv_output_path = LaunchConfiguration("csv_output_path")
    max_file_size_mb = LaunchConfiguration("max_file_size_mb")
    max_files_per_run = LaunchConfiguration("max_files_per_run")
    qos_profile_mode = LaunchConfiguration("qos_profile_mode")

    declared_arguments = [
        DeclareLaunchArgument(
            "topic_type",
            default_value="",
            description="Optional fixed ROS 2 message type for /master/joint_states. Leave empty to auto-discover from publishers.",
        ),
        DeclareLaunchArgument(
            "window_size_sec",
            default_value="5.0",
            description="Sliding window size used by the metrics collector.",
        ),
        DeclareLaunchArgument(
            "metrics_publish_period_sec",
            default_value="1.0",
            description="How often the collector publishes aggregated window metrics.",
        ),
        DeclareLaunchArgument(
            "csv_output_path",
            default_value="./output/kpi_metrics.csv",
            description="CSV output base path or legacy .csv path.",
        ),
        DeclareLaunchArgument(
            "max_file_size_mb",
            default_value="10.0",
            description="Maximum size of each CSV part file before rollover.",
        ),
        DeclareLaunchArgument(
            "max_files_per_run",
            default_value="10",
            description="Maximum number of CSV part files retained in a single run directory.",
        ),
        DeclareLaunchArgument(
            "qos_profile_mode",
            default_value="match_publisher",
            description="QoS behavior in generic_topic mode: match_publisher or manual.",
        ),
    ]

    pipeline_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("ros2_kpi_bringup"),
                    "launch",
                    "kpi_pipeline.launch.py",
                ]
            )
        ),
        launch_arguments={
            "measurement_mode": "generic_topic",
            "enable_publisher": "false",
            "enable_subscriber": "true",
            "enable_collector": "true",
            "enable_exporter": "true",
            "topic_name": "/master/joint_states",
            "topic_type": topic_type,
            "timestamp_field": "header.stamp",
            "sequence_field": "seq",
            "qos_profile_mode": qos_profile_mode,
            "sample_topic_name": "/master/joint_states_kpi_samples",
            "metrics_topic_name": "/kpi_window_stats",
            "dashboard_metrics_topic_name": "/kpi_metrics",
            "window_size_sec": window_size_sec,
            "metrics_publish_period_sec": metrics_publish_period_sec,
            "csv_output_path": csv_output_path,
            "max_file_size_mb": max_file_size_mb,
            "max_files_per_run": max_files_per_run,
        }.items(),
    )

    return LaunchDescription(declared_arguments + [pipeline_launch])

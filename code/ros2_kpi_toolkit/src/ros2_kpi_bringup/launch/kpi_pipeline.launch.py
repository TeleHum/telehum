from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    measurement_mode = LaunchConfiguration("measurement_mode")
    topic_name = LaunchConfiguration("topic_name")
    sample_topic_name = LaunchConfiguration("sample_topic_name")
    metrics_topic_name = LaunchConfiguration("metrics_topic_name")
    dashboard_metrics_topic_name = LaunchConfiguration("dashboard_metrics_topic_name")
    topic_type = LaunchConfiguration("topic_type")
    timestamp_field = LaunchConfiguration("timestamp_field")
    sequence_field = LaunchConfiguration("sequence_field")
    qos_profile_mode = LaunchConfiguration("qos_profile_mode")
    publish_rate_hz = LaunchConfiguration("publish_rate_hz")
    payload_size = LaunchConfiguration("payload_size")
    window_size_sec = LaunchConfiguration("window_size_sec")
    csv_output_path = LaunchConfiguration("csv_output_path")
    max_file_size_mb = LaunchConfiguration("max_file_size_mb")
    max_files_per_run = LaunchConfiguration("max_files_per_run")
    qos_reliability = LaunchConfiguration("qos_reliability")
    qos_history_depth = LaunchConfiguration("qos_history_depth")
    metrics_publish_period_sec = LaunchConfiguration("metrics_publish_period_sec")
    enable_publisher = LaunchConfiguration("enable_publisher")
    enable_subscriber = LaunchConfiguration("enable_subscriber")
    enable_collector = LaunchConfiguration("enable_collector")
    enable_exporter = LaunchConfiguration("enable_exporter")

    declared_arguments = [
        DeclareLaunchArgument(
            "enable_publisher",
            default_value="true",
            description="Whether to start the UE-side probe publisher in probe mode.",
        ),
        DeclareLaunchArgument(
            "enable_subscriber",
            default_value="true",
            description="Whether to start the receiving-side monitor node.",
        ),
        DeclareLaunchArgument(
            "enable_collector",
            default_value="true",
            description="Whether to start the sliding-window metrics collector.",
        ),
        DeclareLaunchArgument(
            "enable_exporter",
            default_value="true",
            description="Whether to start the CSV exporter.",
        ),
        DeclareLaunchArgument(
            "measurement_mode",
            default_value="probe",
            description="Measurement mode: 'probe' for KpiProbe traffic, 'generic_topic' for arbitrary business topics.",
        ),
        DeclareLaunchArgument(
            "topic_name",
            default_value="/kpi_probe",
            description="Measured ROS 2 topic name.",
        ),
        DeclareLaunchArgument(
            "sample_topic_name",
            default_value="/kpi_probe_samples",
            description="Internal topic used by the subscriber to publish per-message KPI samples.",
        ),
        DeclareLaunchArgument(
            "metrics_topic_name",
            default_value="/kpi_window_stats",
            description="Legacy internal topic used by the collector to publish window statistics.",
        ),
        DeclareLaunchArgument(
            "dashboard_metrics_topic_name",
            default_value="/kpi_metrics",
            description="Structured KPI topic intended for PlotJuggler, Foxglove, or custom dashboards.",
        ),
        DeclareLaunchArgument(
            "topic_type",
            default_value="",
            description="ROS 2 message type such as std_msgs/msg/String. Leave empty to auto-discover in generic_topic mode.",
        ),
        DeclareLaunchArgument(
            "timestamp_field",
            default_value="auto",
            description="Field path for send timestamp extraction in generic_topic mode, for example header.stamp. Use auto or disable with an empty string.",
        ),
        DeclareLaunchArgument(
            "sequence_field",
            default_value="auto",
            description="Field path for sequence extraction in generic_topic mode, for example seq or meta.sequence_id. Use auto or disable with an empty string.",
        ),
        DeclareLaunchArgument(
            "qos_profile_mode",
            default_value="match_publisher",
            description="QoS behavior in generic_topic mode: match_publisher or manual.",
        ),
        DeclareLaunchArgument(
            "publish_rate_hz",
            default_value="10.0",
            description="Probe publisher rate in Hz.",
        ),
        DeclareLaunchArgument(
            "payload_size",
            default_value="256",
            description="Payload size of each probe message in bytes.",
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
            description="CSV output base path or legacy .csv path; exporter creates a per-run directory underneath it.",
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
            "qos_reliability",
            default_value="reliable",
            description="QoS reliability policy for probe publisher/subscriber: reliable or best_effort.",
        ),
        DeclareLaunchArgument(
            "qos_history_depth",
            default_value="10",
            description="QoS KEEP_LAST history depth for probe publisher/subscriber.",
        ),
    ]

    nodes = [
        Node(
            package="ros2_kpi_probe",
            executable="probe_publisher",
            name="probe_publisher",
            output="screen",
            condition=IfCondition(
                PythonExpression(
                    [
                        "'",
                        enable_publisher,
                        "' == 'true' and '",
                        measurement_mode,
                        "' == 'probe'",
                    ]
                )
            ),
            parameters=[
                {"use_sim_time": False},
                {
                    "topic_name": topic_name,
                    "publish_rate_hz": ParameterValue(
                        publish_rate_hz,
                        value_type=float,
                    ),
                    "payload_size": ParameterValue(payload_size, value_type=int),
                    "qos_reliability": ParameterValue(
                        qos_reliability,
                        value_type=str,
                    ),
                    "qos_history_depth": ParameterValue(
                        qos_history_depth,
                        value_type=int,
                    ),
                },
            ],
        ),
        Node(
            package="ros2_kpi_probe",
            executable="probe_subscriber",
            name="probe_subscriber",
            output="screen",
            condition=IfCondition(
                PythonExpression(
                    [
                        "'",
                        enable_subscriber,
                        "' == 'true' and '",
                        measurement_mode,
                        "' == 'probe'",
                    ]
                )
            ),
            parameters=[
                {"use_sim_time": False},
                {
                    "topic_name": topic_name,
                    "sample_topic_name": sample_topic_name,
                    "qos_reliability": ParameterValue(
                        qos_reliability,
                        value_type=str,
                    ),
                    "qos_history_depth": ParameterValue(
                        qos_history_depth,
                        value_type=int,
                    ),
                },
            ],
        ),
        Node(
            package="ros2_kpi_probe",
            executable="topic_monitor",
            name="topic_monitor",
            output="screen",
            condition=IfCondition(
                PythonExpression(
                    [
                        "'",
                        enable_subscriber,
                        "' == 'true' and '",
                        measurement_mode,
                        "' == 'generic_topic'",
                    ]
                )
            ),
            parameters=[
                {"use_sim_time": False},
                {
                    "topic_name": topic_name,
                    "sample_topic_name": sample_topic_name,
                    "topic_type": topic_type,
                    "timestamp_field": timestamp_field,
                    "sequence_field": sequence_field,
                    "qos_profile_mode": ParameterValue(
                        qos_profile_mode,
                        value_type=str,
                    ),
                    "qos_reliability": ParameterValue(
                        qos_reliability,
                        value_type=str,
                    ),
                    "qos_history_depth": ParameterValue(
                        qos_history_depth,
                        value_type=int,
                    ),
                },
            ],
        ),
        Node(
            package="ros2_kpi_collector",
            executable="metrics_node",
            name="metrics_node",
            output="screen",
            condition=IfCondition(enable_collector),
            parameters=[
                {"use_sim_time": False},
                {
                    "topic_name": topic_name,
                    "sample_topic_name": sample_topic_name,
                    "metrics_topic_name": metrics_topic_name,
                    "dashboard_metrics_topic_name": dashboard_metrics_topic_name,
                    "window_size_sec": ParameterValue(
                        window_size_sec,
                        value_type=float,
                    ),
                    "metrics_publish_period_sec": ParameterValue(
                        metrics_publish_period_sec,
                        value_type=float,
                    ),
                },
            ],
        ),
        Node(
            package="ros2_kpi_exporter",
            executable="csv_exporter",
            name="csv_exporter",
            output="screen",
            condition=IfCondition(enable_exporter),
            parameters=[
                {"use_sim_time": False},
                {
                    "metrics_topic_name": metrics_topic_name,
                    "csv_output_path": csv_output_path,
                    "max_file_size_mb": ParameterValue(
                        max_file_size_mb,
                        value_type=float,
                    ),
                    "max_files_per_run": ParameterValue(
                        max_files_per_run,
                        value_type=int,
                    ),
                    "topic_name": topic_name,
                    "publish_rate_hz": ParameterValue(
                        publish_rate_hz,
                        value_type=float,
                    ),
                    "payload_size": ParameterValue(payload_size, value_type=int),
                    "qos_reliability": ParameterValue(
                        qos_reliability,
                        value_type=str,
                    ),
                    "qos_history_depth": ParameterValue(
                        qos_history_depth,
                        value_type=int,
                    ),
                    "window_size_sec": ParameterValue(
                        window_size_sec,
                        value_type=float,
                    ),
                    "measurement_mode": ParameterValue(
                        measurement_mode,
                        value_type=str,
                    ),
                    "topic_type": ParameterValue(topic_type, value_type=str),
                    "timestamp_field": ParameterValue(
                        timestamp_field,
                        value_type=str,
                    ),
                    "sequence_field": ParameterValue(
                        sequence_field,
                        value_type=str,
                    ),
                },
            ],
        ),
    ]

    return LaunchDescription(declared_arguments + nodes)

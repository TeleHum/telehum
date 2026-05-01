from types import SimpleNamespace

from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSReliabilityPolicy

from ros2_kpi_probe.measurement_utils import sanitize_discovered_qos_profile
from ros2_kpi_probe.topic_monitor import (
    extract_sequence_value,
    extract_timestamp_ns,
    normalize_topic_type,
)


def test_normalize_topic_type_accepts_short_form() -> None:
    assert normalize_topic_type("std_msgs/String") == "std_msgs/msg/String"
    assert (
        normalize_topic_type("geometry_msgs/msg/Twist")
        == "geometry_msgs/msg/Twist"
    )


def test_extract_timestamp_ns_prefers_header_stamp_in_auto_mode() -> None:
    message = SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=12, nanosec=34)),
    )

    assert extract_timestamp_ns(message, "auto") == 12_000_000_034


def test_extract_sequence_value_supports_custom_field_path() -> None:
    message = SimpleNamespace(meta=SimpleNamespace(sequence_id=42))

    assert extract_sequence_value(message, "meta.sequence_id") == 42


def test_extract_timestamp_ns_returns_none_for_zero_stamp() -> None:
    message = SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=0)),
    )

    assert extract_timestamp_ns(message, "header.stamp") is None


def test_sanitize_discovered_qos_profile_replaces_unknown_policies() -> None:
    raw_qos = SimpleNamespace(
        history=QoSHistoryPolicy.UNKNOWN,
        depth=0,
        reliability=QoSReliabilityPolicy.UNKNOWN,
        durability=QoSDurabilityPolicy.UNKNOWN,
    )

    sanitized_qos, was_sanitized = sanitize_discovered_qos_profile(raw_qos, 10)

    assert was_sanitized is True
    assert sanitized_qos.history == QoSHistoryPolicy.KEEP_LAST
    assert sanitized_qos.depth == 10
    assert sanitized_qos.reliability == QoSReliabilityPolicy.BEST_EFFORT
    assert sanitized_qos.durability == QoSDurabilityPolicy.VOLATILE


def test_sanitize_discovered_qos_profile_preserves_supported_policies() -> None:
    raw_qos = SimpleNamespace(
        history=QoSHistoryPolicy.KEEP_ALL,
        depth=32,
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    )

    sanitized_qos, was_sanitized = sanitize_discovered_qos_profile(raw_qos, 10)

    assert was_sanitized is False
    assert sanitized_qos.history == QoSHistoryPolicy.KEEP_ALL
    assert sanitized_qos.depth == 32
    assert sanitized_qos.reliability == QoSReliabilityPolicy.RELIABLE
    assert sanitized_qos.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL

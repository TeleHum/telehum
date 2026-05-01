import time
from typing import Any, Final, Optional

import rclpy
from builtin_interfaces.msg import Time as TimeMsg
from rclpy.node import Node
from rclpy.serialization import serialize_message
from rosidl_runtime_py.utilities import get_message

from ros2_kpi_interfaces.msg import KpiSample
from ros2_kpi_probe.measurement_utils import (
    build_qos_profile,
    compute_sample_metrics,
    sanitize_discovered_qos_profile,
)

DEFAULT_TOPIC_NAME: Final[str] = "/kpi_probe"
DEFAULT_SAMPLE_TOPIC_NAME: Final[str] = "/kpi_probe_samples"
DEFAULT_TOPIC_TYPE: Final[str] = ""
DEFAULT_TIMESTAMP_FIELD: Final[str] = "auto"
DEFAULT_SEQUENCE_FIELD: Final[str] = "auto"
DEFAULT_QOS_PROFILE_MODE: Final[str] = "match_publisher"
DEFAULT_QOS_RELIABILITY: Final[str] = "reliable"
DEFAULT_QOS_DEPTH: Final[int] = 10
DEFAULT_DISCOVERY_PERIOD_SEC: Final[float] = 1.0

AUTO_TIMESTAMP_FIELDS: Final[tuple[str, ...]] = (
    "header.stamp",
    "stamp",
    "source_stamp",
)
AUTO_SEQUENCE_FIELDS: Final[tuple[str, ...]] = (
    "seq",
    "sequence",
    "sequence_id",
)
DISABLED_FIELD_VALUES: Final[set[str]] = {"", "none", "disable", "disabled", "false"}
WAIT_LOG_INTERVAL_SEC: Final[float] = 5.0
MISSING_FIELD: Final[object] = object()


def normalize_topic_type(topic_type: str) -> str:
    normalized = topic_type.strip()
    if normalized.count("/") == 1:
        package_name, message_name = normalized.split("/", maxsplit=1)
        return f"{package_name}/msg/{message_name}"
    return normalized


def is_field_disabled(field_path: str) -> bool:
    return field_path.strip().lower() in DISABLED_FIELD_VALUES


def resolve_candidate_paths(
    field_path: str,
    auto_candidates: tuple[str, ...],
) -> tuple[str, ...]:
    normalized = field_path.strip()
    normalized_lower = normalized.lower()
    if normalized_lower == "auto":
        return auto_candidates
    if normalized_lower in DISABLED_FIELD_VALUES:
        return ()
    return (normalized,)


def get_nested_field_value(message: Any, field_path: str) -> Any:
    current_value = message
    for attribute_name in field_path.split("."):
        if not hasattr(current_value, attribute_name):
            return MISSING_FIELD
        current_value = getattr(current_value, attribute_name)
    return current_value


def convert_time_like_to_ns(value: Any) -> Optional[int]:
    if value is None:
        return None
    if hasattr(value, "sec") and hasattr(value, "nanosec"):
        timestamp_ns = int(value.sec) * 1_000_000_000 + int(value.nanosec)
        return timestamp_ns if timestamp_ns > 0 else None
    if hasattr(value, "nanoseconds"):
        timestamp_ns = int(value.nanoseconds)
        return timestamp_ns if timestamp_ns > 0 else None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value * 1_000_000_000) if value > 0.0 else None
    return None


def extract_timestamp_ns(message: Any, field_path: str) -> Optional[int]:
    for candidate_path in resolve_candidate_paths(field_path, AUTO_TIMESTAMP_FIELDS):
        value = get_nested_field_value(message, candidate_path)
        if value is MISSING_FIELD:
            continue
        timestamp_ns = convert_time_like_to_ns(value)
        if timestamp_ns is not None:
            return timestamp_ns
    return None


def convert_integer_like(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        integer_value = int(value)
        return integer_value if integer_value >= 0 else None
    try:
        integer_value = int(value)
    except (TypeError, ValueError):
        return None
    return integer_value if integer_value >= 0 else None


def extract_sequence_value(message: Any, field_path: str) -> Optional[int]:
    for candidate_path in resolve_candidate_paths(field_path, AUTO_SEQUENCE_FIELDS):
        value = get_nested_field_value(message, candidate_path)
        if value is MISSING_FIELD:
            continue
        sequence_value = convert_integer_like(value)
        if sequence_value is not None:
            return sequence_value
    return None


def to_time_msg(timestamp_ns: Optional[int]) -> TimeMsg:
    time_message = TimeMsg()
    if timestamp_ns is None or timestamp_ns <= 0:
        return time_message
    time_message.sec = int(timestamp_ns // 1_000_000_000)
    time_message.nanosec = int(timestamp_ns % 1_000_000_000)
    return time_message


def estimate_serialized_size(message: Any) -> int:
    return len(serialize_message(message))


def resolve_message_type(topic_type: str):
    normalized_topic_type = normalize_topic_type(topic_type)
    if not normalized_topic_type:
        raise ValueError("topic_type must not be empty.")

    try:
        return get_message(normalized_topic_type)
    except (AttributeError, ImportError, ModuleNotFoundError, ValueError) as exc:
        raise ValueError(
            f"Unable to resolve topic_type '{normalized_topic_type}': {exc}"
        ) from exc


class TopicMonitor(Node):
    def __init__(self) -> None:
        super().__init__("topic_monitor")

        self.declare_parameter("topic_name", DEFAULT_TOPIC_NAME)
        self.declare_parameter("sample_topic_name", DEFAULT_SAMPLE_TOPIC_NAME)
        self.declare_parameter("topic_type", DEFAULT_TOPIC_TYPE)
        self.declare_parameter("timestamp_field", DEFAULT_TIMESTAMP_FIELD)
        self.declare_parameter("sequence_field", DEFAULT_SEQUENCE_FIELD)
        self.declare_parameter("qos_profile_mode", DEFAULT_QOS_PROFILE_MODE)
        self.declare_parameter("qos_reliability", DEFAULT_QOS_RELIABILITY)
        self.declare_parameter("qos_history_depth", DEFAULT_QOS_DEPTH)
        self.declare_parameter("discovery_poll_period_sec", DEFAULT_DISCOVERY_PERIOD_SEC)

        self._topic_name = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )
        self._sample_topic_name = (
            self.get_parameter("sample_topic_name").get_parameter_value().string_value
        )
        self._topic_type = normalize_topic_type(
            self.get_parameter("topic_type").get_parameter_value().string_value
        )
        self._timestamp_field = (
            self.get_parameter("timestamp_field").get_parameter_value().string_value
        )
        self._sequence_field = (
            self.get_parameter("sequence_field").get_parameter_value().string_value
        )
        self._qos_profile_mode = (
            self.get_parameter("qos_profile_mode")
            .get_parameter_value()
            .string_value.strip()
            .lower()
        )
        self._qos_reliability = (
            self.get_parameter("qos_reliability").get_parameter_value().string_value
        )
        self._qos_history_depth = int(
            self.get_parameter("qos_history_depth").get_parameter_value().integer_value
        )
        discovery_poll_period_sec = max(
            0.1,
            self.get_parameter("discovery_poll_period_sec")
            .get_parameter_value()
            .double_value,
        )

        if self._qos_profile_mode not in {"match_publisher", "manual"}:
            raise ValueError(
                "qos_profile_mode must be either 'match_publisher' or 'manual'."
            )

        self._sample_publisher = self.create_publisher(
            KpiSample,
            self._sample_topic_name,
            100,
        )
        self._subscription = None
        self._discovery_timer = self.create_timer(
            discovery_poll_period_sec,
            self._ensure_subscription,
        )

        self._last_receive_ns: Optional[int] = None
        self._last_seq: Optional[int] = None
        self._last_wait_log_monotonic = 0.0
        self._warned_missing_timestamp = False
        self._warned_missing_sequence = False
        self._warned_payload_size_failure = False
        self._warned_multiple_qos_profiles = False
        self._warned_multiple_topic_types = False
        self._warned_configured_type_mismatch = False

        self.get_logger().info(
            "Preparing generic topic monitor for topic='%s', topic_type='%s', "
            "timestamp_field='%s', sequence_field='%s', qos_profile_mode='%s'"
            % (
                self._topic_name,
                self._topic_type or "<auto>",
                self._timestamp_field,
                self._sequence_field,
                self._qos_profile_mode,
            )
        )

        self._ensure_subscription()

    def _ensure_subscription(self) -> None:
        if self._subscription is not None:
            return

        publisher_infos = self.get_publishers_info_by_topic(self._topic_name)
        topic_type = self._resolve_topic_type(publisher_infos)
        if topic_type is None:
            return

        qos_profile = self._resolve_qos_profile(publisher_infos)
        if qos_profile is None:
            return

        message_type = resolve_message_type(topic_type)
        try:
            self._subscription = self.create_subscription(
                message_type,
                self._topic_name,
                self._on_message,
                qos_profile,
            )
        except Exception as exc:
            self.get_logger().warning(
                "Failed to create subscription for topic '%s' with message type "
                "'%s': %s. Will retry while waiting for publisher discovery/QoS."
                % (self._topic_name, topic_type, exc)
            )
            return
        self._topic_type = topic_type

        if self._discovery_timer is not None:
            self.destroy_timer(self._discovery_timer)
            self._discovery_timer = None

        self.get_logger().info(
            "Monitoring topic '%s' with message type '%s' and publishing samples to '%s'"
            % (self._topic_name, self._topic_type, self._sample_topic_name)
        )

    def _resolve_topic_type(self, publisher_infos: list[Any]) -> Optional[str]:
        discovered_types = sorted(
            {
                normalize_topic_type(publisher_info.topic_type)
                for publisher_info in publisher_infos
                if getattr(publisher_info, "topic_type", "")
            }
        )

        if self._topic_type:
            if (
                discovered_types
                and self._topic_type not in discovered_types
                and not self._warned_configured_type_mismatch
            ):
                self.get_logger().warning(
                    "Configured topic_type '%s' does not match discovered publisher "
                    "types on '%s': %s. The monitor may receive no samples. Set "
                    "topic_type to the exact 'ros2 topic type' result or leave it "
                    "empty to auto-discover."
                    % (self._topic_type, self._topic_name, discovered_types)
                )
                self._warned_configured_type_mismatch = True
            return self._topic_type

        if not discovered_types:
            self._maybe_log_waiting(
                "Waiting for publishers on '%s' to discover topic_type."
                % self._topic_name
            )
            return None

        if len(discovered_types) > 1 and not self._warned_multiple_topic_types:
            self.get_logger().warning(
                "Discovered multiple topic types on '%s': %s. Using '%s'."
                % (self._topic_name, discovered_types, discovered_types[0])
            )
            self._warned_multiple_topic_types = True

        return normalize_topic_type(discovered_types[0])

    def _resolve_qos_profile(self, publisher_infos: list[Any]):
        if self._qos_profile_mode == "manual":
            return build_qos_profile(self._qos_reliability, self._qos_history_depth)

        if not publisher_infos:
            self._maybe_log_waiting(
                "Waiting for publishers on '%s' to match QoS profile."
                % self._topic_name
            )
            return None

        signature_set = {
            (
                publisher_info.qos_profile.history,
                publisher_info.qos_profile.depth,
                publisher_info.qos_profile.reliability,
                publisher_info.qos_profile.durability,
            )
            for publisher_info in publisher_infos
        }
        if len(signature_set) > 1 and not self._warned_multiple_qos_profiles:
            self.get_logger().warning(
                "Discovered multiple publisher QoS profiles on '%s'. Reusing the first one."
                % self._topic_name
            )
            self._warned_multiple_qos_profiles = True

        selected_qos = publisher_infos[0].qos_profile
        sanitized_qos, was_sanitized = sanitize_discovered_qos_profile(
            selected_qos,
            self._qos_history_depth,
        )
        if was_sanitized:
            self.get_logger().warning(
                "Publisher QoS on '%s' reported unsupported or incomplete values. "
                "Using sanitized subscription QoS: history=%s depth=%d reliability=%s "
                "durability=%s."
                % (
                    self._topic_name,
                    sanitized_qos.history.name,
                    sanitized_qos.depth,
                    sanitized_qos.reliability.name,
                    sanitized_qos.durability.name,
                )
            )

        return sanitized_qos

    def _maybe_log_waiting(self, message: str) -> None:
        now_monotonic = time.monotonic()
        if now_monotonic - self._last_wait_log_monotonic >= WAIT_LOG_INTERVAL_SEC:
            self.get_logger().info(message)
            self._last_wait_log_monotonic = now_monotonic

    def _on_message(self, message: Any) -> None:
        recv_time = self.get_clock().now()
        recv_ns = recv_time.nanoseconds

        send_ns = extract_timestamp_ns(message, self._timestamp_field)
        current_seq = extract_sequence_value(message, self._sequence_field)

        if (
            send_ns is None
            and not is_field_disabled(self._timestamp_field)
            and not self._warned_missing_timestamp
        ):
            self.get_logger().warning(
                "Unable to extract a usable send timestamp from topic '%s' with "
                "timestamp_field='%s'. Latency-related KPI values will be NaN."
                % (self._topic_name, self._timestamp_field)
            )
            self._warned_missing_timestamp = True

        if (
            current_seq is None
            and not is_field_disabled(self._sequence_field)
            and not self._warned_missing_sequence
        ):
            self.get_logger().warning(
                "Unable to extract a usable sequence number from topic '%s' with "
                "sequence_field='%s'. Loss and out-of-order KPI values will stay at 0."
                % (self._topic_name, self._sequence_field)
            )
            self._warned_missing_sequence = True

        sample_metrics = compute_sample_metrics(
            recv_ns=recv_ns,
            send_ns=send_ns,
            current_seq=current_seq,
            last_receive_ns=self._last_receive_ns,
            last_seq=self._last_seq,
        )

        payload_size = self._estimate_payload_size(message)

        sample = KpiSample()
        sample.header.stamp = recv_time.to_msg()
        sample.header.frame_id = "topic_monitor"
        sample.source_stamp = to_time_msg(send_ns)
        sample.seq = 0 if current_seq is None else current_seq
        sample.payload_size = payload_size
        sample.latency_ms = sample_metrics.latency_ms
        sample.inter_arrival_ms = sample_metrics.inter_arrival_ms
        sample.seq_gap = sample_metrics.seq_gap
        sample.out_of_order = sample_metrics.out_of_order
        self._sample_publisher.publish(sample)

        self._last_receive_ns = recv_ns
        if current_seq is not None:
            if self._last_seq is None:
                self._last_seq = current_seq
            else:
                self._last_seq = max(self._last_seq, current_seq)

    def _estimate_payload_size(self, message: Any) -> int:
        try:
            return int(estimate_serialized_size(message))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            if not self._warned_payload_size_failure:
                self.get_logger().warning(
                    "Failed to serialize topic '%s' message for payload sizing: %s. "
                    "Falling back to payload_size=0."
                    % (self._topic_name, exc)
                )
                self._warned_payload_size_failure = True
            return 0


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TopicMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

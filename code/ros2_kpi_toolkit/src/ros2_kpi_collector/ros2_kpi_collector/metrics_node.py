import math
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Deque, Final, List, Sequence

import rclpy
from rclpy.node import Node

from ros2_kpi_interfaces.msg import KpiSample, KpiWindowMetrics, KpiWindowStats

DEFAULT_TOPIC_NAME: Final[str] = "/kpi_probe"
DEFAULT_SAMPLE_TOPIC_NAME: Final[str] = "/kpi_probe_samples"
DEFAULT_METRICS_TOPIC_NAME: Final[str] = "/kpi_window_stats"
DEFAULT_DASHBOARD_METRICS_TOPIC_NAME: Final[str] = "/kpi_metrics"
DEFAULT_WINDOW_SIZE_SEC: Final[float] = 5.0
DEFAULT_METRICS_PERIOD_SEC: Final[float] = 1.0


@dataclass
class SampleRecord:
    recv_ns: int
    latency_ms: float
    payload_size: int
    seq_gap: int
    out_of_order: bool


@dataclass(frozen=True)
class WindowStatistics:
    sample_count: int
    received_bytes: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    std_latency_ms: float
    jitter_ms: float
    recv_rate_hz: float
    throughput_bps: float
    lost_count: int
    loss_rate: float
    out_of_order_count: int


def time_msg_to_ns(sec: int, nanosec: int) -> int:
    return sec * 1_000_000_000 + nanosec


def nearest_rank_percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return float(ordered[rank - 1])


def compute_window_statistics(
    samples: Sequence[SampleRecord],
    window_size_sec: float,
) -> WindowStatistics:
    normalized_window_size_sec = max(0.1, float(window_size_sec))
    latencies = [sample.latency_ms for sample in samples if math.isfinite(sample.latency_ms)]
    received_bytes = sum(sample.payload_size for sample in samples)
    lost_count = sum(sample.seq_gap for sample in samples)
    out_of_order_count = sum(1 for sample in samples if sample.out_of_order)
    sample_count = len(samples)

    if latencies:
        avg_latency_ms = statistics.fmean(latencies)
        std_latency_ms = statistics.pstdev(latencies) if len(latencies) > 1 else 0.0
        p95_latency_ms = nearest_rank_percentile(latencies, 95.0)
        p99_latency_ms = nearest_rank_percentile(latencies, 99.0)
    elif sample_count == 0:
        avg_latency_ms = 0.0
        std_latency_ms = 0.0
        p95_latency_ms = 0.0
        p99_latency_ms = 0.0
    else:
        avg_latency_ms = math.nan
        std_latency_ms = math.nan
        p95_latency_ms = math.nan
        p99_latency_ms = math.nan

    recv_rate_hz = sample_count / normalized_window_size_sec
    throughput_bps = received_bytes / normalized_window_size_sec
    total_expected = sample_count + lost_count
    loss_rate = (lost_count / total_expected) if total_expected > 0 else 0.0

    return WindowStatistics(
        sample_count=sample_count,
        received_bytes=received_bytes,
        avg_latency_ms=avg_latency_ms,
        p95_latency_ms=p95_latency_ms,
        p99_latency_ms=p99_latency_ms,
        std_latency_ms=std_latency_ms,
        jitter_ms=std_latency_ms,
        recv_rate_hz=recv_rate_hz,
        throughput_bps=throughput_bps,
        lost_count=lost_count,
        loss_rate=loss_rate,
        out_of_order_count=out_of_order_count,
    )


def build_window_metrics_message(
    window_end,
    topic_name: str,
    window_size_sec: float,
    stats: WindowStatistics,
) -> KpiWindowMetrics:
    metrics = KpiWindowMetrics()
    metrics.window_end = window_end
    metrics.topic_name = topic_name
    metrics.window_size_sec = window_size_sec
    metrics.avg_latency_ms = stats.avg_latency_ms
    metrics.p95_latency_ms = stats.p95_latency_ms
    metrics.p99_latency_ms = stats.p99_latency_ms
    metrics.std_latency_ms = stats.std_latency_ms
    metrics.jitter_ms = stats.jitter_ms
    metrics.recv_rate_hz = stats.recv_rate_hz
    metrics.throughput_bps = stats.throughput_bps
    metrics.received_count = stats.sample_count
    metrics.received_bytes = stats.received_bytes
    metrics.lost_count = stats.lost_count
    metrics.loss_rate = stats.loss_rate
    metrics.out_of_order_count = stats.out_of_order_count
    return metrics


class MetricsNode(Node):
    def __init__(self) -> None:
        super().__init__("metrics_node")

        self.declare_parameter("topic_name", DEFAULT_TOPIC_NAME)
        self.declare_parameter("sample_topic_name", DEFAULT_SAMPLE_TOPIC_NAME)
        self.declare_parameter("metrics_topic_name", DEFAULT_METRICS_TOPIC_NAME)
        self.declare_parameter(
            "dashboard_metrics_topic_name",
            DEFAULT_DASHBOARD_METRICS_TOPIC_NAME,
        )
        self.declare_parameter("window_size_sec", DEFAULT_WINDOW_SIZE_SEC)
        self.declare_parameter("metrics_publish_period_sec", DEFAULT_METRICS_PERIOD_SEC)

        self._topic_name = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )
        self._sample_topic_name = (
            self.get_parameter("sample_topic_name").get_parameter_value().string_value
        )
        self._metrics_topic_name = (
            self.get_parameter("metrics_topic_name").get_parameter_value().string_value
        )
        self._dashboard_metrics_topic_name = (
            self.get_parameter("dashboard_metrics_topic_name")
            .get_parameter_value()
            .string_value
        )
        self._window_size_sec = max(
            0.1,
            self.get_parameter("window_size_sec").get_parameter_value().double_value,
        )
        metrics_period_sec = max(
            0.1,
            self.get_parameter("metrics_publish_period_sec")
            .get_parameter_value()
            .double_value,
        )

        self._window_size_ns = int(self._window_size_sec * 1_000_000_000)
        self._samples: Deque[SampleRecord] = deque()
        self._warned_no_samples = False

        self._subscription = self.create_subscription(
            KpiSample,
            self._sample_topic_name,
            self._on_sample,
            100,
        )
        self._window_stats_publisher = self.create_publisher(
            KpiWindowStats,
            self._metrics_topic_name,
            10,
        )
        self._dashboard_metrics_publisher = self.create_publisher(
            KpiWindowMetrics,
            self._dashboard_metrics_topic_name,
            10,
        )
        self._timer = self.create_timer(metrics_period_sec, self._publish_window_stats)

        self.get_logger().info(
            "Collecting samples from '%s', publishing legacy stats to '%s' and "
            "dashboard metrics to '%s', window_size_sec=%.3f, publish_period_sec=%.3f"
            % (
                self._sample_topic_name,
                self._metrics_topic_name,
                self._dashboard_metrics_topic_name,
                self._window_size_sec,
                metrics_period_sec,
            )
        )

    def _on_sample(self, message: KpiSample) -> None:
        recv_ns = time_msg_to_ns(message.header.stamp.sec, message.header.stamp.nanosec)
        self._samples.append(
            SampleRecord(
                recv_ns=recv_ns,
                latency_ms=message.latency_ms,
                payload_size=int(message.payload_size),
                seq_gap=int(message.seq_gap),
                out_of_order=bool(message.out_of_order),
            )
        )
        self._warned_no_samples = False
        self._trim_window(recv_ns)

    def _trim_window(self, reference_ns: int) -> None:
        cutoff_ns = reference_ns - self._window_size_ns
        while self._samples and self._samples[0].recv_ns < cutoff_ns:
            self._samples.popleft()

    def _publish_window_stats(self) -> None:
        now = self.get_clock().now()
        window_end = now.to_msg()
        now_ns = now.nanoseconds
        self._trim_window(now_ns)
        stats = compute_window_statistics(self._samples, self._window_size_sec)

        if stats.sample_count == 0 and not self._warned_no_samples:
            self.get_logger().warning(
                "No KPI samples received on '%s' during the last %.3f s. Metrics "
                "will stay at 0 until topic_monitor publishes samples. Check that "
                "the monitor is running and that topic_name/topic_type/QoS match "
                "the measured topic."
                % (self._sample_topic_name, self._window_size_sec)
            )
            self._warned_no_samples = True

        legacy_stats = KpiWindowStats()
        legacy_stats.header.stamp = window_end
        legacy_stats.header.frame_id = "metrics_window"
        legacy_stats.topic_name = self._topic_name
        legacy_stats.window_size_sec = self._window_size_sec
        legacy_stats.sample_count = stats.sample_count
        legacy_stats.received_bytes = stats.received_bytes
        legacy_stats.avg_latency_ms = stats.avg_latency_ms
        legacy_stats.p95_latency_ms = stats.p95_latency_ms
        legacy_stats.p99_latency_ms = stats.p99_latency_ms
        legacy_stats.std_latency_ms = stats.std_latency_ms
        legacy_stats.jitter_ms = stats.jitter_ms
        legacy_stats.recv_rate_hz = stats.recv_rate_hz
        legacy_stats.throughput_bps = stats.throughput_bps
        legacy_stats.lost_count = stats.lost_count
        legacy_stats.loss_rate = stats.loss_rate
        legacy_stats.out_of_order_count = stats.out_of_order_count
        self._window_stats_publisher.publish(legacy_stats)

        dashboard_metrics = build_window_metrics_message(
            window_end=window_end,
            topic_name=self._topic_name,
            window_size_sec=self._window_size_sec,
            stats=stats,
        )
        self._dashboard_metrics_publisher.publish(dashboard_metrics)

        self.get_logger().info(
            "window topic=%s samples=%d avg=%.3f ms p95=%.3f ms p99=%.3f ms "
            "rate=%.3f Hz throughput=%.3f Bps lost=%d ooo=%d"
            % (
                self._topic_name,
                stats.sample_count,
                stats.avg_latency_ms,
                stats.p95_latency_ms,
                stats.p99_latency_ms,
                stats.recv_rate_hz,
                stats.throughput_bps,
                stats.lost_count,
                stats.out_of_order_count,
            )
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MetricsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

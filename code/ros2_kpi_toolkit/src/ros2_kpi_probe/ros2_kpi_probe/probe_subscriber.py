from typing import Final, Optional

import rclpy
from rclpy.node import Node
from rclpy.time import Time

from ros2_kpi_interfaces.msg import KpiProbe, KpiSample
from ros2_kpi_probe.measurement_utils import build_qos_profile, compute_sample_metrics

DEFAULT_TOPIC_NAME: Final[str] = "/kpi_probe"
DEFAULT_SAMPLE_TOPIC_NAME: Final[str] = "/kpi_probe_samples"
DEFAULT_QOS_RELIABILITY: Final[str] = "reliable"
DEFAULT_QOS_DEPTH: Final[int] = 10


class ProbeSubscriber(Node):
    def __init__(self) -> None:
        super().__init__("probe_subscriber")

        self.declare_parameter("topic_name", DEFAULT_TOPIC_NAME)
        self.declare_parameter("sample_topic_name", DEFAULT_SAMPLE_TOPIC_NAME)
        self.declare_parameter("qos_reliability", DEFAULT_QOS_RELIABILITY)
        self.declare_parameter("qos_history_depth", DEFAULT_QOS_DEPTH)

        topic_name = self.get_parameter("topic_name").get_parameter_value().string_value
        self._sample_topic_name = (
            self.get_parameter("sample_topic_name").get_parameter_value().string_value
        )
        qos_reliability = (
            self.get_parameter("qos_reliability").get_parameter_value().string_value
        )
        qos_depth = (
            self.get_parameter("qos_history_depth").get_parameter_value().integer_value
        )

        probe_qos = build_qos_profile(qos_reliability, int(qos_depth))
        self._subscriber = self.create_subscription(
            KpiProbe,
            topic_name,
            self._on_probe,
            probe_qos,
        )
        self._sample_publisher = self.create_publisher(
            KpiSample,
            self._sample_topic_name,
            100,
        )

        self._last_receive_ns: Optional[int] = None
        self._last_seq: Optional[int] = None

        self.get_logger().info(
            "Subscribing KPI probes from '%s' and publishing samples to '%s' "
            "with reliability=%s, depth=%d"
            % (topic_name, self._sample_topic_name, qos_reliability, int(qos_depth))
        )

    def _on_probe(self, message: KpiProbe) -> None:
        recv_time = self.get_clock().now()
        recv_ns = recv_time.nanoseconds
        send_time = Time.from_msg(message.header.stamp)
        sample_metrics = compute_sample_metrics(
            recv_ns=recv_ns,
            send_ns=send_time.nanoseconds,
            current_seq=int(message.seq),
            last_receive_ns=self._last_receive_ns,
            last_seq=self._last_seq,
        )

        sample = KpiSample()
        sample.header.stamp = recv_time.to_msg()
        sample.header.frame_id = "base_station_probe"
        sample.source_stamp = message.header.stamp
        sample.seq = message.seq
        sample.payload_size = (
            message.payload_size if message.payload_size > 0 else len(message.payload)
        )
        sample.latency_ms = sample_metrics.latency_ms
        sample.inter_arrival_ms = sample_metrics.inter_arrival_ms
        sample.seq_gap = sample_metrics.seq_gap
        sample.out_of_order = sample_metrics.out_of_order
        self._sample_publisher.publish(sample)

        self._last_receive_ns = recv_ns
        if self._last_seq is None:
            self._last_seq = int(message.seq)
        else:
            self._last_seq = max(self._last_seq, int(message.seq))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ProbeSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

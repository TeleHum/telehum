from typing import Final

import rclpy
from rclpy.node import Node

from ros2_kpi_interfaces.msg import KpiProbe
from ros2_kpi_probe.measurement_utils import build_qos_profile

DEFAULT_TOPIC_NAME: Final[str] = "/kpi_probe"
DEFAULT_PUBLISH_RATE_HZ: Final[float] = 10.0
DEFAULT_PAYLOAD_SIZE: Final[int] = 256
DEFAULT_QOS_RELIABILITY: Final[str] = "reliable"
DEFAULT_QOS_DEPTH: Final[int] = 10


class ProbePublisher(Node):
    def __init__(self) -> None:
        super().__init__("probe_publisher")

        self.declare_parameter("topic_name", DEFAULT_TOPIC_NAME)
        self.declare_parameter("publish_rate_hz", DEFAULT_PUBLISH_RATE_HZ)
        self.declare_parameter("payload_size", DEFAULT_PAYLOAD_SIZE)
        self.declare_parameter("qos_reliability", DEFAULT_QOS_RELIABILITY)
        self.declare_parameter("qos_history_depth", DEFAULT_QOS_DEPTH)

        self._topic_name = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )
        publish_rate_hz = (
            self.get_parameter("publish_rate_hz").get_parameter_value().double_value
        )
        payload_size = (
            self.get_parameter("payload_size").get_parameter_value().integer_value
        )
        qos_reliability = (
            self.get_parameter("qos_reliability").get_parameter_value().string_value
        )
        qos_depth = (
            self.get_parameter("qos_history_depth").get_parameter_value().integer_value
        )

        self._publish_rate_hz = max(0.1, float(publish_rate_hz))
        self._payload_size = max(0, int(payload_size))
        self._payload_template = bytes([0x5A]) * self._payload_size
        self._seq = 0

        qos_profile = build_qos_profile(qos_reliability, int(qos_depth))
        self._publisher = self.create_publisher(KpiProbe, self._topic_name, qos_profile)
        self._timer = self.create_timer(1.0 / self._publish_rate_hz, self._publish_once)

        self.get_logger().info(
            "Publishing KPI probes on '%s' at %.3f Hz with payload_size=%d B, "
            "reliability=%s, depth=%d"
            % (
                self._topic_name,
                self._publish_rate_hz,
                self._payload_size,
                qos_reliability,
                int(qos_depth),
            )
        )

    def _publish_once(self) -> None:
        now = self.get_clock().now()
        message = KpiProbe()
        message.header.stamp = now.to_msg()
        message.header.frame_id = "ue_probe"
        message.seq = self._seq
        message.payload_size = self._payload_size
        message.payload = self._payload_template

        self._publisher.publish(message)
        self._seq += 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ProbePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

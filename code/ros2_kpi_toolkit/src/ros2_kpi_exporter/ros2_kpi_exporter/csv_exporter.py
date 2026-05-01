import csv
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import rclpy
from rclpy.exceptions import ParameterNotDeclaredException
from rclpy.node import Node

from ros2_kpi_interfaces.msg import KpiWindowStats

DEFAULT_METRICS_TOPIC_NAME: Final[str] = "/kpi_window_stats"
DEFAULT_CSV_OUTPUT_PATH: Final[str] = "./output/kpi_metrics.csv"
DEFAULT_MAX_FILE_SIZE_MB: Final[float] = 10.0
DEFAULT_MAX_FILES_PER_RUN: Final[int] = 10
DEFAULT_TOPIC_NAME: Final[str] = "/kpi_probe"
DEFAULT_PUBLISH_RATE_HZ: Final[float] = 10.0
DEFAULT_PAYLOAD_SIZE: Final[int] = 256
DEFAULT_QOS_RELIABILITY: Final[str] = "reliable"
DEFAULT_QOS_DEPTH: Final[int] = 10
DEFAULT_WINDOW_SIZE_SEC: Final[float] = 5.0
DEFAULT_MEASUREMENT_MODE: Final[str] = "probe"
DEFAULT_TOPIC_TYPE: Final[str] = ""
DEFAULT_TIMESTAMP_FIELD: Final[str] = "auto"
DEFAULT_SEQUENCE_FIELD: Final[str] = "auto"
DEFAULT_HOST_ID: Final[str] = "<host-name>"

CSV_COLUMNS: Final[list[str]] = [
    "timestamp_ns",
    "timestamp_iso_utc",
    "topic_name",
    "window_size_sec",
    "sample_count",
    "received_bytes",
    "avg_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "std_latency_ms",
    "jitter_ms",
    "recv_rate_hz",
    "throughput_Bps",
    "lost_count",
    "loss_rate",
    "out_of_order_count",
]


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    measurement_mode: str
    topic_name: str
    topic_type: str
    publish_rate_hz: float
    payload_size: int
    qos_reliability: str
    qos_history_depth: int
    window_size_sec: float
    timestamp_field: str
    sequence_field: str
    hostname: str
    start_time: str
    use_sim_time: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def resolve_output_base_directory(csv_output_path: str) -> Path:
    path = Path(csv_output_path).expanduser()
    if path.suffix.lower() == ".csv":
        return path.parent / path.stem
    return path


def build_run_metadata(
    run_id: str,
    measurement_mode: str,
    topic_name: str,
    topic_type: str,
    publish_rate_hz: float,
    payload_size: int,
    qos_reliability: str,
    qos_history_depth: int,
    window_size_sec: float,
    timestamp_field: str,
    sequence_field: str,
    use_sim_time: bool,
) -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        measurement_mode=measurement_mode,
        topic_name=topic_name,
        topic_type=topic_type,
        publish_rate_hz=publish_rate_hz,
        payload_size=payload_size,
        qos_reliability=qos_reliability,
        qos_history_depth=qos_history_depth,
        window_size_sec=window_size_sec,
        timestamp_field=timestamp_field,
        sequence_field=sequence_field,
        hostname=DEFAULT_HOST_ID,
        start_time=utc_now_iso(),
        use_sim_time=use_sim_time,
    )


class RollingCsvWriter:
    def __init__(
        self,
        output_base_directory: Path,
        run_id: str,
        max_file_size_mb: float,
        max_files_per_run: int,
    ) -> None:
        self._run_id = run_id
        self._run_directory = output_base_directory / f"run_{run_id}"
        self._run_directory.mkdir(parents=True, exist_ok=True)

        self._max_file_size_bytes = max(
            1,
            int(max(0.000001, float(max_file_size_mb)) * 1024 * 1024),
        )
        self._max_files_per_run = max(1, int(max_files_per_run))
        self._part_index = 0
        self._part_paths: list[Path] = []
        self._file_handle = None
        self._writer = None
        self._needs_rollover_before_write = False

        self._open_next_part()

    @property
    def run_directory(self) -> Path:
        return self._run_directory

    @property
    def current_file_path(self) -> Path:
        return self._part_paths[-1]

    def write_row(self, row: dict[str, Any]) -> None:
        if self._needs_rollover_before_write:
            self._open_next_part()
            self._needs_rollover_before_write = False

        self._writer.writerow(row)
        self._file_handle.flush()
        if self._file_handle.tell() >= self._max_file_size_bytes:
            self._needs_rollover_before_write = True

    def close(self) -> None:
        if self._file_handle is not None and not self._file_handle.closed:
            self._file_handle.close()

    def _open_next_part(self) -> None:
        self.close()
        self._part_index += 1
        file_path = self._run_directory / (
            f"metrics_run_{self._run_id}_part_{self._part_index:04d}.csv"
        )
        self._file_handle = file_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file_handle, fieldnames=CSV_COLUMNS)
        self._writer.writeheader()
        self._file_handle.flush()
        self._part_paths.append(file_path)
        self._trim_old_parts()

    def _trim_old_parts(self) -> None:
        while len(self._part_paths) > self._max_files_per_run:
            obsolete_path = self._part_paths.pop(0)
            if obsolete_path.exists():
                obsolete_path.unlink()


class CsvExporter(Node):
    def __init__(self) -> None:
        super().__init__("csv_exporter")

        self.declare_parameter("metrics_topic_name", DEFAULT_METRICS_TOPIC_NAME)
        self.declare_parameter("csv_output_path", DEFAULT_CSV_OUTPUT_PATH)
        self.declare_parameter("max_file_size_mb", DEFAULT_MAX_FILE_SIZE_MB)
        self.declare_parameter("max_files_per_run", DEFAULT_MAX_FILES_PER_RUN)
        self.declare_parameter("topic_name", DEFAULT_TOPIC_NAME)
        self.declare_parameter("publish_rate_hz", DEFAULT_PUBLISH_RATE_HZ)
        self.declare_parameter("payload_size", DEFAULT_PAYLOAD_SIZE)
        self.declare_parameter("qos_reliability", DEFAULT_QOS_RELIABILITY)
        self.declare_parameter("qos_history_depth", DEFAULT_QOS_DEPTH)
        self.declare_parameter("window_size_sec", DEFAULT_WINDOW_SIZE_SEC)
        self.declare_parameter("measurement_mode", DEFAULT_MEASUREMENT_MODE)
        self.declare_parameter("topic_type", DEFAULT_TOPIC_TYPE)
        self.declare_parameter("timestamp_field", DEFAULT_TIMESTAMP_FIELD)
        self.declare_parameter("sequence_field", DEFAULT_SEQUENCE_FIELD)

        metrics_topic_name = (
            self.get_parameter("metrics_topic_name").get_parameter_value().string_value
        )
        csv_output_path = (
            self.get_parameter("csv_output_path").get_parameter_value().string_value
        )
        max_file_size_mb = (
            self.get_parameter("max_file_size_mb").get_parameter_value().double_value
        )
        max_files_per_run = (
            self.get_parameter("max_files_per_run")
            .get_parameter_value()
            .integer_value
        )
        topic_name = self.get_parameter("topic_name").get_parameter_value().string_value
        publish_rate_hz = (
            self.get_parameter("publish_rate_hz").get_parameter_value().double_value
        )
        payload_size = (
            self.get_parameter("payload_size").get_parameter_value().integer_value
        )
        qos_reliability = (
            self.get_parameter("qos_reliability").get_parameter_value().string_value
        )
        qos_history_depth = (
            self.get_parameter("qos_history_depth").get_parameter_value().integer_value
        )
        window_size_sec = (
            self.get_parameter("window_size_sec").get_parameter_value().double_value
        )
        measurement_mode = (
            self.get_parameter("measurement_mode").get_parameter_value().string_value
        )
        topic_type = self.get_parameter("topic_type").get_parameter_value().string_value
        timestamp_field = (
            self.get_parameter("timestamp_field").get_parameter_value().string_value
        )
        sequence_field = (
            self.get_parameter("sequence_field").get_parameter_value().string_value
        )
        use_sim_time = self._read_use_sim_time()

        self._run_id = generate_run_id()
        output_base_directory = resolve_output_base_directory(csv_output_path)
        self._rolling_writer = RollingCsvWriter(
            output_base_directory=output_base_directory,
            run_id=self._run_id,
            max_file_size_mb=max_file_size_mb,
            max_files_per_run=int(max_files_per_run),
        )
        self._metadata = build_run_metadata(
            run_id=self._run_id,
            measurement_mode=measurement_mode,
            topic_name=topic_name,
            topic_type=topic_type,
            publish_rate_hz=float(publish_rate_hz),
            payload_size=int(payload_size),
            qos_reliability=qos_reliability,
            qos_history_depth=int(qos_history_depth),
            window_size_sec=float(window_size_sec),
            timestamp_field=timestamp_field,
            sequence_field=sequence_field,
            use_sim_time=use_sim_time,
        )
        self._write_metadata_file()

        self._subscription = self.create_subscription(
            KpiWindowStats,
            metrics_topic_name,
            self._on_metrics,
            10,
        )

        self.get_logger().info(
            "Exporting metrics from '%s' to run directory '%s' with run_id='%s' "
            "(current_part='%s', max_file_size_mb=%.3f, max_files_per_run=%d)"
            % (
                metrics_topic_name,
                self._rolling_writer.run_directory,
                self._run_id,
                self._rolling_writer.current_file_path.name,
                max_file_size_mb,
                int(max_files_per_run),
            )
        )

    def _on_metrics(self, message: KpiWindowStats) -> None:
        timestamp_ns = (
            message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
        )
        timestamp_iso = datetime.fromtimestamp(
            timestamp_ns / 1_000_000_000,
            tz=timezone.utc,
        ).isoformat()

        row = {
            "timestamp_ns": timestamp_ns,
            "timestamp_iso_utc": timestamp_iso,
            "topic_name": message.topic_name,
            "window_size_sec": message.window_size_sec,
            "sample_count": message.sample_count,
            "received_bytes": message.received_bytes,
            "avg_latency_ms": message.avg_latency_ms,
            "p95_latency_ms": message.p95_latency_ms,
            "p99_latency_ms": message.p99_latency_ms,
            "std_latency_ms": message.std_latency_ms,
            "jitter_ms": message.jitter_ms,
            "recv_rate_hz": message.recv_rate_hz,
            "throughput_Bps": message.throughput_bps,
            "lost_count": message.lost_count,
            "loss_rate": message.loss_rate,
            "out_of_order_count": message.out_of_order_count,
        }
        self._rolling_writer.write_row(row)

    def _read_use_sim_time(self) -> bool:
        try:
            return self.get_parameter("use_sim_time").get_parameter_value().bool_value
        except ParameterNotDeclaredException:
            return False

    def _write_metadata_file(self) -> None:
        metadata_path = self._rolling_writer.run_directory / "metadata.json"
        metadata_path.write_text(
            json.dumps(asdict(self._metadata), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def destroy_node(self) -> bool:
        if hasattr(self, "_rolling_writer"):
            self._rolling_writer.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CsvExporter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

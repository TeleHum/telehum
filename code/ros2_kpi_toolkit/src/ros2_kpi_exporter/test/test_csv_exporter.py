import json
from pathlib import Path

from ros2_kpi_exporter.csv_exporter import (
    CSV_COLUMNS,
    RollingCsvWriter,
    build_run_metadata,
    resolve_output_base_directory,
)


def make_row(index: int) -> dict[str, object]:
    return {
        "timestamp_ns": index,
        "timestamp_iso_utc": f"2026-04-20T00:00:0{index}+00:00",
        "topic_name": "/demo",
        "window_size_sec": 5.0,
        "sample_count": 100,
        "received_bytes": 999999,
        "avg_latency_ms": 1.1,
        "p95_latency_ms": 2.2,
        "p99_latency_ms": 3.3,
        "std_latency_ms": 0.4,
        "jitter_ms": 0.4,
        "recv_rate_hz": 10.0,
        "throughput_Bps": 2048.0,
        "lost_count": 1,
        "loss_rate": 0.01,
        "out_of_order_count": 2,
    }


def test_resolve_output_base_directory_for_legacy_csv_path() -> None:
    resolved = resolve_output_base_directory("~/metrics.csv")
    assert resolved.name == "metrics"


def test_build_run_metadata_contains_required_fields() -> None:
    metadata = build_run_metadata(
        run_id="run_123",
        measurement_mode="probe",
        topic_name="/kpi_probe",
        topic_type="ros2_kpi_interfaces/msg/KpiProbe",
        publish_rate_hz=20.0,
        payload_size=1024,
        qos_reliability="reliable",
        qos_history_depth=10,
        window_size_sec=5.0,
        timestamp_field="header.stamp",
        sequence_field="seq",
        use_sim_time=False,
    )

    assert metadata.run_id == "run_123"
    assert metadata.measurement_mode == "probe"
    assert metadata.topic_name == "/kpi_probe"
    assert metadata.topic_type == "ros2_kpi_interfaces/msg/KpiProbe"
    assert metadata.payload_size == 1024
    assert metadata.timestamp_field == "header.stamp"
    assert metadata.sequence_field == "seq"
    assert metadata.use_sim_time is False
    assert metadata.hostname == "<host-name>"
    assert metadata.start_time


def test_rolling_csv_writer_rolls_and_limits_file_count(tmp_path: Path) -> None:
    writer = RollingCsvWriter(
        output_base_directory=tmp_path,
        run_id="demo_run",
        max_file_size_mb=0.00015,
        max_files_per_run=2,
    )

    for index in range(8):
        writer.write_row(make_row(index))
    writer.close()

    csv_files = sorted(writer.run_directory.glob("metrics_run_demo_run_part_*.csv"))
    assert len(csv_files) <= 2
    assert csv_files
    for csv_file in csv_files:
        content = csv_file.read_text(encoding="utf-8")
        assert CSV_COLUMNS[0] in content
        assert "timestamp_iso_utc" in content

    assert writer.current_file_path.name != "metrics_run_demo_run_part_0001.csv"


def test_metadata_json_can_be_written(tmp_path: Path) -> None:
    metadata = build_run_metadata(
        run_id="demo",
        measurement_mode="generic_topic",
        topic_name="/demo",
        topic_type="std_msgs/msg/String",
        publish_rate_hz=5.0,
        payload_size=128,
        qos_reliability="best_effort",
        qos_history_depth=5,
        window_size_sec=2.0,
        timestamp_field="auto",
        sequence_field="auto",
        use_sim_time=False,
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.__dict__, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "demo"
    assert loaded["measurement_mode"] == "generic_topic"
    assert loaded["qos_reliability"] == "best_effort"

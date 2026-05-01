import math

from builtin_interfaces.msg import Time
from ros2_kpi_collector.metrics_node import (
    SampleRecord,
    build_window_metrics_message,
    compute_window_statistics,
    nearest_rank_percentile,
)


def test_nearest_rank_percentile() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    assert math.isclose(nearest_rank_percentile(values, 95.0), 5.0)
    assert math.isclose(nearest_rank_percentile(values, 50.0), 3.0)
    assert math.isclose(nearest_rank_percentile([], 99.0), 0.0)


def test_compute_window_statistics_with_loss_and_out_of_order() -> None:
    samples = [
        SampleRecord(recv_ns=1, latency_ms=1.0, payload_size=100, seq_gap=0, out_of_order=False),
        SampleRecord(recv_ns=2, latency_ms=2.0, payload_size=200, seq_gap=1, out_of_order=False),
        SampleRecord(recv_ns=3, latency_ms=3.0, payload_size=300, seq_gap=0, out_of_order=True),
    ]

    stats = compute_window_statistics(samples, window_size_sec=2.0)

    assert stats.sample_count == 3
    assert stats.received_bytes == 600
    assert math.isclose(stats.avg_latency_ms, 2.0)
    assert math.isclose(stats.p95_latency_ms, 3.0)
    assert math.isclose(stats.p99_latency_ms, 3.0)
    assert math.isclose(stats.std_latency_ms, 0.816496580927726)
    assert math.isclose(stats.jitter_ms, stats.std_latency_ms)
    assert math.isclose(stats.recv_rate_hz, 1.5)
    assert math.isclose(stats.throughput_bps, 300.0)
    assert stats.lost_count == 1
    assert math.isclose(stats.loss_rate, 0.25)
    assert stats.out_of_order_count == 1


def test_compute_window_statistics_empty_window() -> None:
    stats = compute_window_statistics([], window_size_sec=5.0)

    assert stats.sample_count == 0
    assert stats.received_bytes == 0
    assert math.isclose(stats.avg_latency_ms, 0.0)
    assert math.isclose(stats.p95_latency_ms, 0.0)
    assert math.isclose(stats.p99_latency_ms, 0.0)
    assert math.isclose(stats.std_latency_ms, 0.0)
    assert math.isclose(stats.recv_rate_hz, 0.0)
    assert math.isclose(stats.throughput_bps, 0.0)
    assert stats.lost_count == 0
    assert math.isclose(stats.loss_rate, 0.0)
    assert stats.out_of_order_count == 0


def test_compute_window_statistics_keeps_nan_when_latency_is_unavailable() -> None:
    samples = [
        SampleRecord(
            recv_ns=1,
            latency_ms=math.nan,
            payload_size=100,
            seq_gap=0,
            out_of_order=False,
        ),
        SampleRecord(
            recv_ns=2,
            latency_ms=math.nan,
            payload_size=120,
            seq_gap=0,
            out_of_order=False,
        ),
    ]

    stats = compute_window_statistics(samples, window_size_sec=2.0)

    assert stats.sample_count == 2
    assert stats.received_bytes == 220
    assert math.isnan(stats.avg_latency_ms)
    assert math.isnan(stats.p95_latency_ms)
    assert math.isnan(stats.p99_latency_ms)
    assert math.isnan(stats.std_latency_ms)
    assert math.isnan(stats.jitter_ms)
    assert math.isclose(stats.recv_rate_hz, 1.0)
    assert math.isclose(stats.throughput_bps, 110.0)


def test_build_window_metrics_message() -> None:
    stats = compute_window_statistics(
        [
            SampleRecord(
                recv_ns=1,
                latency_ms=4.0,
                payload_size=256,
                seq_gap=2,
                out_of_order=True,
            )
        ],
        window_size_sec=5.0,
    )

    message = build_window_metrics_message(
        window_end=Time(sec=123, nanosec=456),
        topic_name="/demo",
        window_size_sec=5.0,
        stats=stats,
    )

    assert message.window_end.sec == 123
    assert message.window_end.nanosec == 456
    assert message.topic_name == "/demo"
    assert math.isclose(message.avg_latency_ms, 4.0)
    assert math.isclose(message.throughput_bps, 51.2)
    assert message.received_count == 1
    assert message.received_bytes == 256
    assert message.lost_count == 2
    assert message.out_of_order_count == 1

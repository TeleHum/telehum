import math

from ros2_kpi_probe.measurement_utils import compute_sample_metrics


def test_compute_sample_metrics_for_first_message() -> None:
    metrics = compute_sample_metrics(
        recv_ns=1_250_000_000,
        send_ns=1_000_000_000,
        current_seq=10,
        last_receive_ns=None,
        last_seq=None,
    )

    assert math.isclose(metrics.latency_ms, 250.0)
    assert math.isclose(metrics.inter_arrival_ms, 0.0)
    assert metrics.seq_gap == 0
    assert metrics.out_of_order is False


def test_compute_sample_metrics_detects_gap() -> None:
    metrics = compute_sample_metrics(
        recv_ns=2_500_000_000,
        send_ns=2_400_000_000,
        current_seq=8,
        last_receive_ns=2_000_000_000,
        last_seq=5,
    )

    assert math.isclose(metrics.latency_ms, 100.0)
    assert math.isclose(metrics.inter_arrival_ms, 500.0)
    assert metrics.seq_gap == 2
    assert metrics.out_of_order is False


def test_compute_sample_metrics_detects_out_of_order() -> None:
    metrics = compute_sample_metrics(
        recv_ns=4_000_000_000,
        send_ns=3_950_000_000,
        current_seq=6,
        last_receive_ns=3_500_000_000,
        last_seq=7,
    )

    assert math.isclose(metrics.latency_ms, 50.0)
    assert math.isclose(metrics.inter_arrival_ms, 500.0)
    assert metrics.seq_gap == 0
    assert metrics.out_of_order is True


def test_compute_sample_metrics_without_send_timestamp_or_sequence() -> None:
    metrics = compute_sample_metrics(
        recv_ns=4_000_000_000,
        send_ns=None,
        current_seq=None,
        last_receive_ns=3_750_000_000,
        last_seq=7,
    )

    assert math.isnan(metrics.latency_ms)
    assert math.isclose(metrics.inter_arrival_ms, 250.0)
    assert metrics.seq_gap == 0
    assert metrics.out_of_order is False

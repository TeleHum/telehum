import math
from dataclasses import dataclass
from typing import Any, Optional

from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)


@dataclass(frozen=True)
class SampleMetrics:
    latency_ms: float
    inter_arrival_ms: float
    seq_gap: int
    out_of_order: bool


def build_qos_profile(reliability: str, depth: int) -> QoSProfile:
    reliability_normalized = reliability.strip().lower()
    if reliability_normalized == "best_effort":
        reliability_policy = QoSReliabilityPolicy.BEST_EFFORT
    elif reliability_normalized == "reliable":
        reliability_policy = QoSReliabilityPolicy.RELIABLE
    else:
        raise ValueError(
            "qos_reliability must be either 'reliable' or 'best_effort'."
        )

    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=max(1, depth),
        reliability=reliability_policy,
    )


def sanitize_discovered_qos_profile(
    qos_profile: Any,
    fallback_depth: int,
) -> tuple[QoSProfile, bool]:
    raw_history = getattr(qos_profile, "history", QoSHistoryPolicy.UNKNOWN)
    raw_reliability = getattr(
        qos_profile,
        "reliability",
        QoSReliabilityPolicy.UNKNOWN,
    )
    raw_durability = getattr(
        qos_profile,
        "durability",
        QoSDurabilityPolicy.UNKNOWN,
    )
    raw_depth = getattr(qos_profile, "depth", fallback_depth)

    if isinstance(raw_depth, int) and raw_depth > 0:
        depth = raw_depth
    else:
        depth = max(1, fallback_depth)

    history = QoSHistoryPolicy(raw_history)
    if history in {QoSHistoryPolicy.UNKNOWN, QoSHistoryPolicy.SYSTEM_DEFAULT}:
        history = QoSHistoryPolicy.KEEP_LAST

    reliability = QoSReliabilityPolicy(raw_reliability)
    if reliability in {
        QoSReliabilityPolicy.UNKNOWN,
        QoSReliabilityPolicy.SYSTEM_DEFAULT,
    }:
        # BEST_EFFORT is the more permissive subscriber setting when the
        # publisher only reports an ambiguous reliability policy.
        reliability = QoSReliabilityPolicy.BEST_EFFORT

    durability = QoSDurabilityPolicy(raw_durability)
    if durability in {
        QoSDurabilityPolicy.UNKNOWN,
        QoSDurabilityPolicy.SYSTEM_DEFAULT,
    }:
        durability = QoSDurabilityPolicy.VOLATILE

    sanitized = QoSProfile(
        history=history,
        depth=depth,
        reliability=reliability,
        durability=durability,
    )

    return (
        sanitized,
        (
            history != raw_history
            or reliability != raw_reliability
            or durability != raw_durability
            or depth != raw_depth
        ),
    )


def compute_sample_metrics(
    recv_ns: int,
    send_ns: Optional[int],
    current_seq: Optional[int],
    last_receive_ns: Optional[int],
    last_seq: Optional[int],
) -> SampleMetrics:
    latency_ms = math.nan if send_ns is None else (recv_ns - send_ns) / 1e6

    inter_arrival_ms = 0.0
    if last_receive_ns is not None:
        inter_arrival_ms = (recv_ns - last_receive_ns) / 1e6

    seq_gap = 0
    out_of_order = False
    if current_seq is not None and last_seq is not None:
        if current_seq > last_seq + 1:
            seq_gap = int(current_seq - last_seq - 1)
        if current_seq <= last_seq:
            out_of_order = True

    return SampleMetrics(
        latency_ms=latency_ms,
        inter_arrival_ms=inter_arrival_ms,
        seq_gap=seq_gap,
        out_of_order=out_of_order,
    )

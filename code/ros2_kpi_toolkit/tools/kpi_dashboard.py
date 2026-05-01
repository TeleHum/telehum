#!/usr/bin/env python3
"""Live CSV dashboard for gNB and ROS 2 KPI exports.

The dashboard intentionally uses only Python's standard library so it can run
inside the ROS workspace without adding web framework dependencies.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


DEFAULT_GNB_CSV = Path("gnb_csv") / "gnb_metrics.csv"
DEFAULT_ROS_ROOT = Path("output") / "kpi_metrics"
DEFAULT_EXPORT_DIR = Path("output") / "combined_metrics"
DEFAULT_POLL_MS = 200
DEFAULT_MAX_JOIN_AGE_SEC = 1.0  #原始10
MAX_SERIES_ROWS = 100 #100行数据渲染表格

GNB_METRICS = [
    "UL_THR",
    "ul_BLER",
    "ul_MCS",
    "SNR",
    "PH_dB",
    "raw_rssi",
    "ulsch_current_rbs",
    "ulsch_current_bytes",
]

ROS_METRICS = [
    "avg_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "jitter_ms",
    "recv_rate_hz",
    "throughput_Bps",
    "sample_count",
    "lost_count",
    "loss_rate",
    "out_of_order_count",
]


@dataclass(frozen=True)
class CsvData:
    path: Path | None
    headers: list[str]
    rows: list[dict[str, str]]
    error: str | None = None
    mtime: float | None = None


@dataclass(frozen=True)
class DashboardConfig:
    gnb_csv: Path
    ros_csv: Path | None
    ros_root: Path
    export_dir: Path
    poll_ms: int
    max_join_age_sec: float


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_from_epoch_ms(timestamp_ms: int | float | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc).isoformat()


def iso_from_epoch_ns(timestamp_ns: int | float | None) -> str | None:
    if timestamp_ns is None:
        return None
    return datetime.fromtimestamp(float(timestamp_ns) / 1_000_000_000.0, tz=timezone.utc).isoformat()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None or not math.isfinite(number):
        return None
    return int(number)


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "unnamed"


def normalize_headers(raw_headers: Iterable[str]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for index, raw_name in enumerate(raw_headers):
        name = raw_name.strip() or f"unnamed_{index}"
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}_{seen[name]}"
        names.append(name)
    return names


def read_csv(path: Path | None) -> CsvData:
    if path is None:
        return CsvData(path=None, headers=[], rows=[], error="No CSV path resolved.")

    try:
        stat = path.stat()
    except FileNotFoundError:
        return CsvData(path=path, headers=[], rows=[], error=f"File not found: {path}")

    last_error: Exception | None = None
    for _ in range(3):
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                raw_headers = next(reader, [])
                headers = normalize_headers(raw_headers)
                rows = [
                    {headers[index]: value for index, value in enumerate(row[: len(headers)])}
                    for row in reader
                    if any(cell.strip() for cell in row)
                ]
            return CsvData(path=path, headers=headers, rows=rows, mtime=stat.st_mtime)
        except (OSError, csv.Error, UnicodeDecodeError) as exc:
            last_error = exc
            time.sleep(0.02)

    return CsvData(path=path, headers=[], rows=[], error=str(last_error), mtime=stat.st_mtime)


def resolve_latest_ros_csv(ros_root: Path) -> Path | None:
    if not ros_root.exists():
        return None

    run_dirs = sorted(
        [path for path in ros_root.glob("run_*") if path.is_dir()],
        key=lambda path: path.name,
    )
    for run_dir in reversed(run_dirs):
        parts = sorted(run_dir.glob("metrics_run_*_part_*.csv"), key=lambda path: path.name)
        if parts:
            return parts[-1]
    return None


def parse_gnb_timestamp_ms(row: dict[str, str]) -> int | None:
    return safe_int(row.get("Timestamp"))


def parse_ros_timestamp_ns(row: dict[str, str]) -> int | None:
    timestamp_ns = safe_int(row.get("timestamp_ns"))
    if timestamp_ns is not None:
        return timestamp_ns

    iso_text = row.get("timestamp_iso_utc")
    if not iso_text:
        return None
    try:
        parsed = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def time_range_ms(rows: list[dict[str, str]], parser) -> tuple[int | None, int | None]:
    timestamps = [timestamp for timestamp in (parser(row) for row in rows) if timestamp is not None]
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def series_rate_hz(timestamps: list[int], divisor: float) -> float | None:
    if len(timestamps) < 2:
        return None
    span = (timestamps[-1] - timestamps[0]) / divisor
    if span <= 0:
        return None
    return (len(timestamps) - 1) / span


def numeric_summary(rows: list[dict[str, str]], names: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name in names:
        values = [
            value
            for value in (safe_float(row.get(name)) for row in rows)
            if value is not None and math.isfinite(value)
        ]
        if not values:
            continue
        summary[name] = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1],
        }
    return summary


def summarize_gnb(data: CsvData) -> dict[str, Any]:
    rows = data.rows[-MAX_SERIES_ROWS:]
    timestamps = [timestamp for timestamp in (parse_gnb_timestamp_ms(row) for row in rows) if timestamp is not None]
    first_ms = timestamps[0] if timestamps else None
    last_ms = timestamps[-1] if timestamps else None
    latest = rows[-1] if rows else {}

    return {
        "path": str(data.path) if data.path else None,
        "error": data.error,
        "mtime": data.mtime,
        "rows": len(data.rows),
        "display_rows": len(rows),
        "first_iso": iso_from_epoch_ms(first_ms),
        "last_iso": iso_from_epoch_ms(last_ms),
        "span_ms": (last_ms - first_ms) if first_ms is not None and last_ms is not None else None,
        "row_rate_hz": series_rate_hz(timestamps, 1000.0),
        "latest": {name: latest.get(name, "") for name in ["Timestamp", *GNB_METRICS]},
        "summary": numeric_summary(rows, GNB_METRICS),
        "series": [
            {
                "t": parse_gnb_timestamp_ms(row),
                **{name: safe_float(row.get(name)) for name in GNB_METRICS},
            }
            for row in rows
        ],
    }


def summarize_ros(data: CsvData) -> dict[str, Any]:
    rows = data.rows[-MAX_SERIES_ROWS:]
    timestamps = [timestamp for timestamp in (parse_ros_timestamp_ns(row) for row in rows) if timestamp is not None]
    first_ns = timestamps[0] if timestamps else None
    last_ns = timestamps[-1] if timestamps else None
    latest = rows[-1] if rows else {}

    return {
        "path": str(data.path) if data.path else None,
        "error": data.error,
        "mtime": data.mtime,
        "rows": len(data.rows),
        "display_rows": len(rows),
        "first_iso": iso_from_epoch_ns(first_ns),
        "last_iso": iso_from_epoch_ns(last_ns),
        "span_sec": ((last_ns - first_ns) / 1_000_000_000.0)
        if first_ns is not None and last_ns is not None
        else None,
        "csv_row_rate_hz": series_rate_hz(timestamps, 1_000_000_000.0),
        "latest": {name: latest.get(name, "") for name in ["timestamp_iso_utc", *ROS_METRICS]},
        "summary": numeric_summary(rows, ROS_METRICS),
        "series": [
            {
                "t": parse_ros_timestamp_ns(row),
                **{name: safe_float(row.get(name)) for name in ROS_METRICS},
            }
            for row in rows
        ],
    }


def compute_overlap(gnb_data: CsvData, ros_data: CsvData) -> dict[str, Any]:
    gnb_first, gnb_last = time_range_ms(gnb_data.rows, parse_gnb_timestamp_ms)
    ros_first_ns, ros_last_ns = time_range_ms(ros_data.rows, parse_ros_timestamp_ns)
    ros_first = ros_first_ns // 1_000_000 if ros_first_ns is not None else None
    ros_last = ros_last_ns // 1_000_000 if ros_last_ns is not None else None

    overlap_ms = None
    if None not in (gnb_first, gnb_last, ros_first, ros_last):
        overlap_ms = max(0, min(gnb_last, ros_last) - max(gnb_first, ros_first))

    return {
        "gnb_first_iso": iso_from_epoch_ms(gnb_first),
        "gnb_last_iso": iso_from_epoch_ms(gnb_last),
        "ros_first_iso": iso_from_epoch_ms(ros_first),
        "ros_last_iso": iso_from_epoch_ms(ros_last),
        "overlap_ms": overlap_ms,
    }


def snapshot(config: DashboardConfig) -> dict[str, Any]:
    ros_csv = config.ros_csv or resolve_latest_ros_csv(config.ros_root)
    gnb_data = read_csv(config.gnb_csv)
    ros_data = read_csv(ros_csv)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gnb": summarize_gnb(gnb_data),
        "ros": summarize_ros(ros_data),
        "overlap": compute_overlap(gnb_data, ros_data),
        "config": {
            "gnb_csv": str(config.gnb_csv),
            "ros_csv": str(ros_csv) if ros_csv else None,
            "ros_csv_mode": "explicit" if config.ros_csv else "latest",
            "export_dir": str(config.export_dir),
            "max_join_age_sec": config.max_join_age_sec,
        },
    }


def prefixed_headers(prefix: str, headers: list[str]) -> list[str]:
    output: list[str] = []
    seen: dict[str, int] = {}
    for header in headers:
        candidate = f"{prefix}_{safe_name(header)}"
        seen[candidate] = seen.get(candidate, 0) + 1
        if seen[candidate] > 1:
            candidate = f"{candidate}_{seen[candidate]}"
        output.append(candidate)
    return output


def export_combined_csv(config: DashboardConfig) -> dict[str, Any]:
    ros_csv = config.ros_csv or resolve_latest_ros_csv(config.ros_root)
    gnb_data = read_csv(config.gnb_csv)
    ros_data = read_csv(ros_csv)

    if gnb_data.error:
        raise RuntimeError(gnb_data.error)
    if ros_data.error:
        raise RuntimeError(ros_data.error)
    if not gnb_data.rows:
        raise RuntimeError("gNB CSV has no data rows.")
    if not ros_data.rows:
        raise RuntimeError("ROS CSV has no data rows.")

    ros_entries: list[tuple[int, dict[str, str]]] = []
    for row in ros_data.rows:
        timestamp_ns = parse_ros_timestamp_ns(row)
        if timestamp_ns is not None:
            ros_entries.append((timestamp_ns, row))
    ros_entries.sort(key=lambda item: item[0])
    ros_times = [timestamp for timestamp, _ in ros_entries]

    gnb_output_headers = prefixed_headers("gnb", gnb_data.headers)
    ros_output_headers = prefixed_headers("ros", ros_data.headers)
    fieldnames = [
        "join_timestamp_iso_utc",
        "join_timestamp_ms",
        "matched_ros_timestamp_iso_utc",
        "ros_age_sec",
        *gnb_output_headers,
        *ros_output_headers,
    ]

    output_rows: list[dict[str, Any]] = []
    matched_rows = 0
    for gnb_row in gnb_data.rows:
        gnb_timestamp_ms = parse_gnb_timestamp_ms(gnb_row)
        gnb_timestamp_ns = gnb_timestamp_ms * 1_000_000 if gnb_timestamp_ms is not None else None

        matched_ros_row: dict[str, str] | None = None
        matched_ros_ns: int | None = None
        age_sec: float | None = None

        if gnb_timestamp_ns is not None and ros_times:
            index = bisect.bisect_right(ros_times, gnb_timestamp_ns) - 1
            if index >= 0:
                candidate_ns, candidate_row = ros_entries[index]
                candidate_age_sec = (gnb_timestamp_ns - candidate_ns) / 1_000_000_000.0
                if candidate_age_sec >= 0 and candidate_age_sec <= config.max_join_age_sec:
                    matched_ros_row = candidate_row
                    matched_ros_ns = candidate_ns
                    age_sec = candidate_age_sec
                    matched_rows += 1

        output_row: dict[str, Any] = {
            "join_timestamp_iso_utc": iso_from_epoch_ms(gnb_timestamp_ms),
            "join_timestamp_ms": gnb_timestamp_ms,
            "matched_ros_timestamp_iso_utc": iso_from_epoch_ns(matched_ros_ns),
            "ros_age_sec": f"{age_sec:.6f}" if age_sec is not None else "",
        }

        for source_header, output_header in zip(gnb_data.headers, gnb_output_headers):
            output_row[output_header] = gnb_row.get(source_header, "")
        for source_header, output_header in zip(ros_data.headers, ros_output_headers):
            output_row[output_header] = matched_ros_row.get(source_header, "") if matched_ros_row else ""
        output_rows.append(output_row)

    config.export_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.export_dir / f"combined_gnb_ros_{utc_now_compact()}.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return {
        "output_path": str(output_path.resolve()),
        "rows": len(output_rows),
        "matched_rows": matched_rows,
        "gnb_csv": str(gnb_data.path),
        "ros_csv": str(ros_data.path),
        "max_join_age_sec": config.max_join_age_sec,
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KPI Dashboard</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #62707f;
      --line: #d7dde3;
      --panel: #ffffff;
      --gnb: #087f5b;
      --gnb2: #1864ab;
      --ros: #c2410c;
      --ros2: #7c3aed;
      --warn: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 20px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
    }
    .header-meta {
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 62vw;
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    button {
      border: 1px solid #aeb8c2;
      background: #ffffff;
      color: var(--ink);
      border-radius: 6px;
      padding: 7px 11px;
      font-size: 13px;
      cursor: pointer;
    }
    button:hover { border-color: #64748b; background: #f8fafc; }
    button.primary {
      background: #17202a;
      color: #ffffff;
      border-color: #17202a;
    }
    main {
      display: grid;
      grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
      height: calc(100vh - 58px);
    }
    section {
      min-height: 0;
      padding: 14px 20px 16px;
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: 310px minmax(0, 1fr);
      gap: 16px;
    }
    section:last-child { border-bottom: 0; }
    .side {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .section-title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
    }
    h2 {
      margin: 0;
      font-size: 16px;
      font-weight: 700;
    }
    .status {
      font-size: 12px;
      color: var(--muted);
    }
    .tiles {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .tile {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      min-height: 62px;
    }
    .label {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .value {
      margin-top: 5px;
      font-size: 18px;
      font-weight: 700;
      line-height: 1.1;
      overflow-wrap: anywhere;
    }
    .workspace {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: minmax(120px, 1fr) auto;
      gap: 10px;
    }
    .chart-wrap {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      min-height: 0;
    }
    canvas {
      width: 100%;
      height: 100%;
      display: block;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      font-size: 12px;
    }
    th, td {
      border-bottom: 1px solid #edf0f3;
      padding: 5px 7px;
      text-align: right;
      white-space: nowrap;
    }
    th:first-child, td:first-child { text-align: left; }
    tr:last-child td { border-bottom: 0; }
    th {
      color: var(--muted);
      font-weight: 650;
      background: #fbfcfd;
    }
    .message {
      font-size: 12px;
      color: var(--muted);
      min-height: 18px;
    }
    .error { color: var(--warn); }
    @media (max-width: 900px) {
      main { height: auto; grid-template-rows: auto auto; }
      section { grid-template-columns: 1fr; }
      .header-meta { display: none; }
      .workspace { grid-template-rows: 240px auto; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>ROS 2 and gNB KPI Dashboard</h1>
      <div id="paths" class="header-meta">Loading paths...</div>
    </div>
    <div class="actions">
      <button id="refresh">Refresh</button>
      <button id="export" class="primary">Export Combined CSV</button>
    </div>
  </header>
  <main>
    <section>
      <div class="side">
        <div class="section-title">
          <h2>gNB / 5G KPI</h2>
          <div id="gnb-status" class="status">-</div>
        </div>
        <div id="gnb-tiles" class="tiles"></div>
        <div id="gnb-message" class="message"></div>
      </div>
      <div class="workspace">
        <div class="chart-wrap"><canvas id="gnb-chart"></canvas></div>
        <div id="gnb-table"></div>
      </div>
    </section>
    <section>
      <div class="side">
        <div class="section-title">
          <h2>ROS 2 KPI</h2>
          <div id="ros-status" class="status">-</div>
        </div>
        <div id="ros-tiles" class="tiles"></div>
        <div id="ros-message" class="message"></div>
      </div>
      <div class="workspace">
        <div class="chart-wrap"><canvas id="ros-chart"></canvas></div>
        <div id="ros-table"></div>
      </div>
    </section>
  </main>
  <script>
    const POLL_MS = __POLL_MS__;

    function fmt(value, digits = 3) {
      if (value === null || value === undefined || value === "") return "-";
      const number = Number(value);
      if (!Number.isFinite(number)) return String(value);
      if (Math.abs(number) >= 1000) return number.toFixed(0);
      if (Math.abs(number) >= 100) return number.toFixed(1);
      return number.toFixed(digits);
    }

    function shortTime(iso) {
      if (!iso) return "-";
      const date = new Date(iso);
      if (Number.isNaN(date.getTime())) return iso;
      return date.toISOString().slice(11, 23) + "Z";
    }

    function setTiles(id, items) {
      const root = document.getElementById(id);
      root.innerHTML = items.map(([label, value, suffix]) => `
        <div class="tile">
          <div class="label">${label}</div>
          <div class="value">${fmt(value)}${suffix || ""}</div>
        </div>
      `).join("");
    }

    function table(id, rows, columns) {
      const root = document.getElementById(id);
      const visible = rows.slice(-8).reverse();
      root.innerHTML = `
        <table>
          <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead>
          <tbody>
            ${visible.map(row => `<tr>${columns.map(c => `<td>${c.format ? c.format(row[c.key]) : fmt(row[c.key])}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      `;
    }

    function drawLine(canvas, series, specs) {
      const ctx = canvas.getContext("2d");
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * ratio));
      canvas.height = Math.max(1, Math.floor(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);

      const pad = { left: 44, right: 12, top: 14, bottom: 28 };
      const width = rect.width - pad.left - pad.right;
      const height = rect.height - pad.top - pad.bottom;
      ctx.strokeStyle = "#d7dde3";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, pad.top);
      ctx.lineTo(pad.left, pad.top + height);
      ctx.lineTo(pad.left + width, pad.top + height);
      ctx.stroke();

      const valid = series.filter(point => point && point.t !== null && point.t !== undefined);
      if (!valid.length) {
        ctx.fillStyle = "#62707f";
        ctx.font = "13px sans-serif";
        ctx.fillText("No data", pad.left + 10, pad.top + 28);
        return;
      }

      const xs = valid.map(point => Number(point.t));
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      let values = [];
      for (const spec of specs) {
        for (const point of valid) {
          const v = Number(point[spec.key]);
          if (Number.isFinite(v)) values.push(v);
        }
      }
      if (!values.length) return;
      let minY = Math.min(...values);
      let maxY = Math.max(...values);
      if (minY === maxY) {
        const padY = Math.max(1, Math.abs(minY) * 0.08);
        minY -= padY;
        maxY += padY;
      }

      function xScale(x) {
        if (maxX === minX) return pad.left + width / 2;
        return pad.left + ((x - minX) / (maxX - minX)) * width;
      }
      function yScale(y) {
        return pad.top + height - ((y - minY) / (maxY - minY)) * height;
      }

      ctx.fillStyle = "#62707f";
      ctx.font = "11px sans-serif";
      ctx.fillText(fmt(maxY), 4, pad.top + 8);
      ctx.fillText(fmt(minY), 4, pad.top + height);

      for (const spec of specs) {
        ctx.strokeStyle = spec.color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        let started = false;
        for (const point of valid) {
          const y = Number(point[spec.key]);
          if (!Number.isFinite(y)) continue;
          const px = xScale(Number(point.t));
          const py = yScale(y);
          if (!started) {
            ctx.moveTo(px, py);
            started = true;
          } else {
            ctx.lineTo(px, py);
          }
        }
        ctx.stroke();
      }

      let legendX = pad.left + 8;
      for (const spec of specs) {
        ctx.fillStyle = spec.color;
        ctx.fillRect(legendX, 4, 10, 3);
        ctx.fillStyle = "#17202a";
        ctx.fillText(spec.label, legendX + 14, 9);
        legendX += 92;
      }
    }

    async function loadData() {
      const response = await fetch("/api/data", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }

    async function refresh() {
      try {
        const data = await loadData();
        document.getElementById("paths").textContent =
          `gNB: ${data.config.gnb_csv} | ROS: ${data.config.ros_csv || "not found"} | join age <= ${data.config.max_join_age_sec}s`;

        const gnb = data.gnb;
        const ros = data.ros;
        document.getElementById("gnb-status").textContent =
          `${gnb.rows} rows | ${fmt(gnb.row_rate_hz, 1)} Hz | ${shortTime(gnb.last_iso)}`;
        document.getElementById("ros-status").textContent =
          `${ros.rows} rows | CSV ${fmt(ros.csv_row_rate_hz, 2)} Hz | ${shortTime(ros.last_iso)}`;

        document.getElementById("gnb-message").className = gnb.error ? "message error" : "message";
        document.getElementById("gnb-message").textContent = gnb.error || `Window span ${fmt(gnb.span_ms, 1)} ms`;
        document.getElementById("ros-message").className = ros.error ? "message error" : "message";
        document.getElementById("ros-message").textContent = ros.error || `Overlap ${fmt(data.overlap.overlap_ms, 1)} ms`;

        setTiles("gnb-tiles", [
          ["UL_THR", gnb.latest.UL_THR, ""],
          ["ul_BLER", gnb.latest.ul_BLER, ""],
          ["ul_MCS", gnb.latest.ul_MCS, ""],
          ["SNR", gnb.latest.SNR, ""],
          ["PH_dB", gnb.latest.PH_dB, ""],
          ["raw_rssi", gnb.latest.raw_rssi, ""],
          ["ulsch_rbs", gnb.latest.ulsch_current_rbs, ""],
          ["ulsch_bytes", gnb.latest.ulsch_current_bytes, ""],
        ]);
        setTiles("ros-tiles", [
          ["avg_latency_ms", ros.latest.avg_latency_ms, " ms"],
          ["p99_latency_ms", ros.latest.p99_latency_ms, " ms"],
          ["jitter_ms", ros.latest.jitter_ms, " ms"],
          ["recv_rate_hz", ros.latest.recv_rate_hz, " Hz"],
          ["throughput_Bps", ros.latest.throughput_Bps, " B/s"],
          ["sample_count", ros.latest.sample_count, ""],
          ["loss_rate", ros.latest.loss_rate, ""],
          ["out_of_order", ros.latest.out_of_order_count, ""],
        ]);

        drawLine(document.getElementById("gnb-chart"), gnb.series, [
          { key: "UL_THR", color: "#1864ab", label: "UL_THR" },
          { key: "ul_BLER", color: "#c2410c", label: "ul_BLER" },
          { key: "SNR", color: "#087f5b", label: "SNR" },
        ]);
        drawLine(document.getElementById("ros-chart"), ros.series, [
          { key: "avg_latency_ms", color: "#c2410c", label: "avg ms" },
          { key: "p99_latency_ms", color: "#7c3aed", label: "p99 ms" },
          { key: "jitter_ms", color: "#087f5b", label: "jitter" },
        ]);

        table("gnb-table", gnb.series, [
          { key: "t", label: "time", format: value => shortTime(new Date(Number(value)).toISOString()) },
          { key: "UL_THR", label: "UL_THR" },
          { key: "ul_BLER", label: "ul_BLER" },
          { key: "ul_MCS", label: "ul_MCS" },
          { key: "SNR", label: "SNR" },
          { key: "raw_rssi", label: "raw_rssi" },
        ]);
        table("ros-table", ros.series, [
          { key: "t", label: "time", format: value => shortTime(new Date(Number(value) / 1000000).toISOString()) },
          { key: "avg_latency_ms", label: "avg ms" },
          { key: "p99_latency_ms", label: "p99 ms" },
          { key: "jitter_ms", label: "jitter" },
          { key: "recv_rate_hz", label: "rate Hz" },
          { key: "loss_rate", label: "loss" },
        ]);
      } catch (err) {
        document.getElementById("paths").textContent = String(err);
      }
    }

    async function exportCombined() {
      const button = document.getElementById("export");
      button.disabled = true;
      button.textContent = "Exporting...";
      try {
        const response = await fetch("/api/export", { method: "POST" });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        alert(`Exported ${payload.rows} rows, matched ${payload.matched_rows} rows\n${payload.output_path}`);
      } catch (err) {
        alert(String(err));
      } finally {
        button.disabled = false;
        button.textContent = "Export Combined CSV";
      }
    }

    document.getElementById("refresh").addEventListener("click", refresh);
    document.getElementById("export").addEventListener("click", exportCombined);
    window.addEventListener("resize", refresh);
    refresh();
    setInterval(refresh, POLL_MS);
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server: "DashboardServer"

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.write_html(HTML_TEMPLATE.replace("__POLL_MS__", str(self.server.config.poll_ms)))
            return
        if parsed.path == "/api/data":
            self.write_json(snapshot(self.server.config))
            return
        if parsed.path == "/api/export":
            self.handle_export()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/export":
            self.handle_export()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_export(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        config = self.server.config
        if "max_join_age_sec" in params:
            try:
                config = DashboardConfig(
                    gnb_csv=config.gnb_csv,
                    ros_csv=config.ros_csv,
                    ros_root=config.ros_root,
                    export_dir=config.export_dir,
                    poll_ms=config.poll_ms,
                    max_join_age_sec=float(params["max_join_age_sec"][0]),
                )
            except ValueError:
                self.write_json({"error": "Invalid max_join_age_sec."}, status=HTTPStatus.BAD_REQUEST)
                return

        try:
            result = export_combined_csv(config)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.write_json(result)

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], config: DashboardConfig) -> None:
        super().__init__(address, DashboardRequestHandler)
        self.config = config


def build_config(args: argparse.Namespace) -> DashboardConfig:
    return DashboardConfig(
        gnb_csv=Path(args.gnb_csv),
        ros_csv=Path(args.ros_csv) if args.ros_csv else None,
        ros_root=Path(args.ros_root),
        export_dir=Path(args.export_dir),
        poll_ms=max(50, int(args.poll_ms)),
        max_join_age_sec=max(0.0, float(args.max_join_age_sec)),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live dashboard for gNB and ROS 2 KPI CSV files.")
    parser.add_argument("--gnb-csv", default=str(DEFAULT_GNB_CSV), help="Path to the high-rate gNB CSV.")
    parser.add_argument(
        "--ros-csv",
        default="",
        help="Path to a ROS KPI CSV. If omitted, the newest output/kpi_metrics run is used.",
    )
    parser.add_argument("--ros-root", default=str(DEFAULT_ROS_ROOT), help="Root directory containing ROS KPI run_* folders.")
    parser.add_argument("--export-dir", default=str(DEFAULT_EXPORT_DIR), help="Directory for combined CSV exports.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=8765, help="HTTP bind port.")
    parser.add_argument("--poll-ms", type=int, default=DEFAULT_POLL_MS, help="Browser polling interval in milliseconds.")
    parser.add_argument(
        "--max-join-age-sec",
        type=float,
        default=DEFAULT_MAX_JOIN_AGE_SEC,
        help="Maximum allowed age when attaching the latest ROS row to each gNB row.",
    )
    parser.add_argument(
        "--export-once",
        action="store_true",
        help="Export one combined CSV and exit instead of starting the dashboard server.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_config(args)

    if args.export_once:
        result = export_combined_csv(config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    server = DashboardServer((args.host, args.port), config)
    print(f"KPI dashboard listening on http://{args.host}:{args.port}")
    print(f"gNB CSV: {config.gnb_csv}")
    print(f"ROS CSV: {config.ros_csv or 'latest under ' + str(config.ros_root)}")
    print(f"Combined CSV export dir: {config.export_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_one(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError(f"Expected one summary row in {path}, found {len(rows)}")
    return rows[0]


def number(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        raise ValueError(f"Missing metric {key} in run {row.get('run_id')}")
    return float(value)


def runtime_anomalies(path: Path) -> int:
    if not path.exists():
        return -1
    markers = ("job timeout", "failed to wait job", "soft reset")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return sum(1 for line in lines if any(marker in line.lower() for marker in markers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare RK3588 buffer reuse on/off pipeline runs")
    parser.add_argument("--reuse-summary", required=True)
    parser.add_argument("--noreuse-summary", required=True)
    parser.add_argument("--reuse-monitor", required=True)
    parser.add_argument("--noreuse-monitor", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    reuse = read_one(Path(args.reuse_summary))
    noreuse = read_one(Path(args.noreuse_summary))
    rows = []
    for mode, row, monitor in (
        ("reuse_on", reuse, Path(args.reuse_monitor)),
        ("reuse_off", noreuse, Path(args.noreuse_monitor)),
    ):
        rows.append({
            "run_id": row["run_id"],
            "buffer_reuse_mode": mode,
            "frames": int(float(row["frames"])),
            "fps": number(row, "fps_estimated"),
            "inference_p50_ms": number(row, "inference_p50_ms"),
            "inference_p95_ms": number(row, "inference_p95_ms"),
            "latency_p95_ms": number(row, "latency_p95_ms"),
            "drop_rate": number(row, "drop_frame_rate_total_estimated"),
            "memory_peak_mb": number(row, "memory_mb_peak"),
            "memory_growth_mb_per_hour": number(row, "memory_growth_mb_per_hour"),
            "new_rknpu_anomaly_lines": runtime_anomalies(monitor),
        })

    reuse_row = rows[0]
    noreuse_row = rows[1]
    fps_gain = reuse_row["fps"] / noreuse_row["fps"] - 1.0
    inference_p50_reduction = 1.0 - reuse_row["inference_p50_ms"] / noreuse_row["inference_p50_ms"]
    latency_p95_reduction = 1.0 - reuse_row["latency_p95_ms"] / noreuse_row["latency_p95_ms"]
    memory_peak_reduction = 1.0 - reuse_row["memory_peak_mb"] / noreuse_row["memory_peak_mb"]
    memory_growth_reduction = 1.0 - reuse_row["memory_growth_mb_per_hour"] / noreuse_row["memory_growth_mb_per_hour"]
    drop_rate_delta = reuse_row["drop_rate"] - noreuse_row["drop_rate"]

    clean = reuse_row["new_rknpu_anomaly_lines"] == 0 and noreuse_row["new_rknpu_anomaly_lines"] == 0
    if not clean:
        decision = "buffer_reuse_runtime_anomaly"
    elif reuse_row["drop_rate"] > noreuse_row["drop_rate"] + 0.002 or reuse_row["fps"] < noreuse_row["fps"] * 0.98:
        decision = "buffer_reuse_regression"
    elif inference_p50_reduction > 0.02 or latency_p95_reduction > 0.02 or memory_growth_reduction > 0.02:
        decision = "buffer_reuse_beneficial"
    else:
        decision = "buffer_reuse_no_material_difference"

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# RK3588 Buffer Reuse A/B",
        "",
        f"- decision: `{decision}`",
        f"- fps_gain: `{fps_gain:.6f}`",
        f"- inference_p50_reduction: `{inference_p50_reduction:.6f}`",
        f"- latency_p95_reduction: `{latency_p95_reduction:.6f}`",
        f"- memory_peak_reduction: `{memory_peak_reduction:.6f}`",
        f"- memory_growth_reduction: `{memory_growth_reduction:.6f}`",
        f"- drop_rate_delta: `{drop_rate_delta:.6f}`",
        "",
        "| run_id | buffer_reuse_mode | frames | FPS | inference_p50_ms | inference_p95_ms | latency_p95_ms | drop_rate | memory_peak_mb | memory_growth_mb_per_hour | new_rknpu_anomaly_lines |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run_id']}` | `{row['buffer_reuse_mode']}` | {row['frames']} | {row['fps']:.6f} | "
            f"{row['inference_p50_ms']:.6f} | {row['inference_p95_ms']:.6f} | {row['latency_p95_ms']:.6f} | "
            f"{row['drop_rate']:.6f} | {row['memory_peak_mb']:.2f} | {row['memory_growth_mb_per_hour']:.6f} | "
            f"{row['new_rknpu_anomaly_lines']} |"
        )

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"decision={decision}")
    print(f"comparison_csv={output_csv}")
    print(f"comparison_md={output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

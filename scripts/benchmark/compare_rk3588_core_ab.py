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
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if any(x in line.lower() for x in markers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare RK3588 core0 and core0/1/2 pipeline runs")
    parser.add_argument("--core0-summary", required=True)
    parser.add_argument("--core012-summary", required=True)
    parser.add_argument("--core0-monitor", required=True)
    parser.add_argument("--core012-monitor", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    core0 = read_one(Path(args.core0_summary))
    core012 = read_one(Path(args.core012_summary))
    rows = []
    for mask, row, monitor in (
        ("core0", core0, Path(args.core0_monitor)),
        ("0_1_2", core012, Path(args.core012_monitor)),
    ):
        rows.append({
            "run_id": row["run_id"],
            "core_mask": mask,
            "frames": int(float(row["frames"])),
            "fps": number(row, "fps_estimated"),
            "inference_p50_ms": number(row, "inference_p50_ms"),
            "inference_p95_ms": number(row, "inference_p95_ms"),
            "latency_p95_ms": number(row, "latency_p95_ms"),
            "drop_rate": number(row, "drop_frame_rate_total_estimated"),
            "new_rknpu_anomaly_lines": runtime_anomalies(monitor),
        })

    baseline, current = rows
    fps_gain = current["fps"] / baseline["fps"] - 1.0
    inference_reduction = 1.0 - current["inference_p50_ms"] / baseline["inference_p50_ms"]
    drop_reduction = baseline["drop_rate"] - current["drop_rate"]
    clean = current["new_rknpu_anomaly_lines"] == 0
    improved = fps_gain > 0.02 and inference_reduction > 0.02
    if improved and current["fps"] >= 29.0 and current["drop_rate"] <= 0.03 and clean:
        decision = "three_core_meets_realtime_target"
    elif improved and clean:
        decision = "three_core_improved_but_below_realtime_target"
    elif not clean:
        decision = "three_core_runtime_anomaly"
    else:
        decision = "three_core_no_material_improvement"

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# RK3588 RKNPU Core Mask A/B",
        "",
        f"- decision: `{decision}`",
        f"- fps_gain: `{fps_gain:.6f}`",
        f"- inference_p50_reduction: `{inference_reduction:.6f}`",
        f"- drop_rate_reduction: `{drop_reduction:.6f}`",
        "",
        "| run_id | core_mask | frames | FPS | inference_p50_ms | inference_p95_ms | latency_p95_ms | drop_rate | new_rknpu_anomaly_lines |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run_id']}` | `{row['core_mask']}` | {row['frames']} | {row['fps']:.6f} | "
            f"{row['inference_p50_ms']:.6f} | {row['inference_p95_ms']:.6f} | "
            f"{row['latency_p95_ms']:.6f} | {row['drop_rate']:.6f} | {row['new_rknpu_anomaly_lines']} |"
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

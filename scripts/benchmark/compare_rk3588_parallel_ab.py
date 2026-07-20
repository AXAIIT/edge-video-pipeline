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
    parser = argparse.ArgumentParser(description="Compare RK3588 one-worker and three-worker pipeline runs")
    parser.add_argument("--single-summary", required=True)
    parser.add_argument("--parallel-summary", required=True)
    parser.add_argument("--single-monitor", required=True)
    parser.add_argument("--parallel-monitor", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    single = read_one(Path(args.single_summary))
    parallel = read_one(Path(args.parallel_summary))
    rows = []
    for workers, binding, row, monitor in (
        (1, "core0", single, Path(args.single_monitor)),
        (3, "core0,core1,core2", parallel, Path(args.parallel_monitor)),
    ):
        rows.append({
            "run_id": row["run_id"],
            "inference_workers": workers,
            "core_binding": binding,
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
    drop_reduction = baseline["drop_rate"] - current["drop_rate"]
    clean = current["new_rknpu_anomaly_lines"] == 0
    if current["fps"] >= 29.0 and current["drop_rate"] <= 0.03 and clean:
        decision = "three_worker_meets_realtime_target"
    elif fps_gain > 0.02 and drop_reduction > 0.02 and clean:
        decision = "three_worker_improved_but_below_realtime_target"
    elif not clean:
        decision = "three_worker_runtime_anomaly"
    else:
        decision = "three_worker_no_material_improvement"

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# RK3588 Multi-context Inference A/B",
        "",
        f"- decision: `{decision}`",
        f"- fps_gain: `{fps_gain:.6f}`",
        f"- drop_rate_reduction: `{drop_reduction:.6f}`",
        "",
        "| run_id | workers | core_binding | frames | FPS | inference_p50_ms | inference_p95_ms | latency_p95_ms | drop_rate | new_rknpu_anomaly_lines |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run_id']}` | {row['inference_workers']} | `{row['core_binding']}` | {row['frames']} | "
            f"{row['fps']:.6f} | {row['inference_p50_ms']:.6f} | {row['inference_p95_ms']:.6f} | "
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

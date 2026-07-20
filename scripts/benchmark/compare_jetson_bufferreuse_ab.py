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


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Jetson TensorRT buffer reuse on/off pipeline runs")
    parser.add_argument("--reuse-summary", required=True)
    parser.add_argument("--noreuse-summary", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    reuse = read_one(Path(args.reuse_summary))
    noreuse = read_one(Path(args.noreuse_summary))
    rows: list[dict[str, object]] = []
    for mode, row in (("reuse_on", reuse), ("reuse_off", noreuse)):
        rows.append({
            "run_id": row["run_id"],
            "buffer_reuse_mode": mode,
            "frames": int(float(row["frames"])),
            "fps": number(row, "fps_estimated"),
            "capture_p50_ms": number(row, "capture_p50_ms"),
            "inference_p50_ms": number(row, "inference_p50_ms"),
            "latency_p95_ms": number(row, "latency_p95_ms"),
            "drop_rate": number(row, "drop_frame_rate_total_estimated"),
            "memory_peak_mb": number(row, "memory_mb_peak"),
            "memory_growth_mb_per_hour": number(row, "memory_growth_mb_per_hour"),
            "temperature_peak_c": number(row, "temperature_c_peak"),
            "cpu_fallback": row.get("cpu_fallback", ""),
            "status": row.get("status", ""),
        })

    reuse_row = rows[0]
    noreuse_row = rows[1]
    fps_gain = float(reuse_row["fps"]) / float(noreuse_row["fps"]) - 1.0
    capture_p50_reduction = 1.0 - float(reuse_row["capture_p50_ms"]) / float(noreuse_row["capture_p50_ms"])
    inference_p50_reduction = 1.0 - float(reuse_row["inference_p50_ms"]) / float(noreuse_row["inference_p50_ms"])
    latency_p95_reduction = 1.0 - float(reuse_row["latency_p95_ms"]) / float(noreuse_row["latency_p95_ms"])
    memory_peak_reduction = 1.0 - float(reuse_row["memory_peak_mb"]) / float(noreuse_row["memory_peak_mb"])
    memory_growth_reduction = 1.0 - float(reuse_row["memory_growth_mb_per_hour"]) / float(noreuse_row["memory_growth_mb_per_hour"])
    drop_rate_delta = float(reuse_row["drop_rate"]) - float(noreuse_row["drop_rate"])
    cpu_fallback_seen = str(reuse_row["cpu_fallback"]).lower() == "true" or str(noreuse_row["cpu_fallback"]).lower() == "true"
    status_bad = str(reuse_row["status"]) != "pass" or str(noreuse_row["status"]) != "pass"

    if cpu_fallback_seen or status_bad:
        decision = "buffer_reuse_ab_not_clean"
    elif float(reuse_row["drop_rate"]) > float(noreuse_row["drop_rate"]) + 0.002 or float(reuse_row["fps"]) < float(noreuse_row["fps"]) * 0.98:
        decision = "buffer_reuse_regression"
    elif (
        capture_p50_reduction > 0.02
        or inference_p50_reduction > 0.02
        or latency_p95_reduction > 0.02
        or memory_peak_reduction > 0.02
        or memory_growth_reduction > 0.02
    ):
        decision = "buffer_reuse_beneficial"
    else:
        decision = "buffer_reuse_no_material_difference"

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Jetson TensorRT Buffer Reuse A/B",
        "",
        f"- decision: `{decision}`",
        f"- fps_gain: `{fps_gain:.6f}`",
        f"- capture_p50_reduction: `{capture_p50_reduction:.6f}`",
        f"- inference_p50_reduction: `{inference_p50_reduction:.6f}`",
        f"- latency_p95_reduction: `{latency_p95_reduction:.6f}`",
        f"- memory_peak_reduction: `{memory_peak_reduction:.6f}`",
        f"- memory_growth_reduction: `{memory_growth_reduction:.6f}`",
        f"- drop_rate_delta: `{drop_rate_delta:.6f}`",
        "",
        "| run_id | buffer_reuse_mode | frames | FPS | capture_p50_ms | inference_p50_ms | latency_p95_ms | drop_rate | memory_peak_mb | memory_growth_mb_per_hour | temperature_peak_c | cpu_fallback | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run_id']}` | `{row['buffer_reuse_mode']}` | {row['frames']} | {float(row['fps']):.6f} | "
            f"{float(row['capture_p50_ms']):.6f} | {float(row['inference_p50_ms']):.6f} | {float(row['latency_p95_ms']):.6f} | "
            f"{float(row['drop_rate']):.6f} | {float(row['memory_peak_mb']):.2f} | {float(row['memory_growth_mb_per_hour']):.6f} | "
            f"{float(row['temperature_peak_c']):.2f} | {row['cpu_fallback']} | {row['status']} |"
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

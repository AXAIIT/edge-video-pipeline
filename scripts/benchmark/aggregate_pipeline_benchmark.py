#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import raw_scope


STAGE_FIELDS = [
    "capture_ms",
    "decode_ms",
    "preprocess_ms",
    "inference_ms",
    "postprocess_ms",
    "output_ms",
]

QUEUE_FIELDS = [
    "queue_capture_size",
    "queue_preprocess_size",
    "queue_infer_size",
    "queue_postprocess_size",
]

FIELDNAMES = [
    "run_id",
    "target",
    "board",
    "environment_baseline_id",
    "backend_runtime",
    "execution_provider",
    "loader_api",
    "precision_or_quantization",
    "backend_artifact_sha256",
    "input_source_id",
    "input_source_type",
    "pipeline_mode",
    "queue_policy",
    "queue_capacity",
    "queue_push_timeout_ms",
    "inference_workers",
    "postprocess_workers",
    "rknn_core_binding",
    "buffer_reuse",
    "frames",
    "pass_frames",
    "duration_sec_estimated",
    "fps_estimated",
    "latency_p50_ms",
    "latency_p90_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "capture_p50_ms",
    "capture_p95_ms",
    "capture_p99_ms",
    "decode_p50_ms",
    "decode_p95_ms",
    "decode_p99_ms",
    "preprocess_p50_ms",
    "preprocess_p95_ms",
    "preprocess_p99_ms",
    "inference_p50_ms",
    "inference_p95_ms",
    "inference_p99_ms",
    "postprocess_p50_ms",
    "postprocess_p95_ms",
    "postprocess_p99_ms",
    "output_p50_ms",
    "output_p95_ms",
    "output_p99_ms",
    "queue_capture_p95",
    "queue_capture_max",
    "queue_preprocess_p95",
    "queue_preprocess_max",
    "queue_infer_p95",
    "queue_infer_max",
    "queue_postprocess_p95",
    "queue_postprocess_max",
    "queue_max",
    "frame_id_max",
    "input_frames_estimated",
    "drop_frame_count_total_estimated",
    "drop_frame_rate_total_estimated",
    "frame_keep_rate_estimated",
    "drop_frame_count_max",
    "drop_frame_rate_max",
    "dropped_frame_reason",
    "output_valid_rate",
    "detection_count_mean",
    "memory_mb_peak",
    "memory_growth_mb_per_hour",
    "temperature_c_peak",
    "power_mode",
    "power_w_avg",
    "power_w_peak",
    "cpu_util_avg",
    "gpu_util_avg",
    "throttle_events",
    "cpu_fallback",
    "fallback_reason",
    "runtime_log_path",
    "monitor_log_path",
    "failure_log_path",
    "related_troubleshooting_id",
    "status",
]


def percentile(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return ""
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else ""


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_iso_ts(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def read_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return records


def iter_jsonl(path):
    files, _ = collect_jsonl_inputs(path)
    yield from files


def collect_jsonl_inputs(path, include_legacy=False, exclude_subdirs=None):
    return raw_scope.collect_jsonl_inputs(
        path,
        exclude_subdirs=exclude_subdirs,
        include_legacy=include_legacy,
    )


def parse_monitor(path):
    if not path:
        return {}
    monitor = Path(path)
    if not monitor.exists():
        return {}

    memory = []
    temperatures = []
    power_w = []
    gpu_util = []
    cpu_util = []
    throttle_events = 0
    process_rss = []
    process_hwm = []

    temp_re = re.compile(r"@([0-9]+(?:\.[0-9]+)?)C")
    ram_re = re.compile(r"RAM\s+([0-9]+(?:\.[0-9]+)?)/", re.IGNORECASE)
    gr3d_re = re.compile(r"GR3D_FREQ\s+([0-9]+)%", re.IGNORECASE)
    cpu_re = re.compile(r"CPU\s+\[([^\]]+)\]", re.IGNORECASE)
    power_re = re.compile(r"(?:POM_5V_IN|VDD_IN|POM_5V_GPU)\s+([0-9]+(?:\.[0-9]+)?)(?:/([0-9]+(?:\.[0-9]+)?))?", re.IGNORECASE)
    process_rss_re = re.compile(r"process_rss_mb=([0-9]+(?:\.[0-9]+)?)")
    process_hwm_re = re.compile(r"process_hwm_mb=([0-9]+(?:\.[0-9]+)?)")
    timestamp_re = re.compile(r"timestamp=([^\s]+)")
    rk_temperature_re = re.compile(r"temperature_c=([0-9]+(?:\.[0-9]+)?)")
    rk_max_temperature_re = re.compile(r"max_temp_c=([0-9]+(?:\.[0-9]+)?)")
    throttle_re = re.compile(r"\bthrot(?:tle|tling|tled)?\b|\bthermal[_ -]?thrott\w*\b", re.IGNORECASE)

    for line in monitor.read_text(encoding="utf-8", errors="ignore").splitlines():
        ram_match = ram_re.search(line)
        if ram_match:
            memory.append(float(ram_match.group(1)))
        temperatures.extend(float(x) for x in temp_re.findall(line))
        process_rss_match = process_rss_re.search(line)
        if process_rss_match:
            timestamp_match = timestamp_re.search(line)
            if timestamp_match:
                try:
                    timestamp = dt.datetime.fromisoformat(timestamp_match.group(1))
                    process_rss.append((timestamp, float(process_rss_match.group(1))))
                except ValueError:
                    pass
        process_hwm_match = process_hwm_re.search(line)
        if process_hwm_match:
            process_hwm.append(float(process_hwm_match.group(1)))
        temperatures.extend(float(x) for x in rk_temperature_re.findall(line))
        temperatures.extend(float(x) for x in rk_max_temperature_re.findall(line))
        gr3d_match = gr3d_re.search(line)
        if gr3d_match:
            gpu_util.append(float(gr3d_match.group(1)))
        cpu_match = cpu_re.search(line)
        if cpu_match:
            nums = [float(x) for x in re.findall(r"([0-9]+)%", cpu_match.group(1))]
            if nums:
                cpu_util.append(sum(nums) / len(nums))
        for power_match in power_re.finditer(line):
            # tegrastats power values are usually mW.
            power_w.append(float(power_match.group(1)) / 1000.0)
        if throttle_re.search(line):
            throttle_events += 1

    memory_peak = max(memory) if memory else ""
    memory_growth = ""
    if process_rss:
        memory_peak = max(process_hwm, default=max(value for _, value in process_rss))
    if len(process_rss) >= 20:
        count = len(process_rss)
        start_begin, start_end = int(count * 0.10), max(int(count * 0.20), int(count * 0.10) + 1)
        end_begin, end_end = int(count * 0.80), max(int(count * 0.90), int(count * 0.80) + 1)
        start_window = process_rss[start_begin:start_end]
        end_window = process_rss[end_begin:end_end]
        start_value = percentile([value for _, value in start_window], 0.5)
        end_value = percentile([value for _, value in end_window], 0.5)
        start_time = start_window[len(start_window) // 2][0]
        end_time = end_window[len(end_window) // 2][0]
        duration_hours = (end_time - start_time).total_seconds() / 3600.0
        if duration_hours > 0:
            memory_growth = (end_value - start_value) / duration_hours
    elif len(memory) >= 2:
        duration_hours = max(1, len(memory) - 1) / 3600.0
        memory_growth = (memory[-1] - memory[0]) / duration_hours

    return {
        "memory_mb_peak": memory_peak,
        "memory_growth_mb_per_hour": memory_growth,
        "temperature_c_peak": max(temperatures) if temperatures else "",
        "power_w_avg": mean(power_w),
        "power_w_peak": max(power_w) if power_w else "",
        "cpu_util_avg": mean(cpu_util),
        "gpu_util_avg": mean(gpu_util),
        "throttle_events": throttle_events if throttle_events else "",
    }


def estimate_duration_sec(records):
    output_ts = [parse_iso_ts(r.get("output_ts")) for r in records]
    output_ts = [ts for ts in output_ts if ts is not None]
    if len(output_ts) >= 2:
        duration_sec = (max(output_ts) - min(output_ts)).total_seconds()
        if duration_sec > 0:
            return duration_sec

    input_fps = to_float(records[0].get("input_fps"))
    if input_fps and input_fps > 0:
        return len(records) / input_fps
    return ""


def summarize_records(records, monitor_override=""):
    if not records:
        return None
    first = records[0]
    pass_rows = [r for r in records if r.get("status") == "pass"]
    latency = [to_float(r.get("end_to_end_latency_ms")) for r in pass_rows]
    duration_sec = estimate_duration_sec(records)
    fps = len(pass_rows) / duration_sec if duration_sec else ""

    row = {
        "run_id": first.get("run_id", ""),
        "target": first.get("target", ""),
        "board": first.get("board", ""),
        "environment_baseline_id": first.get("environment_baseline_id", ""),
        "backend_runtime": first.get("backend_runtime", ""),
        "execution_provider": first.get("execution_provider", ""),
        "loader_api": first.get("loader_api", ""),
        "precision_or_quantization": first.get("precision_or_quantization", ""),
        "backend_artifact_sha256": first.get("backend_artifact_sha256", ""),
        "input_source_id": first.get("input_source_id", ""),
        "input_source_type": first.get("input_source_type", ""),
        "pipeline_mode": first.get("pipeline_mode", ""),
        "queue_policy": first.get("queue_policy", ""),
        "queue_capacity": first.get("queue_capacity", ""),
        "queue_push_timeout_ms": first.get("queue_push_timeout_ms", ""),
        "inference_workers": first.get("inference_workers", ""),
        "postprocess_workers": first.get("postprocess_workers", ""),
        "rknn_core_binding": first.get("rknn_core_binding", ""),
        "buffer_reuse": first.get("buffer_reuse", ""),
        "frames": len(records),
        "pass_frames": len(pass_rows),
        "duration_sec_estimated": duration_sec,
        "fps_estimated": fps,
        "latency_p50_ms": percentile(latency, 0.50),
        "latency_p90_ms": percentile(latency, 0.90),
        "latency_p95_ms": percentile(latency, 0.95),
        "latency_p99_ms": percentile(latency, 0.99),
        "cpu_fallback": first.get("cpu_fallback", ""),
        "fallback_reason": first.get("fallback_reason", ""),
        "runtime_log_path": first.get("runtime_log_path", ""),
        "monitor_log_path": monitor_override or first.get("monitor_log_path", ""),
        "failure_log_path": first.get("failure_log_path", ""),
        "related_troubleshooting_id": first.get("related_troubleshooting_id", ""),
    }

    for field in STAGE_FIELDS:
        values = [to_float(r.get(field)) for r in records]
        prefix = field[:-3] if field.endswith("_ms") else field
        row[f"{prefix}_p50_ms"] = percentile(values, 0.50)
        row[f"{prefix}_p95_ms"] = percentile(values, 0.95)
        row[f"{prefix}_p99_ms"] = percentile(values, 0.99)

    queue_maxes = []
    for field in QUEUE_FIELDS:
        values = [to_int(r.get(field)) for r in records]
        prefix = field
        if prefix.startswith("queue_"):
            prefix = prefix[len("queue_"):]
        if prefix.endswith("_size"):
            prefix = prefix[:-len("_size")]
        row[f"queue_{prefix}_p95"] = percentile(values, 0.95)
        row[f"queue_{prefix}_max"] = max([v for v in values if v is not None], default="")
        if row[f"queue_{prefix}_max"] != "":
            queue_maxes.append(row[f"queue_{prefix}_max"])
    row["queue_max"] = max(queue_maxes) if queue_maxes else ""

    frame_ids = [to_int(r.get("frame_id")) for r in records]
    frame_ids = [v for v in frame_ids if v is not None]
    frame_id_max = max(frame_ids, default="")
    input_frames_estimated = frame_id_max + 1 if frame_id_max != "" else ""
    drop_count_total_estimated = (
        max(input_frames_estimated - len(records), 0) if input_frames_estimated != "" else ""
    )
    drop_rate_total_estimated = (
        drop_count_total_estimated / input_frames_estimated
        if input_frames_estimated not in ("", 0)
        else ""
    )
    keep_rate_estimated = (
        len(records) / input_frames_estimated
        if input_frames_estimated not in ("", 0)
        else ""
    )
    row["frame_id_max"] = frame_id_max
    row["input_frames_estimated"] = input_frames_estimated
    row["drop_frame_count_total_estimated"] = drop_count_total_estimated
    row["drop_frame_rate_total_estimated"] = drop_rate_total_estimated
    row["frame_keep_rate_estimated"] = keep_rate_estimated

    drop_counts = [to_int(r.get("drop_frame_count")) for r in records]
    drop_rates = [to_float(r.get("drop_frame_rate")) for r in records]
    reasons = sorted({r.get("dropped_frame_reason") for r in records if r.get("dropped_frame_reason")})
    output_valid = [r.get("output_valid") for r in records if r.get("output_valid") is not None]
    detection_counts = [to_float(r.get("detection_count")) for r in records]
    row["drop_frame_count_max"] = max([v for v in drop_counts if v is not None], default="")
    row["drop_frame_rate_max"] = max([v for v in drop_rates if v is not None], default="")
    row["dropped_frame_reason"] = ";".join(reasons)
    row["output_valid_rate"] = (
        sum(1 for v in output_valid if v is True) / len(output_valid) if output_valid else ""
    )
    row["detection_count_mean"] = mean(detection_counts)

    raw_memory = [to_float(r.get("memory_mb")) for r in records]
    raw_temperature = [to_float(r.get("temperature_c")) for r in records]
    raw_power = [to_float(r.get("power_w")) for r in records]
    row["memory_mb_peak"] = max([v for v in raw_memory if v is not None], default="")
    row["memory_growth_mb_per_hour"] = ""
    row["temperature_c_peak"] = max([v for v in raw_temperature if v is not None], default="")
    row["power_mode"] = first.get("power_mode", "")
    row["power_w_avg"] = mean(raw_power)
    row["power_w_peak"] = max([v for v in raw_power if v is not None], default="")
    row["cpu_util_avg"] = ""
    row["gpu_util_avg"] = ""
    row["throttle_events"] = ""

    monitor_metrics = parse_monitor(row["monitor_log_path"])
    for key, value in monitor_metrics.items():
        if value != "":
            row[key] = value

    if not all(r.get("status") == "pass" for r in records):
        row["status"] = "degraded"
    elif row.get("cpu_fallback") is True:
        row["status"] = "fail"
    elif not row.get("monitor_log_path"):
        row["status"] = "not_verified"
    else:
        row["status"] = "pass"

    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--monitor", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--exclude-subdir", action="append", default=[])
    parser.add_argument("--include-legacy", action="store_true")
    args = parser.parse_args()

    rows = []
    files, _ = collect_jsonl_inputs(
        args.input,
        include_legacy=args.include_legacy,
        exclude_subdirs=args.exclude_subdir,
    )
    for path in files:
        records = read_jsonl(path)
        summary = summarize_records(records, args.monitor)
        if summary:
            rows.append(summary)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

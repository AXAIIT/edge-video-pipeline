#!/usr/bin/env python3
import argparse
import csv
import importlib.util
import re
from pathlib import Path


FIELDNAMES = [
    "run_id",
    "board",
    "target",
    "backend_runtime",
    "input_source_id",
    "pipeline_mode",
    "stability_tier",
    "target_duration_sec",
    "actual_duration_sec",
    "completed",
    "stop_reason",
    "restart_count",
    "reconnect_count",
    "crash_count",
    "watchdog_timeout_count",
    "fps",
    "p95_end_to_end_latency_ms",
    "p99_end_to_end_latency_ms",
    "drop_frame_rate",
    "memory_growth_mb",
    "temperature_c",
    "power_w",
    "throttle_events",
    "runtime_log_path",
    "monitor_log_path",
    "failure_log_path",
    "status",
    "related_troubleshooting_id",
]

TIER_SECONDS = {
    "smoke": 600,
    "short_sustained": 1800,
    "acceptance_sustained": 7200,
    "long_sustained": 28800,
}


def load_aggregate_module():
    script = Path(__file__).resolve().parent / "aggregate_pipeline_benchmark.py"
    spec = importlib.util.spec_from_file_location("aggregate_pipeline_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer_tier(run_id):
    for tier in TIER_SECONDS:
        if tier in run_id:
            return tier
    alias_patterns = {
        "smoke": [r"(?:^|_)stability_smoke(?:_|$)"],
        "short_sustained": [r"(?:^|_)stability_short(?:_|$)"],
        "acceptance_sustained": [r"(?:^|_)stability_acceptance(?:_|$)"],
        "long_sustained": [r"(?:^|_)stability_long(?:_|$)", r"(?:^|_)8h(?:_|$)"],
    }
    for tier, patterns in alias_patterns.items():
        if any(re.search(pattern, run_id) for pattern in patterns):
            return tier
    if "stability" in run_id:
        return "unknown"
    return ""


def infer_target_duration(run_id, tier):
    if tier == "long_sustained" and "_8h_" in run_id:
        mixed_component = re.search(r"_(?:[a-z0-9]+)?(\d+)h$", run_id)
        if mixed_component:
            return int(mixed_component.group(1)) * 3600
    return TIER_SECONDS.get(tier, "")


def count_failure_events(path):
    if not path:
        return {"restart_count": "", "reconnect_count": "", "crash_count": "", "watchdog_timeout_count": ""}
    failure = Path(path)
    if not failure.exists():
        return {"restart_count": "", "reconnect_count": "", "crash_count": "", "watchdog_timeout_count": ""}
    text = failure.read_text(encoding="utf-8", errors="ignore").lower()
    return {
        "restart_count": len(re.findall(r"restart|systemd_restart", text)),
        "reconnect_count": len(re.findall(r"reconnect|input_disconnect", text)),
        "crash_count": len(re.findall(r"crash|segfault|core dumped", text)),
        "watchdog_timeout_count": len(re.findall(r"watchdog|timeout", text)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--monitor", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    agg = load_aggregate_module()
    root = Path(args.raw)
    if root.is_file():
        files = [root]
    else:
        files, _ = agg.collect_jsonl_inputs(args.raw)
    rows = []
    for path in files:
        data = agg.read_jsonl(path)
        if not data:
            continue
        run_id = data[0].get("run_id", "")
        tier = infer_tier(run_id)
        if not tier:
            continue

        summary = agg.summarize_records(data, args.monitor)
        target_duration = infer_target_duration(run_id, tier)
        actual_duration = summary.get("duration_sec_estimated", "")
        completed = False
        if target_duration and actual_duration != "":
            completed = float(actual_duration) >= float(target_duration) * 0.98

        failure_path = summary.get("failure_log_path", "")
        event_counts = count_failure_events(failure_path)
        status = summary.get("status", "")
        stop_reason = ""
        if target_duration and actual_duration != "" and not completed:
            stop_reason = "duration_shorter_than_target"
            status = "fail" if status == "pass" else status
        if not summary.get("monitor_log_path"):
            status = "not_verified" if status == "pass" else status

        rows.append({
            "run_id": run_id,
            "board": summary.get("board", ""),
            "target": summary.get("target", ""),
            "backend_runtime": summary.get("backend_runtime", ""),
            "input_source_id": summary.get("input_source_id", ""),
            "pipeline_mode": summary.get("pipeline_mode", ""),
            "stability_tier": tier,
            "target_duration_sec": target_duration,
            "actual_duration_sec": actual_duration,
            "completed": str(completed).lower() if target_duration else "",
            "stop_reason": stop_reason,
            "restart_count": event_counts["restart_count"],
            "reconnect_count": event_counts["reconnect_count"],
            "crash_count": event_counts["crash_count"],
            "watchdog_timeout_count": event_counts["watchdog_timeout_count"],
            "fps": summary.get("fps_estimated", ""),
            "p95_end_to_end_latency_ms": summary.get("latency_p95_ms", ""),
            "p99_end_to_end_latency_ms": summary.get("latency_p99_ms", ""),
            "drop_frame_rate": summary.get("drop_frame_rate_total_estimated", ""),
            "memory_growth_mb": summary.get("memory_growth_mb_per_hour", ""),
            "temperature_c": summary.get("temperature_c_peak", ""),
            "power_w": summary.get("power_w_avg", ""),
            "throttle_events": summary.get("throttle_events", ""),
            "runtime_log_path": summary.get("runtime_log_path", ""),
            "monitor_log_path": summary.get("monitor_log_path", ""),
            "failure_log_path": failure_path,
            "status": status,
            "related_troubleshooting_id": summary.get("related_troubleshooting_id", ""),
        })

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

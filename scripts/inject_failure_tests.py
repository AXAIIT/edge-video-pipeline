#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PIPELINE_CONFIG = "projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml"
DEFAULT_MODEL_CONFIG = "projects/03_video_pipeline/configs/models/yolo11n.yaml"
DEFAULT_BACKEND_CONFIG = "projects/03_video_pipeline/configs/boards/jetson_8gb.yaml"
DEFAULT_STREAM_CONFIG = "projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml"
DEFAULT_INPUT_SOURCE_ID = "bdd100k_mot_mini_v1_02344f0c-d5d916ff"
DEFAULT_INPUT_SOURCE_TYPE = "video_file"
DEFAULT_INPUT_PATH = "data/videos/bdd100k_mot_mini_v1/02344f0c-d5d916ff.mov"
DEFAULT_QUEUE_INPUT_SOURCE_ID = "video_set_runtime_v1"
DEFAULT_QUEUE_INPUT_SOURCE_TYPE = "video_playlist"
DEFAULT_QUEUE_INPUT_PATH = "data/videos/runtime_playlist_v1.txt"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def to_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def repo_display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_first(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Pattern not found for replacement: {pattern}")
    return updated


def rewrite_backend_config(src: Path, dst: Path, artifact_path: str) -> None:
    text = src.read_text(encoding="utf-8")
    text = replace_first(
        text,
        r"^(\s*backend_artifact_path:\s*).*$",
        rf"\1{artifact_path}",
    )
    write_text(dst, text)


def rewrite_model_config_invalid(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8")
    text = replace_first(
        text,
        r"^(\s*layout:\s*).*$",
        r"\1NHWC",
    )
    write_text(dst, text)


def build_app_args(
    pipeline: Path,
    pipeline_config: Path,
    model_config: Path,
    backend_config: Path,
    stream_config: Path,
    input_source_id: str,
    input_source_type: str,
    input_path: str,
    duration_sec: int,
    raw_output: Path,
    runtime_log: Path,
    monitor_log: Path,
    *,
    no_pace_video_file: bool = False,
    no_loop_video_file: bool = False,
    queue_policy: str | None = None,
    queue_capacity: int | None = None,
    queue_push_timeout_ms: int | None = None,
    output_video: Path | None = None,
) -> list[str]:
    args = [
        str(pipeline),
        "--config",
        repo_display(pipeline_config),
        "--model-config",
        repo_display(model_config),
        "--backend-config",
        repo_display(backend_config),
        "--stream-config",
        repo_display(stream_config),
        "--input-source-id",
        input_source_id,
        "--input-source-type",
        input_source_type,
        "--input",
        input_path,
        "--duration-sec",
        str(duration_sec),
        "--raw-output",
        repo_display(raw_output),
        "--runtime-log",
        repo_display(runtime_log),
        "--monitor-log",
        repo_display(monitor_log),
    ]
    if no_pace_video_file:
        args.append("--no-pace-video-file")
    if no_loop_video_file:
        args.append("--no-loop-video-file")
    if queue_policy:
        args.extend(["--queue-policy", queue_policy])
    if queue_capacity is not None:
        args.extend(["--queue-capacity", str(queue_capacity)])
    if queue_push_timeout_ms is not None:
        args.extend(["--queue-push-timeout-ms", str(queue_push_timeout_ms)])
    if output_video is not None:
        args.extend(["--output-video", repo_display(output_video)])
    return args


def run_command(cmd: list[str], log_path: Path, env: dict[str, str], timeout_sec: int) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"# timestamp={now_iso()}\n")
        f.write(f"# cwd={repo_display(REPO_ROOT)}\n")
        f.write(f"# command={shlex.join(cmd)}\n\n")
        f.flush()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=timeout_sec,
                check=False,
            )
            return completed.returncode
        except subprocess.TimeoutExpired:
            f.write(f"\nTIMEOUT_EXPIRED: timeout_sec={timeout_sec}\n")
            return 124


def log_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8", errors="replace")


def parse_queue_overflow(raw_path: Path) -> dict[str, object]:
    if not raw_path.exists():
        return {"frames": 0, "drop_count": 0, "max_queue": 0, "queue_full_seen": False}
    frames = 0
    drop_count = 0
    max_queue = 0
    queue_full_seen = False
    with raw_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            frames += 1
            row = json.loads(line)
            drop_count = max(drop_count, int(row.get("drop_frame_count", 0) or 0))
            if row.get("dropped_frame_reason") == "queue_full":
                queue_full_seen = True
            max_queue = max(
                max_queue,
                int(row.get("queue_capture_size", 0) or 0),
                int(row.get("queue_preprocess_size", 0) or 0),
                int(row.get("queue_infer_size", 0) or 0),
                int(row.get("queue_postprocess_size", 0) or 0),
            )
    return {
        "frames": frames,
        "drop_count": drop_count,
        "max_queue": max_queue,
        "queue_full_seen": queue_full_seen,
    }


def make_row(
    run_id: str,
    case_id: str,
    input_source_id: str,
    stage: str,
    error_code: str,
    expected_behavior: str,
    actual_behavior: str,
    recovery_action: str,
    exit_code: int,
    log_path: Path,
    status: str,
    *,
    max_recovery_time_sec: float | None = None,
    reconnect_count: int = 0,
    frame_id_continuity_after_recovery: str = "not_applicable",
    drop_frame_reason_after_recovery: str | None = "not_applicable",
    service_status: str = "not_applicable",
    related_troubleshooting_id: str | None = None,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "timestamp": now_iso(),
        "case_id": case_id,
        "input_source_id": input_source_id,
        "stage": stage,
        "error_code": error_code,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "recovery_action": recovery_action,
        "max_recovery_time_sec": max_recovery_time_sec,
        "reconnect_count": reconnect_count,
        "frame_id_continuity_after_recovery": frame_id_continuity_after_recovery,
        "drop_frame_reason_after_recovery": drop_frame_reason_after_recovery,
        "exit_code": exit_code,
        "service_status": service_status,
        "log_path": repo_display(log_path),
        "status": status,
        "related_troubleshooting_id": related_troubleshooting_id,
    }


def default_run_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d')}_jetson_8gb_pipeline_failure_service_test"


def run_input_open_failed(args: argparse.Namespace, workspace: Path, env: dict[str, str]) -> dict[str, object]:
    case_id = "input_open_failed"
    case_run_id = f"{args.run_id}_{case_id}"
    runtime_log = workspace / f"{case_run_id}.log"
    monitor_log = workspace / f"{case_run_id}_monitor.log"
    raw_output = workspace / f"{case_run_id}.jsonl"
    cmd = build_app_args(
        args.pipeline,
        args.pipeline_config,
        args.model_config,
        args.backend_config,
        args.stream_config,
        "missing_video_file",
        "video_file",
        "data/videos/video_fixed_v1/does_not_exist.avi",
        5,
        raw_output,
        runtime_log,
        monitor_log,
        no_loop_video_file=True,
    )
    case_env = dict(env)
    case_env["RUN_ID"] = case_run_id
    exit_code = run_command(cmd, runtime_log, case_env, timeout_sec=120)
    ok = exit_code == 10 and log_contains(runtime_log, "INPUT_OPEN_FAILED")
    actual = (
        "returned_INPUT_OPEN_FAILED_exit10"
        if ok
        else f"unexpected_exit={exit_code}; see log"
    )
    return make_row(
        args.run_id,
        case_id,
        "missing_video_file",
        "capture",
        "INPUT_OPEN_FAILED",
        "reject_missing_input_and_exit_nonzero",
        actual,
        "exit",
        exit_code,
        runtime_log,
        "pass" if ok else "fail",
    )


def run_model_missing(args: argparse.Namespace, workspace: Path, env: dict[str, str]) -> dict[str, object]:
    case_id = "model_missing"
    case_run_id = f"{args.run_id}_{case_id}"
    runtime_log = workspace / f"{case_run_id}.log"
    monitor_log = workspace / f"{case_run_id}_monitor.log"
    raw_output = workspace / f"{case_run_id}.jsonl"
    backend_override = workspace / f"{case_run_id}_backend.yaml"
    rewrite_backend_config(
        args.backend_config,
        backend_override,
        args.missing_artifact_path,
    )
    cmd = build_app_args(
        args.pipeline,
        args.pipeline_config,
        args.model_config,
        backend_override,
        args.stream_config,
        args.input_source_id,
        args.input_source_type,
        args.input_path,
        5,
        raw_output,
        runtime_log,
        monitor_log,
        no_loop_video_file=True,
    )
    case_env = dict(env)
    case_env["RUN_ID"] = case_run_id
    exit_code = run_command(cmd, runtime_log, case_env, timeout_sec=120)
    ok = exit_code == 21 and log_contains(runtime_log, "BACKEND_RUNTIME_FAILED")
    actual = (
        "backend_init_failed_with_exit21"
        if ok
        else f"unexpected_exit={exit_code}; see log"
    )
    return make_row(
        args.run_id,
        case_id,
        args.input_source_id,
        "inference",
        "BACKEND_RUNTIME_FAILED",
        "reject_missing_backend_artifact_and_exit_nonzero",
        actual,
        "exit",
        exit_code,
        runtime_log,
        "pass" if ok else "fail",
    )


def run_invalid_shape(args: argparse.Namespace, workspace: Path, env: dict[str, str]) -> dict[str, object]:
    case_id = "invalid_shape"
    case_run_id = f"{args.run_id}_{case_id}"
    runtime_log = workspace / f"{case_run_id}.log"
    monitor_log = workspace / f"{case_run_id}_monitor.log"
    raw_output = workspace / f"{case_run_id}.jsonl"
    model_override = workspace / f"{case_run_id}_model.yaml"
    rewrite_model_config_invalid(args.model_config, model_override)
    cmd = build_app_args(
        args.pipeline,
        args.pipeline_config,
        model_override,
        args.backend_config,
        args.stream_config,
        args.input_source_id,
        args.input_source_type,
        args.input_path,
        5,
        raw_output,
        runtime_log,
        monitor_log,
        no_loop_video_file=True,
    )
    case_env = dict(env)
    case_env["RUN_ID"] = case_run_id
    exit_code = run_command(cmd, runtime_log, case_env, timeout_sec=120)
    ok = exit_code == 30 and log_contains(runtime_log, "CONFIG_INVALID")
    actual = (
        "config_rejected_before_runtime_exit30"
        if ok
        else f"unexpected_exit={exit_code}; see log"
    )
    return make_row(
        args.run_id,
        case_id,
        args.input_source_id,
        "preprocess",
        "CONFIG_INVALID",
        "reject_invalid_model_shape_or_layout_before_runtime",
        actual,
        "exit",
        exit_code,
        runtime_log,
        "pass" if ok else "fail",
    )


def run_output_unwritable(args: argparse.Namespace, workspace: Path, env: dict[str, str]) -> dict[str, object]:
    case_id = "output_unwritable"
    case_run_id = f"{args.run_id}_{case_id}"
    runtime_log = workspace / f"{case_run_id}.log"
    monitor_log = workspace / f"{case_run_id}_monitor.log"
    raw_output = workspace / "missing_parent" / f"{case_run_id}.jsonl"
    cmd = build_app_args(
        args.pipeline,
        args.pipeline_config,
        args.model_config,
        args.backend_config,
        args.stream_config,
        args.input_source_id,
        args.input_source_type,
        args.input_path,
        5,
        raw_output,
        runtime_log,
        monitor_log,
        no_loop_video_file=True,
    )
    case_env = dict(env)
    case_env["RUN_ID"] = case_run_id
    exit_code = run_command(cmd, runtime_log, case_env, timeout_sec=120)
    ok = exit_code == 40 and log_contains(runtime_log, "OUTPUT_FAILED")
    actual = (
        "raw_output_open_failed_with_exit40"
        if ok
        else f"unexpected_exit={exit_code}; current_app_did_not_report_output_failure_as_expected"
    )
    return make_row(
        args.run_id,
        case_id,
        args.input_source_id,
        "output",
        "OUTPUT_FAILED",
        "reject_unwritable_output_path_and_exit_nonzero",
        actual,
        "exit",
        exit_code,
        runtime_log,
        "pass" if ok else "fail",
    )


def run_queue_overflow(args: argparse.Namespace, workspace: Path, env: dict[str, str]) -> dict[str, object]:
    case_id = "queue_overflow"
    case_run_id = f"{args.run_id}_{case_id}"
    runtime_log = workspace / f"{case_run_id}.log"
    monitor_log = workspace / f"{case_run_id}_monitor.log"
    raw_output = workspace / f"{case_run_id}.jsonl"
    cmd = build_app_args(
        args.pipeline,
        args.pipeline_config,
        args.model_config,
        args.backend_config,
        args.stream_config,
        args.queue_input_source_id,
        args.queue_input_source_type,
        args.queue_input_path,
        args.queue_duration_sec,
        raw_output,
        runtime_log,
        monitor_log,
        no_pace_video_file=True,
        queue_policy="drop_oldest",
        queue_capacity=1,
        queue_push_timeout_ms=20,
    )
    case_env = dict(env)
    case_env["RUN_ID"] = case_run_id
    exit_code = run_command(cmd, runtime_log, case_env, timeout_sec=max(120, args.queue_duration_sec * 4))
    metrics = parse_queue_overflow(raw_output)
    ok = (
        exit_code == 0
        and bool(metrics["queue_full_seen"])
        and int(metrics["drop_count"]) > 0
    )
    actual = (
        f"queue_full_observed frames={metrics['frames']} drop_count={metrics['drop_count']} max_queue={metrics['max_queue']}"
        if ok
        else f"unexpected_exit={exit_code} queue_full_seen={metrics['queue_full_seen']} drop_count={metrics['drop_count']}"
    )
    return make_row(
        args.run_id,
        case_id,
        args.queue_input_source_id,
        "capture",
        "QUEUE_OVERFLOW",
        "bounded_queue_should_limit_backpressure_and_record_queue_full_drop",
        actual,
        "drop_or_limit_by_queue_policy",
        exit_code,
        runtime_log,
        "pass" if ok else "fail",
        frame_id_continuity_after_recovery="gap_with_reason" if ok else "unknown",
        drop_frame_reason_after_recovery="queue_full" if ok else "unknown",
    )


def run_not_automated(
    args: argparse.Namespace,
    workspace: Path,
    case_id: str,
    input_source_id: str,
    stage: str,
    error_code: str,
    expected_behavior: str,
    actual_behavior: str,
) -> dict[str, object]:
    log_path = workspace / f"{args.run_id}_{case_id}.log"
    write_text(
        log_path,
        (
            f"# timestamp={now_iso()}\n"
            f"# case_id={case_id}\n"
            f"{actual_behavior}\n"
        ),
    )
    return make_row(
        args.run_id,
        case_id,
        input_source_id,
        stage,
        error_code,
        expected_behavior,
        actual_behavior,
        "manual_board_run_required",
        -1,
        log_path,
        "blocked",
        frame_id_continuity_after_recovery="unknown",
        drop_frame_reason_after_recovery="unknown",
        service_status="manual_required",
    )


CASE_HANDLERS: dict[str, Callable[[argparse.Namespace, Path, dict[str, str]], dict[str, object]]] = {
    "input_open_failed": run_input_open_failed,
    "model_missing": run_model_missing,
    "invalid_shape": run_invalid_shape,
    "output_unwritable": run_output_unwritable,
    "queue_overflow": run_queue_overflow,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject video pipeline failure cases and write failure-schema JSONL.",
    )
    parser.add_argument("--pipeline", required=True, help="Path to built video_pipeline_app.")
    parser.add_argument("--pipeline-config", default=DEFAULT_PIPELINE_CONFIG)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--backend-config", default=DEFAULT_BACKEND_CONFIG)
    parser.add_argument("--stream-config", default=DEFAULT_STREAM_CONFIG)
    parser.add_argument("--input-source-id", default=DEFAULT_INPUT_SOURCE_ID)
    parser.add_argument("--input-source-type", default=DEFAULT_INPUT_SOURCE_TYPE)
    parser.add_argument("--input", dest="input_path", default=DEFAULT_INPUT_PATH)
    parser.add_argument("--queue-input-source-id", default=DEFAULT_QUEUE_INPUT_SOURCE_ID)
    parser.add_argument("--queue-input-source-type", default=DEFAULT_QUEUE_INPUT_SOURCE_TYPE)
    parser.add_argument("--queue-input", dest="queue_input_path", default=DEFAULT_QUEUE_INPUT_PATH)
    parser.add_argument("--queue-duration-sec", type=int, default=5)
    parser.add_argument(
        "--missing-artifact-path",
        default="models/yolo11n/tensorrt/does_not_exist.engine",
        help="Backend artifact path used by the model_missing case.",
    )
    parser.add_argument("--output", required=True, help="Failure JSONL output path.")
    parser.add_argument("--run-id", default=default_run_id())
    parser.add_argument(
        "--cases",
        nargs="+",
        required=True,
        help=(
            "Cases to execute. Supported: input_open_failed model_missing invalid_shape "
            "output_unwritable queue_overflow input_disconnect systemd_restart"
        ),
    )
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--environment-baseline-id", default=os.environ.get("ENVIRONMENT_BASELINE_ID", ""))
    args = parser.parse_args()

    args.pipeline = to_repo_path(args.pipeline)
    args.pipeline_config = to_repo_path(args.pipeline_config)
    args.model_config = to_repo_path(args.model_config)
    args.backend_config = to_repo_path(args.backend_config)
    args.stream_config = to_repo_path(args.stream_config)
    args.output = to_repo_path(args.output)
    return args


def validate_paths(args: argparse.Namespace) -> None:
    required_paths = [
        args.pipeline,
        args.pipeline_config,
        args.model_config,
        args.backend_config,
        args.stream_config,
    ]
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"Required path not found: {path}")
    if not os.access(args.pipeline, os.X_OK):
        raise PermissionError(f"Pipeline app is not executable: {args.pipeline}")


def main() -> int:
    args = parse_args()
    validate_paths(args)

    workspace = args.output.parent / f"{args.output.stem}_artifacts"
    workspace.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    if args.environment_baseline_id:
        env["ENVIRONMENT_BASELINE_ID"] = args.environment_baseline_id

    rows = []
    for case_id in args.cases:
        if case_id in CASE_HANDLERS:
            rows.append(CASE_HANDLERS[case_id](args, workspace, env))
            continue
        if case_id == "input_disconnect":
            rows.append(
                run_not_automated(
                    args,
                    workspace,
                    case_id,
                    "rtsp_stream_001",
                    "capture",
                    "INPUT_DISCONNECTED",
                    "reconnect_or_fail_with_clear_log_and_recovery_metrics",
                    (
                        "automation_not_in_cli_subset; "
                        "use board wrapper "
                        "projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_imx219_disconnect.sh"
                    ),
                )
            )
            continue
        if case_id == "systemd_restart":
            rows.append(
                run_not_automated(
                    args,
                    workspace,
                    case_id,
                    "not_applicable",
                    "service",
                    "OK",
                    "service_start_restart_stop_and_journal_should_be_traceable",
                    "automation_not_implemented_for_systemd_case; run_on_board_with_systemctl_and_journalctl",
                )
            )
            continue
        raise ValueError(f"Unsupported case: {case_id}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    for row in rows:
        print(
            f"case={row['case_id']} status={row['status']} exit_code={row['exit_code']} "
            f"log={row['log_path']}"
        )
    print(f"failure_jsonl={repo_display(args.output)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

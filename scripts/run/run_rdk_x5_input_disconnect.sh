#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault}"
PIPELINE_RUNNER="${PIPELINE_RUNNER:-projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-imx219_rdkx5_hbn_001}"
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-mipi_camera_hbn}"
INPUT_PATH="${INPUT_PATH:-srcampy://video_idx0}"
INPUT_PATH_RECORD="${INPUT_PATH_RECORD:-${INPUT_PATH}}"
DURATION_SEC="${DURATION_SEC:-30}"
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-10}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PREVIEW_WINDOW="${PREVIEW_WINDOW:-auto}"
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION:-}"
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-0}"
QUEUE_POLICY="${QUEUE_POLICY:-}"
QUEUE_CAPACITY="${QUEUE_CAPACITY:-}"
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS:-}"
INFERENCE_WORKERS="${INFERENCE_WORKERS:-}"
POSTPROCESS_WORKERS="${POSTPROCESS_WORKERS:-}"
SRCAMPY_PYTHON="${SRCAMPY_PYTHON:-python3}"
SRCAMPY_STREAM_SCRIPT="${SRCAMPY_STREAM_SCRIPT:-projects/03_video_pipeline/scripts/run/rdk_x5_srcampy_stream.py}"
SRCAMPY_VIDEO_IDX="${SRCAMPY_VIDEO_IDX:-0}"
SRCAMPY_WIDTH="${SRCAMPY_WIDTH:-640}"
SRCAMPY_HEIGHT="${SRCAMPY_HEIGHT:-640}"
SRCAMPY_SENSOR_WIDTH="${SRCAMPY_SENSOR_WIDTH:-1920}"
SRCAMPY_SENSOR_HEIGHT="${SRCAMPY_SENSOR_HEIGHT:-1080}"
SRCAMPY_FPS="${SRCAMPY_FPS:-30}"
SRCAMPY_WARMUP="${SRCAMPY_WARMUP:-10}"
SRCAMPY_STARTUP_TIMEOUT_SEC="${SRCAMPY_STARTUP_TIMEOUT_SEC:-8}"

RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
RAW_PATH="benchmark/raw/03_video_pipeline/rdk_x5_8gb/${RUN_ID}.jsonl"
RUNTIME_LOG="logs/runtime/03_video_pipeline/rdk_x5_8gb/${RUN_ID}.log"
AUTOMATION_LOG="logs/failures/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_input_disconnect_automation.log"
FAILURE_JSONL="logs/failures/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_failure_injection.jsonl"
FAILURE_SUMMARY="benchmark/processed/03_video_pipeline/${RUN_ID}_failure_summary.csv"

timestamp() {
  date --iso-8601=seconds
}

log_note() {
  printf '[%s] %s\n' "$(timestamp)" "$*" | tee -a "${AUTOMATION_LOG}"
}

probe_srcampy_helper() {
  log_note "srcampy_probe_begin helper=${SRCAMPY_STREAM_SCRIPT} video_idx=${SRCAMPY_VIDEO_IDX}"
  [[ -f "${SRCAMPY_STREAM_SCRIPT}" ]] || {
    log_note "srcampy_probe_missing_helper path=${SRCAMPY_STREAM_SCRIPT}"
    return 1
  }
  "${SRCAMPY_PYTHON}" - "${SRCAMPY_STREAM_SCRIPT}" "${SRCAMPY_VIDEO_IDX}" \
    "${SRCAMPY_WIDTH}" "${SRCAMPY_HEIGHT}" "${SRCAMPY_SENSOR_WIDTH}" "${SRCAMPY_SENSOR_HEIGHT}" \
    "${SRCAMPY_WARMUP}" "${SRCAMPY_STARTUP_TIMEOUT_SEC}" >>"${AUTOMATION_LOG}" 2>&1 <<'PY'
import subprocess
import sys
import os

script, video_idx, width, height, sensor_width, sensor_height, warmup, timeout_sec = sys.argv[1:]
read_fd, write_fd = os.pipe()
cmd = [
    sys.executable,
    script,
    "--video-idx",
    video_idx,
    "--width",
    width,
    "--height",
    height,
    "--sensor-width",
    sensor_width,
    "--sensor-height",
    sensor_height,
    "--warmup",
    warmup,
    "--startup-timeout-sec",
    timeout_sec,
    "--stream-fd",
    str(write_fd),
]
try:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(write_fd,),
        close_fds=True,
    )
    os.close(write_fd)
    stream = os.fdopen(read_fd, "rb", buffering=0)
    header = stream.readline().decode("ascii", errors="replace").strip()
    if header.startswith("FRAME "):
        print(f"srcampy_probe_header={header}")
        parts = header.split()
        if len(parts) >= 5:
            payload_size = int(parts[4])
            payload = stream.read(payload_size)
            print(f"srcampy_probe_payload_bytes={len(payload)}")
        print("srcampy_probe_status=pass")
        proc.terminate()
        stderr = proc.stderr.read().decode("utf-8", errors="replace")
        if stderr:
            print(stderr.rstrip())
        proc.wait(timeout=5)
        sys.exit(0)
    stderr = proc.stderr.read().decode("utf-8", errors="replace")
    print(f"srcampy_probe_status=fail header={header!r}")
    if stderr:
        print(stderr.rstrip())
    proc.terminate()
    proc.wait(timeout=5)
    sys.exit(1)
except Exception as exc:
    print(f"srcampy_probe_exception={exc}")
    sys.exit(1)
finally:
    try:
        os.close(write_fd)
    except OSError:
        pass
    try:
        os.close(read_fd)
    except OSError:
        pass
PY
  log_note "srcampy_probe_end"
}

mkdir -p "${RUN_DIR}" "$(dirname "${AUTOMATION_LOG}")" "$(dirname "${FAILURE_SUMMARY}")"
rm -f "${AUTOMATION_LOG}" "${FAILURE_JSONL}" "${FAILURE_SUMMARY}"

if [[ ! -f "${PIPELINE_RUNNER}" ]]; then
  echo "Pipeline runner not found: ${PIPELINE_RUNNER}" >&2
  exit 2
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
  exit 2
fi
if (( DURATION_SEC <= FAULT_INJECT_DISCONNECT_AFTER_SEC )); then
  echo "DURATION_SEC must be greater than FAULT_INJECT_DISCONNECT_AFTER_SEC" >&2
  exit 2
fi
if [[ "${INPUT_SOURCE_TYPE}" != "mipi_camera_hbn" && "${INPUT_SOURCE_TYPE}" != "rtsp" ]]; then
  echo "Unsupported INPUT_SOURCE_TYPE=${INPUT_SOURCE_TYPE}; expected mipi_camera_hbn or rtsp" >&2
  exit 2
fi
if [[ "${INPUT_SOURCE_TYPE}" == "rtsp" && -z "${INPUT_PATH}" ]]; then
  echo "RTSP INPUT_PATH must not be empty" >&2
  exit 2
fi
if [[ "${INPUT_SOURCE_TYPE}" != "mipi_camera_hbn" ]]; then
  SRCAMPY_VIDEO_IDX=""
  SRCAMPY_WIDTH=""
  SRCAMPY_HEIGHT=""
  SRCAMPY_SENSOR_WIDTH=""
  SRCAMPY_SENSOR_HEIGHT=""
  SRCAMPY_FPS=""
  SRCAMPY_WARMUP=""
  SRCAMPY_STARTUP_TIMEOUT_SEC=""
fi

if [[ -z "${INPUT_ORIENTATION_CORRECTION}" ]]; then
  if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_hbn" ]]; then
    INPUT_ORIENTATION_CORRECTION=rotate180
  else
    INPUT_ORIENTATION_CORRECTION=auto
  fi
fi

log_note "automation_start run_id=${RUN_ID} input_source_id=${INPUT_SOURCE_ID} input_source_type=${INPUT_SOURCE_TYPE} runtime_log=${RUNTIME_LOG}"
if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_hbn" ]]; then
  probe_srcampy_helper
fi

set +e
RUN_ID="${RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE}" \
INPUT_PATH="${INPUT_PATH}" \
INPUT_PATH_RECORD="${INPUT_PATH_RECORD}" \
DURATION_SEC="${DURATION_SEC}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW}" \
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION}" \
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS}" \
QUEUE_POLICY="${QUEUE_POLICY}" \
QUEUE_CAPACITY="${QUEUE_CAPACITY}" \
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
POSTPROCESS_WORKERS="${POSTPROCESS_WORKERS}" \
SRCAMPY_PYTHON="${SRCAMPY_PYTHON}" \
SRCAMPY_STREAM_SCRIPT="${SRCAMPY_STREAM_SCRIPT}" \
SRCAMPY_VIDEO_IDX="${SRCAMPY_VIDEO_IDX}" \
SRCAMPY_WIDTH="${SRCAMPY_WIDTH}" \
SRCAMPY_HEIGHT="${SRCAMPY_HEIGHT}" \
SRCAMPY_SENSOR_WIDTH="${SRCAMPY_SENSOR_WIDTH}" \
SRCAMPY_SENSOR_HEIGHT="${SRCAMPY_SENSOR_HEIGHT}" \
SRCAMPY_FPS="${SRCAMPY_FPS}" \
SRCAMPY_WARMUP="${SRCAMPY_WARMUP}" \
SRCAMPY_STARTUP_TIMEOUT_SEC="${SRCAMPY_STARTUP_TIMEOUT_SEC}" \
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC}" \
  bash "${PIPELINE_RUNNER}"
PIPELINE_EXIT=$?
set -e

STATUS=fail
ACTUAL_BEHAVIOR="missing_disconnect_evidence"
if [[ "${PIPELINE_EXIT}" -eq 11 ]] && \
   [[ -s "${RAW_PATH}" ]] && \
   [[ -f "${RUNTIME_LOG}" ]] && \
   grep -q "INPUT_DISCONNECTED" "${RUNTIME_LOG}" && \
   grep -q "FAULT_INJECTED_DISCONNECT" "${RUNTIME_LOG}"; then
  STATUS=pass
  ACTUAL_BEHAVIOR="runtime_log_contains_INPUT_DISCONNECTED_and_FAULT_INJECTED_DISCONNECT_exit11"
fi

"${PYTHON_BIN}" - "${FAILURE_JSONL}" "${RUN_ID}" "${INPUT_SOURCE_ID}" \
  "${PIPELINE_EXIT}" "${STATUS}" "${ACTUAL_BEHAVIOR}" "${RUNTIME_LOG}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

out, run_id, source_id, exit_code, status, actual, runtime_log = sys.argv[1:]
row = {
    "run_id": run_id,
    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
    "case_id": "input_disconnect",
    "input_source_id": source_id,
    "stage": "capture",
    "error_code": "INPUT_DISCONNECTED",
    "expected_behavior": "real_live_source_then_safe_injected_disconnect_should_emit_clear_error_and_exit11",
    "actual_behavior": actual,
    "recovery_action": "exit_after_clear_error",
    "max_recovery_time_sec": None,
    "reconnect_count": 0,
    "frame_id_continuity_after_recovery": "not_applicable",
    "drop_frame_reason_after_recovery": "not_applicable",
    "exit_code": int(exit_code),
    "service_status": "not_applicable",
    "log_path": runtime_log,
    "status": status,
    "related_troubleshooting_id": None,
}
Path(out).write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
PY

"${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_failure_service.py \
  --input "${FAILURE_JSONL}" \
  --schema benchmark/schemas/video_pipeline_failure_schema.yaml \
  --output "${FAILURE_SUMMARY}"

cat >> "${RUN_DIR}/run.md" <<EOF

## RDK X5 Live Disconnect Evidence

- authoritative_result: use this section and failure_summary as the 03G verdict; inner pipeline wrapper exit 11 is expected for injected disconnect
- automation_log_path: ${AUTOMATION_LOG}
- input_source_id: ${INPUT_SOURCE_ID}
- input_source_type: ${INPUT_SOURCE_TYPE}
- input_path: ${INPUT_PATH_RECORD}
- preview_window_requested: ${PREVIEW_WINDOW}
- input_orientation_correction: ${INPUT_ORIENTATION_CORRECTION}
- inference_workers_override: ${INFERENCE_WORKERS}
- postprocess_workers_override: ${POSTPROCESS_WORKERS}
- srcampy_python: ${SRCAMPY_PYTHON}
- srcampy_stream_script: ${SRCAMPY_STREAM_SCRIPT}
- srcampy_video_idx: ${SRCAMPY_VIDEO_IDX}
- srcampy_width: ${SRCAMPY_WIDTH}
- srcampy_height: ${SRCAMPY_HEIGHT}
- srcampy_sensor_width: ${SRCAMPY_SENSOR_WIDTH}
- srcampy_sensor_height: ${SRCAMPY_SENSOR_HEIGHT}
- srcampy_fps: ${SRCAMPY_FPS}
- srcampy_warmup: ${SRCAMPY_WARMUP}
- srcampy_startup_timeout_sec: ${SRCAMPY_STARTUP_TIMEOUT_SEC}
- fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC}
- pipeline_exit: ${PIPELINE_EXIT}
- disconnect_status: ${STATUS}
- failure_jsonl: ${FAILURE_JSONL}
- failure_summary: ${FAILURE_SUMMARY}
EOF

if [[ -f "${RUNTIME_LOG}" ]]; then
  {
    echo "disconnect_runtime_excerpt_begin"
    grep -nE 'INPUT_DISCONNECTED|FAULT_INJECTED_DISCONNECT|INPUT_OPEN_FAILED|BACKEND_RUNTIME_FAILED|CONFIG_INVALID' "${RUNTIME_LOG}" || true
    echo "disconnect_runtime_excerpt_end"
  } | tee -a "${AUTOMATION_LOG}"
fi

log_note "automation_done pipeline_exit=${PIPELINE_EXIT} disconnect_status=${STATUS}"
echo "pipeline_exit=${PIPELINE_EXIT}"
echo "disconnect_status=${STATUS}"
echo "runtime_log=${RUNTIME_LOG}"
echo "raw_result=${RAW_PATH}"
echo "automation_log=${AUTOMATION_LOG}"
echo "failure_jsonl=${FAILURE_JSONL}"
echo "failure_summary=${FAILURE_SUMMARY}"
echo "inference_workers_override=${INFERENCE_WORKERS}"
echo "postprocess_workers_override=${POSTPROCESS_WORKERS}"
echo "note=inner_pipeline_exit11_is_expected_for_injected_disconnect_use_disconnect_status_as_authoritative_03G_result"

[[ "${STATUS}" == "pass" ]]

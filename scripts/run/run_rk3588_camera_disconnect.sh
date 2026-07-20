#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_astra_openni_disconnect_appfault}"
PIPELINE_RUNNER="${PIPELINE_RUNNER:-projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh}"
PYTHON_BIN="${PYTHON_BIN:-$HOME/venvs/rk3588_rknn/bin/python}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-astra_s_openni_001}"
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-openni_camera}"
INPUT_PATH="${INPUT_PATH:-${OPENNI_DEVICE_SELECTOR:-2bc5/0402}}"
DURATION_SEC="${DURATION_SEC:-30}"
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-10}"
INFERENCE_WORKERS="${INFERENCE_WORKERS:-3}"

RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
RUNTIME_LOG="logs/runtime/03_video_pipeline/rk3588_8gb/${RUN_ID}.log"
RAW_PATH="benchmark/raw/03_video_pipeline/rk3588_8gb/${RUN_ID}.jsonl"
FAILURE_JSONL="logs/failures/03_video_pipeline/rk3588_8gb/${RUN_ID}_failure_injection.jsonl"
FAILURE_SUMMARY="benchmark/processed/03_video_pipeline/${RUN_ID}_failure_summary.csv"

if [[ "${INPUT_SOURCE_TYPE}" != "openni_camera" && ! -e "${INPUT_PATH}" ]]; then
  echo "Camera device does not exist: ${INPUT_PATH}" >&2
  echo "Run: v4l2-ctl --list-devices" >&2
  exit 2
fi
if (( DURATION_SEC <= FAULT_INJECT_DISCONNECT_AFTER_SEC )); then
  echo "DURATION_SEC must be greater than FAULT_INJECT_DISCONNECT_AFTER_SEC" >&2
  exit 2
fi

mkdir -p "${RUN_DIR}" "$(dirname "${FAILURE_JSONL}")" "$(dirname "${FAILURE_SUMMARY}")"
rm -f "${FAILURE_JSONL}" "${FAILURE_SUMMARY}"

set +e
RUN_ID="${RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE}" \
INPUT_PATH="${INPUT_PATH}" \
DURATION_SEC="${DURATION_SEC}" \
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
TRACE_FAIL_ON_GAPS=0 \
SAVE_OUTPUT_VIDEO=0 \
PYTHON_BIN="${PYTHON_BIN}" \
  bash "${PIPELINE_RUNNER}"
PIPELINE_EXIT=$?
set -e

STATUS=fail
ACTUAL_BEHAVIOR="missing_disconnect_evidence"
if [[ "${PIPELINE_EXIT}" -eq 11 ]] && \
   [[ -s "${RAW_PATH}" ]] && \
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
    "expected_behavior": "real_camera_capture_then_safe_injected_disconnect_should_emit_clear_error_and_exit11",
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

## RK3588 Camera Disconnect Evidence

- input_source_id: ${INPUT_SOURCE_ID}
- input_source_type: ${INPUT_SOURCE_TYPE}
- input_path: ${INPUT_PATH}
- fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC}
- pipeline_exit: ${PIPELINE_EXIT}
- disconnect_status: ${STATUS}
- failure_jsonl: ${FAILURE_JSONL}
- failure_summary: ${FAILURE_SUMMARY}
EOF

echo "pipeline_exit=${PIPELINE_EXIT}"
echo "disconnect_status=${STATUS}"
echo "runtime_log=${RUNTIME_LOG}"
echo "raw_result=${RAW_PATH}"
echo "failure_jsonl=${FAILURE_JSONL}"
echo "failure_summary=${FAILURE_SUMMARY}"

[[ "${STATUS}" == pass ]]

#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_cpp_pipeline}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_set_runtime_v1}"
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-video_playlist}"
DEFAULT_INPUT_PATH="data/videos/runtime_playlist_v1.txt"
INPUT_PATH="${INPUT_PATH:-${DEFAULT_INPUT_PATH}}"
DURATION_SEC="${DURATION_SEC:-600}"
LOOP_VIDEO_FILE="${LOOP_VIDEO_FILE:-1}"
PACE_VIDEO_FILE="${PACE_VIDEO_FILE:-1}"
BUILD_DIR="${BUILD_DIR:-build/03_video_pipeline_jetson}"
APP="${APP:-${BUILD_DIR}/video_pipeline_app}"
PIPELINE_CONFIG="${PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml}"
MODEL_CONFIG="${MODEL_CONFIG:-projects/03_video_pipeline/configs/models/yolo11n.yaml}"
BOARD_CONFIG="${BOARD_CONFIG:-projects/03_video_pipeline/configs/boards/jetson_8gb.yaml}"
STREAM_CONFIG="${STREAM_CONFIG:-projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PREVIEW_WINDOW="${PREVIEW_WINDOW:-auto}"
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION:-auto}"
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-0}"
QUEUE_POLICY="${QUEUE_POLICY:-}"
QUEUE_CAPACITY="${QUEUE_CAPACITY:-}"
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS:-}"
V4L2_RAW="${V4L2_RAW:-}"
V4L2_WIDTH="${V4L2_WIDTH:-}"
V4L2_HEIGHT="${V4L2_HEIGHT:-}"
V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE:-}"
V4L2_FPS="${V4L2_FPS:-}"
BAYER_PATTERN="${BAYER_PATTERN:-}"
V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE:-}"
V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE:-}"
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-}"
ARGUS_PIPELINE="${ARGUS_PIPELINE:-}"
ARGUS_SENSOR_ID="${ARGUS_SENSOR_ID:-}"
ARGUS_WIDTH="${ARGUS_WIDTH:-}"
ARGUS_HEIGHT="${ARGUS_HEIGHT:-}"
ARGUS_FPS="${ARGUS_FPS:-}"
ARGUS_FLIP_METHOD="${ARGUS_FLIP_METHOD:-}"
PROJECT1_PREPROCESS_CONFIG="${PROJECT1_PREPROCESS_CONFIG:-projects/01_vision_deploy/configs/preprocess/yolo11n_640.yaml}"
PROJECT1_POSTPROCESS_CONFIG="${PROJECT1_POSTPROCESS_CONFIG:-projects/01_vision_deploy/configs/postprocess/yolo11n_nms.yaml}"

build_default_argus_pipeline() {
  local sensor_id="$1"
  local width="$2"
  local height="$3"
  local fps="$4"
  local flip_method="$5"
  printf '%s' \
    "nvarguscamerasrc sensor-id=${sensor_id} ! video/x-raw(memory:NVMM), width=(int)${width}, height=(int)${height}, framerate=(fraction)${fps}/1 ! nvvidconv flip-method=${flip_method} ! video/x-raw, width=(int)${width}, height=(int)${height}, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink drop=true max-buffers=1 sync=false"
}

yaml_single_quote() {
  local value="${1//\'/\'\'}"
  printf "'%s'" "${value}"
}

if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera" ]]; then
  [[ -n "${V4L2_RAW}" ]] || V4L2_RAW=1
  [[ -n "${V4L2_WIDTH}" ]] || V4L2_WIDTH=1920
  [[ -n "${V4L2_HEIGHT}" ]] || V4L2_HEIGHT=1080
  [[ -n "${V4L2_SENSOR_MODE}" ]] || V4L2_SENSOR_MODE=2
  [[ -n "${V4L2_FPS}" ]] || V4L2_FPS=30
  [[ -n "${BAYER_PATTERN}" ]] || BAYER_PATTERN=RG
fi

if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_argus" ]]; then
  [[ -n "${ARGUS_SENSOR_ID}" ]] || ARGUS_SENSOR_ID=0
  [[ -n "${ARGUS_WIDTH}" ]] || ARGUS_WIDTH=1280
  [[ -n "${ARGUS_HEIGHT}" ]] || ARGUS_HEIGHT=720
  [[ -n "${ARGUS_FPS}" ]] || ARGUS_FPS=30
  [[ -n "${ARGUS_FLIP_METHOD}" ]] || ARGUS_FLIP_METHOD=0

  if [[ -n "${ARGUS_PIPELINE}" ]]; then
    INPUT_PATH="${ARGUS_PIPELINE}"
  elif [[ -z "${INPUT_PATH}" || "${INPUT_PATH}" == "${DEFAULT_INPUT_PATH}" || "${INPUT_PATH}" == "jetson_argus_default" ]]; then
    INPUT_PATH="$(build_default_argus_pipeline "${ARGUS_SENSOR_ID}" "${ARGUS_WIDTH}" "${ARGUS_HEIGHT}" "${ARGUS_FPS}" "${ARGUS_FLIP_METHOD}")"
  fi

  V4L2_RAW=0
  V4L2_WIDTH=""
  V4L2_HEIGHT=""
  V4L2_SENSOR_MODE=""
  V4L2_FPS=""
  BAYER_PATTERN=""
  V4L2_NORMALIZE_MODE=""
  V4L2_DISABLE_WHITE_BALANCE=""
fi

EFFECTIVE_PACE_VIDEO_FILE=0
if [[ "${INPUT_SOURCE_TYPE}" == "video_file" || "${INPUT_SOURCE_TYPE}" == "video_playlist" ]]; then
  EFFECTIVE_PACE_VIDEO_FILE="${PACE_VIDEO_FILE}"
fi

EFFECTIVE_QUEUE_POLICY="${QUEUE_POLICY}"
if [[ "${EFFECTIVE_QUEUE_POLICY}" == "block_timeout" ]]; then
  EFFECTIVE_QUEUE_POLICY="block_with_timeout"
fi
if [[ "${EFFECTIVE_QUEUE_POLICY}" == "block" && -n "${QUEUE_PUSH_TIMEOUT_MS}" ]]; then
  EFFECTIVE_QUEUE_POLICY="block_with_timeout"
fi

RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
RAW_PATH="benchmark/raw/03_video_pipeline/jetson_8gb/${RUN_ID}.jsonl"
RUNTIME_LOG="logs/runtime/03_video_pipeline/jetson_8gb/${RUN_ID}.log"
MONITOR_LOG="logs/monitor/03_video_pipeline/jetson_8gb/${RUN_ID}_tegrastats.log"
MONITOR_PID="logs/monitor/03_video_pipeline/jetson_8gb/${RUN_ID}_tegrastats.pid"
PROCESSED_SUMMARY="benchmark/processed/03_video_pipeline/${RUN_ID}_summary.csv"
SCHEMA_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_schema_check.md"
TRACE_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_trace_check.md"
CONSISTENCY_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_prepost_consistency.md"
OUTPUT_VIDEO="${RUN_DIR}/outputs/${RUN_ID}.mp4"
ENVIRONMENT_BASELINE_ID_VALUE="${ENVIRONMENT_BASELINE_ID:-pending_project3_jetson_env_baseline}"
INPUT_PATH_YAML="$(yaml_single_quote "${INPUT_PATH}")"

mkdir -p "${RUN_DIR}/outputs" \
  benchmark/raw/03_video_pipeline/jetson_8gb \
  benchmark/processed/03_video_pipeline \
  logs/runtime/03_video_pipeline/jetson_8gb \
  logs/monitor/03_video_pipeline/jetson_8gb \
  logs/failures/03_video_pipeline/jetson_8gb

# Prevent stale artifacts from a previous run with the same RUN_ID from
# being misread as outputs of the current execution.
rm -f "${RAW_PATH}" \
  "${PROCESSED_SUMMARY}" \
  "${SCHEMA_CHECK}" \
  "${TRACE_CHECK}" \
  "${CONSISTENCY_CHECK}" \
  "${RUNTIME_LOG}" \
  "${MONITOR_LOG}" \
  "${MONITOR_PID}" \
  "${OUTPUT_VIDEO}"

cat > "${RUN_DIR}/run.md" <<EOF
# ${RUN_ID}

\`\`\`yaml
run_id: ${RUN_ID}
date: $(date --iso-8601=seconds)
spec_ref: projects/03_video_pipeline/specs/03D_Jetson_TensorRT_CppPipeline规范.md
stage: jetson_tensorrt_cpp_pipeline
status: not_verified

environment:
  environment_baseline_id: ${ENVIRONMENT_BASELINE_ID_VALUE}
  target: jetson_8gb
  board: Jetson Xavier NX 8GB

model:
  model_name: yolo11n
  backend_runtime: tensorrt
  precision_or_quantization: int8_ptq
  backend_artifact_path: models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine
  backend_artifact_format: engine
  backend_artifact_sha256: 1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d
  loader_api: TensorRT C++ API
  execution_provider: TensorRT-GPU
  cpu_fallback: false

input_source:
  input_source_id: ${INPUT_SOURCE_ID}
  input_source_type: ${INPUT_SOURCE_TYPE}
  uri: ${INPUT_PATH_YAML}
  pace_video_file_requested: ${PACE_VIDEO_FILE}
  pace_video_file_effective: ${EFFECTIVE_PACE_VIDEO_FILE}
  v4l2_raw: ${V4L2_RAW:-null}
  v4l2_width: ${V4L2_WIDTH:-null}
  v4l2_height: ${V4L2_HEIGHT:-null}
  v4l2_sensor_mode: ${V4L2_SENSOR_MODE:-null}
  v4l2_fps: ${V4L2_FPS:-null}
  bayer_pattern: ${BAYER_PATTERN:-null}
  v4l2_normalize_mode: ${V4L2_NORMALIZE_MODE:-null}
  v4l2_disable_white_balance: ${V4L2_DISABLE_WHITE_BALANCE:-null}
  fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC:-null}
  argus_sensor_id: ${ARGUS_SENSOR_ID:-null}
  argus_width: ${ARGUS_WIDTH:-null}
  argus_height: ${ARGUS_HEIGHT:-null}
  argus_fps: ${ARGUS_FPS:-null}
  argus_flip_method: ${ARGUS_FLIP_METHOD:-null}

configs:
  pipeline_config: ${PIPELINE_CONFIG}
  stream_config: ${STREAM_CONFIG}
  model_config: ${MODEL_CONFIG}
  board_config: ${BOARD_CONFIG}
  preview_window_requested: ${PREVIEW_WINDOW}
  input_orientation_correction: ${INPUT_ORIENTATION_CORRECTION}
  queue_policy_override_requested: ${QUEUE_POLICY:-null}
  queue_policy_override_effective: ${EFFECTIVE_QUEUE_POLICY:-null}
  queue_capacity_override: ${QUEUE_CAPACITY:-null}
  queue_push_timeout_ms_override: ${QUEUE_PUSH_TIMEOUT_MS:-null}

outputs:
  raw_result_path: ${RAW_PATH}
  processed_result_path: ${PROCESSED_SUMMARY}
  runtime_log_path: ${RUNTIME_LOG}
  monitor_log_path: ${MONITOR_LOG}
  consistency_check_path: ${CONSISTENCY_CHECK}
  trace_check_path: ${TRACE_CHECK}
  output_video_path: ${OUTPUT_VIDEO}
\`\`\`

## 执行命令

\`\`\`bash
RUN_ID="${RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE}" \
INPUT_PATH="${INPUT_PATH}" \
DURATION_SEC="${DURATION_SEC}" \
LOOP_VIDEO_FILE="${LOOP_VIDEO_FILE}" \
PACE_VIDEO_FILE="${PACE_VIDEO_FILE}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW}" \
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION}" \
QUEUE_POLICY="${QUEUE_POLICY:-}" \
QUEUE_CAPACITY="${QUEUE_CAPACITY:-}" \
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS:-}" \
V4L2_RAW="${V4L2_RAW:-}" \
V4L2_WIDTH="${V4L2_WIDTH:-}" \
V4L2_HEIGHT="${V4L2_HEIGHT:-}" \
V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE:-}" \
V4L2_FPS="${V4L2_FPS:-}" \
BAYER_PATTERN="${BAYER_PATTERN:-}" \
V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE:-}" \
V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE:-}" \
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-}" \
ARGUS_PIPELINE="${ARGUS_PIPELINE:-}" \
ARGUS_SENSOR_ID="${ARGUS_SENSOR_ID:-}" \
ARGUS_WIDTH="${ARGUS_WIDTH:-}" \
ARGUS_HEIGHT="${ARGUS_HEIGHT:-}" \
ARGUS_FPS="${ARGUS_FPS:-}" \
ARGUS_FLIP_METHOD="${ARGUS_FLIP_METHOD:-}" \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
\`\`\`
EOF

if [[ ! -x "${APP}" ]]; then
  echo "Pipeline app not found or not executable: ${APP}" >&2
  echo "Run projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh first." >&2
  exit 2
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python 3 executable not found: ${PYTHON_BIN}" >&2
  echo "Set PYTHON_BIN to a Python 3 executable, for example: PYTHON_BIN=python3" >&2
  exit 2
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 6) else 1)
PY
then
  echo "Python 3.6+ is required for pipeline postchecks: ${PYTHON_BIN}" >&2
  "${PYTHON_BIN}" --version >&2 || true
  exit 2
fi

if ! "${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/check_prepost_consistency.py \
  --project1-preprocess "${PROJECT1_PREPROCESS_CONFIG}" \
  --project1-postprocess "${PROJECT1_POSTPROCESS_CONFIG}" \
  --project3-model "${MODEL_CONFIG}" \
  --project3-source "projects/03_video_pipeline/src/video_pipeline_app.cpp" \
  --output-md "${CONSISTENCY_CHECK}"; then
  echo "Pre/post consistency check failed: ${CONSISTENCY_CHECK}" >&2
  exit 2
fi

check_mipi_camera_conflict() {
  if [[ "${INPUT_SOURCE_TYPE}" != "mipi_camera" ]]; then
    return 0
  fi
  if [[ ! -e "${INPUT_PATH}" ]]; then
    echo "INPUT_SOURCE_MISSING: ${INPUT_PATH}" >&2
    return 0
  fi
  if ! command -v fuser >/dev/null 2>&1; then
    return 0
  fi

  local pids=""
  pids="$(fuser "${INPUT_PATH}" 2>/dev/null || true)"
  pids="$(echo "${pids}" | xargs || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi

  echo "INPUT_SOURCE_BUSY: device=${INPUT_PATH} pids=${pids}" >&2
  if command -v ps >/dev/null 2>&1; then
    ps -fp ${pids} >&2 || true
  fi
  echo "INPUT_SOURCE_BUSY_HINT: stop conflicting camera preview / v4l2-ctl / gst-launch / python-opencv processes, then retry." >&2
}

check_mipi_camera_conflict

MONITOR_STARTED=0
if command -v tegrastats >/dev/null 2>&1; then
  tegrastats --interval 1000 --logfile "${MONITOR_LOG}" &
  echo "$!" > "${MONITOR_PID}"
  MONITOR_STARTED=1
else
  echo "tegrastats not found; monitor evidence is not_verified" > "${MONITOR_LOG}"
fi

cleanup() {
  if [[ "${MONITOR_STARTED}" -eq 1 && -f "${MONITOR_PID}" ]]; then
    kill "$(cat "${MONITOR_PID}")" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

set +e
APP_ARGS=(
  --config "${PIPELINE_CONFIG}"
  --model-config "${MODEL_CONFIG}"
  --backend-config "${BOARD_CONFIG}"
  --stream-config "${STREAM_CONFIG}"
  --input-source-id "${INPUT_SOURCE_ID}"
  --input-source-type "${INPUT_SOURCE_TYPE}"
  --input "${INPUT_PATH}"
  --duration-sec "${DURATION_SEC}"
  --raw-output "${RAW_PATH}"
  --runtime-log "${RUNTIME_LOG}"
  --monitor-log "${MONITOR_LOG}"
  --preview-window "${PREVIEW_WINDOW}"
  --input-orientation-correction "${INPUT_ORIENTATION_CORRECTION}"
)
if [[ "${SAVE_OUTPUT_VIDEO}" == "1" ]]; then
  APP_ARGS+=(--output-video "${OUTPUT_VIDEO}")
fi
if [[ ("${INPUT_SOURCE_TYPE}" == "video_file" || "${INPUT_SOURCE_TYPE}" == "video_playlist") && "${LOOP_VIDEO_FILE}" == "0" ]]; then
  APP_ARGS+=(--no-loop-video-file)
fi
if [[ ("${INPUT_SOURCE_TYPE}" == "video_file" || "${INPUT_SOURCE_TYPE}" == "video_playlist") && "${PACE_VIDEO_FILE}" == "0" ]]; then
  APP_ARGS+=(--no-pace-video-file)
fi
if [[ -n "${EFFECTIVE_QUEUE_POLICY}" ]]; then
  APP_ARGS+=(--queue-policy "${EFFECTIVE_QUEUE_POLICY}")
fi
if [[ -n "${QUEUE_CAPACITY}" ]]; then
  APP_ARGS+=(--queue-capacity "${QUEUE_CAPACITY}")
fi
if [[ -n "${QUEUE_PUSH_TIMEOUT_MS}" ]]; then
  APP_ARGS+=(--queue-push-timeout-ms "${QUEUE_PUSH_TIMEOUT_MS}")
fi
if [[ "${V4L2_RAW}" == "1" ]]; then
  APP_ARGS+=(--v4l2-raw)
fi
if [[ -n "${V4L2_WIDTH}" ]]; then
  APP_ARGS+=(--v4l2-width "${V4L2_WIDTH}")
fi
if [[ -n "${V4L2_HEIGHT}" ]]; then
  APP_ARGS+=(--v4l2-height "${V4L2_HEIGHT}")
fi
if [[ -n "${V4L2_SENSOR_MODE}" ]]; then
  APP_ARGS+=(--v4l2-sensor-mode "${V4L2_SENSOR_MODE}")
fi
if [[ -n "${V4L2_FPS}" ]]; then
  APP_ARGS+=(--v4l2-fps "${V4L2_FPS}")
fi
if [[ -n "${BAYER_PATTERN}" ]]; then
  APP_ARGS+=(--bayer-pattern "${BAYER_PATTERN}")
fi
if [[ -n "${V4L2_NORMALIZE_MODE}" ]]; then
  APP_ARGS+=(--v4l2-normalize-mode "${V4L2_NORMALIZE_MODE}")
fi
if [[ "${V4L2_DISABLE_WHITE_BALANCE}" == "1" ]]; then
  APP_ARGS+=(--v4l2-disable-white-balance)
fi
if [[ -n "${FAULT_INJECT_DISCONNECT_AFTER_SEC}" ]]; then
  APP_ARGS+=(--fault-inject-disconnect-after-sec "${FAULT_INJECT_DISCONNECT_AFTER_SEC}")
fi
"${APP}" "${APP_ARGS[@]}" > "${RUNTIME_LOG}" 2>&1
APP_EXIT=$?
set -e

REBUILD_HINT=""
if [[ "${APP_EXIT}" -eq 30 ]] && grep -q "^CONFIG_INVALID: Unknown argument: --queue-policy" "${RUNTIME_LOG}" 2>/dev/null; then
  REBUILD_HINT="rebuild_required_binary_missing_queue_override_args"
elif [[ "${APP_EXIT}" -eq 30 ]] && grep -q "^CONFIG_INVALID: Unknown argument: --preview-window" "${RUNTIME_LOG}" 2>/dev/null; then
  REBUILD_HINT="rebuild_required_binary_missing_preview_window_arg"
fi
BUSY_DEVICE_HINT=""
if [[ "${APP_EXIT}" -eq 10 ]] && grep -q "Device or resource busy" "${RUNTIME_LOG}" 2>/dev/null; then
  BUSY_DEVICE_HINT="input_source_device_busy_stop_conflicting_camera_processes"
fi

SCHEMA_EXIT=0
TRACE_EXIT=0
AGGREGATE_EXIT=0
if [[ -s "${RAW_PATH}" ]]; then
  set +e
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/validate_pipeline_raw_schema.py \
    --input "${RAW_PATH}" \
    --schema benchmark/schemas/video_pipeline_raw_schema.yaml \
    --output "${SCHEMA_CHECK}"
  SCHEMA_EXIT=$?

  TRACE_ARGS=(--raw "${RAW_PATH}" --output "${TRACE_CHECK}")
  if [[ "${TRACE_FAIL_ON_GAPS}" == "1" ]]; then
    TRACE_ARGS+=(--fail-on-gaps)
  fi
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/check_pipeline_trace.py "${TRACE_ARGS[@]}"
  TRACE_EXIT=$?

  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_pipeline_benchmark.py \
    --input "${RAW_PATH}" \
    --monitor "${MONITOR_LOG}" \
    --output "${PROCESSED_SUMMARY}"
  AGGREGATE_EXIT=$?
  set -e
else
  SCHEMA_EXIT=2
  TRACE_EXIT=2
  AGGREGATE_EXIT=2
fi

FINAL_STATUS="not_verified"
FINAL_EXIT="${APP_EXIT}"
if [[ "${APP_EXIT}" -eq 0 && "${SCHEMA_EXIT}" -eq 0 && "${TRACE_EXIT}" -eq 0 && "${AGGREGATE_EXIT}" -eq 0 ]]; then
  FINAL_STATUS="runtime_pass_all_postchecks_pass"
  FINAL_EXIT=0
elif [[ "${APP_EXIT}" -eq 0 ]]; then
  FINAL_STATUS="runtime_pass_postcheck_failure"
  FINAL_EXIT=3
else
  FINAL_STATUS="fail"
fi

cat >> "${RUN_DIR}/run.md" <<EOF

## 执行结果

- exit_code: ${APP_EXIT}
- schema_check_exit_code: ${SCHEMA_EXIT}
- trace_check_exit_code: ${TRACE_EXIT}
- aggregate_exit_code: ${AGGREGATE_EXIT}
- raw_result_path: ${RAW_PATH}
- processed_result_path: ${PROCESSED_SUMMARY}
- schema_check_path: ${SCHEMA_CHECK}
- trace_check_path: ${TRACE_CHECK}
- consistency_check_path: ${CONSISTENCY_CHECK}
- runtime_log_path: ${RUNTIME_LOG}
- monitor_log_path: ${MONITOR_LOG}
- output_video_path: ${OUTPUT_VIDEO}
- output_video_saved: ${SAVE_OUTPUT_VIDEO}
- preview_window_requested: ${PREVIEW_WINDOW}
- input_orientation_correction: ${INPUT_ORIENTATION_CORRECTION}
- trace_fail_on_gaps: ${TRACE_FAIL_ON_GAPS}
- pace_video_file_requested: ${PACE_VIDEO_FILE}
- pace_video_file_effective: ${EFFECTIVE_PACE_VIDEO_FILE}
- queue_policy_override_requested: ${QUEUE_POLICY:-}
- queue_policy_override_effective: ${EFFECTIVE_QUEUE_POLICY:-}
- queue_capacity_override: ${QUEUE_CAPACITY:-}
- queue_push_timeout_ms_override: ${QUEUE_PUSH_TIMEOUT_MS:-}
- v4l2_raw: ${V4L2_RAW:-}
- v4l2_width: ${V4L2_WIDTH:-}
- v4l2_height: ${V4L2_HEIGHT:-}
- v4l2_sensor_mode: ${V4L2_SENSOR_MODE:-}
- v4l2_fps: ${V4L2_FPS:-}
- bayer_pattern: ${BAYER_PATTERN:-}
- v4l2_normalize_mode: ${V4L2_NORMALIZE_MODE:-}
- v4l2_disable_white_balance: ${V4L2_DISABLE_WHITE_BALANCE:-}
- fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC:-}
- argus_sensor_id: ${ARGUS_SENSOR_ID:-}
- argus_width: ${ARGUS_WIDTH:-}
- argus_height: ${ARGUS_HEIGHT:-}
- argus_fps: ${ARGUS_FPS:-}
- argus_flip_method: ${ARGUS_FLIP_METHOD:-}
- busy_device_hint: ${BUSY_DEVICE_HINT:-}
- status: ${FINAL_STATUS}
EOF

echo "final_status=${FINAL_STATUS}"
echo "final_exit=${FINAL_EXIT}"
echo "app_exit=${APP_EXIT}"
echo "schema_exit=${SCHEMA_EXIT}"
echo "trace_exit=${TRACE_EXIT}"
echo "aggregate_exit=${AGGREGATE_EXIT}"
echo "run_id=${RUN_ID}"
echo "raw_result=${RAW_PATH}"
echo "processed_summary=${PROCESSED_SUMMARY}"
echo "schema_check=${SCHEMA_CHECK}"
echo "trace_check=${TRACE_CHECK}"
echo "consistency_check=${CONSISTENCY_CHECK}"
echo "runtime_log=${RUNTIME_LOG}"
echo "monitor_log=${MONITOR_LOG}"
echo "output_video=${OUTPUT_VIDEO}"
echo "output_video_saved=${SAVE_OUTPUT_VIDEO}"
echo "preview_window_requested=${PREVIEW_WINDOW}"
echo "input_orientation_correction=${INPUT_ORIENTATION_CORRECTION}"
echo "trace_fail_on_gaps=${TRACE_FAIL_ON_GAPS}"
echo "pace_video_file_requested=${PACE_VIDEO_FILE}"
echo "pace_video_file_effective=${EFFECTIVE_PACE_VIDEO_FILE}"
echo "queue_policy_override_requested=${QUEUE_POLICY}"
echo "queue_policy_override_effective=${EFFECTIVE_QUEUE_POLICY}"
echo "queue_capacity_override=${QUEUE_CAPACITY}"
echo "queue_push_timeout_ms_override=${QUEUE_PUSH_TIMEOUT_MS}"
echo "v4l2_raw=${V4L2_RAW}"
echo "v4l2_width=${V4L2_WIDTH}"
echo "v4l2_height=${V4L2_HEIGHT}"
echo "v4l2_sensor_mode=${V4L2_SENSOR_MODE}"
echo "v4l2_fps=${V4L2_FPS}"
echo "bayer_pattern=${BAYER_PATTERN}"
echo "v4l2_normalize_mode=${V4L2_NORMALIZE_MODE}"
echo "v4l2_disable_white_balance=${V4L2_DISABLE_WHITE_BALANCE}"
echo "fault_inject_disconnect_after_sec=${FAULT_INJECT_DISCONNECT_AFTER_SEC}"
echo "argus_sensor_id=${ARGUS_SENSOR_ID}"
echo "argus_width=${ARGUS_WIDTH}"
echo "argus_height=${ARGUS_HEIGHT}"
echo "argus_fps=${ARGUS_FPS}"
echo "argus_flip_method=${ARGUS_FLIP_METHOD}"
echo "busy_device_hint=${BUSY_DEVICE_HINT}"
if [[ -n "${REBUILD_HINT}" ]]; then
  echo "hint=${REBUILD_HINT}"
  if [[ "${REBUILD_HINT}" == "rebuild_required_binary_missing_preview_window_arg" ]]; then
    echo "hint_detail=board_binary_is_older_than_current_script_and_does_not_support_--preview-window"
    echo "suggested_fix=rm -rf build/03_video_pipeline_jetson && RUN_ID=\$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_build_preview_refresh bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh"
  elif [[ "${REBUILD_HINT}" == "rebuild_required_binary_missing_queue_override_args" ]]; then
    echo "hint_detail=board_binary_is_older_than_current_script_and_does_not_support_queue_override_args"
    echo "suggested_fix=rm -rf build/03_video_pipeline_jetson && RUN_ID=\$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_build_queue_refresh bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh"
  fi
fi
if [[ -n "${BUSY_DEVICE_HINT}" ]]; then
  echo "hint=${BUSY_DEVICE_HINT}"
fi

exit "${FINAL_EXIT}"

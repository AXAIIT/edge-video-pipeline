#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_set_runtime_v1}"
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-video_playlist}"
INPUT_PATH="${INPUT_PATH:-data/videos/runtime_playlist_v1.txt}"
INPUT_PATH_RECORD="${INPUT_PATH_RECORD:-${INPUT_PATH}}"
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION:-}"
DURATION_SEC="${DURATION_SEC:-600}"
LOOP_VIDEO_FILE="${LOOP_VIDEO_FILE:-1}"
PACE_VIDEO_FILE="${PACE_VIDEO_FILE:-1}"
BUILD_DIR="${BUILD_DIR:-build/03_video_pipeline_rdk_x5}"
APP="${APP:-${BUILD_DIR}/video_pipeline_app}"
PIPELINE_CONFIG="${PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml}"
MODEL_CONFIG="${MODEL_CONFIG:-projects/03_video_pipeline/configs/models/yolo11n.yaml}"
BOARD_CONFIG="${BOARD_CONFIG:-projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml}"
STREAM_CONFIG="${STREAM_CONFIG:-projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PREVIEW_WINDOW="${PREVIEW_WINDOW:-auto}"
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-0}"
QUEUE_POLICY="${QUEUE_POLICY:-}"
QUEUE_CAPACITY="${QUEUE_CAPACITY:-}"
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS:-}"
INFERENCE_WORKERS="${INFERENCE_WORKERS:-}"
POSTPROCESS_WORKERS="${POSTPROCESS_WORKERS:-}"
V4L2_RAW="${V4L2_RAW:-}"
V4L2_WIDTH="${V4L2_WIDTH:-}"
V4L2_HEIGHT="${V4L2_HEIGHT:-}"
V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE:-}"
V4L2_FPS="${V4L2_FPS:-}"
BAYER_PATTERN="${BAYER_PATTERN:-}"
V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE:-}"
V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE:-}"
SRCAMPY_PYTHON="${SRCAMPY_PYTHON:-python3}"
SRCAMPY_STREAM_SCRIPT="${SRCAMPY_STREAM_SCRIPT:-projects/03_video_pipeline/scripts/run/rdk_x5_srcampy_stream.py}"
SRCAMPY_VIDEO_IDX="${SRCAMPY_VIDEO_IDX:-}"
SRCAMPY_WIDTH="${SRCAMPY_WIDTH:-}"
SRCAMPY_HEIGHT="${SRCAMPY_HEIGHT:-}"
SRCAMPY_SENSOR_WIDTH="${SRCAMPY_SENSOR_WIDTH:-}"
SRCAMPY_SENSOR_HEIGHT="${SRCAMPY_SENSOR_HEIGHT:-}"
SRCAMPY_FPS="${SRCAMPY_FPS:-}"
SRCAMPY_WARMUP="${SRCAMPY_WARMUP:-}"
SRCAMPY_STARTUP_TIMEOUT_SEC="${SRCAMPY_STARTUP_TIMEOUT_SEC:-}"
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-}"
PROJECT1_PREPROCESS_CONFIG="${PROJECT1_PREPROCESS_CONFIG:-projects/01_vision_deploy/configs/preprocess/yolo11n_640.yaml}"
PROJECT1_POSTPROCESS_CONFIG="${PROJECT1_POSTPROCESS_CONFIG:-projects/01_vision_deploy/configs/postprocess/yolo11n_nms.yaml}"
BACKEND_ARTIFACT="${BACKEND_ARTIFACT:-models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin}"
EXPECTED_ARTIFACT_SHA256="${EXPECTED_ARTIFACT_SHA256:-2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c}"
SOURCE_PROJECT2_SHA256="${SOURCE_PROJECT2_SHA256:-2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c}"
FIXED_INPUT_ALIGNMENT_STATUS="$(awk -F': *' '$1 ~ /^[[:space:]]*fixed_input_alignment_status$/ {print $2; exit}' "${PIPELINE_CONFIG}" | tr -d '[:space:]')"

if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera" ]]; then
  [[ -n "${V4L2_RAW}" ]] || V4L2_RAW=1
  [[ -n "${V4L2_WIDTH}" ]] || V4L2_WIDTH=1280
  [[ -n "${V4L2_HEIGHT}" ]] || V4L2_HEIGHT=720
  [[ -n "${V4L2_SENSOR_MODE}" ]] || V4L2_SENSOR_MODE=5
  [[ -n "${V4L2_FPS}" ]] || V4L2_FPS=60
  [[ -n "${BAYER_PATTERN}" ]] || BAYER_PATTERN=RG
  [[ -n "${V4L2_NORMALIZE_MODE}" ]] || V4L2_NORMALIZE_MODE=fixed_10bit
  [[ -n "${V4L2_DISABLE_WHITE_BALANCE}" ]] || V4L2_DISABLE_WHITE_BALANCE=1
fi

if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_hbn" ]]; then
  if [[ -z "${INPUT_PATH}" || "${INPUT_PATH}" == "data/videos/runtime_playlist_v1.txt" ]]; then
    INPUT_PATH="srcampy://video_idx0"
  fi
  if [[ -z "${INPUT_PATH_RECORD}" || "${INPUT_PATH_RECORD}" == "data/videos/runtime_playlist_v1.txt" ]]; then
    INPUT_PATH_RECORD="${INPUT_PATH}"
  fi
  [[ -n "${SRCAMPY_VIDEO_IDX}" ]] || SRCAMPY_VIDEO_IDX=0
  [[ -n "${SRCAMPY_WIDTH}" ]] || SRCAMPY_WIDTH=640
  [[ -n "${SRCAMPY_HEIGHT}" ]] || SRCAMPY_HEIGHT=640
  [[ -n "${SRCAMPY_SENSOR_WIDTH}" ]] || SRCAMPY_SENSOR_WIDTH=1920
  [[ -n "${SRCAMPY_SENSOR_HEIGHT}" ]] || SRCAMPY_SENSOR_HEIGHT=1080
  [[ -n "${SRCAMPY_FPS}" ]] || SRCAMPY_FPS=30
  [[ -n "${SRCAMPY_WARMUP}" ]] || SRCAMPY_WARMUP=10
  [[ -n "${SRCAMPY_STARTUP_TIMEOUT_SEC}" ]] || SRCAMPY_STARTUP_TIMEOUT_SEC=8
  V4L2_RAW=""
  V4L2_WIDTH=""
  V4L2_HEIGHT=""
  V4L2_SENSOR_MODE=""
  V4L2_FPS=""
  BAYER_PATTERN=""
  V4L2_NORMALIZE_MODE=""
  V4L2_DISABLE_WHITE_BALANCE=""
fi

if [[ -z "${INPUT_ORIENTATION_CORRECTION}" ]]; then
  if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_hbn" ]]; then
    INPUT_ORIENTATION_CORRECTION=rotate180
  else
    INPUT_ORIENTATION_CORRECTION=auto
  fi
fi

# Only file-backed inputs honor loop/pacing controls; live sources keep these
# fields for reproducibility but should record them as not_applicable.
VIDEO_FILELIKE_INPUT=0
if [[ "${INPUT_SOURCE_TYPE}" == "video_file" || "${INPUT_SOURCE_TYPE}" == "video_playlist" ]]; then
  VIDEO_FILELIKE_INPUT=1
fi
if [[ "${VIDEO_FILELIKE_INPUT}" -eq 1 ]]; then
  LOOP_VIDEO_FILE_RECORD="${LOOP_VIDEO_FILE}"
  PACE_VIDEO_FILE_RECORD="${PACE_VIDEO_FILE}"
  COMMAND_VIDEO_TIMING_OVERRIDES="LOOP_VIDEO_FILE=${LOOP_VIDEO_FILE} PACE_VIDEO_FILE=${PACE_VIDEO_FILE} "
else
  LOOP_VIDEO_FILE_RECORD="not_applicable"
  PACE_VIDEO_FILE_RECORD="not_applicable"
  COMMAND_VIDEO_TIMING_OVERRIDES=""
fi

EFFECTIVE_QUEUE_POLICY="${QUEUE_POLICY}"
if [[ "${EFFECTIVE_QUEUE_POLICY}" == "block_timeout" ]]; then
  EFFECTIVE_QUEUE_POLICY="block_with_timeout"
fi
if [[ "${EFFECTIVE_QUEUE_POLICY}" == "block" && -n "${QUEUE_PUSH_TIMEOUT_MS}" ]]; then
  EFFECTIVE_QUEUE_POLICY="block_with_timeout"
fi

RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
RAW_PATH="benchmark/raw/03_video_pipeline/rdk_x5_8gb/${RUN_ID}.jsonl"
RUNTIME_LOG="logs/runtime/03_video_pipeline/rdk_x5_8gb/${RUN_ID}.log"
MONITOR_LOG="logs/monitor/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_bpu.log"
MONITOR_PID="logs/monitor/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_bpu.pid"
PROCESSED_SUMMARY="benchmark/processed/03_video_pipeline/${RUN_ID}_summary.csv"
SCHEMA_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_schema_check.md"
TRACE_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_trace_check.md"
CONSISTENCY_CHECK="benchmark/processed/03_video_pipeline/${RUN_ID}_prepost_consistency.md"
OUTPUT_VIDEO="${RUN_DIR}/outputs/${RUN_ID}.mp4"
ENVIRONMENT_BASELINE_ID_VALUE="${ENVIRONMENT_BASELINE_ID:-20260612_rdk_x5_8gb_env_baseline}"

mkdir -p "${RUN_DIR}/outputs" \
  benchmark/raw/03_video_pipeline/rdk_x5_8gb \
  benchmark/processed/03_video_pipeline \
  logs/runtime/03_video_pipeline/rdk_x5_8gb \
  logs/monitor/03_video_pipeline/rdk_x5_8gb \
  logs/failures/03_video_pipeline/rdk_x5_8gb

rm -f "${RAW_PATH}" \
  "${PROCESSED_SUMMARY}" \
  "${SCHEMA_CHECK}" \
  "${TRACE_CHECK}" \
  "${CONSISTENCY_CHECK}" \
  "${RUNTIME_LOG}" \
  "${MONITOR_LOG}" \
  "${MONITOR_PID}" \
  "${OUTPUT_VIDEO}"

ACTUAL_SHA256="missing"
if [[ -f "${BACKEND_ARTIFACT}" ]]; then
  ACTUAL_SHA256="$(sha256sum "${BACKEND_ARTIFACT}" | awk '{print $1}')"
fi
CONFIGURED_SHA256="$(awk -F': *' '$1 ~ /^[[:space:]]*backend_artifact_sha256$/ {print $2; exit}' "${BOARD_CONFIG}" | tr -d '[:space:]')"
HASH_STATUS="pass"
if [[ "${ACTUAL_SHA256}" != "${EXPECTED_ARTIFACT_SHA256}" ]]; then
  HASH_STATUS="blocked_hash_recheck"
elif [[ "${CONFIGURED_SHA256}" != "${ACTUAL_SHA256}" ]]; then
  HASH_STATUS="blocked_config_hash_mismatch"
fi

cat > "${RUN_DIR}/run.md" <<EOF
# ${RUN_ID}

\`\`\`yaml
run_id: ${RUN_ID}
date: $(date --iso-8601=seconds)
spec_ref: projects/03_video_pipeline/specs/03F_RDK_X5_BPU_CppPipeline规范.md
stage: rdk_x5_bpu_cpp_pipeline
status: not_verified

environment:
  environment_baseline_id: ${ENVIRONMENT_BASELINE_ID_VALUE}
  target: rdk_x5_8gb
  board: RDK X5 8GB

model:
  model_name: yolo11n
  backend_runtime: bpu
  precision_or_quantization: int8_ptq
  backend_artifact_path: ${BACKEND_ARTIFACT}
  backend_artifact_format: bin
  backend_artifact_sha256_actual: ${ACTUAL_SHA256}
  backend_artifact_sha256_expected: ${EXPECTED_ARTIFACT_SHA256}
  source_project2_artifact_sha256: ${SOURCE_PROJECT2_SHA256}
  artifact_selection_status: project3_selected_split_head_mainline
  backend_artifact_hash_status: ${HASH_STATUS}
  loader_api: Horizon hbDNN C API
  execution_provider: BPU
  cpu_fallback: false

input_source:
  input_source_id: ${INPUT_SOURCE_ID}
  input_source_type: ${INPUT_SOURCE_TYPE}
  uri: ${INPUT_PATH_RECORD}
  loop_video_file: ${LOOP_VIDEO_FILE_RECORD}
  pace_video_file: ${PACE_VIDEO_FILE_RECORD}
  v4l2_raw: ${V4L2_RAW:-null}
  v4l2_width: ${V4L2_WIDTH:-null}
  v4l2_height: ${V4L2_HEIGHT:-null}
  v4l2_sensor_mode: ${V4L2_SENSOR_MODE:-null}
  v4l2_fps: ${V4L2_FPS:-null}
  bayer_pattern: ${BAYER_PATTERN:-null}
  v4l2_normalize_mode: ${V4L2_NORMALIZE_MODE:-null}
  v4l2_disable_white_balance: ${V4L2_DISABLE_WHITE_BALANCE:-null}
  srcampy_python: ${SRCAMPY_PYTHON:-null}
  srcampy_stream_script: ${SRCAMPY_STREAM_SCRIPT:-null}
  srcampy_video_idx: ${SRCAMPY_VIDEO_IDX:-null}
  srcampy_width: ${SRCAMPY_WIDTH:-null}
  srcampy_height: ${SRCAMPY_HEIGHT:-null}
  srcampy_sensor_width: ${SRCAMPY_SENSOR_WIDTH:-null}
  srcampy_sensor_height: ${SRCAMPY_SENSOR_HEIGHT:-null}
  srcampy_fps: ${SRCAMPY_FPS:-null}
  srcampy_warmup: ${SRCAMPY_WARMUP:-null}
  srcampy_startup_timeout_sec: ${SRCAMPY_STARTUP_TIMEOUT_SEC:-null}

configs:
  pipeline_config: ${PIPELINE_CONFIG}
  stream_config: ${STREAM_CONFIG}
  model_config: ${MODEL_CONFIG}
  board_config: ${BOARD_CONFIG}
  queue_policy_override_requested: ${QUEUE_POLICY:-null}
  queue_policy_override_effective: ${EFFECTIVE_QUEUE_POLICY:-null}
  queue_capacity_override: ${QUEUE_CAPACITY:-null}
  queue_push_timeout_ms_override: ${QUEUE_PUSH_TIMEOUT_MS:-null}
  inference_workers_override: ${INFERENCE_WORKERS:-null}
  postprocess_workers_override: ${POSTPROCESS_WORKERS:-null}
  preview_window_requested: ${PREVIEW_WINDOW}
  input_orientation_correction: ${INPUT_ORIENTATION_CORRECTION}
  fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC:-null}

outputs:
  raw_result_path: ${RAW_PATH}
  processed_result_path: ${PROCESSED_SUMMARY}
  runtime_log_path: ${RUNTIME_LOG}
  monitor_log_path: ${MONITOR_LOG}
  schema_check_path: ${SCHEMA_CHECK}
  consistency_check_path: ${CONSISTENCY_CHECK}
  trace_check_path: ${TRACE_CHECK}
  output_video_path: ${OUTPUT_VIDEO}
\`\`\`

## 执行命令

\`\`\`bash
RUN_ID=${RUN_ID} INPUT_SOURCE_ID=${INPUT_SOURCE_ID} INPUT_SOURCE_TYPE=${INPUT_SOURCE_TYPE} INPUT_PATH=${INPUT_PATH_RECORD} DURATION_SEC=${DURATION_SEC} ${COMMAND_VIDEO_TIMING_OVERRIDES}SAVE_OUTPUT_VIDEO=${SAVE_OUTPUT_VIDEO} PREVIEW_WINDOW=${PREVIEW_WINDOW} INPUT_ORIENTATION_CORRECTION=${INPUT_ORIENTATION_CORRECTION} QUEUE_POLICY=${QUEUE_POLICY:-} QUEUE_CAPACITY=${QUEUE_CAPACITY:-} QUEUE_PUSH_TIMEOUT_MS=${QUEUE_PUSH_TIMEOUT_MS:-} INFERENCE_WORKERS=${INFERENCE_WORKERS:-} POSTPROCESS_WORKERS=${POSTPROCESS_WORKERS:-} V4L2_RAW=${V4L2_RAW:-} V4L2_WIDTH=${V4L2_WIDTH:-} V4L2_HEIGHT=${V4L2_HEIGHT:-} V4L2_SENSOR_MODE=${V4L2_SENSOR_MODE:-} V4L2_FPS=${V4L2_FPS:-} BAYER_PATTERN=${BAYER_PATTERN:-} V4L2_NORMALIZE_MODE=${V4L2_NORMALIZE_MODE:-} V4L2_DISABLE_WHITE_BALANCE=${V4L2_DISABLE_WHITE_BALANCE:-} SRCAMPY_PYTHON=${SRCAMPY_PYTHON:-} SRCAMPY_STREAM_SCRIPT=${SRCAMPY_STREAM_SCRIPT:-} SRCAMPY_VIDEO_IDX=${SRCAMPY_VIDEO_IDX:-} SRCAMPY_WIDTH=${SRCAMPY_WIDTH:-} SRCAMPY_HEIGHT=${SRCAMPY_HEIGHT:-} SRCAMPY_SENSOR_WIDTH=${SRCAMPY_SENSOR_WIDTH:-} SRCAMPY_SENSOR_HEIGHT=${SRCAMPY_SENSOR_HEIGHT:-} SRCAMPY_FPS=${SRCAMPY_FPS:-} SRCAMPY_WARMUP=${SRCAMPY_WARMUP:-} SRCAMPY_STARTUP_TIMEOUT_SEC=${SRCAMPY_STARTUP_TIMEOUT_SEC:-} FAULT_INJECT_DISCONNECT_AFTER_SEC=${FAULT_INJECT_DISCONNECT_AFTER_SEC:-} \\
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
\`\`\`
EOF

if [[ "${HASH_STATUS}" != "pass" && "${ALLOW_HASH_MISMATCH:-0}" != "1" ]]; then
  echo "BPU artifact hash mismatch: actual=${ACTUAL_SHA256}, configured=${CONFIGURED_SHA256:-missing}, expected=${EXPECTED_ARTIFACT_SHA256}" >&2
  echo "Set ALLOW_HASH_MISMATCH=1 only for diagnostic runs; formal 03F benchmark must recheck and align the artifact hash." >&2
  exit 2
fi

if [[ "${INPUT_SOURCE_TYPE}" == "video_file" ]]; then
  if [[ ! -f "${INPUT_PATH}" ]]; then
    echo "INPUT_FILE_MISSING: ${INPUT_PATH}" >&2
    echo "cwd=${REPO_ROOT}" >&2
    exit 2
  fi
fi

if [[ "${INPUT_SOURCE_TYPE}" == "video_playlist" ]]; then
  if [[ ! -f "${INPUT_PATH}" ]]; then
    echo "PLAYLIST_FILE_MISSING: ${INPUT_PATH}" >&2
    echo "cwd=${REPO_ROOT}" >&2
    exit 2
  fi
  FIRST_PLAYLIST_ITEM="$(awk '!/^[[:space:]]*#/ && NF {print; exit}' "${INPUT_PATH}")"
  if [[ -z "${FIRST_PLAYLIST_ITEM}" ]]; then
    echo "PLAYLIST_EMPTY: ${INPUT_PATH}" >&2
    exit 2
  fi
  if [[ ! -f "${FIRST_PLAYLIST_ITEM}" ]]; then
    echo "PLAYLIST_ITEM_MISSING: ${FIRST_PLAYLIST_ITEM}" >&2
    echo "playlist=${INPUT_PATH}" >&2
    echo "cwd=${REPO_ROOT}" >&2
    exit 2
  fi
fi

if [[ ! -x "${APP}" ]]; then
  if [[ "${AUTO_BUILD:-1}" == "1" && -f "projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh" ]]; then
    echo "Pipeline app not found or not executable: ${APP}" >&2
    echo "AUTO_BUILD=1: running projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh" >&2
    RUN_ID="${RUN_ID}_build" BUILD_DIR="${BUILD_DIR}" bash projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh
  fi
fi

if [[ ! -x "${APP}" ]]; then
  echo "Pipeline app not found or not executable after build attempt: ${APP}" >&2
  echo "Check logs/runtime/03_video_pipeline/build/${RUN_ID}_build_configure.log and ${RUN_ID}_build_build.log." >&2
  exit 2
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python 3 executable not found: ${PYTHON_BIN}" >&2
  exit 2
fi

if ! "${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/check_prepost_consistency.py \
  --project1-preprocess "${PROJECT1_PREPROCESS_CONFIG}" \
  --project1-postprocess "${PROJECT1_POSTPROCESS_CONFIG}" \
  --project3-model "${MODEL_CONFIG}" \
  --project3-board "${BOARD_CONFIG}" \
  --project3-source "projects/03_video_pipeline/src/video_pipeline_app.cpp" \
  --output-md "${CONSISTENCY_CHECK}"; then
  echo "Pre/post consistency check failed: ${CONSISTENCY_CHECK}" >&2
  exit 2
fi

MONITOR_STARTED=0
APP_MATCH_PATTERN="${APP}" bash projects/03_video_pipeline/scripts/monitor/monitor_rdk_x5_bpu.sh "${MONITOR_LOG}" &
echo "$!" > "${MONITOR_PID}"
MONITOR_STARTED=1

cleanup() {
  if [[ "${MONITOR_STARTED}" -eq 1 && -f "${MONITOR_PID}" ]]; then
    kill "$(cat "${MONITOR_PID}")" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

set +e
APP_ARGS=(
  --config "${PIPELINE_CONFIG}" \
  --model-config "${MODEL_CONFIG}" \
  --backend-config "${BOARD_CONFIG}" \
  --stream-config "${STREAM_CONFIG}" \
  --input-source-id "${INPUT_SOURCE_ID}" \
  --input-source-type "${INPUT_SOURCE_TYPE}" \
  --input "${INPUT_PATH}" \
  --input-orientation-correction "${INPUT_ORIENTATION_CORRECTION}" \
  --duration-sec "${DURATION_SEC}" \
  --raw-output "${RAW_PATH}" \
  --runtime-log "${RUNTIME_LOG}" \
  --monitor-log "${MONITOR_LOG}" \
  --preview-window "${PREVIEW_WINDOW}"
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
if [[ -n "${INFERENCE_WORKERS}" ]]; then
  APP_ARGS+=(--inference-workers "${INFERENCE_WORKERS}")
fi
if [[ -n "${POSTPROCESS_WORKERS}" ]]; then
  APP_ARGS+=(--postprocess-workers "${POSTPROCESS_WORKERS}")
fi
if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera" ]]; then
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
fi
if [[ "${INPUT_SOURCE_TYPE}" == "mipi_camera_hbn" ]]; then
  APP_ARGS+=(
    --srcampy-python "${SRCAMPY_PYTHON}"
    --srcampy-stream-script "${SRCAMPY_STREAM_SCRIPT}"
    --srcampy-video-idx "${SRCAMPY_VIDEO_IDX}"
    --srcampy-width "${SRCAMPY_WIDTH}"
    --srcampy-height "${SRCAMPY_HEIGHT}"
    --srcampy-sensor-width "${SRCAMPY_SENSOR_WIDTH}"
    --srcampy-sensor-height "${SRCAMPY_SENSOR_HEIGHT}"
    --srcampy-fps "${SRCAMPY_FPS}"
    --srcampy-warmup "${SRCAMPY_WARMUP}"
    --srcampy-startup-timeout-sec "${SRCAMPY_STARTUP_TIMEOUT_SEC}"
  )
fi
if [[ -n "${FAULT_INJECT_DISCONNECT_AFTER_SEC}" ]]; then
  APP_ARGS+=(--fault-inject-disconnect-after-sec "${FAULT_INJECT_DISCONNECT_AFTER_SEC}")
fi
"${APP}" "${APP_ARGS[@]}" > "${RUNTIME_LOG}" 2>&1
APP_EXIT=$?
set -e

if [[ "${APP_EXIT}" -ne 0 ]]; then
  echo "Pipeline app failed: exit=${APP_EXIT}, runtime_log=${RUNTIME_LOG}" >&2
  echo "----- runtime log tail -----" >&2
  tail -n 40 "${RUNTIME_LOG}" >&2 || true
  echo "----------------------------" >&2
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
  if [[ "${FIXED_INPUT_ALIGNMENT_STATUS}" == pass* || "${FIXED_INPUT_ALIGNMENT_STATUS}" == superseded_by_bdd100k_labeled_video_quality ]]; then
    FINAL_STATUS="pass"
  else
    FINAL_STATUS="not_verified_until_fixed_input_alignment_and_report_pass"
  fi
  FINAL_EXIT=0
elif [[ "${APP_EXIT}" -eq 0 ]]; then
  FINAL_STATUS="not_verified_due_to_postcheck_failure"
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
- backend_artifact_hash_status: ${HASH_STATUS}
- raw_result_path: ${RAW_PATH}
- processed_result_path: ${PROCESSED_SUMMARY}
- schema_check_path: ${SCHEMA_CHECK}
- trace_check_path: ${TRACE_CHECK}
- consistency_check_path: ${CONSISTENCY_CHECK}
- runtime_log_path: ${RUNTIME_LOG}
- monitor_log_path: ${MONITOR_LOG}
- output_video_path: ${OUTPUT_VIDEO}
- output_video_saved: ${SAVE_OUTPUT_VIDEO}
- trace_fail_on_gaps: ${TRACE_FAIL_ON_GAPS}
- fixed_input_alignment_status: ${FIXED_INPUT_ALIGNMENT_STATUS:-missing}
- loop_video_file: ${LOOP_VIDEO_FILE_RECORD}
- pace_video_file: ${PACE_VIDEO_FILE_RECORD}
- queue_policy_override_requested: ${QUEUE_POLICY:-}
- queue_policy_override_effective: ${EFFECTIVE_QUEUE_POLICY:-}
- queue_capacity_override: ${QUEUE_CAPACITY:-}
- queue_push_timeout_ms_override: ${QUEUE_PUSH_TIMEOUT_MS:-}
- inference_workers_override: ${INFERENCE_WORKERS:-}
- postprocess_workers_override: ${POSTPROCESS_WORKERS:-}
- v4l2_raw: ${V4L2_RAW:-}
- v4l2_width: ${V4L2_WIDTH:-}
- v4l2_height: ${V4L2_HEIGHT:-}
- v4l2_sensor_mode: ${V4L2_SENSOR_MODE:-}
- v4l2_fps: ${V4L2_FPS:-}
- bayer_pattern: ${BAYER_PATTERN:-}
- v4l2_normalize_mode: ${V4L2_NORMALIZE_MODE:-}
- v4l2_disable_white_balance: ${V4L2_DISABLE_WHITE_BALANCE:-}
- srcampy_python: ${SRCAMPY_PYTHON:-}
- srcampy_stream_script: ${SRCAMPY_STREAM_SCRIPT:-}
- srcampy_video_idx: ${SRCAMPY_VIDEO_IDX:-}
- srcampy_width: ${SRCAMPY_WIDTH:-}
- srcampy_height: ${SRCAMPY_HEIGHT:-}
- srcampy_sensor_width: ${SRCAMPY_SENSOR_WIDTH:-}
- srcampy_sensor_height: ${SRCAMPY_SENSOR_HEIGHT:-}
- srcampy_fps: ${SRCAMPY_FPS:-}
- srcampy_warmup: ${SRCAMPY_WARMUP:-}
- srcampy_startup_timeout_sec: ${SRCAMPY_STARTUP_TIMEOUT_SEC:-}
- fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC:-}
- status: ${FINAL_STATUS}
EOF

echo "final_status=${FINAL_STATUS}"
echo "final_exit=${FINAL_EXIT}"
echo "fixed_input_alignment_status=${FIXED_INPUT_ALIGNMENT_STATUS:-missing}"
echo "hash_status=${HASH_STATUS}"
echo "actual_sha256=${ACTUAL_SHA256}"
echo "expected_artifact_sha256=${EXPECTED_ARTIFACT_SHA256}"
echo "source_project2_sha256=${SOURCE_PROJECT2_SHA256}"
echo "run_id=${RUN_ID}"
echo "raw_result=${RAW_PATH}"
echo "processed_summary=${PROCESSED_SUMMARY}"
echo "schema_check=${SCHEMA_CHECK}"
echo "trace_check=${TRACE_CHECK}"
echo "consistency_check=${CONSISTENCY_CHECK}"
echo "runtime_log=${RUNTIME_LOG}"
echo "monitor_log=${MONITOR_LOG}"
echo "queue_policy_override_requested=${QUEUE_POLICY}"
echo "queue_policy_override_effective=${EFFECTIVE_QUEUE_POLICY}"
echo "queue_capacity_override=${QUEUE_CAPACITY}"
echo "queue_push_timeout_ms_override=${QUEUE_PUSH_TIMEOUT_MS}"
echo "inference_workers_override=${INFERENCE_WORKERS}"
echo "postprocess_workers_override=${POSTPROCESS_WORKERS}"
echo "preview_window_requested=${PREVIEW_WINDOW}"

exit "${FINAL_EXIT}"

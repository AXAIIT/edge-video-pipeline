#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_auto}"
PIPELINE_RUNNER="${PIPELINE_RUNNER:-projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-imx219_csi_001}"
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-mipi_camera}"
INPUT_PATH="${INPUT_PATH:-/dev/video0}"
DURATION_SEC="${DURATION_SEC:-600}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PREVIEW_WINDOW="${PREVIEW_WINDOW:-off}"
V4L2_RAW="${V4L2_RAW:-1}"
V4L2_WIDTH="${V4L2_WIDTH:-1280}"
V4L2_HEIGHT="${V4L2_HEIGHT:-720}"
V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE:-5}"
V4L2_FPS="${V4L2_FPS:-60}"
BAYER_PATTERN="${BAYER_PATTERN:-RG}"
V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE:-fixed_10bit}"
V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE:-1}"
QUEUE_POLICY="${QUEUE_POLICY:-}"
QUEUE_CAPACITY="${QUEUE_CAPACITY:-}"
QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS:-}"
DISCONNECT_METHOD="${DISCONNECT_METHOD:-app_fault}"
DISCONNECT_DRIVER_DIR="${DISCONNECT_DRIVER_DIR:-/sys/bus/i2c/drivers/imx219}"
DISCONNECT_DEVICE_ID="${DISCONNECT_DEVICE_ID:-10-0010}"
DISCONNECT_WARMUP_SEC="${DISCONNECT_WARMUP_SEC:-30}"
DISCONNECT_HOLD_SEC="${DISCONNECT_HOLD_SEC:-8}"
DISCONNECT_POST_RECOVERY_SEC="${DISCONNECT_POST_RECOVERY_SEC:-60}"
PIPELINE_START_TIMEOUT_SEC="${PIPELINE_START_TIMEOUT_SEC:-90}"
ALLOW_INTERACTIVE_SUDO="${ALLOW_INTERACTIVE_SUDO:-0}"
FAULT_INJECT_DISCONNECT_AFTER_SEC="${FAULT_INJECT_DISCONNECT_AFTER_SEC:-${DISCONNECT_WARMUP_SEC}}"

RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
RUNTIME_LOG="logs/runtime/03_video_pipeline/jetson_8gb/${RUN_ID}.log"
AUTOMATION_LOG="logs/failures/03_video_pipeline/jetson_8gb/${RUN_ID}_imx219_disconnect_automation.log"

mkdir -p "${RUN_DIR}" "$(dirname "${AUTOMATION_LOG}")"
rm -f "${AUTOMATION_LOG}"

PIPELINE_PID=""
PIPELINE_FINISHED=0
PIPELINE_EXIT=0
TRIGGER_STATUS="not_started"
EVIDENCE_STATUS="not_checked"

timestamp() {
  date --iso-8601=seconds
}

log_note() {
  printf '[%s] %s\n' "$(timestamp)" "$*" | tee -a "${AUTOMATION_LOG}"
}

cleanup() {
  if [[ "${PIPELINE_FINISHED}" -eq 0 && -n "${PIPELINE_PID}" ]] && kill -0 "${PIPELINE_PID}" 2>/dev/null; then
    log_note "cleanup_terminating_pipeline pid=${PIPELINE_PID}"
    kill "${PIPELINE_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

run_privileged() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi
  if [[ "${ALLOW_INTERACTIVE_SUDO}" == "1" ]]; then
    sudo "$@"
    return
  fi
  sudo -n "$@"
}

write_driver_state() {
  local action="$1"
  local path="${DISCONNECT_DRIVER_DIR}/${action}"
  if [[ ! -e "${path}" ]]; then
    log_note "driver_path_missing path=${path}"
    return 1
  fi
  log_note "driver_action=${action} device=${DISCONNECT_DEVICE_ID} path=${path}"
  printf '%s\n' "${DISCONNECT_DEVICE_ID}" | run_privileged tee "${path}" >/dev/null
}

runtime_has_startup_fatal() {
  [[ -f "${RUNTIME_LOG}" ]] || return 1
  grep -Eq 'BACKEND_RUNTIME_FAILED|Could not initialize cudnn|Engine deserialization failed|CONFIG_INVALID|INPUT_OPEN_FAILED' "${RUNTIME_LOG}"
}

runtime_has_disconnect_evidence() {
  [[ -f "${RUNTIME_LOG}" ]] || return 1
  grep -Eq 'INPUT_DISCONNECTED|FAULT_INJECTED_DISCONNECT|No such device|device disconnected|capture failed|read failed|VIDIOC_DQBUF' "${RUNTIME_LOG}"
}

capture_v4l2_devices() {
  if ! command -v v4l2-ctl >/dev/null 2>&1; then
    log_note "v4l2_ctl_missing"
    return 0
  fi
  log_note "v4l2_devices_begin"
  v4l2-ctl --list-devices 2>&1 | tee -a "${AUTOMATION_LOG}"
  log_note "v4l2_devices_end"
}

MIN_DURATION_SEC=$((DISCONNECT_WARMUP_SEC + DISCONNECT_HOLD_SEC + DISCONNECT_POST_RECOVERY_SEC + 10))
if (( DURATION_SEC < MIN_DURATION_SEC )); then
  echo "DURATION_SEC=${DURATION_SEC} is too short for automated disconnect; require >= ${MIN_DURATION_SEC}" >&2
  exit 2
fi

if [[ ! -x "${PIPELINE_RUNNER}" && ! -f "${PIPELINE_RUNNER}" ]]; then
  echo "Pipeline runner not found: ${PIPELINE_RUNNER}" >&2
  exit 2
fi

if [[ "${DISCONNECT_METHOD}" != "app_fault" && "${DISCONNECT_METHOD}" != "driver_unbind" ]]; then
  echo "Unsupported DISCONNECT_METHOD=${DISCONNECT_METHOD}; expected app_fault or driver_unbind" >&2
  exit 2
fi

if [[ "${DISCONNECT_METHOD}" == "driver_unbind" && ! -d "${DISCONNECT_DRIVER_DIR}" ]]; then
  echo "IMX219 driver directory not found: ${DISCONNECT_DRIVER_DIR}" >&2
  exit 2
fi

log_note "automation_start run_id=${RUN_ID} runtime_log=${RUNTIME_LOG} disconnect_method=${DISCONNECT_METHOD}"
capture_v4l2_devices

PIPELINE_FAULT_INJECT_VALUE=""
if [[ "${DISCONNECT_METHOD}" == "app_fault" ]]; then
  PIPELINE_FAULT_INJECT_VALUE="${FAULT_INJECT_DISCONNECT_AFTER_SEC}"
fi

(
  RUN_ID="${RUN_ID}" \
  INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
  INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE}" \
  INPUT_PATH="${INPUT_PATH}" \
  DURATION_SEC="${DURATION_SEC}" \
  SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
  PREVIEW_WINDOW="${PREVIEW_WINDOW}" \
  V4L2_RAW="${V4L2_RAW}" \
  V4L2_WIDTH="${V4L2_WIDTH}" \
  V4L2_HEIGHT="${V4L2_HEIGHT}" \
  V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE}" \
  V4L2_FPS="${V4L2_FPS}" \
  BAYER_PATTERN="${BAYER_PATTERN}" \
  V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE}" \
  V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE}" \
  QUEUE_POLICY="${QUEUE_POLICY}" \
  QUEUE_CAPACITY="${QUEUE_CAPACITY}" \
  QUEUE_PUSH_TIMEOUT_MS="${QUEUE_PUSH_TIMEOUT_MS}" \
  FAULT_INJECT_DISCONNECT_AFTER_SEC="${PIPELINE_FAULT_INJECT_VALUE}" \
  bash "${PIPELINE_RUNNER}"
) &
PIPELINE_PID=$!
log_note "pipeline_started pid=${PIPELINE_PID}"

WAITED_SEC=0
until [[ -f "${RUNTIME_LOG}" ]]; do
  if ! kill -0 "${PIPELINE_PID}" 2>/dev/null; then
    log_note "pipeline_exited_before_runtime_log"
    break
  fi
  if (( WAITED_SEC >= PIPELINE_START_TIMEOUT_SEC )); then
    log_note "runtime_log_wait_timeout timeout_sec=${PIPELINE_START_TIMEOUT_SEC}"
    break
  fi
  sleep 1
  WAITED_SEC=$((WAITED_SEC + 1))
done

if [[ ! -f "${RUNTIME_LOG}" ]]; then
  set +e
  wait "${PIPELINE_PID}"
  PIPELINE_EXIT=$?
  set -e
  PIPELINE_FINISHED=1
  TRIGGER_STATUS="skipped_no_runtime_log"
  EVIDENCE_STATUS="not_checked_no_runtime_log"
else
  log_note "runtime_log_ready waited_sec=${WAITED_SEC}"

  ELAPSED_SEC=0
  while (( ELAPSED_SEC < DISCONNECT_WARMUP_SEC )); do
    if runtime_has_startup_fatal; then
      TRIGGER_STATUS="skipped_due_to_startup_failure"
      EVIDENCE_STATUS="startup_failed_before_disconnect"
      log_note "startup_fatal_detected before_disconnect"
      break
    fi
    if ! kill -0 "${PIPELINE_PID}" 2>/dev/null; then
      TRIGGER_STATUS="skipped_pipeline_exited_early"
      EVIDENCE_STATUS="pipeline_exited_before_disconnect"
      log_note "pipeline_exited_before_disconnect elapsed_sec=${ELAPSED_SEC}"
      break
    fi
    sleep 1
    ELAPSED_SEC=$((ELAPSED_SEC + 1))
  done

  if [[ "${TRIGGER_STATUS}" == "not_started" && "${DISCONNECT_METHOD}" == "app_fault" ]]; then
    TRIGGER_STATUS="app_fault_requested"
    OBSERVED_SEC=0
    MAX_WAIT_SEC=$((DISCONNECT_WARMUP_SEC + DISCONNECT_POST_RECOVERY_SEC + 30))
    while (( OBSERVED_SEC < MAX_WAIT_SEC )); do
      if runtime_has_disconnect_evidence; then
        EVIDENCE_STATUS="disconnect_evidence_found"
        log_note "disconnect_evidence_found method=app_fault"
        break
      fi
      if ! kill -0 "${PIPELINE_PID}" 2>/dev/null; then
        break
      fi
      sleep 1
      OBSERVED_SEC=$((OBSERVED_SEC + 1))
    done
    if [[ "${EVIDENCE_STATUS}" == "not_checked" ]]; then
      EVIDENCE_STATUS="disconnect_action_executed_but_no_runtime_evidence"
      log_note "disconnect_evidence_not_found method=app_fault"
    fi
  fi

  if [[ "${TRIGGER_STATUS}" == "not_started" && "${DISCONNECT_METHOD}" == "driver_unbind" ]]; then
    if ! write_driver_state "unbind"; then
      log_note "unbind_failed driver_dir=${DISCONNECT_DRIVER_DIR} device=${DISCONNECT_DEVICE_ID}"
      exit 5
    fi
    TRIGGER_STATUS="unbind_sent"
    sleep "${DISCONNECT_HOLD_SEC}"

    if ! write_driver_state "bind"; then
      log_note "bind_failed driver_dir=${DISCONNECT_DRIVER_DIR} device=${DISCONNECT_DEVICE_ID}"
      exit 5
    fi
    TRIGGER_STATUS="unbind_and_bind_sent"
    capture_v4l2_devices

    OBSERVED_SEC=0
    while (( OBSERVED_SEC < DISCONNECT_POST_RECOVERY_SEC )); do
      if ! kill -0 "${PIPELINE_PID}" 2>/dev/null; then
        break
      fi
      sleep 1
      OBSERVED_SEC=$((OBSERVED_SEC + 1))
    done

    if runtime_has_disconnect_evidence; then
      EVIDENCE_STATUS="disconnect_evidence_found"
      log_note "disconnect_evidence_found"
    else
      EVIDENCE_STATUS="disconnect_action_executed_but_no_runtime_evidence"
      log_note "disconnect_evidence_not_found"
    fi
  fi

  set +e
  wait "${PIPELINE_PID}"
  PIPELINE_EXIT=$?
  set -e
  PIPELINE_FINISHED=1
fi

cat >> "${RUN_DIR}/run.md" <<EOF

## IMX219 Disconnect Automation

- automation_log_path: ${AUTOMATION_LOG}
- disconnect_method: ${DISCONNECT_METHOD}
- disconnect_driver_dir: ${DISCONNECT_DRIVER_DIR}
- disconnect_device_id: ${DISCONNECT_DEVICE_ID}
- disconnect_warmup_sec: ${DISCONNECT_WARMUP_SEC}
- disconnect_hold_sec: ${DISCONNECT_HOLD_SEC}
- disconnect_post_recovery_sec: ${DISCONNECT_POST_RECOVERY_SEC}
- fault_inject_disconnect_after_sec: ${FAULT_INJECT_DISCONNECT_AFTER_SEC}
- preview_window_requested: ${PREVIEW_WINDOW}
- disconnect_trigger_status: ${TRIGGER_STATUS}
- disconnect_evidence_status: ${EVIDENCE_STATUS}
EOF

if [[ -f "${RUNTIME_LOG}" ]]; then
  {
    echo "disconnect_runtime_excerpt_begin"
    grep -nE 'INPUT_DISCONNECTED|FAULT_INJECTED_DISCONNECT|No such device|device disconnected|capture failed|read failed|VIDIOC_DQBUF|BACKEND_RUNTIME_FAILED|Could not initialize cudnn|Engine deserialization failed' "${RUNTIME_LOG}" || true
    echo "disconnect_runtime_excerpt_end"
  } | tee -a "${AUTOMATION_LOG}"
fi

log_note "automation_done pipeline_exit=${PIPELINE_EXIT} trigger_status=${TRIGGER_STATUS} evidence_status=${EVIDENCE_STATUS}"
echo "run_id=${RUN_ID}"
echo "runtime_log=${RUNTIME_LOG}"
echo "automation_log=${AUTOMATION_LOG}"
echo "preview_window_requested=${PREVIEW_WINDOW}"
echo "disconnect_method=${DISCONNECT_METHOD}"
echo "disconnect_trigger_status=${TRIGGER_STATUS}"
echo "disconnect_evidence_status=${EVIDENCE_STATUS}"
echo "pipeline_exit=${PIPELINE_EXIT}"

exit "${PIPELINE_EXIT}"

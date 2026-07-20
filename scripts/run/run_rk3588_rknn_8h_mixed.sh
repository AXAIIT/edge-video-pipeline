#!/usr/bin/env bash
set -euo pipefail

RUN_GROUP_ID="${RUN_GROUP_ID:-$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h}"
VIDEO_RUN_ID="${VIDEO_RUN_ID:-${RUN_GROUP_ID}_video4h}"
CAMERA_RUN_ID="${CAMERA_RUN_ID:-${RUN_GROUP_ID}_astra4h}"
VIDEO_DURATION_SEC="${VIDEO_DURATION_SEC:-14400}"
CAMERA_DURATION_SEC="${CAMERA_DURATION_SEC:-14400}"
INFERENCE_WORKERS="${INFERENCE_WORKERS:-3}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PREVIEW_WINDOW_CAMERA="${PREVIEW_WINDOW_CAMERA:-auto}"
PREVIEW_WINDOW_VIDEO="${PREVIEW_WINDOW_VIDEO:-off}"
TRACE_FAIL_ON_GAPS_VIDEO="${TRACE_FAIL_ON_GAPS_VIDEO:-0}"

GROUP_DIR="projects/03_video_pipeline/runs/${RUN_GROUP_ID}"
mkdir -p "${GROUP_DIR}"

write_group_run_md() {
  local status="$1"
  local camera_exit="${2:-pending}"
  local video_exit="${3:-pending}"
  cat > "${GROUP_DIR}/run.md" <<EOF
# ${RUN_GROUP_ID}

\`\`\`yaml
run_group_id: ${RUN_GROUP_ID}
stage: rk3588_rknn_8h_mixed
status: ${status}
plan:
  - run_id: ${CAMERA_RUN_ID}
    input_source_id: astra_s_openni_001
    input_source_type: openni_camera
    duration_sec: ${CAMERA_DURATION_SEC}
  - run_id: ${VIDEO_RUN_ID}
    input_source_id: video_set_stability_v1
    input_source_type: video_playlist
    duration_sec: ${VIDEO_DURATION_SEC}
results:
  camera_exit: ${camera_exit}
  video_exit: ${video_exit}
  preview_window_camera: ${PREVIEW_WINDOW_CAMERA}
  preview_window_video: ${PREVIEW_WINDOW_VIDEO}
  trace_fail_on_gaps_video: ${TRACE_FAIL_ON_GAPS_VIDEO}
\`\`\`
EOF
}

write_group_run_md "running"

set +e
RUN_ID="${CAMERA_RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID_CAMERA:-astra_s_openni_001}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE_CAMERA:-openni_camera}" \
INPUT_PATH="${INPUT_PATH_CAMERA:-2bc5/0402}" \
DURATION_SEC="${CAMERA_DURATION_SEC}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW_CAMERA}" \
PYTHON_BIN="${PYTHON_BIN}" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
CAMERA_EXIT=$?

RUN_ID="${VIDEO_RUN_ID}" \
TIER="long_sustained" \
DURATION_SEC="${VIDEO_DURATION_SEC}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS_VIDEO}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW_VIDEO}" \
PYTHON_BIN="${PYTHON_BIN}" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh
VIDEO_EXIT=$?
set -e

GROUP_STATUS="pass"
if [[ "${CAMERA_EXIT}" -ne 0 || "${VIDEO_EXIT}" -ne 0 ]]; then
  GROUP_STATUS="fail"
fi

write_group_run_md "${GROUP_STATUS}" "${CAMERA_EXIT}" "${VIDEO_EXIT}"

cat >> "${GROUP_DIR}/run.md" <<EOF

## 完成

- camera_run_id: ${CAMERA_RUN_ID}
- video_run_id: ${VIDEO_RUN_ID}
- camera_exit: ${CAMERA_EXIT}
- video_exit: ${VIDEO_EXIT}
- status: ${GROUP_STATUS}
EOF

echo "run_group_id=${RUN_GROUP_ID}"
echo "video_run_id=${VIDEO_RUN_ID}"
echo "camera_run_id=${CAMERA_RUN_ID}"
echo "group_run_md=${GROUP_DIR}/run.md"

if [[ "${CAMERA_EXIT}" -ne 0 ]]; then
  exit "${CAMERA_EXIT}"
fi
exit "${VIDEO_EXIT}"

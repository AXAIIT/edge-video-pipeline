#!/usr/bin/env bash
set -euo pipefail

RUN_GROUP_ID="${RUN_GROUP_ID:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_8h_video4h_imx2194h}"
VIDEO_RUN_ID="${VIDEO_RUN_ID:-${RUN_GROUP_ID}_video4h}"
CAMERA_RUN_ID="${CAMERA_RUN_ID:-${RUN_GROUP_ID}_imx2194h}"
VIDEO_DURATION_SEC="${VIDEO_DURATION_SEC:-14400}"
CAMERA_DURATION_SEC="${CAMERA_DURATION_SEC:-14400}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
PREVIEW_WINDOW_VIDEO="${PREVIEW_WINDOW_VIDEO:-off}"
PREVIEW_WINDOW_CAMERA="${PREVIEW_WINDOW_CAMERA:-off}"

GROUP_DIR="projects/03_video_pipeline/runs/${RUN_GROUP_ID}"
mkdir -p "${GROUP_DIR}"

cat > "${GROUP_DIR}/run.md" <<EOF
# ${RUN_GROUP_ID}

\`\`\`yaml
run_group_id: ${RUN_GROUP_ID}
stage: jetson_tensorrt_8h_mixed
status: running
plan:
  - run_id: ${VIDEO_RUN_ID}
    input_source_id: video_set_stability_v1
    input_source_type: video_playlist
    duration_sec: ${VIDEO_DURATION_SEC}
  - run_id: ${CAMERA_RUN_ID}
    input_source_id: imx219_csi_001
    input_source_type: mipi_camera
    duration_sec: ${CAMERA_DURATION_SEC}
\`\`\`
EOF

RUN_ID="${VIDEO_RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID_VIDEO:-video_set_stability_v1}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE_VIDEO:-video_playlist}" \
INPUT_PATH="${INPUT_PATH_VIDEO:-data/videos/stability_playlist_v1.txt}" \
DURATION_SEC="${VIDEO_DURATION_SEC}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW_VIDEO}" \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh

RUN_ID="${CAMERA_RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID_CAMERA:-imx219_csi_001}" \
INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE_CAMERA:-mipi_camera}" \
INPUT_PATH="${INPUT_PATH_CAMERA:-/dev/video0}" \
DURATION_SEC="${CAMERA_DURATION_SEC}" \
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${PREVIEW_WINDOW_CAMERA}" \
V4L2_RAW="${V4L2_RAW_CAMERA:-1}" \
V4L2_WIDTH="${V4L2_WIDTH_CAMERA:-1280}" \
V4L2_HEIGHT="${V4L2_HEIGHT_CAMERA:-720}" \
V4L2_SENSOR_MODE="${V4L2_SENSOR_MODE_CAMERA:-5}" \
V4L2_FPS="${V4L2_FPS_CAMERA:-60}" \
BAYER_PATTERN="${BAYER_PATTERN_CAMERA:-RG}" \
V4L2_NORMALIZE_MODE="${V4L2_NORMALIZE_MODE_CAMERA:-fixed_10bit}" \
V4L2_DISABLE_WHITE_BALANCE="${V4L2_DISABLE_WHITE_BALANCE_CAMERA:-1}" \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh

cat >> "${GROUP_DIR}/run.md" <<EOF

## 完成

- video_run_id: ${VIDEO_RUN_ID}
- camera_run_id: ${CAMERA_RUN_ID}
- preview_window_video: ${PREVIEW_WINDOW_VIDEO}
- preview_window_camera: ${PREVIEW_WINDOW_CAMERA}
- status: completed_pending_report_review
EOF

echo "run_group_id=${RUN_GROUP_ID}"
echo "video_run_id=${VIDEO_RUN_ID}"
echo "camera_run_id=${CAMERA_RUN_ID}"
echo "group_run_md=${GROUP_DIR}/run.md"

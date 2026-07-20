#!/usr/bin/env bash
set -euo pipefail

DATE="${DATE:-$(date +%Y%m%d)}"
DURATION_SEC="${DURATION_SEC:-600}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_SCRIPT="projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh"
COMPARE_SCRIPT="projects/03_video_pipeline/scripts/benchmark/compare_jetson_bufferreuse_ab.py"
PROCESSED_DIR="benchmark/processed/03_video_pipeline"

REUSE_RUN_ID="${REUSE_RUN_ID:-${DATE}_jetson_8gb_yolo11n_tensorrt_bufferreuse_on_ab${DURATION_SEC}}"
NOREUSE_RUN_ID="${NOREUSE_RUN_ID:-${DATE}_jetson_8gb_yolo11n_tensorrt_bufferreuse_off_ab${DURATION_SEC}}"
COMPARE_ID="${DATE}_jetson_8gb_yolo11n_tensorrt_bufferreuse_ab${DURATION_SEC}"

COMMON_INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_set_runtime_v1}"
COMMON_INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-video_playlist}"
COMMON_INPUT_PATH="${INPUT_PATH:-data/videos/runtime_playlist_v1.txt}"
COMMON_SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
COMMON_PREVIEW_WINDOW="${PREVIEW_WINDOW:-off}"

set +e
RUN_ID="${REUSE_RUN_ID}" \
PIPELINE_CONFIG="projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml" \
INPUT_SOURCE_ID="${COMMON_INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="${COMMON_INPUT_SOURCE_TYPE}" \
INPUT_PATH="${COMMON_INPUT_PATH}" \
DURATION_SEC="${DURATION_SEC}" \
SAVE_OUTPUT_VIDEO="${COMMON_SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${COMMON_PREVIEW_WINDOW}" \
  bash "${RUN_SCRIPT}"
REUSE_EXIT=$?
set -e
if [[ "${REUSE_EXIT}" -ne 0 ]]; then
  echo "Reuse-on run failed with exit ${REUSE_EXIT}; reuse-off run and comparison were not executed." >&2
  echo "Inspect logs/runtime/03_video_pipeline/jetson_8gb/${REUSE_RUN_ID}.log" >&2
  exit "${REUSE_EXIT}"
fi

set +e
RUN_ID="${NOREUSE_RUN_ID}" \
PIPELINE_CONFIG="projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline_noreuse.yaml" \
INPUT_SOURCE_ID="${COMMON_INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="${COMMON_INPUT_SOURCE_TYPE}" \
INPUT_PATH="${COMMON_INPUT_PATH}" \
DURATION_SEC="${DURATION_SEC}" \
SAVE_OUTPUT_VIDEO="${COMMON_SAVE_OUTPUT_VIDEO}" \
PREVIEW_WINDOW="${COMMON_PREVIEW_WINDOW}" \
  bash "${RUN_SCRIPT}"
NOREUSE_EXIT=$?
set -e
if [[ "${NOREUSE_EXIT}" -ne 0 ]]; then
  echo "Reuse-off run failed with exit ${NOREUSE_EXIT}; comparison was not generated." >&2
  echo "Inspect logs/runtime/03_video_pipeline/jetson_8gb/${NOREUSE_RUN_ID}.log" >&2
  exit "${NOREUSE_EXIT}"
fi

"${PYTHON_BIN}" "${COMPARE_SCRIPT}" \
  --reuse-summary "${PROCESSED_DIR}/${REUSE_RUN_ID}_summary.csv" \
  --noreuse-summary "${PROCESSED_DIR}/${NOREUSE_RUN_ID}_summary.csv" \
  --output-csv "${PROCESSED_DIR}/${COMPARE_ID}.csv" \
  --output-md "${PROCESSED_DIR}/${COMPARE_ID}.md"

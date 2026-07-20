#!/usr/bin/env bash
set -euo pipefail

DATE="${DATE:-$(date +%Y%m%d)}"
DURATION_SEC="${DURATION_SEC:-600}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INFERENCE_WORKERS="${INFERENCE_WORKERS:-3}"
RUN_SCRIPT="projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh"
COMPARE_SCRIPT="projects/03_video_pipeline/scripts/benchmark/compare_rk3588_bufferreuse_ab.py"
PROCESSED_DIR="benchmark/processed/03_video_pipeline"
MONITOR_DIR="logs/monitor/03_video_pipeline/rk3588_8gb"

REUSE_RUN_ID="${REUSE_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_bufferreuse_on_ab${DURATION_SEC}}"
NOREUSE_RUN_ID="${NOREUSE_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_bufferreuse_off_ab${DURATION_SEC}}"
COMPARE_ID="${DATE}_rk3588_8gb_yolo11n_rknn_bufferreuse_ab${DURATION_SEC}"

set +e
RUN_ID="${REUSE_RUN_ID}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
DURATION_SEC="${DURATION_SEC}" \
PIPELINE_CONFIG="projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml" \
  bash "${RUN_SCRIPT}"
REUSE_EXIT=$?
set -e
if [[ "${REUSE_EXIT}" -ne 0 ]]; then
  echo "Reuse-on run failed with exit ${REUSE_EXIT}; reuse-off run and comparison were not executed." >&2
  echo "Inspect logs/runtime/03_video_pipeline/rk3588_8gb/${REUSE_RUN_ID}.log" >&2
  exit "${REUSE_EXIT}"
fi

set +e
RUN_ID="${NOREUSE_RUN_ID}" \
INFERENCE_WORKERS="${INFERENCE_WORKERS}" \
DURATION_SEC="${DURATION_SEC}" \
PIPELINE_CONFIG="projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline_noreuse.yaml" \
  bash "${RUN_SCRIPT}"
NOREUSE_EXIT=$?
set -e
if [[ "${NOREUSE_EXIT}" -ne 0 ]]; then
  echo "Reuse-off run failed with exit ${NOREUSE_EXIT}; comparison was not generated." >&2
  echo "Inspect logs/runtime/03_video_pipeline/rk3588_8gb/${NOREUSE_RUN_ID}.log" >&2
  exit "${NOREUSE_EXIT}"
fi

"${PYTHON_BIN}" "${COMPARE_SCRIPT}" \
  --reuse-summary "${PROCESSED_DIR}/${REUSE_RUN_ID}_summary.csv" \
  --noreuse-summary "${PROCESSED_DIR}/${NOREUSE_RUN_ID}_summary.csv" \
  --reuse-monitor "${MONITOR_DIR}/${REUSE_RUN_ID}_rknpu.log" \
  --noreuse-monitor "${MONITOR_DIR}/${NOREUSE_RUN_ID}_rknpu.log" \
  --output-csv "${PROCESSED_DIR}/${COMPARE_ID}.csv" \
  --output-md "${PROCESSED_DIR}/${COMPARE_ID}.md"

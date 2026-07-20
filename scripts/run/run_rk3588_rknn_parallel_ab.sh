#!/usr/bin/env bash
set -euo pipefail

DATE="${DATE:-$(date +%Y%m%d)}"
DURATION_SEC="${DURATION_SEC:-120}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SINGLE_RUN_ID="${SINGLE_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_1worker_ab${DURATION_SEC}}"
PARALLEL_RUN_ID="${PARALLEL_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_3worker_ab${DURATION_SEC}}"
RUN_SCRIPT="projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh"
COMPARE_SCRIPT="projects/03_video_pipeline/scripts/benchmark/compare_rk3588_parallel_ab.py"
PROCESSED_DIR="benchmark/processed/03_video_pipeline"
MONITOR_DIR="logs/monitor/03_video_pipeline/rk3588_8gb"
COMPARE_ID="${DATE}_rk3588_8gb_yolo11n_rknn_parallel_ab${DURATION_SEC}"

set +e
RUN_ID="${SINGLE_RUN_ID}" RKNN_CORE_MASK=core0 INFERENCE_WORKERS=1 DURATION_SEC="${DURATION_SEC}" \
  bash "${RUN_SCRIPT}"
SINGLE_EXIT=$?
set -e
if [[ "${SINGLE_EXIT}" -ne 0 ]]; then
  echo "Single-worker baseline failed with exit ${SINGLE_EXIT}; three-worker run and comparison were not executed." >&2
  echo "Inspect logs/runtime/03_video_pipeline/rk3588_8gb/${SINGLE_RUN_ID}.log" >&2
  exit "${SINGLE_EXIT}"
fi

set +e
RUN_ID="${PARALLEL_RUN_ID}" INFERENCE_WORKERS=3 DURATION_SEC="${DURATION_SEC}" \
  bash "${RUN_SCRIPT}"
PARALLEL_EXIT=$?
set -e
if [[ "${PARALLEL_EXIT}" -ne 0 ]]; then
  echo "Three-worker run failed with exit ${PARALLEL_EXIT}; comparison was not generated." >&2
  echo "Inspect logs/runtime/03_video_pipeline/rk3588_8gb/${PARALLEL_RUN_ID}.log" >&2
  exit "${PARALLEL_EXIT}"
fi

"${PYTHON_BIN}" "${COMPARE_SCRIPT}" \
  --single-summary "${PROCESSED_DIR}/${SINGLE_RUN_ID}_summary.csv" \
  --parallel-summary "${PROCESSED_DIR}/${PARALLEL_RUN_ID}_summary.csv" \
  --single-monitor "${MONITOR_DIR}/${SINGLE_RUN_ID}_rknpu.log" \
  --parallel-monitor "${MONITOR_DIR}/${PARALLEL_RUN_ID}_rknpu.log" \
  --output-csv "${PROCESSED_DIR}/${COMPARE_ID}.csv" \
  --output-md "${PROCESSED_DIR}/${COMPARE_ID}.md"

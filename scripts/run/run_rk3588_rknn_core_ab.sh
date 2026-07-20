#!/usr/bin/env bash
set -euo pipefail

DATE="${DATE:-$(date +%Y%m%d)}"
DURATION_SEC="${DURATION_SEC:-120}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CORE0_RUN_ID="${CORE0_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_core0_ab${DURATION_SEC}}"
CORE012_RUN_ID="${CORE012_RUN_ID:-${DATE}_rk3588_8gb_yolo11n_rknn_core012_ab${DURATION_SEC}}"
RUN_SCRIPT="projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh"
COMPARE_SCRIPT="projects/03_video_pipeline/scripts/benchmark/compare_rk3588_core_ab.py"
PROCESSED_DIR="benchmark/processed/03_video_pipeline"
MONITOR_DIR="logs/monitor/03_video_pipeline/rk3588_8gb"
COMPARE_ID="${DATE}_rk3588_8gb_yolo11n_rknn_core_ab${DURATION_SEC}"

RUN_ID="${CORE0_RUN_ID}" RKNN_CORE_MASK=core0 INFERENCE_WORKERS=1 DURATION_SEC="${DURATION_SEC}" \
  bash "${RUN_SCRIPT}"

RUN_ID="${CORE012_RUN_ID}" RKNN_CORE_MASK=0_1_2 INFERENCE_WORKERS=1 DURATION_SEC="${DURATION_SEC}" \
  bash "${RUN_SCRIPT}"

"${PYTHON_BIN}" "${COMPARE_SCRIPT}" \
  --core0-summary "${PROCESSED_DIR}/${CORE0_RUN_ID}_summary.csv" \
  --core012-summary "${PROCESSED_DIR}/${CORE012_RUN_ID}_summary.csv" \
  --core0-monitor "${MONITOR_DIR}/${CORE0_RUN_ID}_rknpu.log" \
  --core012-monitor "${MONITOR_DIR}/${CORE012_RUN_ID}_rknpu.log" \
  --output-csv "${PROCESSED_DIR}/${COMPARE_ID}.csv" \
  --output-md "${PROCESSED_DIR}/${COMPARE_ID}.md"

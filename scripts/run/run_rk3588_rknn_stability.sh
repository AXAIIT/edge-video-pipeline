#!/usr/bin/env bash
set -euo pipefail

TIER="${TIER:-short_sustained}"
case "${TIER}" in
  smoke)
    DURATION_SEC="${DURATION_SEC:-600}"
    ;;
  short_sustained)
    DURATION_SEC="${DURATION_SEC:-1800}"
    ;;
  acceptance_sustained)
    DURATION_SEC="${DURATION_SEC:-7200}"
    ;;
  long_sustained)
    DURATION_SEC="${DURATION_SEC:-28800}"
    ;;
  *)
    echo "Unknown stability tier: ${TIER}" >&2
    exit 2
    ;;
esac

export RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_stability_${TIER}}"
export INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_set_stability_v1}"
export INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-video_playlist}"
export INPUT_PATH="${INPUT_PATH:-data/videos/stability_playlist_v1.txt}"
export PACE_VIDEO_FILE="${PACE_VIDEO_FILE:-1}"
export SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
export PREVIEW_WINDOW="${PREVIEW_WINDOW:-off}"
export TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-0}"
export DURATION_SEC

set +e
bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
PIPELINE_EXIT=$?
set -e

PYTHON_BIN="${PYTHON_BIN:-python3}"
RAW_PATH="benchmark/raw/03_video_pipeline/rk3588_8gb/${RUN_ID}.jsonl"
MONITOR_LOG="logs/monitor/03_video_pipeline/rk3588_8gb/${RUN_ID}_rknpu.log"
STABILITY_SUMMARY="benchmark/processed/03_video_pipeline/${RUN_ID}_stability.csv"

STABILITY_AGGREGATE_EXIT=0
if [[ -s "${RAW_PATH}" ]]; then
  set +e
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_stability.py \
    --raw "${RAW_PATH}" \
    --monitor "${MONITOR_LOG}" \
    --output "${STABILITY_SUMMARY}"
  STABILITY_AGGREGATE_EXIT=$?
  set -e
else
  echo "Stability raw result missing or empty: ${RAW_PATH}" >&2
  STABILITY_AGGREGATE_EXIT=2
fi

echo "stability_summary=${STABILITY_SUMMARY}"
echo "stability_aggregate_exit=${STABILITY_AGGREGATE_EXIT}"
if [[ "${PIPELINE_EXIT}" -ne 0 ]]; then
  exit "${PIPELINE_EXIT}"
fi
exit "${STABILITY_AGGREGATE_EXIT}"

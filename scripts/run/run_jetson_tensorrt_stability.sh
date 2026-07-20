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

export RUN_ID="${RUN_ID:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_stability_${TIER}}"
export INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_set_stability_v1}"
export INPUT_SOURCE_TYPE="${INPUT_SOURCE_TYPE:-video_playlist}"
export INPUT_PATH="${INPUT_PATH:-data/videos/stability_playlist_v1.txt}"
export PACE_VIDEO_FILE="${PACE_VIDEO_FILE:-1}"
export SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
export PREVIEW_WINDOW="${PREVIEW_WINDOW:-off}"
export DURATION_SEC

bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh

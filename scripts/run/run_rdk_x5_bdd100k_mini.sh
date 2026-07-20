#!/usr/bin/env bash
set -euo pipefail

export TARGET_RESULT_DIR="${TARGET_RESULT_DIR:-rdk_x5_8gb}"
export PIPELINE_SCRIPT="${PIPELINE_SCRIPT:-projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh}"
export PIPELINE_CONFIG="${PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_bdd100k_quality.yaml}"
export RUN_PREFIX="${RUN_PREFIX:-$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini}"
export SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
export TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-1}"
export PREVIEW_WINDOW="${PREVIEW_WINDOW:-off}"
export INFERENCE_WORKERS="${INFERENCE_WORKERS:-2}"
export POSTPROCESS_WORKERS="${POSTPROCESS_WORKERS:-2}"
export PACE_VIDEO_FILE="${PACE_VIDEO_FILE:-0}"
export INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION:-auto}"

bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh

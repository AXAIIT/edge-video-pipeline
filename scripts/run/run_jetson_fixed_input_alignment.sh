#!/usr/bin/env bash
set -euo pipefail

if [[ "${ALLOW_HISTORICAL_VIDEO_SHORT_DIAGNOSTIC:-0}" != "1" ]]; then
  echo "Deprecated historical unlabeled diagnostic only; current and formal runs must use bdd100k_mot_mini_v1." >&2
  echo "Set ALLOW_HISTORICAL_VIDEO_SHORT_DIAGNOSTIC=1 only to reproduce an existing issue record." >&2
  exit 2
fi

RUN_PREFIX="${RUN_PREFIX:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_fixed_input_alignment}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENVIRONMENT_BASELINE_ID_VALUE="${ENVIRONMENT_BASELINE_ID:-pending_project3_jetson_env_baseline}"

MANIFEST="${MANIFEST:-data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json}"
VIDEO_PATH="${VIDEO_PATH:-data/videos/video_fixed_v1/video_short_001.avi}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_short_001}"

PROJECT2_ENGINE="${PROJECT2_ENGINE:-models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine}"
P1_PREPROCESS_CONFIG="${P1_PREPROCESS_CONFIG:-projects/01_vision_deploy/configs/preprocess/yolo11n_640.yaml}"
P1_POSTPROCESS_CONFIG="${P1_POSTPROCESS_CONFIG:-projects/01_vision_deploy/configs/postprocess/yolo11n_nms.yaml}"
P1_BOARD_CONFIG="${P1_BOARD_CONFIG:-projects/01_vision_deploy/configs/boards/jetson_tensorrt.yaml}"
P1_MODEL_CONFIG="${P1_MODEL_CONFIG:-projects/01_vision_deploy/configs/models/yolo11n.yaml}"

P3_PIPELINE_CONFIG="${P3_PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_fixed_input_alignment.yaml}"
P3_MODEL_CONFIG="${P3_MODEL_CONFIG:-projects/03_video_pipeline/configs/models/yolo11n.yaml}"
P3_BOARD_CONFIG="${P3_BOARD_CONFIG:-projects/03_video_pipeline/configs/boards/jetson_8gb.yaml}"

ALIGN_IOU_MIN="${ALIGN_IOU_MIN:-0.50}"
ALIGN_CONFIDENCE_MIN="${ALIGN_CONFIDENCE_MIN:-0.25}"
ALIGN_CLASS_MATCH_RATE_MIN="${ALIGN_CLASS_MATCH_RATE_MIN:-0.98}"
ALIGN_MEAN_IOU_MIN="${ALIGN_MEAN_IOU_MIN:-0.90}"

FRAME_DIR="data/validation/video_fixed_v1_alignment/frames/${RUN_PREFIX}"
BASELINE_PROJECT2_RUN_ID="${RUN_PREFIX}_project2_int8_baseline"
BASELINE_PROJECT2_RAW="benchmark/raw/02_quantization/jetson_8gb/${BASELINE_PROJECT2_RUN_ID}.jsonl"
BASELINE_PROJECT2_DECODED_DIR="benchmark/raw/02_quantization/jetson_8gb/decoded/${BASELINE_PROJECT2_RUN_ID}"
BASELINE_NORMALIZED_RAW="benchmark/raw/03_video_pipeline/jetson_8gb/${RUN_PREFIX}_project2_int8_baseline_video_short_001.jsonl"

CURRENT_RUN_ID="${RUN_PREFIX}_project3_current"
CURRENT_RAW="benchmark/raw/03_video_pipeline/jetson_8gb/${CURRENT_RUN_ID}.jsonl"
ALIGNMENT_MD="benchmark/processed/03_video_pipeline/${RUN_PREFIX}_fixed_input_alignment.md"
ALIGNMENT_CSV="benchmark/processed/03_video_pipeline/${RUN_PREFIX}_fixed_input_alignment.csv"

mkdir -p \
  "${FRAME_DIR}" \
  "benchmark/raw/02_quantization/jetson_8gb/decoded" \
  "benchmark/raw/03_video_pipeline/jetson_8gb" \
  "benchmark/processed/03_video_pipeline"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
  exit 2
fi

echo "[1/4] extract fixed alignment frames"
"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/extract_video_alignment_frames.py \
  --manifest "${MANIFEST}" \
  --output-dir "${FRAME_DIR}"

echo "[2/4] generate project2 TensorRT INT8 baseline on extracted frames"
"${PYTHON_BIN}" projects/01_vision_deploy/scripts/benchmark/benchmark_tensorrt.py \
  --engine "${PROJECT2_ENGINE}" \
  --input-set "${FRAME_DIR}" \
  --preprocess-config "${P1_PREPROCESS_CONFIG}" \
  --postprocess-config "${P1_POSTPROCESS_CONFIG}" \
  --board-config "${P1_BOARD_CONFIG}" \
  --model-config "${P1_MODEL_CONFIG}" \
  --warmup 0 \
  --repeat 1 \
  --max-images 0 \
  --decoded-output-dir "${BASELINE_PROJECT2_DECODED_DIR}" \
  --output "${BASELINE_PROJECT2_RAW}" \
  --env-baseline-id "${ENVIRONMENT_BASELINE_ID_VALUE}" \
  --save-decoded-first-only

"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/convert_project1_alignment_to_video_raw.py \
  --project1-raw "${BASELINE_PROJECT2_RAW}" \
  --manifest "${MANIFEST}" \
  --output "${BASELINE_NORMALIZED_RAW}"

echo "[3/4] run project3 current pipeline on full fixed video once"
RUN_ID="${CURRENT_RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="video_file" \
INPUT_PATH="${VIDEO_PATH}" \
DURATION_SEC=0 \
LOOP_VIDEO_FILE=0 \
SAVE_OUTPUT_VIDEO=0 \
TRACE_FAIL_ON_GAPS=1 \
PIPELINE_CONFIG="${P3_PIPELINE_CONFIG}" \
MODEL_CONFIG="${P3_MODEL_CONFIG}" \
BOARD_CONFIG="${P3_BOARD_CONFIG}" \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh

echo "[4/4] compare baseline/current detections on manifest frames"
"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/compare_detection_alignment.py \
  --baseline "${BASELINE_NORMALIZED_RAW}" \
  --current "${CURRENT_RAW}" \
  --manifest "${MANIFEST}" \
  --output-md "${ALIGNMENT_MD}" \
  --output-csv "${ALIGNMENT_CSV}" \
  --iou-min "${ALIGN_IOU_MIN}" \
  --confidence-min "${ALIGN_CONFIDENCE_MIN}" \
  --class-match-rate-min "${ALIGN_CLASS_MATCH_RATE_MIN}" \
  --mean-iou-min "${ALIGN_MEAN_IOU_MIN}"

echo "run_prefix=${RUN_PREFIX}"
echo "baseline_project2_int8_raw=${BASELINE_PROJECT2_RAW}"
echo "baseline_normalized_raw=${BASELINE_NORMALIZED_RAW}"
echo "current_project3_raw=${CURRENT_RAW}"
echo "alignment_report=${ALIGNMENT_MD}"
echo "alignment_details=${ALIGNMENT_CSV}"

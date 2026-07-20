#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

RUN_PREFIX="${RUN_PREFIX:-$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_fixed_input_alignment}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENVIRONMENT_BASELINE_ID_VALUE="${ENVIRONMENT_BASELINE_ID:-20260612_rdk_x5_8gb_env_baseline}"

MANIFEST="${MANIFEST:-data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json}"
VIDEO_PATH="${VIDEO_PATH:-data/videos/video_fixed_v1/video_short_001.avi}"
INPUT_SOURCE_ID="${INPUT_SOURCE_ID:-video_short_001}"

PROJECT2_MODEL="${PROJECT2_MODEL:-models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin}"
PROJECT2_MODEL_SHA256="${PROJECT2_MODEL_SHA256:-2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c}"
PROJECT2_SCRIPT="${PROJECT2_SCRIPT:-projects/02_quantization/scripts/benchmark/07_run_rdkx5_split_head_python_runtime_predictions.py}"

P3_PIPELINE_CONFIG="${P3_PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_fixed_input_alignment.yaml}"
P3_MODEL_CONFIG="${P3_MODEL_CONFIG:-projects/03_video_pipeline/configs/models/yolo11n.yaml}"
P3_BOARD_CONFIG="${P3_BOARD_CONFIG:-projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml}"
P3_STREAM_CONFIG="${P3_STREAM_CONFIG:-projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml}"

ALIGN_IOU_MIN="${ALIGN_IOU_MIN:-0.50}"
ALIGN_CONFIDENCE_MIN="${ALIGN_CONFIDENCE_MIN:-0.25}"
ALIGN_CLASS_MATCH_RATE_MIN="${ALIGN_CLASS_MATCH_RATE_MIN:-0.98}"
ALIGN_MEAN_IOU_MIN="${ALIGN_MEAN_IOU_MIN:-0.90}"

FRAME_DIR="data/validation/video_fixed_v1_alignment/frames/${RUN_PREFIX}"
BASELINE_PROJECT2_RUN_ID="${RUN_PREFIX}_project2_int8_baseline"
BASELINE_PROJECT2_PREDICTIONS="benchmark/raw/02_quantization/rdk_x5_8gb/${BASELINE_PROJECT2_RUN_ID}_predictions.json"
BASELINE_PROJECT2_INDEX="benchmark/raw/02_quantization/rdk_x5_8gb/${BASELINE_PROJECT2_RUN_ID}_stream_index.jsonl"
BASELINE_PROJECT2_SUMMARY="benchmark/raw/02_quantization/rdk_x5_8gb/${BASELINE_PROJECT2_RUN_ID}_runtime_summary.json"
BASELINE_PROJECT2_DECODED_DIR="benchmark/raw/02_quantization/rdk_x5_8gb/decoded/${BASELINE_PROJECT2_RUN_ID}"
BASELINE_NORMALIZED_RAW="benchmark/raw/03_video_pipeline/rdk_x5_8gb/${RUN_PREFIX}_project2_int8_baseline_video_short_001.jsonl"

CURRENT_RUN_ID="${RUN_PREFIX}_project3_current"
CURRENT_RAW="benchmark/raw/03_video_pipeline/rdk_x5_8gb/${CURRENT_RUN_ID}.jsonl"
CURRENT_SUMMARY="benchmark/processed/03_video_pipeline/${CURRENT_RUN_ID}_summary.csv"
ALIGNMENT_MD="benchmark/processed/03_video_pipeline/${RUN_PREFIX}_fixed_input_alignment.md"
ALIGNMENT_CSV="benchmark/processed/03_video_pipeline/${RUN_PREFIX}_fixed_input_alignment.csv"

mkdir -p \
  "${FRAME_DIR}" \
  "benchmark/raw/02_quantization/rdk_x5_8gb/decoded" \
  "benchmark/raw/03_video_pipeline/rdk_x5_8gb" \
  "benchmark/processed/03_video_pipeline"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
  exit 2
fi

echo "[1/4] extract fixed alignment frames"
"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/extract_video_alignment_frames.py \
  --manifest "${MANIFEST}" \
  --output-dir "${FRAME_DIR}"

echo "[2/4] generate project2 RDK X5 Python baseline on extracted frames"
"${PYTHON_BIN}" "${PROJECT2_SCRIPT}" \
  --run-id "${BASELINE_PROJECT2_RUN_ID}" \
  --model "${PROJECT2_MODEL}" \
  --backend-artifact-sha256 "${PROJECT2_MODEL_SHA256}" \
  --annotations "" \
  --image-root "${FRAME_DIR}" \
  --output-predictions-json "${BASELINE_PROJECT2_PREDICTIONS}" \
  --output-index-jsonl "${BASELINE_PROJECT2_INDEX}" \
  --output-summary-json "${BASELINE_PROJECT2_SUMMARY}" \
  --decoded-output-dir "${BASELINE_PROJECT2_DECODED_DIR}" \
  --max-images 0 \
  --warmup 0 \
  --resize-mode letterbox \
  --allow-missing-annotations

"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/convert_project2_alignment_to_video_raw.py \
  --project2-index "${BASELINE_PROJECT2_INDEX}" \
  --manifest "${MANIFEST}" \
  --output "${BASELINE_NORMALIZED_RAW}"

echo "[3/4] run project3 current pipeline on full fixed video once"
set +e
RUN_ID="${CURRENT_RUN_ID}" \
INPUT_SOURCE_ID="${INPUT_SOURCE_ID}" \
INPUT_SOURCE_TYPE="video_file" \
INPUT_PATH="${VIDEO_PATH}" \
DURATION_SEC=0 \
LOOP_VIDEO_FILE=0 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=off \
TRACE_FAIL_ON_GAPS=1 \
PIPELINE_CONFIG="${P3_PIPELINE_CONFIG}" \
MODEL_CONFIG="${P3_MODEL_CONFIG}" \
BOARD_CONFIG="${P3_BOARD_CONFIG}" \
STREAM_CONFIG="${P3_STREAM_CONFIG}" \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
PIPELINE_EXIT=$?
set -e

if [[ "${PIPELINE_EXIT}" -ne 0 && "${PIPELINE_EXIT}" -ne 3 ]]; then
  echo "Project3 pipeline failed before alignment compare: exit=${PIPELINE_EXIT}" >&2
  exit "${PIPELINE_EXIT}"
fi

if [[ ! -f "${CURRENT_RAW}" ]]; then
  echo "Current project3 raw not found: ${CURRENT_RAW}" >&2
  exit 2
fi

echo "[4/4] compare baseline/current detections on manifest frames"
"${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/compare_detection_alignment.py \
  --baseline "${BASELINE_NORMALIZED_RAW}" \
  --current "${CURRENT_RAW}" \
  --manifest "${MANIFEST}" \
  --pipeline-summary "${CURRENT_SUMMARY}" \
  --output-md "${ALIGNMENT_MD}" \
  --output-csv "${ALIGNMENT_CSV}" \
  --iou-min "${ALIGN_IOU_MIN}" \
  --confidence-min "${ALIGN_CONFIDENCE_MIN}" \
  --class-match-rate-min "${ALIGN_CLASS_MATCH_RATE_MIN}" \
  --mean-iou-min "${ALIGN_MEAN_IOU_MIN}"

echo "run_prefix=${RUN_PREFIX}"
echo "environment_baseline_id=${ENVIRONMENT_BASELINE_ID_VALUE}"
echo "baseline_project2_index=${BASELINE_PROJECT2_INDEX}"
echo "baseline_normalized_raw=${BASELINE_NORMALIZED_RAW}"
echo "current_project3_raw=${CURRENT_RAW}"
echo "alignment_report=${ALIGNMENT_MD}"
echo "alignment_details=${ALIGNMENT_CSV}"

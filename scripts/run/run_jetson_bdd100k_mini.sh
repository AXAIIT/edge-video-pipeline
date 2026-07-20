#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
MANIFEST="${MANIFEST:-data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json}"
PIPELINE_SCRIPT="${PIPELINE_SCRIPT:-projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh}"
STREAM_CONFIG="${STREAM_CONFIG:-projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml}"
PIPELINE_CONFIG="${PIPELINE_CONFIG:-projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml}"
MODEL_CONFIG="${MODEL_CONFIG:-projects/03_video_pipeline/configs/models/yolo11n.yaml}"
RUN_PREFIX="${RUN_PREFIX:-$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bdd100k_mini}"
TARGET_RESULT_DIR="${TARGET_RESULT_DIR:-jetson_8gb}"

START_INDEX="${START_INDEX:-0}"
LIMIT="${LIMIT:-0}"
CONTINUE_ON_ERROR="${CONTINUE_ON_ERROR:-1}"
EVALUATE="${EVALUATE:-1}"
EVALUATE_STRICT="${EVALUATE_STRICT:-0}"

# For sparse labeled video quality, read each video once and stop at EOF.
DURATION_SEC="${DURATION_SEC:-0}"
LOOP_VIDEO_FILE="${LOOP_VIDEO_FILE:-0}"
SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO:-0}"
TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS:-1}"

CLASS_IDS="${CLASS_IDS:-0,1,2,3,5,6,7}"
CONFIDENCE_MIN="${CONFIDENCE_MIN:-0.25}"
IOU_MIN="${IOU_MIN:-0.50}"
OVERALL_AP50_MIN="${OVERALL_AP50_MIN:-0.25}"
OVERALL_RECALL_MIN="${OVERALL_RECALL_MIN:-0.50}"
EXPECTED_INPUT_WIDTH="${EXPECTED_INPUT_WIDTH:-1280}"
EXPECTED_INPUT_HEIGHT="${EXPECTED_INPUT_HEIGHT:-720}"
INPUT_ORIENTATION_CORRECTION="${INPUT_ORIENTATION_CORRECTION:-auto}"
MOV_ORIENTATION_DETECTOR="${MOV_ORIENTATION_DETECTOR:-projects/03_video_pipeline/scripts/quality/detect_mov_orientation.py}"
BATCH_SUMMARY="${BATCH_SUMMARY:-benchmark/processed/03_video_pipeline/${RUN_PREFIX}_batch.csv}"
BATCH_QUALITY_CSV="${BATCH_QUALITY_CSV:-benchmark/processed/03_video_pipeline/${RUN_PREFIX}_bdd100k_mot_quality_aggregate.csv}"
BATCH_QUALITY_DETAIL_CSV="${BATCH_QUALITY_DETAIL_CSV:-benchmark/processed/03_video_pipeline/${RUN_PREFIX}_bdd100k_mot_quality_per_sequence.csv}"
BATCH_QUALITY_MD="${BATCH_QUALITY_MD:-benchmark/processed/03_video_pipeline/${RUN_PREFIX}_bdd100k_mot_quality_aggregate.md}"

if [[ "${PYTHON_BIN}" == */* ]]; then
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "PYTHON_BIN not found or not executable: ${PYTHON_BIN}" >&2
    echo 'Expected examples: PYTHON_BIN=python3 or PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python"' >&2
    exit 2
  fi
else
  resolved_python_bin="$(command -v "${PYTHON_BIN}" || true)"
  if [[ -z "${resolved_python_bin}" ]]; then
    echo "PYTHON_BIN not found in PATH: ${PYTHON_BIN}" >&2
    echo 'Expected examples: PYTHON_BIN=python3 or PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python"' >&2
    exit 2
  fi
  PYTHON_BIN="${resolved_python_bin}"
fi

if [[ ! -f "${MANIFEST}" ]]; then
  echo "Manifest not found: ${MANIFEST}" >&2
  exit 2
fi

if [[ ! -f "${PIPELINE_SCRIPT}" ]]; then
  echo "Pipeline script not found: ${PIPELINE_SCRIPT}" >&2
  exit 2
fi

revalidate_postcheck_failure() {
  local raw_path="$1"
  local schema_check_path="$2"
  local trace_check_path="$3"
  local runtime_summary_path="$4"
  local monitor_log_path="$5"

  if [[ ! -f "${raw_path}" ]]; then
    return 1
  fi

  local schema_exit=0
  local trace_exit=0
  local aggregate_exit=0

  set +e
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/validate_pipeline_raw_schema.py \
    --input "${raw_path}" \
    --schema benchmark/schemas/video_pipeline_raw_schema.yaml \
    --output "${schema_check_path}"
  schema_exit=$?

  local trace_args=(--raw "${raw_path}" --output "${trace_check_path}")
  if [[ "${TRACE_FAIL_ON_GAPS}" == "1" ]]; then
    trace_args+=(--fail-on-gaps)
  fi
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/check_pipeline_trace.py "${trace_args[@]}"
  trace_exit=$?

  if [[ -f "${monitor_log_path}" ]]; then
    "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_pipeline_benchmark.py \
      --input "${raw_path}" \
      --monitor "${monitor_log_path}" \
      --output "${runtime_summary_path}"
    aggregate_exit=$?
  else
    "${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_pipeline_benchmark.py \
      --input "${raw_path}" \
      --output "${runtime_summary_path}"
    aggregate_exit=$?
  fi
  set -e

  if [[ "${schema_exit}" -eq 0 && "${trace_exit}" -eq 0 && "${aggregate_exit}" -eq 0 ]]; then
    return 0
  fi
  return 1
}

mkdir -p "$(dirname "${BATCH_SUMMARY}")"
printf "run_index,sequence_id,run_id,input_source_id,video_path,video_sha256,label_path,label_sha256,labeled_frame_count,input_orientation_requested,input_orientation_effective,raw_path,runtime_summary_path,quality_md,quality_csv,quality_summary_csv,overall_ap50_weighted,overall_precision,overall_recall,overall_f1,labeled_frame_coverage,pipeline_exit,evaluate_exit,evaluate_status,status,pipeline_config,model_config,confidence_min,overall_ap50_min,overall_recall_min\n" > "${BATCH_SUMMARY}"

mapfile -t sequence_rows < <(
  "${PYTHON_BIN}" - "${MANIFEST}" "${START_INDEX}" "${LIMIT}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
start = int(sys.argv[2])
limit = int(sys.argv[3])
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
sequences = manifest.get("sequences", [])
if start < 0:
    raise SystemExit("START_INDEX must be >= 0")
end = None if limit <= 0 else start + limit
for index, seq in enumerate(sequences[start:end], start=start):
    sequence_id = seq["sequence_id"]
    input_source_id = seq.get("input_source_id", f"bdd100k_mot_mini_v1_{sequence_id}")
    video_path = seq["video_path"]
    video_sha256 = seq.get("video_sha256", "")
    label_path = seq["label_path"]
    label_sha256 = seq.get("label_sha256", "")
    labeled_frame_count = seq.get("labeled_frame_count", "")
    print("\t".join([
        str(index),
        sequence_id,
        input_source_id,
        video_path,
        video_sha256,
        label_path,
        label_sha256,
        str(labeled_frame_count),
    ]))
PY
)

if [[ "${#sequence_rows[@]}" -eq 0 ]]; then
  echo "No sequence selected from ${MANIFEST}" >&2
  exit 2
fi

pipeline_failures=0
quality_failures=0
strict_failures=0
for row in "${sequence_rows[@]}"; do
  IFS=$'\t' read -r run_index sequence_id input_source_id video_path video_sha256 label_path label_sha256 labeled_frame_count <<< "${row}"
  run_id="${RUN_PREFIX}_${sequence_id}"
  raw_path="benchmark/raw/03_video_pipeline/${TARGET_RESULT_DIR}/${run_id}.jsonl"
  runtime_summary_path="benchmark/processed/03_video_pipeline/${run_id}_summary.csv"
  schema_check_path="benchmark/processed/03_video_pipeline/${run_id}_schema_check.md"
  trace_check_path="benchmark/processed/03_video_pipeline/${run_id}_trace_check.md"
  quality_md="benchmark/processed/03_video_pipeline/${run_id}_bdd100k_mot_quality.md"
  quality_csv="benchmark/processed/03_video_pipeline/${run_id}_bdd100k_mot_quality.csv"
  quality_summary_csv="benchmark/processed/03_video_pipeline/${run_id}_bdd100k_mot_quality_summary.csv"
  monitor_log_path=""
  for candidate in \
    "logs/monitor/03_video_pipeline/${TARGET_RESULT_DIR}/${run_id}_tegrastats.log" \
    "logs/monitor/03_video_pipeline/${TARGET_RESULT_DIR}/${run_id}_rknn.log" \
    "logs/monitor/03_video_pipeline/${TARGET_RESULT_DIR}/${run_id}_bpu.log"; do
    if [[ -f "${candidate}" ]]; then
      monitor_log_path="${candidate}"
      break
    fi
  done
  overall_ap50_weighted=""
  overall_precision=""
  overall_recall=""
  overall_f1=""
  labeled_frame_coverage=""
  pipeline_exit=0
  evaluate_exit=""
  evaluate_status="not_run"
  status="pass"
  effective_orientation_correction="${INPUT_ORIENTATION_CORRECTION}"

  echo "[${run_index}] run_id=${run_id}"
  echo "  video=${video_path}"
  echo "  labels=${label_path}"

  if [[ ! -f "${video_path}" ]]; then
    echo "Video not found: ${video_path}" >&2
    pipeline_exit=2
    status="missing_video"
  elif [[ ! -f "${label_path}" ]]; then
    echo "Labels not found: ${label_path}" >&2
    pipeline_exit=2
    status="missing_labels"
  else
    if [[ "${INPUT_ORIENTATION_CORRECTION}" == "container" ]]; then
      set +e
      effective_orientation_correction="$(
        "${PYTHON_BIN}" "${MOV_ORIENTATION_DETECTOR}" --video "${video_path}"
      )"
      orientation_exit=$?
      set -e
      if [[ "${orientation_exit}" -ne 0 ]]; then
        echo "Failed to resolve MOV orientation: ${video_path}" >&2
        pipeline_exit=32
        status="input_orientation_detection_failed"
      else
        echo "input_orientation_requested=container input_orientation_effective=${effective_orientation_correction}"
      fi
    fi

    if [[ "${pipeline_exit}" -ne 0 ]]; then
      :
    else
    set +e
    RUN_ID="${run_id}" \
    PYTHON_BIN="${PYTHON_BIN}" \
    INPUT_SOURCE_ID="${input_source_id}" \
    INPUT_SOURCE_TYPE="video_file" \
    INPUT_SOURCE_SHA256="${video_sha256}" \
    LABEL_SOURCE_SHA256="${label_sha256}" \
    INPUT_PATH="${video_path}" \
    INPUT_ORIENTATION_CORRECTION="${effective_orientation_correction}" \
    DURATION_SEC="${DURATION_SEC}" \
    LOOP_VIDEO_FILE="${LOOP_VIDEO_FILE}" \
    SAVE_OUTPUT_VIDEO="${SAVE_OUTPUT_VIDEO}" \
    TRACE_FAIL_ON_GAPS="${TRACE_FAIL_ON_GAPS}" \
    PIPELINE_CONFIG="${PIPELINE_CONFIG}" \
    MODEL_CONFIG="${MODEL_CONFIG}" \
    STREAM_CONFIG="${STREAM_CONFIG}" \
      bash "${PIPELINE_SCRIPT}"
    pipeline_exit=$?
    set -e
      if [[ "${pipeline_exit}" -eq 3 ]]; then
        if revalidate_postcheck_failure \
          "${raw_path}" \
          "${schema_check_path}" \
          "${trace_check_path}" \
          "${runtime_summary_path}" \
          "${monitor_log_path}"; then
          echo "postcheck_recovered=1 run_id=${run_id}"
          pipeline_exit=0
        fi
      fi
    fi

    if [[ "${pipeline_exit}" -eq 0 ]]; then
      set +e
      "${PYTHON_BIN}" - "${raw_path}" "${EXPECTED_INPUT_WIDTH}" "${EXPECTED_INPUT_HEIGHT}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = (int(sys.argv[2]), int(sys.argv[3]))
first = None
with path.open("r", encoding="utf-8-sig") as f:
    for line in f:
        if line.strip():
            first = json.loads(line)
            break
if first is None:
    raise SystemExit(f"empty raw result: {path}")
actual = (int(first.get("input_width", 0)), int(first.get("input_height", 0)))
if actual != expected:
    print(
        f"INPUT_DIMENSION_MISMATCH: raw={path} actual={actual[0]}x{actual[1]} "
        f"expected={expected[0]}x{expected[1]}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print(f"input_dimension_status=pass actual={actual[0]}x{actual[1]}")
PY
      dimension_exit=$?
      set -e
      if [[ "${dimension_exit}" -ne 0 ]]; then
        pipeline_exit=31
        status="input_dimension_mismatch"
      fi
    fi

    if [[ "${pipeline_exit}" -ne 0 ]]; then
      if [[ "${status}" != "input_dimension_mismatch" && "${status}" != "input_orientation_detection_failed" ]]; then
        status="pipeline_fail"
      fi
    elif [[ "${EVALUATE}" == "1" ]]; then
      set +e
      "${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/evaluate_bdd100k_mot_detection.py \
        --pred-raw "${raw_path}" \
        --labels "${label_path}" \
        --sequence-id "${sequence_id}" \
        --class-ids "${CLASS_IDS}" \
        --confidence-min "${CONFIDENCE_MIN}" \
        --iou-min "${IOU_MIN}" \
        --overall-ap50-min "${OVERALL_AP50_MIN}" \
        --overall-recall-min "${OVERALL_RECALL_MIN}" \
        --output-md "${quality_md}" \
        --output-csv "${quality_csv}" \
        --output-summary-csv "${quality_summary_csv}"
      evaluate_exit=$?
      set -e
      if [[ -f "${quality_summary_csv}" ]]; then
        IFS=$'\t' read -r overall_ap50_weighted overall_precision overall_recall overall_f1 labeled_frame_coverage < <(
          "${PYTHON_BIN}" - "${quality_summary_csv}" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("r", encoding="utf-8-sig", newline="") as f:
    row = next(csv.DictReader(f))
print("\t".join([
    row.get("overall_ap50_weighted", ""),
    row.get("overall_precision", ""),
    row.get("overall_recall", ""),
    row.get("overall_f1", ""),
    row.get("labeled_frame_coverage", ""),
]))
PY
        )
      fi
      if [[ "${evaluate_exit}" -ne 0 ]]; then
        evaluate_status="fail"
        status="quality_threshold_fail"
      else
        evaluate_status="pass"
      fi
    else
      evaluate_status="disabled"
      status="not_evaluated"
    fi
  fi

  if [[ "${pipeline_exit}" -ne 0 ]]; then
    pipeline_failures=$((pipeline_failures + 1))
  fi
  if [[ "${evaluate_status}" == "fail" ]]; then
    quality_failures=$((quality_failures + 1))
  fi
  if [[ "${pipeline_exit}" -ne 0 || ("${EVALUATE_STRICT}" == "1" && "${evaluate_status}" == "fail") ]]; then
    strict_failures=$((strict_failures + 1))
  fi

  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "${run_index}" \
    "${sequence_id}" \
    "${run_id}" \
    "${input_source_id}" \
    "${video_path}" \
    "${video_sha256}" \
    "${label_path}" \
    "${label_sha256}" \
    "${labeled_frame_count}" \
    "${INPUT_ORIENTATION_CORRECTION}" \
    "${effective_orientation_correction}" \
    "${raw_path}" \
    "${runtime_summary_path}" \
    "${quality_md}" \
    "${quality_csv}" \
    "${quality_summary_csv}" \
    "${overall_ap50_weighted}" \
    "${overall_precision}" \
    "${overall_recall}" \
    "${overall_f1}" \
    "${labeled_frame_coverage}" \
    "${pipeline_exit}" \
    "${evaluate_exit}" \
    "${evaluate_status}" \
    "${status}" \
    "${PIPELINE_CONFIG}" \
    "${MODEL_CONFIG}" \
    "${CONFIDENCE_MIN}" \
    "${OVERALL_AP50_MIN}" \
    "${OVERALL_RECALL_MIN}" >> "${BATCH_SUMMARY}"

  if [[ "${pipeline_exit}" -ne 0 && "${CONTINUE_ON_ERROR}" != "1" ]]; then
    echo "Stopping because pipeline failed and CONTINUE_ON_ERROR=${CONTINUE_ON_ERROR}" >&2
    exit "${pipeline_exit}"
  fi

  if [[ "${EVALUATE_STRICT}" == "1" && "${evaluate_status}" == "fail" && "${CONTINUE_ON_ERROR}" != "1" ]]; then
    echo "Stopping because evaluation failed and EVALUATE_STRICT=${EVALUATE_STRICT}" >&2
    exit "${evaluate_exit}"
  fi
done

if [[ "${EVALUATE}" == "1" && "${pipeline_failures}" -eq 0 ]]; then
  "${PYTHON_BIN}" projects/03_video_pipeline/scripts/quality/sweep_bdd100k_confidence.py \
    --batch-csv "${BATCH_SUMMARY}" \
    --confidence-mins "${CONFIDENCE_MIN}" \
    --class-ids "${CLASS_IDS}" \
    --iou-min "${IOU_MIN}" \
    --overall-ap50-min "${OVERALL_AP50_MIN}" \
    --overall-recall-min "${OVERALL_RECALL_MIN}" \
    --output-csv "${BATCH_QUALITY_CSV}" \
    --output-detail-csv "${BATCH_QUALITY_DETAIL_CSV}" \
    --output-md "${BATCH_QUALITY_MD}"
fi

echo "batch_summary=${BATCH_SUMMARY}"
echo "batch_quality_csv=${BATCH_QUALITY_CSV}"
echo "batch_quality_detail_csv=${BATCH_QUALITY_DETAIL_CSV}"
echo "batch_quality_md=${BATCH_QUALITY_MD}"
echo "pipeline_failures=${pipeline_failures}"
echo "quality_failures=${quality_failures}"
echo "strict_failures=${strict_failures}"
if [[ "${strict_failures}" -ne 0 ]]; then
  exit 3
fi

#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_40bce_coco2017_recheck}"
PYTHON_BIN="${PYTHON_BIN:-}"
MODEL="${MODEL:-models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn}"
EXPECTED_SHA256="${EXPECTED_SHA256:-40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c}"
ANNOTATIONS="${ANNOTATIONS:-data/validation/coco2017_val2017/annotations/instances_val2017.json}"
IMAGE_ROOT="${IMAGE_ROOT:-data/validation/coco2017_val2017/images/val2017}"
EVAL_SCRIPT="${EVAL_SCRIPT:-projects/01_vision_deploy/scripts/eval/eval_rknn_official_coco.py}"
SUMMARY_SCRIPT="${SUMMARY_SCRIPT:-projects/03_video_pipeline/scripts/quality/summarize_rk3588_coco_recheck.py}"
MONITOR_SCRIPT="${MONITOR_SCRIPT:-projects/01_vision_deploy/scripts/monitor/rknpu_monitor.py}"
RAW_DIR="benchmark/raw/03_video_pipeline/rk3588_8gb/quality"
PROCESSED_DIR="benchmark/processed/03_video_pipeline"
LOG_DIR="logs/eval/03_video_pipeline/rk3588_8gb"
MONITOR_DIR="logs/monitor/03_video_pipeline/rk3588_8gb"
RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
EVAL_JSON="${RAW_DIR}/${RUN_ID}_coco_official.json"
SUMMARY_CSV="${PROCESSED_DIR}/${RUN_ID}_coco_quality.csv"
SUMMARY_MD="${PROCESSED_DIR}/${RUN_ID}_coco_quality.md"
LOG_PATH="${LOG_DIR}/${RUN_ID}.log"
MONITOR_LOG="${MONITOR_DIR}/${RUN_ID}_rknpu.log"

mkdir -p "${RAW_DIR}" "${PROCESSED_DIR}" "${LOG_DIR}" "${MONITOR_DIR}" "${RUN_DIR}"

check_python() {
  local candidate="$1"
  command -v "${candidate}" >/dev/null 2>&1 || return 1
  "${candidate}" -c 'import cv2, yaml, tqdm; from pycocotools.coco import COCO; from rknnlite.api import RKNNLite' >/dev/null 2>&1
}

if [[ -n "${PYTHON_BIN}" ]]; then
  if ! check_python "${PYTHON_BIN}"; then
    echo "PYTHON_BIN cannot import the RKNN COCOeval dependencies: ${PYTHON_BIN}" >&2
    "${PYTHON_BIN}" -c 'import cv2, yaml, tqdm; from pycocotools.coco import COCO; from rknnlite.api import RKNNLite' >&2 || true
    exit 2
  fi
else
  for candidate in "${HOME}/venvs/rk3588_rknn/bin/python" "${HOME}/venvs/rknn160/bin/python" python python3; do
    if check_python "${candidate}"; then
      PYTHON_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "No Python interpreter can import rknnlite, pycocotools, cv2, yaml and tqdm." >&2
  for candidate in "${HOME}/venvs/rk3588_rknn/bin/python" "${HOME}/venvs/rknn160/bin/python" python python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "--- ${candidate}: $(command -v "${candidate}") ---" >&2
      "${candidate}" --version >&2 || true
      "${candidate}" -c 'import cv2, yaml, tqdm; from pycocotools.coco import COCO; from rknnlite.api import RKNNLite' >&2 || true
    fi
  done
  exit 2
fi
echo "python_bin=$(command -v "${PYTHON_BIN}")"
"${PYTHON_BIN}" --version

for path in "${MODEL}" "${ANNOTATIONS}" "${EVAL_SCRIPT}" "${SUMMARY_SCRIPT}" "${MONITOR_SCRIPT}"; do
  if [[ ! -f "${path}" ]]; then
    echo "Required file not found: ${path}" >&2
    exit 2
  fi
done
if [[ ! -d "${IMAGE_ROOT}" ]]; then
  echo "COCO image root not found: ${IMAGE_ROOT}" >&2
  exit 2
fi

ACTUAL_SHA256="$(sha256sum "${MODEL}" | awk '{print $1}')"
if [[ "${ACTUAL_SHA256}" != "${EXPECTED_SHA256}" ]]; then
  echo "RKNN artifact hash mismatch: actual=${ACTUAL_SHA256}, expected=${EXPECTED_SHA256}" >&2
  exit 2
fi

IMAGE_COUNT="$(find "${IMAGE_ROOT}" -maxdepth 1 -type f -name '*.jpg' | wc -l)"
if [[ "${IMAGE_COUNT}" -ne 5000 ]]; then
  echo "Full COCO val2017 requires 5000 images, found ${IMAGE_COUNT}" >&2
  exit 2
fi

cat > "${RUN_DIR}/run.md" <<EOF
# ${RUN_ID}

\`\`\`yaml
run_id: ${RUN_ID}
stage: rk3588_rknn_artifact_coco2017_recheck
status: running
environment_baseline_id: 20260611_rk3588_8gb_env_baseline
model: ${MODEL}
backend_artifact_sha256: ${ACTUAL_SHA256}
dataset_id: coco2017_val2017
evaluated_images: 5000
baseline_quality: 0.3865
max_accuracy_drop: 0.03
eval_json: ${EVAL_JSON}
summary_csv: ${SUMMARY_CSV}
summary_md: ${SUMMARY_MD}
runtime_log: ${LOG_PATH}
monitor_log: ${MONITOR_LOG}
\`\`\`
EOF

"${PYTHON_BIN}" "${MONITOR_SCRIPT}" start --logfile "${MONITOR_LOG}" --interval 1
trap '"${PYTHON_BIN}" "${MONITOR_SCRIPT}" stop --logfile "${MONITOR_LOG}" >/dev/null 2>&1 || true' EXIT

"${PYTHON_BIN}" "${EVAL_SCRIPT}" \
  --model "${MODEL}" \
  --data-coco-json "${ANNOTATIONS}" \
  --image-root "${IMAGE_ROOT}" \
  --preprocess-config projects/01_vision_deploy/configs/preprocess/yolo11n_640.yaml \
  --postprocess-config projects/01_vision_deploy/configs/postprocess/yolo11n_nms.yaml \
  --board-config projects/01_vision_deploy/configs/boards/rk3588_rknn.yaml \
  --output "${EVAL_JSON}" \
  --max-images 0 \
  --confidence-threshold 0.001 \
  --iou-threshold 0.7 \
  --max-detections 300 \
  2>&1 | tee "${LOG_PATH}"

"${PYTHON_BIN}" "${MONITOR_SCRIPT}" stop --logfile "${MONITOR_LOG}" >/dev/null 2>&1 || true
trap - EXIT

set +e
"${PYTHON_BIN}" "${SUMMARY_SCRIPT}" \
  --run-id "${RUN_ID}" \
  --model "${MODEL}" \
  --expected-sha256 "${EXPECTED_SHA256}" \
  --eval-json "${EVAL_JSON}" \
  --baseline-quality 0.3865 \
  --reference-quality 0.3814960637396267 \
  --max-accuracy-drop 0.03 \
  --expected-images 5000 \
  --output-csv "${SUMMARY_CSV}" \
  --output-md "${SUMMARY_MD}" | tee -a "${LOG_PATH}"
SUMMARY_EXIT="${PIPESTATUS[0]}"
set -e

FINAL_STATUS="fail"
if [[ "${SUMMARY_EXIT}" -eq 0 ]]; then
  FINAL_STATUS="pass"
fi
cat >> "${RUN_DIR}/run.md" <<EOF

## Result

- status: \`${FINAL_STATUS}\`
- summary_exit: \`${SUMMARY_EXIT}\`
EOF

echo "eval_json=${EVAL_JSON}"
echo "summary_csv=${SUMMARY_CSV}"
echo "summary_md=${SUMMARY_MD}"
echo "log=${LOG_PATH}"
echo "monitor_log=${MONITOR_LOG}"
echo "status=${FINAL_STATUS}"
exit "${SUMMARY_EXIT}"

#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rk3588_8gb_pipeline_failure_test}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP="${APP:-build/03_video_pipeline_rk3588/video_pipeline_app}"
OUTPUT="${OUTPUT:-logs/failures/03_video_pipeline/rk3588_8gb/${RUN_ID}_failure_injection.jsonl}"
SUMMARY="${SUMMARY:-benchmark/processed/03_video_pipeline/${RUN_ID}_failure_summary.csv}"
RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"

if [[ ! -x "${APP}" ]]; then
  echo "Pipeline app not found or not executable: ${APP}" >&2
  exit 2
fi

mkdir -p "$(dirname "${OUTPUT}")" "$(dirname "${SUMMARY}")" "${RUN_DIR}"

cat > "${RUN_DIR}/run.md" <<EOF
# ${RUN_ID}

\`\`\`yaml
run_id: ${RUN_ID}
date: $(date --iso-8601=seconds)
spec_ref: projects/03_video_pipeline/specs/03G_异常恢复与服务化部署规范.md
stage: rk3588_failure_injection
status: not_verified
environment_baseline_id: ${ENVIRONMENT_BASELINE_ID:-missing}
target: rk3588_8gb
backend_runtime: rknn
pipeline_app: ${APP}
failure_jsonl: ${OUTPUT}
processed_summary: ${SUMMARY}
\`\`\`
EOF

set +e
"${PYTHON_BIN}" projects/03_video_pipeline/scripts/inject_failure_tests.py \
  --pipeline "${APP}" \
  --pipeline-config projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml \
  --model-config projects/03_video_pipeline/configs/models/yolo11n.yaml \
  --backend-config projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml \
  --stream-config projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml \
  --input-source-id bdd100k_mot_mini_v1_02344f0c-d5d916ff \
  --input-source-type video_file \
  --input data/videos/bdd100k_mot_mini_v1/02344f0c-d5d916ff.mov \
  --queue-input-source-id video_set_runtime_v1 \
  --queue-input-source-type video_playlist \
  --queue-input data/videos/runtime_playlist_v1.txt \
  --missing-artifact-path models/yolo11n/rknn/does_not_exist.rknn \
  --cases input_open_failed model_missing invalid_shape output_unwritable queue_overflow \
  --output "${OUTPUT}" \
  --run-id "${RUN_ID}" \
  --environment-baseline-id "${ENVIRONMENT_BASELINE_ID:-}"
INJECT_EXIT=$?
set -e

"${PYTHON_BIN}" projects/03_video_pipeline/scripts/benchmark/aggregate_failure_service.py \
  --input "${OUTPUT}" \
  --schema benchmark/schemas/video_pipeline_failure_schema.yaml \
  --output "${SUMMARY}"

set +e
"${PYTHON_BIN}" - "${OUTPUT}" "${SUMMARY}" <<'PY'
import csv
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
with Path(sys.argv[2]).open("r", encoding="utf-8", newline="") as f:
    summary_rows = list(csv.DictReader(f))
expected = {"input_open_failed", "model_missing", "invalid_shape", "output_unwritable", "queue_overflow"}
actual = {row.get("case_id") for row in rows}
failed = [row.get("case_id") for row in rows if row.get("status") != "pass"]
schema_failed = [row.get("case_id") for row in summary_rows if row.get("schema_status") != "pass"]
if actual != expected or failed or schema_failed:
    print(
        f"failure_gate=fail expected={sorted(expected)} actual={sorted(actual)} "
        f"failed={failed} schema_failed={schema_failed}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("failure_gate=pass")
PY
GATE_EXIT=$?
set -e

FINAL_STATUS=pass
FINAL_EXIT=0
if [[ "${INJECT_EXIT}" -ne 0 || "${GATE_EXIT}" -ne 0 ]]; then
  FINAL_STATUS=fail
  FINAL_EXIT=1
fi

cat >> "${RUN_DIR}/run.md" <<EOF

## 执行结果

- injection_exit: ${INJECT_EXIT}
- gate_exit: ${GATE_EXIT}
- failure_jsonl: ${OUTPUT}
- processed_summary: ${SUMMARY}
- status: ${FINAL_STATUS}
EOF

echo "run_id=${RUN_ID}"
echo "failure_jsonl=${OUTPUT}"
echo "processed_summary=${SUMMARY}"
echo "status=${FINAL_STATUS}"
exit "${FINAL_EXIT}"

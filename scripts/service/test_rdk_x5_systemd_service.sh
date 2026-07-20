#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_rdk_x5_8gb_systemd_service_test}"
SERVICE_NAME="${SERVICE_NAME:-edge-video-pipeline-rdkx5}"
SERVICE_TEMPLATE="${SERVICE_TEMPLATE:-projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-rdkx5.service}"
SERVICE_INSTALL_PATH="${SERVICE_INSTALL_PATH:-/etc/systemd/system/${SERVICE_NAME}.service}"
STATUS_LOG="${STATUS_LOG:-logs/runtime/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_systemd_status.log}"
JOURNAL_LOG="${JOURNAL_LOG:-logs/runtime/03_video_pipeline/rdk_x5_8gb/${RUN_ID}_journal.log}"
RUN_DIR="projects/03_video_pipeline/runs/${RUN_ID}"
SETTLE_SEC="${SETTLE_SEC:-10}"
STATE_TIMEOUT_SEC="${STATE_TIMEOUT_SEC:-30}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-1}"
SERVICE_USER="${SERVICE_USER:-root}"
WORKDIR="${WORKDIR:-${REPO_ROOT}}"
ENV_BASELINE="${ENVIRONMENT_BASELINE_ID:-20260612_rdk_x5_8gb_env_baseline}"
PLACEHOLDER_WORKDIR="/path/to/edge-inference-deploy-lab"

if [[ "${WORKDIR}" == "${PLACEHOLDER_WORKDIR}" ]]; then
  echo "WORKDIR_PLACEHOLDER_NOT_REPLACED: ${WORKDIR}" >&2
  exit 64
fi
if [[ ! -d "${WORKDIR}" ]]; then
  echo "WORKDIR_NOT_FOUND: ${WORKDIR}" >&2
  exit 64
fi
RUN_SCRIPT="${WORKDIR}/projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh"
if [[ ! -f "${RUN_SCRIPT}" ]]; then
  echo "RUN_SCRIPT_NOT_FOUND: ${RUN_SCRIPT}" >&2
  exit 64
fi

mkdir -p "$(dirname "${STATUS_LOG}")" "$(dirname "${JOURNAL_LOG}")" "${RUN_DIR}"

append_status() {
  local label="$1"
  {
    echo "## ${label}"
    echo "timestamp=$(date --iso-8601=seconds)"
    sudo systemctl status "${SERVICE_NAME}" --no-pager || true
    echo
    echo "is-active=$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"
    echo "is-enabled=$(sudo systemctl is-enabled "${SERVICE_NAME}" 2>/dev/null || true)"
    echo "active-state=$(sudo systemctl show "${SERVICE_NAME}" -p ActiveState --value 2>/dev/null || true)"
    echo "sub-state=$(sudo systemctl show "${SERVICE_NAME}" -p SubState --value 2>/dev/null || true)"
    echo "result=$(sudo systemctl show "${SERVICE_NAME}" -p Result --value 2>/dev/null || true)"
    echo
  } >> "${STATUS_LOG}"
}

wait_for_service_state() {
  local deadline=$(( $(date +%s) + STATE_TIMEOUT_SEC ))
  local state=""
  while true; do
    state="$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"
    if [[ "${state}" == "active" || "${state}" == "failed" || "${state}" == "inactive" ]]; then
      echo "${state}"
      return 0
    fi
    if (( $(date +%s) >= deadline )); then
      echo "${state}"
      return 0
    fi
    sleep "${POLL_INTERVAL_SEC}"
  done
}

TMP_SERVICE="$(mktemp)"
trap 'rm -f "${TMP_SERVICE}"' EXIT
sed \
  -e "s|__WORKDIR__|${WORKDIR}|g" \
  -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  -e "s|__ENV_BASELINE__|${ENV_BASELINE}|g" \
  -e "s|__RUN_SCRIPT__|${RUN_SCRIPT}|g" \
  "${SERVICE_TEMPLATE}" > "${TMP_SERVICE}"

echo "# ${RUN_ID}" > "${STATUS_LOG}"
echo "service_name=${SERVICE_NAME}" >> "${STATUS_LOG}"
echo "service_template=${SERVICE_TEMPLATE}" >> "${STATUS_LOG}"
echo "service_install_path=${SERVICE_INSTALL_PATH}" >> "${STATUS_LOG}"
echo "service_user=${SERVICE_USER}" >> "${STATUS_LOG}"
echo "workdir=${WORKDIR}" >> "${STATUS_LOG}"
echo >> "${STATUS_LOG}"

sudo cp "${TMP_SERVICE}" "${SERVICE_INSTALL_PATH}"
sudo systemctl daemon-reload
append_status "after_daemon_reload"

sudo systemctl start "${SERVICE_NAME}"
sleep "${SETTLE_SEC}"
append_status "after_start"
START_STATUS="$(wait_for_service_state)"
append_status "after_start_wait"

sudo systemctl restart "${SERVICE_NAME}"
sleep "${SETTLE_SEC}"
append_status "after_restart"
RESTART_STATUS="$(wait_for_service_state)"
append_status "after_restart_wait"

sudo journalctl -u "${SERVICE_NAME}" --since "15 min ago" --no-pager > "${JOURNAL_LOG}" || true
HEALTH_STATUS=fail
if grep -q "prepost_status=pass" "${JOURNAL_LOG}"; then
  HEALTH_STATUS=pass
fi

sudo systemctl stop "${SERVICE_NAME}"
sleep 2
append_status "after_stop"
STOP_STATUS="$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"

FINAL_STATUS=pass
if [[ "${START_STATUS}" != active || "${RESTART_STATUS}" != active || "${STOP_STATUS}" != inactive || "${HEALTH_STATUS}" != pass ]]; then
  FINAL_STATUS=fail
fi

cat > "${RUN_DIR}/run.md" <<EOF
# ${RUN_ID}

\`\`\`yaml
run_id: ${RUN_ID}
date: $(date --iso-8601=seconds)
spec_ref: projects/03_video_pipeline/specs/03G_异常恢复与服务化部署规范.md
stage: rdk_x5_systemd_service_test
target: rdk_x5_8gb
backend_runtime: bpu
service_name: ${SERVICE_NAME}
service_user: ${SERVICE_USER}
working_directory: ${WORKDIR}
service_start_status: ${START_STATUS}
service_restart_status: ${RESTART_STATUS}
service_stop_status: ${STOP_STATUS}
health_check_status: ${HEALTH_STATUS}
status_log_path: ${STATUS_LOG}
journal_log_path: ${JOURNAL_LOG}
status: ${FINAL_STATUS}
\`\`\`
EOF

echo "service_name=${SERVICE_NAME}"
echo "service_template=${SERVICE_TEMPLATE}"
echo "service_install_path=${SERVICE_INSTALL_PATH}"
echo "status_log=${STATUS_LOG}"
echo "journal_log=${JOURNAL_LOG}"
echo "start_status=${START_STATUS}"
echo "restart_status=${RESTART_STATUS}"
echo "stop_status=${STOP_STATUS}"
echo "health_check_status=${HEALTH_STATUS}"
echo "status=${FINAL_STATUS}"

[[ "${FINAL_STATUS}" == pass ]]

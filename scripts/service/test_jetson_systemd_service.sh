#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_jetson_8gb_systemd_service_test}"
SERVICE_NAME="${SERVICE_NAME:-edge-video-pipeline-jetson}"
SERVICE_TEMPLATE="${SERVICE_TEMPLATE:-projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-jetson.service}"
SERVICE_INSTALL_PATH="${SERVICE_INSTALL_PATH:-/etc/systemd/system/${SERVICE_NAME}.service}"
STATUS_LOG="${STATUS_LOG:-logs/runtime/03_video_pipeline/jetson_8gb/${RUN_ID}_systemd_status.log}"
JOURNAL_LOG="${JOURNAL_LOG:-logs/runtime/03_video_pipeline/jetson_8gb/${RUN_ID}_journal.log}"
SETTLE_SEC="${SETTLE_SEC:-5}"

mkdir -p \
  "$(dirname "${STATUS_LOG}")" \
  "$(dirname "${JOURNAL_LOG}")"

append_status() {
  local label="$1"
  {
    echo "## ${label}"
    echo "timestamp=$(date --iso-8601=seconds)"
    sudo systemctl status "${SERVICE_NAME}" --no-pager || true
    echo
    echo "is-active=$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"
    echo "is-enabled=$(sudo systemctl is-enabled "${SERVICE_NAME}" 2>/dev/null || true)"
    echo
  } >> "${STATUS_LOG}"
}

echo "# ${RUN_ID}" > "${STATUS_LOG}"
echo "service_name=${SERVICE_NAME}" >> "${STATUS_LOG}"
echo "service_template=${SERVICE_TEMPLATE}" >> "${STATUS_LOG}"
echo "service_install_path=${SERVICE_INSTALL_PATH}" >> "${STATUS_LOG}"
echo >> "${STATUS_LOG}"

sudo cp "${SERVICE_TEMPLATE}" "${SERVICE_INSTALL_PATH}"
sudo systemctl daemon-reload
append_status "after_daemon_reload"

sudo systemctl start "${SERVICE_NAME}"
sleep "${SETTLE_SEC}"
append_status "after_start"
START_STATUS="$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"

sudo systemctl restart "${SERVICE_NAME}"
sleep "${SETTLE_SEC}"
append_status "after_restart"
RESTART_STATUS="$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"

sudo journalctl -u "${SERVICE_NAME}" --since "15 min ago" --no-pager > "${JOURNAL_LOG}" || true

sudo systemctl stop "${SERVICE_NAME}"
sleep 2
append_status "after_stop"
STOP_STATUS="$(sudo systemctl is-active "${SERVICE_NAME}" 2>/dev/null || true)"

echo "service_name=${SERVICE_NAME}"
echo "service_template=${SERVICE_TEMPLATE}"
echo "service_install_path=${SERVICE_INSTALL_PATH}"
echo "status_log=${STATUS_LOG}"
echo "journal_log=${JOURNAL_LOG}"
echo "start_status=${START_STATUS}"
echo "restart_status=${RESTART_STATUS}"
echo "stop_status=${STOP_STATUS}"

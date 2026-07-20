#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-logs/monitor/03_video_pipeline/rk3588_8gb/rknpu_monitor.log}"
INTERVAL_SEC="${INTERVAL_SEC:-1}"
APP_MATCH_PATTERN="${APP_MATCH_PATTERN:-build/03_video_pipeline_rk3588/video_pipeline_app}"

mkdir -p "$(dirname "${OUT}")"

echo "# rk3588 rknpu monitor started_at=$(date --iso-8601=seconds)" > "${OUT}"
echo "# load_paths=/sys/class/devfreq/fdab0000.npu/load,/sys/kernel/debug/rknpu/load" >> "${OUT}"
echo "# app_match_pattern=${APP_MATCH_PATTERN}" >> "${OUT}"
while true; do
  ts="$(date --iso-8601=seconds)"
  load="null"
  if [[ -r /sys/class/devfreq/fdab0000.npu/load ]]; then
    load="$(cat /sys/class/devfreq/fdab0000.npu/load 2>/dev/null || echo null)"
  elif [[ -r /sys/kernel/debug/rknpu/load ]]; then
    load="$(cat /sys/kernel/debug/rknpu/load 2>/dev/null || echo null)"
  fi
  temp="null"
  if [[ -r /sys/class/thermal/thermal_zone0/temp ]]; then
    raw_temp="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "")"
    if [[ -n "${raw_temp}" ]]; then
      temp="$(awk "BEGIN { printf \"%.2f\", ${raw_temp}/1000.0 }")"
    fi
  fi
  mem_available="null"
  mem_total="null"
  if [[ -r /proc/meminfo ]]; then
    mem_total="$(awk '/MemTotal/ {printf "%.2f", $2/1024.0}' /proc/meminfo)"
    mem_available="$(awk '/MemAvailable/ {printf "%.2f", $2/1024.0}' /proc/meminfo)"
  fi
  app_pid="$(pgrep -n -f -- "${APP_MATCH_PATTERN}" 2>/dev/null || true)"
  process_rss_mb="null"
  process_hwm_mb="null"
  if [[ -n "${app_pid}" && -r "/proc/${app_pid}/status" ]]; then
    process_rss_mb="$(awk '/^VmRSS:/ {printf "%.2f", $2/1024.0}' "/proc/${app_pid}/status")"
    process_hwm_mb="$(awk '/^VmHWM:/ {printf "%.2f", $2/1024.0}' "/proc/${app_pid}/status")"
    process_rss_mb="${process_rss_mb:-null}"
    process_hwm_mb="${process_hwm_mb:-null}"
  else
    app_pid="null"
  fi
  echo "timestamp=${ts} rknpu_load=${load} temperature_c=${temp} mem_total_mb=${mem_total} mem_available_mb=${mem_available} app_pid=${app_pid} process_rss_mb=${process_rss_mb} process_hwm_mb=${process_hwm_mb}" >> "${OUT}"
  sleep "${INTERVAL_SEC}"
done

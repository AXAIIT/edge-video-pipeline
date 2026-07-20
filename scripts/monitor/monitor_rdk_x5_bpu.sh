#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-logs/monitor/03_video_pipeline/rdk_x5_8gb/bpu_monitor.log}"
INTERVAL_SEC="${INTERVAL_SEC:-1}"
APP_MATCH_PATTERN="${APP_MATCH_PATTERN:-build/03_video_pipeline_rdk_x5/video_pipeline_app}"

mkdir -p "$(dirname "${OUT}")"

find_freq_file() {
  local pattern
  for pattern in "$@"; do
    local first
    first="$(compgen -G "${pattern}" | head -n 1 || true)"
    if [[ -n "${first}" ]]; then
      printf '%s\n' "${first}"
      return 0
    fi
  done
  return 1
}

read_freq_mhz() {
  local path="$1"
  [[ -r "${path}" ]] || {
    printf 'null'
    return 0
  }
  local raw
  raw="$(cat "${path}" 2>/dev/null || true)"
  [[ -n "${raw}" ]] || {
    printf 'null'
    return 0
  }
  awk -v value="${raw}" 'BEGIN {
    if (value > 1000000) printf "%.3f", value / 1000000.0;
    else if (value > 10000) printf "%.3f", value / 1000.0;
    else printf "%.3f", value + 0.0;
  }'
}

read_temp_c() {
  local path="$1"
  [[ -r "${path}" ]] || {
    printf 'null'
    return 0
  }
  local raw
  raw="$(cat "${path}" 2>/dev/null || true)"
  [[ -n "${raw}" ]] || {
    printf 'null'
    return 0
  }
  awk -v value="${raw}" 'BEGIN {
    if (value > 1000 || value < -1000) printf "%.3f", value / 1000.0;
    else printf "%.3f", value + 0.0;
  }'
}

BPU_FREQ_PATH="$(find_freq_file /sys/class/devfreq/*bpu*/cur_freq /sys/class/devfreq/*BPU*/cur_freq /sys/devices/platform/*bpu*/devfreq/*/cur_freq || true)"
DDR_FREQ_PATH="$(find_freq_file /sys/class/devfreq/*ddr*/cur_freq /sys/class/devfreq/*DDR*/cur_freq || true)"
GPU_FREQ_PATH="$(find_freq_file /sys/class/devfreq/*gc8000*/cur_freq /sys/class/devfreq/*gpu*/cur_freq || true)"
BPU_LOAD_PATH="$(find_freq_file /sys/class/devfreq/*bpu*/load /sys/class/devfreq/*BPU*/load /sys/kernel/debug/*bpu*/*load* || true)"

echo "# rdk_x5 bpu monitor started_at=$(date --iso-8601=seconds)" > "${OUT}"
echo "# bpu_freq_path=${BPU_FREQ_PATH:-not_found}" >> "${OUT}"
echo "# ddr_freq_path=${DDR_FREQ_PATH:-not_found}" >> "${OUT}"
echo "# gpu_freq_path=${GPU_FREQ_PATH:-not_found}" >> "${OUT}"
echo "# bpu_load_path=${BPU_LOAD_PATH:-not_found}" >> "${OUT}"
echo "# app_match_pattern=${APP_MATCH_PATTERN}" >> "${OUT}"

while true; do
  ts="$(date --iso-8601=seconds)"
  bpu_freq_mhz="$(read_freq_mhz "${BPU_FREQ_PATH:-}")"
  ddr_freq_mhz="$(read_freq_mhz "${DDR_FREQ_PATH:-}")"
  gpu_freq_mhz="$(read_freq_mhz "${GPU_FREQ_PATH:-}")"
  bpu_load="null"
  if [[ -n "${BPU_LOAD_PATH:-}" && -r "${BPU_LOAD_PATH}" ]]; then
    bpu_load="$(tr '\n' ' ' < "${BPU_LOAD_PATH}" 2>/dev/null | xargs echo -n || echo null)"
    [[ -n "${bpu_load}" ]] || bpu_load="null"
  fi
  mem_total_mb="null"
  mem_available_mb="null"
  mem_used_mb="null"
  if [[ -r /proc/meminfo ]]; then
    mem_total_mb="$(awk '/MemTotal/ {printf "%.3f", $2/1024.0}' /proc/meminfo)"
    mem_available_mb="$(awk '/MemAvailable/ {printf "%.3f", $2/1024.0}' /proc/meminfo)"
    mem_used_mb="$(awk '/MemTotal/ {total=$2} /MemAvailable/ {avail=$2} END {if (total>0 && avail>=0) printf "%.3f", (total-avail)/1024.0; else print "null"}' /proc/meminfo)"
  fi

  max_temp_sensor="null"
  max_temp_c="null"
  for temp_path in /sys/class/thermal/thermal_zone*/temp; do
    [[ -e "${temp_path}" ]] || continue
    zone_dir="$(dirname "${temp_path}")"
    sensor_name="$(cat "${zone_dir}/type" 2>/dev/null || basename "${zone_dir}")"
    sensor_temp="$(read_temp_c "${temp_path}")"
    if [[ "${sensor_temp}" != "null" ]]; then
      if [[ "${max_temp_c}" == "null" ]] || awk -v a="${sensor_temp}" -v b="${max_temp_c}" 'BEGIN { exit !(a > b) }'; then
        max_temp_c="${sensor_temp}"
        max_temp_sensor="${sensor_name}"
      fi
    fi
  done

  hrut_bpu_ratio="null"
  hrut_ddr_temp_c="null"
  hrut_cpu_temp_c="null"
  hrut_bpu_temp_c="null"
  if command -v hrut_somstatus >/dev/null 2>&1; then
    hrut_output="$(hrut_somstatus 2>/dev/null || true)"
    if [[ -n "${hrut_output}" ]]; then
      hrut_bpu_ratio="$(printf '%s\n' "${hrut_output}" | awk -F'[: ]+' '/bpu0/ && /ratio/ {for(i=1;i<=NF;i++) if ($i ~ /^[0-9.]+$/) {print $i; exit}}')"
      hrut_ddr_temp_c="$(printf '%s\n' "${hrut_output}" | awk -F'[: ]+' '/DDR/ && /temp/ {for(i=1;i<=NF;i++) if ($i ~ /^[0-9.]+$/) {print $i; exit}}')"
      hrut_cpu_temp_c="$(printf '%s\n' "${hrut_output}" | awk -F'[: ]+' '/CPU/ && /temp/ {for(i=1;i<=NF;i++) if ($i ~ /^[0-9.]+$/) {print $i; exit}}')"
      hrut_bpu_temp_c="$(printf '%s\n' "${hrut_output}" | awk -F'[: ]+' '/BPU/ && /temp/ {for(i=1;i<=NF;i++) if ($i ~ /^[0-9.]+$/) {print $i; exit}}')"
      hrut_bpu_ratio="${hrut_bpu_ratio:-null}"
      hrut_ddr_temp_c="${hrut_ddr_temp_c:-null}"
      hrut_cpu_temp_c="${hrut_cpu_temp_c:-null}"
      hrut_bpu_temp_c="${hrut_bpu_temp_c:-null}"
    fi
  fi

  app_pid="$(pgrep -n -f -- "${APP_MATCH_PATTERN}" 2>/dev/null || true)"
  process_rss_mb="null"
  process_hwm_mb="null"
  if [[ -n "${app_pid}" && -r "/proc/${app_pid}/status" ]]; then
    process_rss_mb="$(awk '/^VmRSS:/ {printf "%.3f", $2/1024.0}' "/proc/${app_pid}/status")"
    process_hwm_mb="$(awk '/^VmHWM:/ {printf "%.3f", $2/1024.0}' "/proc/${app_pid}/status")"
    process_rss_mb="${process_rss_mb:-null}"
    process_hwm_mb="${process_hwm_mb:-null}"
  else
    app_pid="null"
  fi

  echo "timestamp=${ts} bpu_freq_mhz=${bpu_freq_mhz} ddr_freq_mhz=${ddr_freq_mhz} gpu_freq_mhz=${gpu_freq_mhz} bpu_load=${bpu_load} max_temp_sensor=${max_temp_sensor} max_temp_c=${max_temp_c} hrut_bpu_ratio=${hrut_bpu_ratio} hrut_ddr_temp_c=${hrut_ddr_temp_c} hrut_cpu_temp_c=${hrut_cpu_temp_c} hrut_bpu_temp_c=${hrut_bpu_temp_c} mem_total_mb=${mem_total_mb} mem_available_mb=${mem_available_mb} mem_used_mb=${mem_used_mb} app_pid=${app_pid} process_rss_mb=${process_rss_mb} process_hwm_mb=${process_hwm_mb}" >> "${OUT}"
  sleep "${INTERVAL_SEC}"
done

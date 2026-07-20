#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_jetson_8gb_tegrastats_probe}"
INTERVAL_MS="${INTERVAL_MS:-1000}"
OUTPUT="${OUTPUT:-logs/monitor/03_video_pipeline/jetson_8gb/${RUN_ID}_tegrastats.log}"

mkdir -p "$(dirname "${OUTPUT}")"

tegrastats --interval "${INTERVAL_MS}" --logfile "${OUTPUT}"

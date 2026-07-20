# 项目三稳定性报告

## 当前状态

partial_executed

稳定性结论必须来自 03H 的 stability run。10 分钟 smoke 只用于确认配置可跑；30 分钟 short sustained 是项目三基础稳定性必测；2 小时 acceptance sustained 是项目验收目标。目标时长未完成时，必须记录 `actual_duration_sec`、`stop_reason`、runtime log、monitor log 和 failure log，不能用更短档位替代。

## Jetson TensorRT 稳定性计划

Jetson 是项目三稳定性实验的第一块板。当前旧的单文件高压灌流 smoke 已经降级为历史对照；正式默认口径已切到 `playlist-paced + SAVE_OUTPUT_VIDEO=0`。

| tier | duration_sec | command | raw result | runtime log | monitor log | status |
|---|---:|---|---|---|---|---|
| smoke | 600 | `TIER=smoke bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` | noout_baseline_verified |
| short_sustained | 1800 | `TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` | noout_baseline_verified |
| acceptance_sustained | 7200 | `TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` | noout_baseline_verified |
| long_sustained | 28800 | `TIER=long_sustained bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` | not_executed |

Jetson 稳定性验收边界：

- 30 分钟 `short_sustained` 是必须项；未完成时不能进入项目三稳定性通过结论。
- 2 小时 `acceptance_sustained` 是项目验收目标；未完成时必须显示目标未达成，不能用 30 分钟替代。
- `tegrastats` 日志缺失时，资源结论必须写 `not_verified` 或 `degraded`。
- 温控降频、内存增长、队列堆积、断流重连失败必须进入 `reports/troubleshooting.md`。

## Stability Summary

| run_id | target | backend_runtime | input_source_id | stability_tier | target_duration_sec | actual_duration_sec | completed | stop_reason | fps_avg | p95_latency_ms | p99_latency_ms | memory_growth_mb_per_hour | temperature_c_peak | throttle_events | status |
|---|---|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` | jetson_8gb | tensorrt | video_set_stability_v1 | smoke | 600 | 596.0 | true |  | 30.1091 | 52.7732 | 55.0918 | 308.0 | 57.5 | 616 | pass_noout_baseline |
| `20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` | jetson_8gb | tensorrt | video_set_stability_v1 | smoke | 600 | 596.0 | true |  | 30.1023 | 51.9486 | 53.5553 | 145.0 | 57.0 | 617 | pass_block_with_timeout_candidate |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | jetson_8gb | tensorrt | video_set_stability_v1 | short_sustained | 1800 | 1797.0 | true |  | 30.0395 | 71.7296 | 74.4355 | 625.0 | 60.5 | 1835 | pass_noout_baseline |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | jetson_8gb | tensorrt | video_set_stability_v1 | acceptance_sustained | 7200 | 7196.0 | true |  | 30.0573 | 52.0953 | 53.9539 | -170.0 | 60.0 | 7326 | pass_noout_baseline |

## Resource Trace

| run_id | monitor_log_path | sample_interval_sec | memory_mb_peak | memory_growth_mb_per_hour | temperature_c_avg | temperature_c_peak | power_mode | power_w_avg | power_w_peak | cpu_util_avg | gpu_util_avg | throttle_events | status |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` | `logs/monitor/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout_tegrastats.log` | 1 | 2317.0 | 308.0 |  | 57.5 | not_recorded |  |  | 25.3612 | 22.6769 | 616 | pass_noout_baseline |
| `20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` | `logs/monitor/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout_tegrastats.log` | 1 | 2187.0 | 145.0 |  | 57.0 | not_recorded |  |  | 24.3614 | 22.3517 | 617 | pass_block_with_timeout_candidate |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | `logs/monitor/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout_tegrastats.log` | 1 | 2226.0 | 625.0 |  | 60.5 | not_recorded |  |  | 29.6449 | 23.0033 | 1835 | pass_noout_baseline |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | `logs/monitor/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout_tegrastats.log` | 1 | 3920.0 | -170.0 |  | 60.0 | not_recorded |  |  | 24.5810 | 22.8475 | 7326 | pass_noout_baseline |

## Queue / Drop Trend

| run_id | window_sec | queue_capture_p95 | queue_preprocess_p95 | queue_infer_p95 | queue_postprocess_p95 | queue_max | drop_frame_count | drop_frame_rate | dropped_frame_reason | latency_trend | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` | 60 | 0.0 | 0.0 | 0.0 | 0.0 | 7 | 103 | 0.00571 | queue_full | not_assessed | pass_noout_baseline |
| `20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` | 60 | 0.0 | 0.0 | 0.0 | 0.0 | 8 | 107 | 0.00593 | queue_full | not_assessed | pass_block_with_timeout_candidate |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | 60 | 0.0 | 0.0 | 0.0 | 0.0 | 8 | 112 | 0.00207 | queue_full | not_assessed | pass_noout_baseline |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | 60 | 0.0 | 0.0 | 0.0 | 0.0 | 7 | 110 | 0.00051 | queue_full | not_assessed | pass_noout_baseline |

## Stability Events

| run_id | restart_count | reconnect_count | crash_count | watchdog_count | input_disconnect_count | backend_error_count | output_error_count | recovery_success_count | max_recovery_time_sec | failure_log_path | related_troubleshooting_id | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  | pass_noout_baseline |
| `20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  | pass_block_with_timeout_candidate |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  | pass_noout_baseline |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  | pass_noout_baseline |

## RK3588 RKNN 稳定性计划

RK3588 稳定性测试继承项目二 RKNN runtime 基线，但必须重新跑项目三 C++ video pipeline。项目二单模型稳定性不能替代本表。

| tier | duration_sec | command | raw result | runtime log | monitor log | status |
|---|---:|---|---|---|---|---|
| smoke | 600 | `TIER=smoke bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/<run_id>_rknpu.log` | superseded_by_runtime600_clean |
| short_sustained | 1800 | `TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/<run_id>_rknpu.log` | pass |
| acceptance_sustained | 7200 | `TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/<run_id>_rknpu.log` | pass_realtime_with_negligible_drop |
| long_sustained | 28800 | `RUN_GROUP_ID=<run_group_id> bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_8h_mixed.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/<camera_run_id>.jsonl` + `benchmark/raw/03_video_pipeline/rk3588_8gb/<video_run_id>.jsonl` | `logs/runtime/03_video_pipeline/rk3588_8gb/<camera_run_id>.log` + `logs/runtime/03_video_pipeline/rk3588_8gb/<video_run_id>.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/<camera_run_id>_rknpu.log` + `logs/monitor/03_video_pipeline/rk3588_8gb/<video_run_id>_rknpu.log` | pass_mixed_8h_realtime_with_negligible_drop |

RK3588 长稳已按 mixed 口径正式完成：`20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h` 顺序执行 `astra_s_openni_001` 4 小时和 `video_set_stability_v1` 4 小时，总计 8 小时。camera 4h 零 gap/零 drop/零乱序；video 4h 的严格 trace 记录 5 个 gap event、共 8 帧，实时策略 trace 为 `degraded`、0 out-of-order，聚合稳定性状态为 `pass`。因此当前长稳结论应按“实时策略通过并保留严格 trace 失败证据”解释，而不是 `not_executed`。

### RK3588 Stability Summary

| run_id | target | backend_runtime | input_source_id | stability_tier | target_duration_sec | actual_duration_sec | completed | stop_reason | fps_avg | p95_latency_ms | p99_latency_ms | memory_growth_mb_per_hour | temperature_c_peak | throttle_events | status |
|---|---|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | rk3588_8gb | rknn | video_set_runtime_v1 | smoke_equivalent | 600 | 600.0 | true |  | 30.0800 | 120.0783 | 124.8260 | 72.2559 | 55.46 | not_observable | pass_runtime600_clean |
| `20260620_rk3588_8gb_yolo11n_rknn_stability_short_sustained` | rk3588_8gb | rknn | video_set_stability_v1 | short_sustained | 1800 | 1800.0 | true |  | 30.0517 | 118.1514 | 122.7302 | 12.6186 | 49.00 | not_observable | pass |
| `20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained` | rk3588_8gb | rknn | video_set_stability_v1 | acceptance_sustained | 7200 | 7199.0 | true |  | 30.0592 | 118.6353 | 123.4141 | 3.9635 | 57.31 | not_observable | pass_realtime_with_6_drops |
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h` | rk3588_8gb | rknn | astra_s_openni_001 | mixed_camera4h | 14400 | 14400.0 | true |  | 29.6003 | 122.3240 | 125.4860 | 1.9712 | 55.46 | not_observable | pass |
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h` | rk3588_8gb | rknn | video_set_stability_v1 | mixed_video4h | 14400 | 14400.0 | true |  | 30.0521 | 118.7670 | 123.7015 | 1.5607 | 56.38 | not_observable | pass_realtime_with_8_drops_strict_trace_fail_separate |

### RK3588 Resource Trace

| run_id | monitor_log_path | sample_interval_sec | memory_mb_peak | memory_growth_mb_per_hour | temperature_c_avg | temperature_c_peak | power_mode | power_w_avg | power_w_peak | cpu_util_avg | rknpu_util | throttle_events | status |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---:|---|
| `20260620_rk3588_8gb_yolo11n_rknn_stability_short_sustained` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260620_rk3588_8gb_yolo11n_rknn_stability_short_sustained_rknpu.log` | 1 | 326.79 | 12.6186 | 47.4271 | 49.00 | not_recorded | not_observable | not_observable | not_recorded | avg=100%, peak=100%@1GHz | not_observable | pass |
| `20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained_rknpu.log` | 1 | 355.63 | 3.9635 | 52.4234 | 57.31 | not_recorded | not_observable | not_observable | not_recorded | avg=100%, peak=100%@1GHz | not_observable | pass |
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h_rknpu.log` | 1 | 253.95 | 1.9712 | not_recorded | 55.46 | not_recorded | not_observable | not_observable | not_recorded | avg=100%, peak=100%@1GHz | not_observable | pass |
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_rknpu.log` | 1 | 365.42 | 1.5607 | not_recorded | 56.38 | not_recorded | not_observable | not_observable | not_recorded | avg=100%, peak=100%@1GHz | not_observable | pass |

### RK3588 MLPerf-style Summary

#### Scenario

- Task: C++ sustained realtime video inference pipeline
- Board: RK3588 8GB
- Backend/runtime: RKNN
- Execution provider: RKNPU
- Loader API: RKNN C API
- Model: YOLO11n
- Backend artifact: `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn`
- Input source: `astra_s_openni_001` 4h + `video_set_stability_v1` 4h（mixed 8h）
- Pipeline mode: backend_pipeline
- Queue policy: drop_oldest mainline
- Batch / concurrency: batch=1, concurrency=3；三个独立 RKNN context 分别绑定 core0/core1/core2
- Warmup: 30 frames in config
- Repeat / duration: camera 14400 sec + video 14400 sec = total 28800 sec（正式 long_sustained 收口）

#### Quality Gate

| item | value |
|---|---|
| Detection quality | 稳定性 run 不重复评估；COCO2017 artifact 复检通过，BDD100K full80 见 `runtime_benchmark.md` |
| Fixed-input alignment | `superseded_by_bdd100k_labeled_video_quality` |
| Task-level quality | `closed_nonblocking_task_fail`：BDD100K Recall=0.445810<0.50 |
| Frame trace | camera 4h：426245 帧，0 gaps，0 out-of-order，0 drop；video 4h：432750 帧，严格 trace 为 5 gap events/8 帧、0 out-of-order，realtime-policy trace 为 degraded |
| Queue policy | drop_oldest，capacity=8；camera drop rate=0%；video drop rate=0.000018486（8/432758 est） |
| Output validity | pass：camera 426245/426245，video 432750/432750，valid rate=1.0 |
| Pass / Fail | `mixed_8h_pass_realtime_with_negligible_drop_task_quality_fail` |

#### Performance

| metric | value |
|---|---:|
| camera 4h p50 / p95 / p99 latency | 107.4570 / 122.3240 / 125.4860 ms |
| camera 4h FPS | 29.6003 |
| video 4h p50 / p95 / p99 latency | 103.9450 / 118.7670 / 123.7015 ms |
| video 4h FPS | 30.0521 |
| video 4h drop frame rate | 0.000018486（8/432758 est） |

#### Resource

| metric | value |
|---|---:|
| camera 4h memory peak / growth | 253.95 MB / 1.9712 MB/h |
| video 4h memory peak / growth | 365.42 MB / 1.5607 MB/h |
| temperature max | camera 55.46 C；video 56.38 C |
| power mode / power | not_recorded / not_observable |
| CPU/GPU/NPU/BPU utilization | CPU not_recorded / GPU N/A / RKNPU avg=100%, peak=100%@1GHz |
| CPU fallback | false |

#### Reproducibility

- Environment baseline: `20260611_rk3588_8gb_env_baseline`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn`
- Command: `RUN_GROUP_ID=20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h INFERENCE_WORKERS=3 SAVE_OUTPUT_VIDEO=0 PREVIEW_WINDOW_CAMERA=auto PREVIEW_WINDOW_VIDEO=off PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_8h_mixed.sh`
- Camera raw / summary / runtime / monitor:
  - `benchmark/raw/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h.jsonl`
  - `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h_summary.csv`
  - `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h.log`
  - `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h_rknpu.log`
- Video raw / summary / runtime / monitor:
  - `benchmark/raw/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h.jsonl`
  - `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_summary.csv`
  - `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h.log`
  - `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_rknpu.log`
- Video strict trace: `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_trace_check.md`
- Video realtime-policy trace: `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_trace_check_realtime_policy.md`
- Related run: `projects/03_video_pipeline/runs/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h/run.md`
- Related troubleshooting: `P3-TRB-20260618-RK3588-005`, `P3-TRB-20260620-012`, `P3-TRB-20260621-013`

### RK3588 8h Mixed Update（2026-06-23）

- Command: `RUN_GROUP_ID=20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h INFERENCE_WORKERS=3 SAVE_OUTPUT_VIDEO=0 PREVIEW_WINDOW_CAMERA=auto PREVIEW_WINDOW_VIDEO=off PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_8h_mixed.sh`
- Group run: `projects/03_video_pipeline/runs/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h/run.md`
- Camera raw/log/monitor:
  - `benchmark/raw/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h.jsonl`
  - `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h.log`
  - `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h_rknpu.log`
- Video raw/log/monitor:
  - `benchmark/raw/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h.jsonl`
  - `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h.log`
  - `logs/monitor/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_rknpu.log`
- Video strict trace: `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_trace_check.md`
- Video realtime-policy trace: `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_trace_check_realtime_policy.md`
- Video stability aggregate: `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h_stability.csv`

结论：

1. camera 4h：`426245` 帧，`29.6003 FPS`，`frame_id_gaps=0`，`frame_id_out_of_order=0`，`drop_frame_count_total_estimated=0`，`memory_peak=253.95 MB`，`temperature_c_peak=55.46 C`，状态 `pass`。
2. video 4h：`432750` 帧，`30.0521 FPS`，严格 trace 记录 `5` 个 gap event、共 `8` 帧，`frame_id_out_of_order=0`，聚合丢帧率 `1.8486e-05`，`dropped_frame_reason=queue_full`，`memory_peak=365.42 MB`，`temperature_c_peak=56.38 C`。
3. 该 video 4h 的 realtime-policy trace 为 `degraded` 而不是 `fail`；结合 `status_counts={'pass': 432750}`、0 out-of-order、runtime log 无 `error/timeout/reset/OOM/CPU fallback`、monitor log 无新增 RKNPU dmesg 异常，当前应按 `pass_realtime_with_negligible_drop` 收口。
4. 因此，RK3588 长稳正式口径更新为：`8h mixed（camera 4h + video 4h）已完成，实时稳定性通过；严格 zero-gap trace 失败证据保留，但不再覆盖实时策略结论`。

## Failure During Stability

| run_id | failure_log_path | error_code | stage | expected_behavior | actual_behavior | recovery_action | stop_reason | related_troubleshooting_id | status |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  | not_executed |

## MLPerf-style Summary

### Scenario

- Task: C++ sustained realtime video inference pipeline
- Board: Jetson 8GB
- Backend/runtime: TensorRT
- Execution provider: TensorRT-GPU
- Loader API: TensorRT C++ API
- Model: YOLO11n
- Backend artifact: `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine`
- Backend artifact SHA256: `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d`
- Input source: `video_set_stability_v1`
- Pipeline mode: backend_pipeline
- Queue policy: drop_oldest mainline
- Batch / concurrency: batch=1, concurrency=1
- Warmup: 30 frames in config
- Repeat / duration: smoke 600 sec; short 1800 sec; acceptance 7200 sec

### Quality Gate

| item | value |
|---|---|
| Detection quality | `not_reexecuted_in_stability_run`，正式口径参考 `runtime_benchmark.md` |
| Fixed-input alignment | `pass` |
| Task-level quality | `quality_threshold_fail` |
| Quality alignment exemption | `not_applicable` |
| Frame trace | `degraded_startup_gap_only` |
| Queue policy | `drop_oldest` mainline，当前稳定性默认口径为 `SAVE_OUTPUT_VIDEO=0` |
| Output validity | `pass_1.0` |
| Pass / Fail | `stability_pass_quality_not_closed_live_source_pending` |

### Performance

| metric | value |
|---|---:|
| p50 end-to-end latency | 49.0838 |
| p90 end-to-end latency | 50.66618 |
| p95 end-to-end latency | 52.0953 |
| p99 end-to-end latency | 53.953863 |
| FPS | 30.057254 |
| drop frame rate | 0.0005083 |

### Resource

| metric | value |
|---|---:|
| memory peak | 3920.0 MB |
| memory growth | -170.0 MB/hour |
| temperature max | 60.0 C |
| power mode / power | not_recorded |
| CPU/GPU/NPU/BPU utilization | cpu_avg=24.5810, gpu_avg=22.8475 |
| CPU fallback | false |

### Reproducibility

- Environment baseline: `20260609_jetson_8gb_env_baseline`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine`
- Command: `RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout TIER=acceptance_sustained SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh`
- Raw result: `benchmark/raw/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout.jsonl`
- Processed result: `benchmark/processed/03_video_pipeline/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout_stability.csv`
- Runtime logs: `logs/runtime/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout.log`
- Monitor logs: `logs/monitor/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout_tegrastats.log`
- Failure logs: not_applicable
- Related run: `projects/03_video_pipeline/runs/20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout/run.md`
- Related troubleshooting: `P3-TRB-20260617-005`, `P3-TRB-20260617-007`

## 2026-06-17 Update: Playlist-paced Sustained Runs

本节覆盖已经同步回本地并重新核验的 playlist-paced sustained run。和此前的 `video_long_loop_001` 单文件高压灌流不同，这几轮已经明确进入真实播放语义。

### 运行时确认

- `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80.log` 记录：`INPUT_PACING ... input_source_type=video_playlist ... playlist_items=80`
- `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80.log` 记录：`INPUT_PACING ... pacing_mode=source_timestamps_with_fps_fallback`
- `frame_id` 推进速度已恢复到接近源视频帧率：
  - smoke：`18048 / 596.0 ≈ 30.3 FPS`
  - short：`54093 / 1797.0 ≈ 30.1 FPS`
  - acceptance：`216402 / 7196.0 ≈ 30.1 FPS`

### 结果汇总

| run_id | duration_sec_estimated | fps_estimated | input_frames_estimated | drop_frame_count_total_estimated | drop_frame_rate_total_estimated | frame_keep_rate_estimated | output_p50_ms | inference_p50_ms | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80` | 596.0 | 25.2164 | 18048 | 3019 | 0.1673 | 0.8327 | 38.3934 | 9.7622 | `pass_with_drop_oldest_degraded_trace` |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80` | 1797.0 | 26.1241 | 54093 | 7148 | 0.1321 | 0.8679 | 37.0924 | 9.7470 | `pass_with_drop_oldest_degraded_trace` |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80` | 7196.0 | 25.7510 | 216402 | 31098 | 0.1437 | 0.8563 | 37.6594 | 9.7642 | `pass_with_drop_oldest_degraded_trace` |

### 当前解读

- 03H 的 playlist-paced sustained run 已经真正执行成功，之前的 `fixed_locally_pending_board_verification` 可以结束。
- 当前 sustained 问题不再是输入节流语义错误，而是 output 路径持续慢于 `30 FPS` 帧预算。
- acceptance run 虽然已经跑到目标时长附近，但由于主线策略是 `drop_oldest`，且 trace 仍有 `frame_id_gaps`，它是“实时低延迟 sustained 证据”，不是 no-drop sustained 证据。
- 从当前指标看，下一步最直接的对照实验应该是关闭 `SAVE_OUTPUT_VIDEO`，隔离 output 开销。

## 2026-06-17 Update: No-output Smoke Confirmation

`20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` 已经完成，并且进一步确认了 output 路径是主瓶颈。

| metric | `smoke_playlist80` | `smoke_playlist80_noout` | delta |
|---|---:|---:|---:|
| fps_estimated | 25.2164 | 30.1091 | +4.8927 |
| drop_frame_rate_total_estimated | 0.1673 | 0.00571 | -0.1616 |
| frame_keep_rate_estimated | 0.8327 | 0.9943 | +0.1616 |
| frame_id_gaps | 2834 | 1 | -2833 |
| output_p50_ms | 38.3934 | 0.0364 | -38.3570 |
| latency_p50_ms | 88.1575 | 50.6552 | -37.5023 |
| queue_postprocess_p95 | 8.0 | 0.0 | -8.0 |

结论：

- 在 sustained smoke 场景下，关闭输出视频后的效果与 runtime600 A/B 对照一致。
- 当前 `drop_oldest` 主线下的大部分丢帧并非来自输入 pacing 问题，也不是 inference 吞吐不足，而是输出视频写盘路径过慢。
- 因此，后续 stability 默认应以 `SAVE_OUTPUT_VIDEO=0` 作为主测口径；如需留样视频，应单独显式开启。

## 2026-06-18 Update: No-output Short And Acceptance Completed

`20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` 和 `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` 已同步回本地并完成复核。虽然当前桌面日期是 `2026-06-18`，但 Jetson 侧生成 `RUN_ID` 时仍使用了 `2026-06-17`，因此文件名前缀保持为 `20260617`。

| run_id | target_duration_sec | actual_duration_sec | fps_estimated | drop_frame_rate_total_estimated | frame_keep_rate_estimated | output_p50_ms | trace_gap_count | status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | 1800 | 1797.0 | 30.0395 | 0.00207 | 0.99793 | 0.0391 | 1 | `pass_noout_baseline` |
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | 7200 | 7196.0 | 30.0573 | 0.00051 | 0.99949 | 0.0370 | 1 | `pass_noout_baseline` |

补充解读：

- 两轮都已经达到 `98%` 完成阈值，因此可以按既定标准记为 completed。
- trace 仍为 `degraded`，但两轮都只剩启动阶段单个 gap：
  - short：`0 -> 113`
  - acceptance：`0 -> 111`
- 在不保存输出视频的默认口径下，Jetson 8GB 已经能够长期稳定跟上这组约 `30 FPS` 的 playlist 输入。
- 因此，03H 当前可以正式收口为：`playlist-paced + SAVE_OUTPUT_VIDEO=0` 的 smoke、short、acceptance 三档稳定性基线已验证完成。

## 2026-06-18 Update: `block_with_timeout(33ms)` Smoke Contrast

`20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` 已同步回本地并完成复核。该 run 使用：

- `TIER=smoke`
- `QUEUE_POLICY=block_with_timeout`
- `QUEUE_PUSH_TIMEOUT_MS=33`
- `SAVE_OUTPUT_VIDEO=0`
- `pace_video_file=1`
- `video_set_stability_v1`（80 视频 playlist）

与默认 noout smoke 基线 `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` 的对比如下：

| metric | `smoke_playlist80_noout` (`drop_oldest`) | `smoke_block_timeout` | delta |
|---|---:|---:|---:|
| fps_estimated | 30.1091 | 30.1023 | -0.0068 |
| drop_frame_count_total_estimated | 103 | 107 | +4 |
| drop_frame_rate_total_estimated | 0.00571 | 0.00593 | +0.00022 |
| frame_keep_rate_estimated | 0.99429 | 0.99407 | -0.00022 |
| latency_p50_ms | 50.6552 | 49.0913 | -1.5639 |
| latency_p95_ms | 52.7732 | 51.9486 | -0.8246 |
| queue_max | 7 | 8 | +1 |
| frame_id_gaps | 1 | 3 | +2 |
| memory_mb_peak | 2317.0 | 2187.0 | -130.0 |
| memory_growth_mb_per_hour | 308.0 | 145.0 | -163.0 |
| cpu_util_avg | 25.3612 | 24.3614 | -0.9998 |

这轮的正确解读是：

- 它再次证明 `block_with_timeout(33ms)` 已经真正生效，不再是“名义切换、实际未切换”的无效 run。
- 在 `video_set_stability_v1` 的 smoke 场景里，`block_with_timeout` 没有像 `runtime600 + video_set_runtime_v1` 那样继续改善总体丢帧：
  - 总丢帧 `107`，略差于 `drop_oldest` 基线的 `103`
  - trace gap `3`，高于基线的 `1`
- 但它也表现出一些局部优势：
  - p50 / p95 延迟略低
  - memory peak、memory growth、CPU 利用率略低

因此当前最准确的工程结论是：

- `block_with_timeout(33ms)` 仍然可以保留为候选策略；
- 但证据已经从“runtime600 单点更优”变成“不同视频集下表现不完全一致”；
- 这进一步说明**现在还不能把默认主线从 `drop_oldest` 直接切到 `block_with_timeout`**。

## RDK X5 BPU 稳定性计划

RDK X5 的 smoke / short / acceptance sustained 三档项目三 C++ BPU 长稳产物已经在 `2026-06-24` 回传。和 runtime 一样，需要补充一条口径：

- 板端原始 `run.md` 中的 `schema_check_exit_code=1` 来自旧 schema 对 `video_playlist` 的误判。
- 当前仓库 schema 已允许 `video_playlist`；同步后重跑的 schema check 现为 `pass`。
- 因此这三档稳定性 run 可以进入正式稳定性表，但 frame trace 仍需按真实结果记录为 `degraded`，因为 `drop_oldest` 主线下存在大量 `queue_full` 解释型 gap。

| tier | duration_sec | command | raw result | runtime log | monitor log | status |
|---|---:|---|---|---|---|---|
| smoke | 600 | `TIER=smoke bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke.jsonl` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke_bpu.log` | board_run_synced |
| short_sustained | 1800 | `TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained.jsonl` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained_bpu.log` | board_run_synced |
| acceptance_sustained | 7200 | `TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained.jsonl` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained_bpu.log` | board_run_synced |
| long_sustained | 28800 | `TIER=long_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/<run_id>.jsonl` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/<run_id>.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/<run_id>_bpu.log` | not_executed |

`2026-06-30` 又补齐了一条比默认 playlist 更贴近正式实时源的稳定性证据：

- `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained`
- 输入源固定为 `imx219_rdkx5_hbn_001`
- 线程拓扑固定为 `2 infer / 2 postprocess`
- `actual_duration_sec=1798.0`
- `fps=30.3921`
- `drop_frame_rate=0.0`
- `frame_id_gaps=0`
- `trace_check=pass`

### RDK X5 Stability Summary

| run_id | target | backend_runtime | input_source_id | stability_tier | target_duration_sec | actual_duration_sec | completed | stop_reason | fps_avg | p95_latency_ms | p99_latency_ms | memory_growth_mb_per_hour | temperature_c_peak | throttle_events | evidence_scope | status |
|---|---|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | rdk_x5_8gb | bpu | `coco2017_val2017_images` | runtime_reference_only | 0 | 783.828 | true | dataset_completed | 6.572482 | 207.65165 | 264.906608 |  | 57.067 | not_observable | reference_from_project2_only | reference_from_project2_only |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke` | rdk_x5_8gb | bpu | `video_set_stability_v1` | smoke | 600 | 600.0 | true | duration_reached | 18.1367 | 170.5050 | 178.4508 | 77.6608 | 67.032 | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained` | rdk_x5_8gb | bpu | `video_set_stability_v1` | short_sustained | 1800 | 1800.0 | true | duration_reached | 18.3172 | 167.4585 | 173.0032 | 6.9688 | 67.765 | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | rdk_x5_8gb | bpu | `video_set_stability_v1` | acceptance_sustained | 7200 | 7200.0 | true | duration_reached | 18.4794 | 166.5849 | 172.3195 | 0.3597 | 67.961 | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` | rdk_x5_8gb | bpu | `imx219_rdkx5_hbn_001` | short_sustained | 1800 | 1798.0 | true | duration_reached | 30.3921 | 165.8410 | 169.9096 | 3.6314 | 72.846 | not_observable | project3_cpp_live_source_short_sustained_synced_back | pass_live_source_short_sustained_mainline |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` | rdk_x5_8gb | bpu | `imx219_rdkx5_hbn_001` | acceptance_sustained | 7200 | 7198.0 | true | duration_reached | 30.3865 | 165.4440 | 169.4286 | 4.2382 | 72.113 | not_observable | project3_cpp_live_source_acceptance_sustained_synced_back | pass_live_source_acceptance_sustained_mainline |

### RDK X5 Resource Trace

| run_id | monitor_log_path | sample_interval_sec | memory_mb_peak | memory_growth_mb_per_hour | temperature_c_avg | temperature_c_peak | power_mode | power_w_avg | power_w_peak | cpu_util_avg | bpu_devfreq_mhz | bpu_load | throttle_events | evidence_scope | status |
|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---|---:|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | `logs/monitor/02_quantization/rdk_x5_8gb/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor_resource_monitor.jsonl` | 1 | 1146.219 system / 443.75 process_hwm |  |  | 57.067 | `performance / fixed fan if available` | not_available | not_available | 16.748267 | 996.0 | not_readable | not_observable | reference_from_project2_only | reference_from_project2_only |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke_bpu.log` | 1 | 241.402 process_hwm | 77.6608 | not_recorded | 67.032 | `not_recorded` | not_recorded | not_recorded | not_recorded | 996.0 | `not_readable (bpu_load_path=not_found)` | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained_bpu.log` | 1 | 241.793 process_hwm | 6.9688 | not_recorded | 67.765 | `not_recorded` | not_recorded | not_recorded | not_recorded | 996.0 | `not_readable (bpu_load_path=not_found)` | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained_bpu.log` | 1 | 238.793 process_hwm | 0.3597 | not_recorded | 67.961 | `not_recorded` | not_recorded | not_recorded | not_recorded | 996.0 | `not_readable (bpu_load_path=not_found)` | not_observable | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained_bpu.log` | 1 | 137.777 process_hwm | 3.6314 | not_recorded | 72.846 | `not_recorded` | not_recorded | not_recorded | not_recorded | 996.0 | `not_readable (bpu_load_path=not_found)` | not_observable | project3_cpp_live_source_short_sustained_synced_back | pass_live_source_short_sustained_mainline |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_bpu.log` | 1 | 142.758 process_hwm | 4.2382 | not_recorded | 72.113 | `not_recorded` | not_recorded | not_recorded | not_recorded | 996.0 | `not_readable (bpu_load_path=not_found)` | not_observable | project3_cpp_live_source_acceptance_sustained_synced_back | pass_live_source_acceptance_sustained_mainline |

### RDK X5 Queue / Drop Trend

| run_id | window_sec | queue_capture_p95 | queue_preprocess_p95 | queue_infer_p95 | queue_postprocess_p95 | queue_max | drop_frame_count | drop_frame_rate | dropped_frame_reason | latency_trend | evidence_scope | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke` | 60 | 0.0 | 8.0 | 0.0 | 0.0 | 8 | 7166 | 0.3971 | `queue_full` | `p95=170.5050, degraded trace, 0 out-of-order` | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained` | 60 | 0.0 | 8.0 | 0.0 | 0.0 | 8 | 21122 | 0.3905 | `queue_full` | `p95=167.4585, degraded trace, 0 out-of-order` | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | 60 | 0.0 | 8.0 | 0.0 | 0.0 | 8 | 83350 | 0.3852 | `queue_full` | `p95=166.5849, degraded trace, 0 out-of-order` | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` | 60 | 0.0 | 1.0 | 0.0 | 0.0 | 1 | 0 | 0.0000 | `none` | `p95=165.8410, trace pass, 0 out-of-order` | project3_cpp_live_source_short_sustained_synced_back | pass_live_source_short_sustained_mainline |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` | 60 | 0.0 | 1.0 | 0.0 | 0.0 | 1 | 0 | 0.0000 | `none` | `p95=165.4440, trace pass, 0 out-of-order` | project3_cpp_live_source_acceptance_sustained_synced_back | pass_live_source_acceptance_sustained_mainline |

### RDK X5 Stability Events

| run_id | restart_count | reconnect_count | crash_count | watchdog_count | input_disconnect_count | backend_error_count | output_error_count | recovery_success_count | max_recovery_time_sec | failure_log_path | related_troubleshooting_id | evidence_scope | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_applicable | `not_applicable` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_applicable | `not_applicable` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_applicable | `not_applicable` |  | project3_cpp_board_run_synced_back | pass |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_applicable | `not_applicable` | `P3-TRB-20260629-016` | project3_cpp_live_source_short_sustained_synced_back | pass_live_source_short_sustained_mainline |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_applicable | `not_applicable` | `P3-TRB-20260629-016` | project3_cpp_live_source_acceptance_sustained_synced_back | pass_live_source_acceptance_sustained_mainline |

### 2026-06-30 Update: RDK X5 IMX219 live-source `short_sustained`

这轮 `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` 的意义不是重复 playlist `short_sustained`，而是把 `20260629` 已选定的实时摄像头正式主线 `2 infer / 2 postprocess + rotate180 + PREVIEW_WINDOW=off` 延长到 `1798s`。

| item | value |
|---|---|
| run_id | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` |
| input_source_id | `imx219_rdkx5_hbn_001` |
| input_source_type | `mipi_camera_hbn` |
| workers | `2 infer / 2 postprocess` |
| actual_duration_sec | `1798.0` |
| fps | `30.3921` |
| p95 / p99 latency | `165.8410 / 169.9096 ms` |
| drop_frame_rate | `0.0000` |
| frame_id_gaps / out_of_order | `0 / 0` |
| memory_peak / growth | `137.777 MB / 3.6314 MB/h` |
| max_temp_c from monitor log | `72.846` |
| queue_max | `1` |
| schema / trace / stability | `pass / pass / pass` |

补充说明：

- 这轮同步回来的 `schema_check.md` 当前已经是 `pass`，因此 03H live-source `short_sustained` 的权威结论不再受旧 `mipi_camera_hbn` schema 误报影响。
- 历史 `run.md` 中出现的 `LOOP_VIDEO_FILE=1 / PACE_VIDEO_FILE=1` 只是旧 wrapper 对 file/playlist 参数的默认记录；runtime log 已明确写出 `input_source_type=mipi_camera_hbn`、`pace_video_file=false`、`playlist_input=false`。
- 这轮结果说明 `20260629` 收敛出的 `2 infer / 2 postprocess` 不只是 `59s` 的短跑优化，而是已经具备 `30 分钟` 级实时稳定性。

### 2026-06-30 Update: RDK X5 IMX219 live-source `acceptance_sustained`

这轮 `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` 则把同一条 live-source 正式主线继续延长到 `7198s`，对应项目三 `03H` 的 `2 小时` 验收口径。

| item | value |
|---|---|
| run_id | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` |
| input_source_id | `imx219_rdkx5_hbn_001` |
| input_source_type | `mipi_camera_hbn` |
| workers | `2 infer / 2 postprocess` |
| actual_duration_sec | `7198.0` |
| fps | `30.3865` |
| p95 / p99 latency | `165.4440 / 169.4286 ms` |
| drop_frame_rate | `0.0000` |
| frame_id_gaps / out_of_order | `0 / 0` |
| memory_peak / growth | `142.758 MB / 4.2382 MB/h` |
| max_temp_c from monitor log | `72.113` |
| queue_max | `1` |
| schema / trace / stability | `pass / pass / pass` |

补充说明：

- 板端同步回来的 `run.md` 仍保留 `final_exit=3`，原因是当时写入的 `schema_check.md` 仍属于旧 postcheck 结果；当前仓库下对同一 raw 的 `schema_check.md` 已按现行 schema 本地重验为 `pass`。
- runtime log 已明确记录 `INFERENCE_WORKERS: count=2`、`POSTPROCESS_WORKERS: count=2`、`INPUT_ORIENTATION_CORRECTION ... rotate180` 与 `INPUT_PACING ... pace_video_file=false`。
- 至此，RDK X5 IMX219 live-source 的 `short_sustained` 与 `acceptance_sustained` 两档 sustained 证据都已补齐，`03H` 的实时摄像头主线验收口径可以按 `2 infer / 2 postprocess + rotate180 + PREVIEW_WINDOW=off` 正式收口。

### RDK X5 MLPerf-style Summary

#### Scenario

- Task: C++ sustained realtime video inference pipeline
- Board: RDK X5 8GB
- Backend/runtime: BPU
- Execution provider: BPU
- Loader API: Horizon hbDNN C API
- Model: YOLO11n split-head INT8 PTQ
- Backend artifact: `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin`
- Input source: `imx219_rdkx5_hbn_001`
- Input type / path: `mipi_camera_hbn` / `srcampy://video_idx0`
- Orientation correction: `rotate180`
- Pipeline mode: `backend_pipeline`
- Queue policy: `drop_oldest` mainline
- Workers: `2 infer / 2 postprocess`
- Batch / concurrency: batch=1, concurrency=1
- Warmup: 30 frames in config
- Repeat / duration: 当前正式 live-source acceptance run 为 `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained`，`actual_duration_sec=7198.0`
- Playlist reference: `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` 继续保留为 video playlist sustained baseline

#### Quality Gate

| item | value |
|---|---|
| Detection quality | `reference_from_project2_only`：COCO2017 `mAP50_95=0.36855805289535165` |
| Fixed-input alignment | `pending_live_source_prepost_pass_only` |
| Task-level quality | `reference_from_project2_only` |
| Frame trace | `pass_218722_frames_0_gap` |
| Queue policy | `drop_oldest` realtime bounded queue |
| Output validity | `pass_1.0` |
| Pass / Fail | `pass_live_source_acceptance_sustained_task_quality_pending` |

#### Performance

| metric | value |
|---|---:|
| p50 end-to-end latency | 141.4790 |
| p90 end-to-end latency | 163.2220 |
| p95 end-to-end latency | 165.4440 |
| p99 end-to-end latency | 169.4286 |
| FPS | 30.3865 |
| drop frame rate | 0.0000 |
| frame gap | 0 |

#### Resource

| metric | value |
|---|---:|
| memory peak | 142.758 process_hwm MB |
| memory growth | 4.2382 MB/hour |
| temperature max | 72.113 C |
| power mode / power | not_recorded |
| CPU/GPU/NPU/BPU utilization | `bpu_devfreq=996 MHz`, `ddr=4266 MHz`, `gpu=996 MHz`, `bpu_load_path=not_found` |
| throttle events | `not_observable` |

#### Reproducibility

- Environment baseline: `20260612_rdk_x5_8gb_env_baseline`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin`
- Command: `RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained TIER=acceptance_sustained INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 SRCAMPY_VIDEO_IDX=0 SRCAMPY_WIDTH=640 SRCAMPY_HEIGHT=640 SRCAMPY_SENSOR_WIDTH=1920 SRCAMPY_SENSOR_HEIGHT=1080 SRCAMPY_FPS=30 SRCAMPY_WARMUP=10 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh`
- Raw result: `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained.jsonl`
- Processed summary: `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_summary.csv`
- Stability result: `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_stability.csv`
- Schema check: `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_schema_check.md`
- Trace check: `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_trace_check.md`
- Runtime logs: `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained.log`
- Monitor logs: `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_bpu.log`
- Related run: `projects/03_video_pipeline/runs/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained/run.md`
- Related troubleshooting: `P3-TRB-20260629-016`

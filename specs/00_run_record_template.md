# 项目三 run 记录模板

本模板用于项目三每一次环境基线、单线程 demo、多线程 pipeline、队列策略、端侧后端、异常注入、服务化、稳定性测试和最终汇总。执行者可以增加字段，但不能删除下面的硬性字段。

项目三统一使用目录式 run：

```text
projects/03_video_pipeline/runs/<run_id>/run.md
```

每个 run 可包含：

```text
projects/03_video_pipeline/runs/<run_id>/
  run.md
  outputs/
  config_snapshot/
  notes.md
```

`status` 只能使用：

```text
pass
fail
degraded
blocked
not_executed
not_verified
```

状态语义：

| status | 使用条件 | 能否进入正式 runtime/stability 总表 | 后续要求 |
|---|---|---|---|
| `pass` | raw、run、模型、输入源、runtime log、monitor log、后端证据和质量检查完整 | 可以 | 可作为正式结论引用 |
| `fail` | 构建、运行、后端加载、输入源、服务或稳定性失败 | 不可以 | 必须进入问题库 |
| `degraded` | 可运行但资源、稳定性、后端证据、监控或质量检查不完整 | 可以，但必须显著标注 | 必须说明影响和恢复路径 |
| `blocked` | 缺硬件、视频源、权限、驱动、工具链或外部条件 | 只能进入状态表 | 必须说明恢复条件 |
| `not_executed` | 可选路线尚未执行，且不是失败 | 只能进入状态表 | 必须说明未执行原因 |
| `not_verified` | 已有结果但缺 schema、输入源 hash、模型 hash、日志、monitor 或后端调用证据 | 只能进入状态表 | 补齐证据后重新生成 run |

## YAML 记录区

```yaml
run_id:
date:
spec_ref:
stage:
status:

environment:
  environment_baseline_id:
  target:
  board:
  os:
  runtime_versions:
  driver_versions:
  power_mode:
  cooling:

project_dependencies:
  project1_model_ref:
  project2_model_ref:
  source_project:
  source_run_id:
  source_report_path:

model:
  model_name: yolo11n
  backend_runtime:
  precision_or_quantization:
  backend_artifact_path:
  backend_artifact_format:
  backend_artifact_sha256:
  loader_api:
  execution_provider:
  runtime_evidence_path:
  accelerator_evidence_path:
  cpu_fallback:
  fallback_reason:

input_source:
  input_source_id:
  input_source_type:
  uri:
  video_sha256:
  codec:
  width:
  height:
  fps:
  duration_sec:
  frame_count:
  bitrate:
  loop_mode:
  timestamp_source:
  availability:

pipeline:
  pipeline_mode:
  thread_model:
  stages:
  queue_policy:
  queue_capacity:
  buffer_reuse:
  buffer_pool_size:
  output_mode:

configs:
  pipeline_config:
  pipeline_config_sha256:
  stream_config:
  stream_config_sha256:
  model_config:
  model_config_sha256:
  board_config:
  board_config_sha256:

commands:
  - name:
    command:
    cwd:
    log_path:
    exit_code:

outputs:
  raw_result_path:
  processed_result_path:
  runtime_log_path:
  monitor_log_path:
  failure_log_path:
  output_sample_path:
  output_video_path:

performance:
  duration_sec:
  warmup_sec:
  fps:
  p50_end_to_end_latency_ms:
  p90_end_to_end_latency_ms:
  p95_end_to_end_latency_ms:
  p99_end_to_end_latency_ms:
  drop_frame_rate:
  trace_check_path:

resource:
  memory_mb:
  memory_growth_mb:
  temperature_c:
  power_w:
  power_mode:
  utilization:
  throttle_events:

stability:
  stability_tier:
  target_duration_sec:
  actual_duration_sec:
  completed:
  stop_reason:
  restart_count:
  reconnect_count:
  crash_count:
  watchdog_timeout_count:

service:
  service_mode:
  service_start_status:
  service_restart_status:
  service_stop_status:
  journal_log_path:

failure_recovery:
  case_id:
  stage:
  expected_behavior:
  actual_behavior:
  recovery_action:
  max_recovery_time_sec:
  reconnect_count:
  frame_id_continuity_after_recovery:
  drop_frame_reason_after_recovery:
  service_status:
  failure_schema_path:

issues:
  related_troubleshooting_id:
  notes:
```

## 文字说明区

### 目的

说明本次 run 验证什么，例如单线程最小链路、多线程队列策略、Jetson TensorRT pipeline、BPU 稳定性 2 小时、异常注入或最终汇总。

### 关键差异

如果本次 run 与主线配置不同，必须说明差异和原因，例如输入源、队列策略、buffer pool、后端精度、电源模式、监控不可读或服务化方式变化。

### 结论

写清楚是否达到对应 spec 验收标准。`fail`、`degraded`、`not_verified` 必须说明缺失证据、影响范围和后续动作。

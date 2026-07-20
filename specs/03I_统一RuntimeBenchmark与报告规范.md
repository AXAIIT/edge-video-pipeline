# 03I_统一RuntimeBenchmark与报告规范

## 适用范围

本规范用于项目三所有 pipeline 实验完成后的汇总阶段：

```text
raw result 校验
-> pipeline trace 校验
-> 选择最新有效 run
-> runtime 指标聚合
-> stability 指标聚合
-> failure/service 辅助汇总
-> video_pipeline.md
-> runtime_benchmark.md
-> stability_report.md
-> failure_and_fallback.md
-> runbook.md
```

它解决的问题是：别人拿到项目三结果时，能否从最终报告反向追溯到每一次 run、输入源、配置、命令、日志、raw result 和问题库。

## 执行原则

下面的校验、聚合和报告生成命令是推荐路径，不是唯一实现。可以替换 schema 工具、聚合脚本、可视化方式或报告生成方式，但不能降低证据要求：最终报告中的每个结论都必须能追溯到 run、配置、日志、raw result、monitor 结果和问题库。替代路径必须写入汇总 run，并同步更新 `benchmark/processed/03_video_pipeline/` 与 `projects/03_video_pipeline/reports/`。

## 路径口径

本 spec 使用当前仓库结构：

- run 记录放在 `projects/03_video_pipeline/runs/`。
- run 模板使用 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- pipeline 配置放在 `projects/03_video_pipeline/configs/pipeline/`。
- stream 配置放在 `projects/03_video_pipeline/configs/streams/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/`，按开发板分子目录；raw 只接受 frame-level 记录。
- processed result 放在 `benchmark/processed/03_video_pipeline/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/`。
- monitor 日志放在 `logs/monitor/03_video_pipeline/`。
- failure 日志放在 `logs/failures/03_video_pipeline/`。
- 报告放在 `projects/03_video_pipeline/reports/`。

## 前置条件

至少完成：

- `03A_单线程最小Demo规范.md`
- `03B_多线程Pipeline规范.md`
- `03C_队列限流与Buffer复用规范.md`
- 至少一个后端集成 spec：`03D`、`03E` 或 `03F`
- `03G_异常恢复与服务化部署规范.md`
- `03H_稳定性监控规范.md`

如果某块板卡或某个后端暂不可用，必须在对应 run 记录、状态表和问题库条目中说明原因。该状态只影响该板卡或后端的正式结论，不作为其他开发板执行、补测或汇总的前置阻塞。

## 输入

| 输入 | 路径 |
|---|---|
| run 记录 | `projects/03_video_pipeline/runs/**/run.md` |
| run 模板 | `projects/03_video_pipeline/specs/00_run_record_template.md` |
| raw schema | `benchmark/schemas/video_pipeline_raw_schema.yaml` |
| failure schema | `benchmark/schemas/video_pipeline_failure_schema.yaml` |
| raw result | `benchmark/raw/03_video_pipeline/**/*.jsonl` 或 `.csv` |
| processed result | `benchmark/processed/03_video_pipeline/` |
| pipeline 配置 | `projects/03_video_pipeline/configs/pipeline/*.yaml` |
| stream 配置 | `projects/03_video_pipeline/configs/streams/*.yaml` |
| runtime 日志 | `logs/runtime/03_video_pipeline/**/*` |
| monitor 日志 | `logs/monitor/03_video_pipeline/**/*` |
| failure 日志 | `logs/failures/03_video_pipeline/**/*` |
| 问题记录 | `projects/03_video_pipeline/reports/troubleshooting.md` |

## 执行步骤

### 1. 校验 raw result 字段

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/benchmark/validate_pipeline_raw_schema.py \
  --input benchmark/raw/03_video_pipeline \
  --schema benchmark/schemas/video_pipeline_raw_schema.yaml \
  --output benchmark/processed/03_video_pipeline/schema_check_report.md
```

必须检查：

- raw result 每行是否表示一帧，是否包含 `frame_id`。
- 是否包含 frame_id、阶段耗时、端到端耗时、队列长度、丢帧率。
- 是否包含 backend、board、model、input_source、backend artifact、loader API 和 execution_provider。
- 是否包含资源字段和状态字段。
- 是否包含 `runtime_evidence_path`、`accelerator_evidence_path`、`cpu_fallback`。
- 模型 artifact、后端 wrapper、前处理、后处理、输出解析或 NMS 变化时，是否包含 `change_type`、`fixed_input_alignment_status`、`task_level_quality_status` 和 baseline/current artifact 引用。
- 如果本次只是队列、日志、监控、服务或报告聚合变化，是否包含 `quality_alignment_exemption` 及不影响输出的说明。
- 失败或 degraded 记录是否有 `related_troubleshooting_id`。

raw result 必须包含 `measurement_scope: frame`。窗口级统计、FPS、p50/p90/p95/p99、memory growth、runtime summary 和 stability summary 不进入 raw result，必须从 frame-level raw 和 monitor log 聚合生成。

派生指标生成规则：

| derived metric | source |
|---|---|
| `fps` | 从 frame timestamp、有效输出帧数和运行时长聚合 |
| `p50/p90/p95/p99_end_to_end_latency_ms` | 从逐帧 `end_to_end_latency_ms` 聚合 |
| `memory_growth_mb` | 从 monitor log 内存曲线聚合 |
| `throttle_events` | 从 monitor log 或板卡 runtime 日志聚合 |

### 2. 选择最新有效 run

按下面维度分组选择候选：

```text
board
backend_runtime
input_source_id
pipeline_mode
queue_policy
precision_or_quantization
stability_tier
```

正式 runtime/stability 总表只纳入满足下面条件的 run：

- run 路径为 `projects/03_video_pipeline/runs/<run_id>/run.md`。
- run 对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- raw result 通过 `benchmark/schemas/video_pipeline_raw_schema.yaml` 校验。
- 输入源能追溯到 `projects/03_video_pipeline/configs/streams/` 和 `projects/03_video_pipeline/reports/input_sources.md`。
- 模型路径、格式、SHA256、loader API、execution_provider 完整。
- runtime log、monitor log、frame trace 检查、后端证据和必要的模型变更质量对齐完整，或缺失项已导致状态降级。

状态处理规则：

| status | 汇总处理 |
|---|---|
| `pass` | 可进入正式 runtime/stability 总表 |
| `degraded` | 可进入正式总表，但必须显著标注降级原因 |
| `not_verified` | 不进入正式性能或稳定性结论，只进入状态表 |
| `fail` | 不进入正式结论，必须进入问题库 |
| `blocked` | 不进入正式结论，只进入状态表 |
| `not_executed` | 不进入正式结论，只进入状态表 |

同一分组多个候选时，按下面顺序选择：

1. 优先选择 `status: pass`，其次才是 `degraded`。
2. 优先选择 schema 通过的 run。
3. 优先选择 run 模板完整、输入源 hash 完整、模型 hash 完整、runtime log 完整、monitor log 完整、frame trace 检查通过，并且模型变更质量对齐或豁免记录完整的 run。
4. 优先选择日期最新的 run。
5. 如果仍然并列，选择 `run_id` 字典序最大的 run，并在汇总 run 中说明。

必须生成：

```text
benchmark/processed/03_video_pipeline/excluded_runs.md
```

排除清单至少包含：

```text
run_id
status
excluded_reason
missing_evidence
related_troubleshooting_id
```

### 3. 聚合 runtime 指标

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/benchmark/aggregate_runtime_benchmark.py \
  --input benchmark/raw/03_video_pipeline \
  --run-dir projects/03_video_pipeline/runs \
  --excluded-output benchmark/processed/03_video_pipeline/excluded_runs.md \
  --output benchmark/processed/03_video_pipeline/runtime_summary.csv
```

聚合结果至少包含：

```text
board
run_id
backend_runtime
execution_provider
loader_api
backend_artifact_sha256
change_type
fixed_input_alignment_status
task_level_quality_status
environment_baseline_id
input_source_id
input_source_type
pipeline_mode
queue_policy
queue_capacity
fps
p50_end_to_end_latency_ms
p90_end_to_end_latency_ms
p95_end_to_end_latency_ms
p99_end_to_end_latency_ms
capture_ms
preprocess_ms
inference_ms
postprocess_ms
output_ms
drop_frame_rate
queue_max
memory_mb
temperature_c
cpu_gpu_npu_bpu_utilization
runtime_log_path
monitor_log_path
failure_log_path
cpu_fallback
related_troubleshooting_id
status
```

### 4. 聚合稳定性指标

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/benchmark/aggregate_stability.py \
  --raw benchmark/raw/03_video_pipeline \
  --monitor logs/monitor/03_video_pipeline \
  --output benchmark/processed/03_video_pipeline/stability_summary.csv
```

聚合结果至少包含：

```text
run_id
board
backend_runtime
input_source_id
pipeline_mode
stability_tier
target_duration_sec
actual_duration_sec
completed
stop_reason
restart_count
reconnect_count
crash_count
watchdog_timeout_count
fps
p95_end_to_end_latency_ms
p99_end_to_end_latency_ms
memory_growth_mb
temperature_c
power_w
throttle_events
status
related_troubleshooting_id
```

### 5. 聚合 failure/service 辅助结果

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/benchmark/aggregate_failure_service.py \
  --input logs/failures/03_video_pipeline \
  --schema benchmark/schemas/video_pipeline_failure_schema.yaml \
  --output benchmark/processed/03_video_pipeline/failure_service_summary.csv
```

failure/service 结果是辅助表，不能替代正式 runtime 或 stability 总表。

### 6. 更新项目报告

必须更新：

- `projects/03_video_pipeline/reports/video_pipeline.md`
- `projects/03_video_pipeline/reports/runtime_benchmark.md`
- `projects/03_video_pipeline/reports/stability_report.md`
- `projects/03_video_pipeline/reports/failure_and_fallback.md`
- `projects/03_video_pipeline/reports/runbook.md`
- `projects/03_video_pipeline/reports/troubleshooting.md`

### 7. 写入 MLPerf-style Summary

`projects/03_video_pipeline/reports/runtime_benchmark.md` 和 `projects/03_video_pipeline/reports/stability_report.md` 必须包含或引用：

```markdown
## MLPerf-style Summary

### Scenario
- Task:
- Board:
- Backend/runtime:
- Execution provider:
- Loader API:
- Model:
- Backend artifact:
- Backend artifact SHA256:
- Input source:
- Pipeline mode:
- Queue policy:
- Batch / concurrency:
- Warmup:
- Repeat / duration:

### Quality Gate
- Detection quality:
- Fixed-input alignment:
- Task-level quality:
- Quality alignment exemption:
- Frame trace:
- Queue policy:
- Output validity:
- Pass / Fail:

### Performance
| metric | value |
|---|---:|
| p50 end-to-end latency |  |
| p90 end-to-end latency |  |
| p95 end-to-end latency |  |
| p99 end-to-end latency |  |
| FPS |  |
| drop frame rate |  |

### Resource
| metric | value |
|---|---:|
| memory peak |  |
| memory growth |  |
| temperature max |  |
| power mode / power |  |
| CPU/GPU/NPU/BPU utilization |  |
| CPU fallback |  |

### Reproducibility
- Environment baseline:
- Pipeline config:
- Stream config:
- Model config:
- Backend artifact:
- Command:
- Raw result:
- Processed result:
- Runtime logs:
- Monitor logs:
- Failure logs:
- Related run:
- Related troubleshooting:
```

## 记录要求

- 汇总阶段必须新建 run 记录，例如 `projects/03_video_pipeline/runs/<yyyymmdd>_all_yolo11n_video_pipeline_summary/run.md`。
- schema 校验、有效 run 选择、runtime 聚合、stability 聚合、failure/service 聚合和报告生成命令都必须写入 run。
- schema 校验结果保存到 `benchmark/processed/03_video_pipeline/schema_check_report.md`。
- 聚合表保存到 `benchmark/processed/03_video_pipeline/`。
- 被排除 run 保存到 `benchmark/processed/03_video_pipeline/excluded_runs.md`。
- 最终报告必须引用 raw result、processed result、run 记录、runtime 日志、monitor 日志和 failure 日志。
- 汇总阶段不能修改 `benchmark/raw/` 中的原始结果；如需修正，只能重新生成新的 raw result，并保留旧文件和原因说明。

## 输出文件

| 文件 | 要求 |
|---|---|
| `benchmark/processed/03_video_pipeline/schema_check_report.md` | raw result 字段检查 |
| `benchmark/processed/03_video_pipeline/runtime_summary.csv` | runtime 聚合指标 |
| `benchmark/processed/03_video_pipeline/stability_summary.csv` | stability 聚合指标 |
| `benchmark/processed/03_video_pipeline/window_metrics.csv` | 窗口级 runtime 指标 |
| `benchmark/processed/03_video_pipeline/failure_service_summary.csv` | failure/service 辅助表 |
| `benchmark/processed/03_video_pipeline/excluded_runs.md` | 被排除 run 和原因 |
| `projects/03_video_pipeline/reports/video_pipeline.md` | pipeline 架构和线程模型 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | runtime benchmark |
| `projects/03_video_pipeline/reports/stability_report.md` | sustained 稳定性报告 |
| `projects/03_video_pipeline/reports/failure_and_fallback.md` | 异常恢复和降级 |
| `projects/03_video_pipeline/reports/runbook.md` | 复现步骤 |

## 验收标准

- 每个报告结论都能反向追溯到 run、命令、配置、raw result、monitor 和日志。
- `runtime_benchmark.md` 同时包含端到端、分阶段、队列、丢帧、资源和可复现信息。
- `stability_report.md` 包含 30 分钟和 2 小时测试状态。
- 2 小时测试没完成时必须显示为目标未达成，不能用 30 分钟替代。
- `failure_and_fallback.md` 覆盖断流、模型加载失败、输入尺寸错误、后端异常和服务重启。
- 如果某后端或某测试未完成，报告中必须明确状态：`not_executed`、`blocked`、`degraded`、`not_verified` 或 `fail`。

## 降级和问题库

汇总阶段发现下面情况也要进入问题库：

- raw result 字段不一致，无法横向比较。
- 指标无法追溯到 run。
- runtime 结论与 raw result 不一致。
- 稳定性测试只有截图或日志，没有结构化结果。
- 队列、丢帧或异常恢复状态不明确。
- `runtime_only`、failure/service 辅助结果被误用于正式 runtime/stability 结论。

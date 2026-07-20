# 03F_RDK_X5_BPU_CppPipeline规范

## 适用范围

本规范用于在 RDK X5 8GB 上将项目二已量化完成的 YOLO11n INT8 split-head `.bin` 模型接入项目三 C++ 实时视频流推理 pipeline，并完成端到端 benchmark、稳定性、异常恢复与服务化记录。

本 spec 只定义 RDK X5 BPU 这一条单板执行路线，不把 Jetson 或 RK3588 作为前置条件。RDK X5 直接继承项目二 RDK X5 环境基线和主线 artifact，但项目三仍必须重新生成 C++ pipeline 级 raw result、runtime log、monitor log、failure/service 证据和报告表格，不能把项目二 Python runtime 指标直接写成项目三 C++ `pass`。

## 执行原则

下面的 C++ wrapper、构建命令、monitor 脚本和 benchmark 命令是推荐路径，不是唯一实现。可以替换 BPU runtime 封装、日志库、systemd 模板或资源监控实现，但不能降低证据要求。必须保留：

- 项目二继承环境基线 ID。
- split-head `.bin` artifact 路径与 SHA256。
- C++ build 命令、board/pipeline 配置和 run 记录。
- frame-level raw result、runtime log、monitor log、trace/schema check。
- BPU 调用证据、CPU fallback 判断、资源不可观测原因。
- 异常恢复、service 生命周期和问题记录。

替代路径必须同步写入对应 `projects/03_video_pipeline/runs/`，并回填 `projects/03_video_pipeline/reports/`。

## 路径口径

本 spec 使用当前仓库结构：

- RDK X5 配置放在 `projects/03_video_pipeline/configs/boards/` 和 `projects/03_video_pipeline/configs/pipeline/`。
- 项目三 RDK X5 C++ 入口为 `projects/03_video_pipeline/src/video_pipeline_app.cpp`。
- split-head `.bin` 模型放在 `models/yolo11n/rdk_x5_bpu_split_head/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/rdk_x5_8gb/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/rdk_x5_8gb/`。
- monitor 日志放在 `logs/monitor/03_video_pipeline/rdk_x5_8gb/`。
- failure 日志放在 `logs/failures/03_video_pipeline/rdk_x5_8gb/`。
- build 日志放在 `logs/runtime/03_video_pipeline/build/`。

## 前置条件

- 已完成项目二 RDK X5 环境基线 `20260612_rdk_x5_8gb_env_baseline`。
- 已完成项目二 RDK X5 正式主线 artifact：
  - `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin`
  - SHA256 `2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c`
- 已确认项目三使用的是项目二 split-head + external DFL + class-aware NMS 路线，不再使用 all-in-one `.bin` 作为正式主线。
- 已准备：
  - `projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml`
  - `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml`
  - `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml`
- 已准备固定视频源和实时输入候选源。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- 如复用项目二环境基线，run 中必须显式记录继承的 `environment_baseline_id`，并补充项目三的 C++ build、视频输入、runtime log 和 monitor log。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| backend | `bpu` | 固定字段名 |
| execution_provider | `BPU` | 只有能证明 BPU 推理时填写 |
| loader_api | `Horizon hbDNN C API` | 如使用其他封装，按实际填写 |
| backend_artifact_format | `bin` | 当前主线为 split-head `.bin` |
| precision | `int8_ptq` | 直接继承项目二正式主线 |
| input_contract | `NV12 bytes` | 当前主线输入契约 |
| postprocess_route | `split_head_external_dfl_nms` | 当前主线后处理口径 |
| mainline_workers | `inference_workers=2`、`postprocess_workers=2` | `20260629` IMX219 live-source 优化后正式主线 |
| input_source | video file + realtime source | 至少一种实时源要有计划或状态记录 |
| monitor | x5 devfreq + thermal + process memory + optional `hrut_somstatus` | 必须保存日志 |
| benchmark duration | 10 分钟基础，30 分钟稳定性 | 2 小时进入 03H |

RDK X5 当前正式 artifact 口径补充：

- 项目三正式主线固定使用项目二 split-head `.bin`，不使用 all-in-one `.bin` 作为默认 fallback。
- 项目二的 Python runtime 质量与资源结果只作为 `artifact / quality / resource reference`。
- 当前 BPU 路线仍需明确记录 mixed execution 事实，不能把项目二已有 CPU hotspot 隐藏掉。

## RDK X5 单板执行清单

| 项目阶段 | RDK X5 任务 | 交付物 | 状态规则 |
|---|---|---|---|
| 阶段 0 | 继承项目二环境基线，补充项目三增量确认：split-head `.bin` hash、C++ build、固定视频可打开、monitor 可记录、raw schema/trace 可生成 | `configs/boards/rdk_x5_8gb.yaml`、build log、runtime log、monitor log、schema/trace check | 缺 baseline id 或项目三增量证据时写 `not_verified` |
| 阶段 1 | 用项目二 INT8 split-head `.bin` 跑 C++ 单线程最小链路 | `rdk_x5_bpu_single_thread.yaml`、`single_thread` raw/log/output | 只跑项目二 Python runtime 不算通过 |
| 阶段 2 | 用项目二 INT8 split-head `.bin` 跑多线程 pipeline | `rdk_x5_bpu_pipeline.yaml`、trace check、queue log | 缺 frame_id 或队列证据写 `not_verified` |
| 阶段 3 | 比较 `drop_oldest`、`drop_newest`、`block_with_timeout`，固定 RDK X5 主线策略 | queue runs、monitor log、`runtime_benchmark.md` 队列表 | 无 monitor 或无策略语义说明不能写 `pass` |
| 阶段 4 | 固定 BPU C++ wrapper、NV12 输入路径和 BPU 调用证据 | build log、runtime log、BPU monitor、raw result | 无法证明 BPU 调用写 `not_verified` |
| 阶段 7 | 在 RDK X5 做断流、模型路径错误、输出不可写、队列堆积、systemd 启停 | failure JSONL、systemd journal、`failure_and_fallback.md` | 失败隐藏或假运行写 `fail` |
| 阶段 8 | RDK X5 10 分钟 smoke、30 分钟 short sustained、2 小时目标测试 | stability raw、monitor log、`stability_report.md` | 30 分钟未通过写 `fail` 或 `blocked` |
| 阶段 9 | 生成 RDK X5 单板 runtime/stability/failure 汇总，并进入全项目状态矩阵 | runtime/stability/failure summary | `not_verified` 不进入正式性能结论 |

## RDK X5 artifact 选择

项目三 RDK X5 主线使用项目二正式收口的 split-head `.bin`，不使用 all-in-one `.bin` 作为正式主线或默认 fallback。项目二结果只能作为输入资产和质量/资源参考来源，项目三仍必须重新生成 pipeline 级 raw result 和稳定性证据。

| 用途 | artifact | SHA256 | 来源 | 项目三使用规则 |
|---|---|---|---|---|
| 主线 | `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin` | `2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c` | 项目二 | 默认 RDK X5 C++ pipeline artifact |
| 历史对照 | `models/yolo11n/rdk_x5_bpu/yolo11n_640_rdkx5_int8_ptq_calib500.bin` | `5382070be5d7b96deccdb06e915944020612a6fe6da3e22f5369182f78bf8cd9` | 项目二早期 all-in-one | 只保留为问题追溯，不得写成正式主线 |

项目二正式参考 run：

- `projects/02_quantization/runs/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor/run.md`

该 run 可作为项目三的：

- artifact 选择依据
- fixed input / task-level quality 参考
- 资源边界参考

但不能直接写成项目三 C++ runtime 或 stability `pass`。

## 执行步骤

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline/run.md
```

### 2. 记录 artifact hash

```bash
sha256sum models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin
```

run 和 raw result 必须记录：

```yaml
backend_runtime: bpu
execution_provider: BPU
loader_api: Horizon hbDNN C API
backend_artifact_format: bin
backend_artifact_path: models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin
backend_artifact_sha256: 2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c
runtime_evidence_path:
accelerator_evidence_path:
cpu_fallback:
fallback_reason:
```

### 3. 构建 BPU pipeline

命令模板：

```bash
RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh
```

如官方 SDK 未装到默认路径，允许额外传入：

```bash
HOBOT_DNN_ROOT=<sdk_root>
HB_DNN_INCLUDE_DIR=<include_dir>
HB_DNN_LIBRARY=<libdnn.so>
HB_HBRT_LIBRARY=<libhbrt*.so>
```

### 4. 运行 benchmark

命令模板：

```bash
RUN_ID=<yyyymmdd>_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

### 5. 运行稳定性

```bash
TIER=smoke bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
```

### 6. 运行 03G failure / service

CLI failure：

```bash
RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh
```

systemd：

```bash
RUN_ID=<run_id> \
WORKDIR=/edge-inference-deploy-lab \
SERVICE_USER=root \
  bash projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh
```

## RDK X5 Benchmark 指标表

RDK X5 的项目三结果必须是 pipeline 级结果。未执行时在对应报告中保留空值和 `not_executed`；已执行但证据不完整时写 `not_verified`；只引用项目二 Python runtime 参考时写 `reference_from_project2_only`。

| 指标组 | 指标 | 单位 / 取值 | raw 字段或日志来源 | 必须写入的报告表 |
|---|---|---|---|---|
| 场景 | run_id、target、environment_baseline_id | string | run、raw result | Runtime Summary、Reproducibility |
| 场景 | input_source_id、input_source_type、input_width、input_height、input_fps | string / number | stream config、raw result | Runtime Summary、Scenario |
| 后端 | backend_runtime、execution_provider、loader_api | string | board config、raw result、runtime log | Runtime Summary、Resource/Accelerator |
| 后端 | backend_artifact_path、backend_artifact_sha256、precision_or_quantization | path / sha256 / enum | board config、run、raw result | Artifact Matrix、Reproducibility |
| 性能 | FPS | frame/s | frame timestamp、processed result | Runtime Summary、MLPerf Performance |
| 性能 | p50/p90/p95/p99 end-to-end latency | ms | `end_to_end_latency_ms` | Runtime Summary、MLPerf Performance |
| 分阶段 | capture、decode、preprocess、inference、postprocess、output p50/p95/p99 | ms | `*_ms` | Stage Latency |
| 线程 | inference_workers、postprocess_workers | count | raw result、pipeline config、runtime log | Runtime Summary、Reproducibility |
| 队列 | queue p50/p95/max per stage | frames | `queue_*_size` | Queue/Buffer |
| 丢帧 | drop_frame_count、drop_frame_rate、dropped_frame_reason | count / ratio / enum | raw result | Queue/Buffer、Failure Impact |
| Buffer | buffer_reuse、buffer_pool_size、bpu_input_buffer_reuse | boolean / count | pipeline config、run | Queue/Buffer |
| 资源 | memory peak、memory growth | MB、MB/hour | monitor log、processed stability | Resource、Stability |
| 资源 | temperature max、throttle events | degC、count | thermal sysfs、monitor log | Resource、Stability |
| 资源 | power mode、power avg/peak | mode、W | run、monitor log | Resource、Stability |
| 加速器证据 | runtime_evidence_path、accelerator_evidence_path、BPU devfreq、BPU load、`hrut_somstatus` | path / MHz / string | runtime log、monitor log | Resource/Accelerator |
| fallback | cpu_fallback、fallback_reason | boolean / string/null | raw result、runtime log、failure log | CPU Fallback |
| 质量 | output_valid、detection_count、detection_quality_status | boolean / count / enum | raw result、输出样例、对齐报告 | Quality Gate |
| 质量 | fixed-input alignment、task-level quality、quality_alignment_exemption | enum / object | 项目二报告、项目三 run | Quality Gate |
| 稳定性 | stability_tier、target_duration_sec、actual_duration_sec、completed | enum / sec / boolean | stability run、raw result | Stability Summary |
| 稳定性 | restart_count、reconnect_count、crash_count、watchdog_count | count | failure log、service log | Stability Summary、Failure During Stability |
| 可复现 | pipeline_config、stream_config、model_config、board_config、command、raw/log path | path / command | run 记录 | Reproducibility |

## RDK X5 Benchmark 执行矩阵

| run 类型 | 建议 run_id 后缀 | 输入源 | 时长 / 范围 | 主要目的 | 必须更新的表 |
|---|---|---|---:|---|---|
| env baseline | `env_baseline` | `not_applicable` | `not_applicable` | 固定 RDK X5 系统、BPU runtime、OpenCV、monitor 能力 | `video_pipeline.md` 当前状态、`runtime_benchmark.md` Reproducibility |
| single thread | `single_thread_demo` | `video_set_runtime_v1` | 60 sec | 验证单线程最小 C++ BPU 链路、playlist 输入、NV12 输入和输出格式 | Runtime Summary、Stage Latency、Quality Gate |
| multithread | `multithread_pipeline` | `video_set_runtime_v1` | 600 sec | 验证线程解耦、frame_id、队列长度和端到端延迟 | Runtime Summary、Stage Latency、Queue/Buffer |
| queue policy | `queue_<policy>` | 高负载视频或实时源 | 600 sec / policy | 比较 `drop_oldest`、`drop_newest`、`block_with_timeout` | Queue/Buffer、Resource |
| BPU backend | `bpu_cpp_pipeline` | 固定视频 + 至少一种实时源计划 | 600 sec | 证明 hbDNN C API 和 BPU 实际参与推理 | Resource/Accelerator、CPU Fallback |
| INT8 mainline | `bpu_int8_mainline` | 同一固定视频 | 600 sec | 验证项目二 INT8 split-head `.bin` 的 pipeline 级性能、质量和尾延迟风险 | Runtime Summary、Artifact Matrix |
| failure/service | `failure_service_test` | 故障注入源 | case by case | 验证模型错误、输出不可写、队列堆积和 systemd 启停 | Failure Cases、CPU Fallback、Service Recovery |
| stability smoke | `stability_smoke` | `video_set_stability_v1` | 600 sec | 确认稳定性配置可跑 | Stability Summary、Resource Trace |
| stability short | `stability_short_sustained` | `video_set_stability_v1` | 1800 sec | 项目三基础稳定性必测 | Stability Summary、Resource Trace、Queue/Drop Trend |
| stability acceptance | `stability_acceptance_sustained` | `video_set_stability_v1` | 7200 sec | 项目验收目标 | Stability Summary、MLPerf-style Summary |

## 2026-06-24 实测回填

当前仓库已经同步回 `2026-06-24` 的 RDK X5 项目三板端产物。需要先说明一件事：

- 原始 `run.md` 中的 `schema_check_exit_code=1` 来自旧 schema 对 `video_playlist` 的误判。
- 当前 `benchmark/schemas/video_pipeline_raw_schema.yaml` 已允许 `video_playlist`；同步后按当前 schema 重跑的本地校验已经全部 `pass`。
- 因此，下面这张表以“同步 raw/log/monitor + 当前 schema 重验结果”为正式口径。

| run_id | 类型 | 输入源 | 关键指标 | 证据状态 | 当前结论 |
|---|---|---|---|---|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | single_thread | `video_set_runtime_v1` | `404` 帧 / `60s`、`6.7333 FPS`、`p95=146.5713 ms`、`0` drop | prepost `pass`、schema `pass`、trace `pass`、cpu_fallback=false | `pass_smoke` |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | backend_pipeline | `video_set_runtime_v1` | `10888` 帧 / `601s`、`18.1165 FPS`、`p95=167.0899 ms`、drop rate `0.3967` | prepost `pass`、schema `pass`、trace `degraded`、`6894` gap、`0` out-of-order、reason=`queue_full` | `pass_with_drop_oldest_degraded_trace` |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_smoke` | stability smoke | `video_set_stability_v1` | `18.1367 FPS`、`p95=170.5050 ms`、memory growth `77.6608 MB/h`、temp peak `67.032 C` | completed=true、schema `pass`、trace `degraded` | `pass_with_drop_oldest_degraded_trace` |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_short_sustained` | stability short | `video_set_stability_v1` | `18.3172 FPS`、`p95=167.4585 ms`、memory growth `6.9688 MB/h`、temp peak `67.765 C` | completed=true、schema `pass`、trace `degraded` | `pass_with_drop_oldest_degraded_trace` |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | stability acceptance | `video_set_stability_v1` | `18.4794 FPS`、`p95=166.5849 ms`、memory growth `0.3597 MB/h`、temp peak `67.961 C` | completed=true、schema `pass`、trace `degraded` | `pass_with_drop_oldest_degraded_trace` |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | failure wrapper | mixed | CLI 5 case 全通过 | failure summary `pass` | `pass_cli_5of5` |
| `20260624_rdk_x5_8gb_systemd_service_test_v2` | systemd lifecycle | service | `start=active`、`restart=active`、`stop=inactive`、health_check=pass | journal/status 已回传，`working_directory=/edge-inference-deploy-lab`、`result=success`；旧 placeholder fail 已转排障样本 | `pass` |

`2026-06-29` 的 IMX219 live-source 性能优化回填如下：

| run_id | workers | 输入源 | 关键指标 | 证据状态 | 当前结论 |
|---|---|---|---|---|---|
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2` | `1 infer / 1 postprocess` | `imx219_rdkx5_hbn_001` | `20.0169 FPS`、`p95=141.9370 ms`、drop rate `0.3346`、`594` gap | prepost `pass`、schema `pass`、trace `degraded`、detection_count_mean=`0.0627` | 正确性恢复，但吞吐不足 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1` | `2 infer / 1 postprocess` | `imx219_rdkx5_hbn_001` | `19.9322 FPS`、`p95=150.7385 ms`、drop rate `0.3375`、`598` gap | prepost `pass`、schema `pass`、trace `degraded`、POSTPROCESS_WORKERS=`1` | 单 postprocess worker 成为瓶颈，不作为主线 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `2 infer / 2 postprocess` | `imx219_rdkx5_hbn_001` | `30.0847 FPS`、`p95=165.1727 ms`、drop rate `0.0`、`0` gap、detection_count_mean=`0.8496` | prepost `pass`、schema `pass`、trace `pass`、INFERENCE_WORKERS=`2`、POSTPROCESS_WORKERS=`2` | 当前 IMX219 live-source 正式性能主线 |

优化过程、逐步诊断和复现实验顺序不放在本规范正文里，统一落到：

- `projects/03_video_pipeline/reports/runtime_benchmark.md` 的 `RDK X5 Optimization Walkthrough`
- `projects/03_video_pipeline/reports/runbook.md` 的 `Step 3` 与 `opt2 / opt3_i2_p1 / opt3_i2_p2` 复现命令

当前 live-source `input_disconnect` 仍待板端实测，但仓库已经补入 `projects/03_video_pipeline/scripts/run/run_rdk_x5_input_disconnect.sh`，并把当前正式 live-source 收敛为 `imx219_rdkx5_hbn_001`。该入口不再假设 `/dev/video0` 存在，而是使用 `mipi_camera_hbn + HBN/srcampy -> 本地 helper -> 当前 C++ app` 的板端采集链路；当检测到图形显示器时仍按 `PREVIEW_WINDOW=auto` 打开本地实时窗口。当前这路 IMX219 的正式朝向口径固定为 `INPUT_ORIENTATION_CORRECTION=rotate180`，runtime log 必须出现 `effective=rotate180` 或等效的 `rotate180` 生效证据；默认 benchmark 口径已更新为 `INFERENCE_WORKERS=2 + POSTPROCESS_WORKERS=2 + PREVIEW_WINDOW=off`。

## RDK X5 证据矩阵

| 证据 | 最低要求 | 合格状态 | 不合格状态 |
|---|---|---|---|
| `.bin` hash | run、board config、raw result 三处一致 | `pass` | hash 缺失或不一致写 `not_verified` |
| BPU 初始化 | runtime log 含 model load、input/output tensor 或 wrapper 初始化信息 | `pass` | 无 runtime log 写 `not_verified` |
| BPU 调用 | runtime log、monitor log、devfreq 或 `hrut_somstatus` 至少能对齐 run 时间窗 | `pass` / `degraded` | 无法证明 BPU 参与写 `not_verified` |
| CPU fallback | raw result 与 failure 报告都明确 `cpu_fallback=false`；若为 true 必须说明原因 | `pass` | fallback 被隐藏写 `fail` |
| frame trace | `frame_id`、阶段 timestamp、输出结果可追踪 | `pass` | 缺 frame_id 或乱序不可解释写 `fail` |
| queue evidence | 每阶段队列长度、容量、策略和丢帧原因完整 | `pass` | 队列字段缺失写 `not_verified` |
| resource monitor | 至少有内存、温度、BPU devfreq 或不可观测原因 | `pass` / `degraded` | monitor 缺失写 `not_verified` |
| quality gate | 复用项目二质量 baseline；项目三变更前后处理或 wrapper 时补 fixed-input 或任务级质量对齐 | `pass` / `not_verified` | 缺质量证据却写 pass 视为 `fail` |
| reproducibility | run、命令、配置、raw、runtime log、monitor log、输出样例路径完整 | `pass` | 任一核心路径缺失写 `not_verified` |

## 记录要求

- split-head `.bin` 路径和 hash 必须记录。
- `backend_artifact_format/path/sha256`、`loader_api`、`execution_provider`、`runtime_evidence_path`、`accelerator_evidence_path`、`cpu_fallback` 必须写入 run 和 raw result。
- `queue_policy`、`queue_capacity`、`queue_push_timeout_ms` 必须写入 run 和 raw result；如存在覆盖，还必须写 `queue_policy_override_requested` 和 `queue_policy_override_effective`。
- RDK X5 单板 run 在写入 runtime 或 quality 结论前，必须生成 `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md`。
- runtime 日志保存到 `logs/runtime/03_video_pipeline/rdk_x5_8gb/`。
- monitor 日志保存到 `logs/monitor/03_video_pipeline/rdk_x5_8gb/`。
- raw result 保存到 `benchmark/raw/03_video_pipeline/rdk_x5_8gb/`。
- 聚合结果保存到 `benchmark/processed/03_video_pipeline/`。
- 若 `power_w`、BPU 标准 load、某个 thermal 节点不可读，必须保留字段并在 run 中解释原因。

## 输出文件

| 文件 | 要求 |
|---|---|
| `projects/03_video_pipeline/CMakeLists.txt` | C++17/OpenCV/BPU 构建入口 |
| `projects/03_video_pipeline/src/video_pipeline_app.cpp` | RDK X5 BPU pipeline 应用入口 |
| `projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml` | RDK X5 board/runtime/artifact 配置 |
| `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml` | RDK X5 单线程最小链路配置 |
| `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml` | RDK X5 多线程 pipeline 配置 |
| `projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh` | RDK X5 BPU 构建入口 |
| `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` | RDK X5 runtime benchmark 入口 |
| `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | RDK X5 稳定性入口 |
| `projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh` | RDK X5 CLI failure 入口 |
| `projects/03_video_pipeline/scripts/monitor/monitor_rdk_x5_bpu.sh` | RDK X5 BPU monitor |
| `projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh` | RDK X5 systemd 生命周期入口 |
| `projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-rdkx5.service` | RDK X5 systemd 模板 |
| `benchmark/raw/03_video_pipeline/rdk_x5_8gb/*rdk*x5*bpu*.jsonl` | raw result |
| `logs/monitor/03_video_pipeline/rdk_x5_8gb/*rdk*x5*bpu*.log` | RDK X5 monitor |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | RDK X5 benchmark |
| `projects/03_video_pipeline/reports/stability_report.md` | RDK X5 10 分钟、30 分钟、2 小时稳定性状态 |
| `projects/03_video_pipeline/reports/failure_and_fallback.md` | RDK X5 异常注入、CPU fallback 和服务恢复 |
| `projects/03_video_pipeline/reports/video_pipeline.md` | RDK X5 线程、队列、buffer 和后端链路 |
| `projects/03_video_pipeline/reports/runbook.md` | RDK X5 复现步骤 |

## 验收标准

- pipeline 使用 BPU 后端可连续运行。
- 有端到端和分阶段耗时。
- 有 BPU 调用证据，或至少有明确不可观测说明和 degraded 状态。
- 温度、BPU devfreq、内存曲线或不可观测原因有记录。
- 结果能与项目二单模型 / Python runtime benchmark 对照，但不能直接复用其 FPS 作为 pipeline FPS。
- raw result、runtime log、monitor log、run 记录和报告结论可以互相追溯。

## 降级和问题库

下面问题必须进入问题库：

- `.bin` 加载失败。
- hbDNN / hbSys runtime 错误。
- NV12 输入路径错误或 split-head decode 错误。
- BPU 调用证据缺失。
- 温度、load 或功耗不可观测且原因不明。
- pipeline 性能显著低于项目二 reference 且无法解释。
- 出现 CPU fallback。
- fixed-input alignment 或任务级质量证据不完整却试图写入 `pass`。

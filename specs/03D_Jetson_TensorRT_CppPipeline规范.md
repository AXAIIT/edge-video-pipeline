# 03D_Jetson_TensorRT_CppPipeline规范

## 适用范围

本规范用于在 Jetson 8GB 上将 TensorRT YOLO11n engine 集成到 C++ pipeline，并完成端到端 benchmark。

本 spec 承接项目一或项目二的 TensorRT engine，不重新定义模型转换路线。本规范只定义 Jetson TensorRT 这一条单板执行路线；Jetson 可以作为项目三的参考实现，但不作为 RK3588 或 RDK X5 的前置条件。其他板卡应分别按 `03E`、`03F` 独立执行。

## 执行原则

下面的 C++ wrapper 接口、构建命令和 benchmark 命令是推荐路径，不是唯一实现。可以替换 TensorRT 封装方式、CUDA buffer 管理、日志库或监控工具，但不能降低证据要求：必须保留 engine hash、C++ build 命令、端到端 raw result、TensorRT 调用证据、资源监控和问题记录。替代路径必须写入对应 `projects/03_video_pipeline/runs/`，并同步更新相关 `projects/03_video_pipeline/reports/`。

## 路径口径

本 spec 使用当前仓库结构：

- Jetson 配置放在 `projects/03_video_pipeline/configs/boards/` 和 `projects/03_video_pipeline/configs/pipeline/`。
- TensorRT engine 放在 `models/yolo11n/tensorrt/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/jetson_8gb/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/jetson_8gb/`。
- monitor 日志放在 `logs/monitor/03_video_pipeline/jetson_8gb/`。
- build 日志放在 `logs/runtime/03_video_pipeline/build/`。

## 前置条件

- 已完成项目一 TensorRT engine，或项目二 TensorRT 量化 engine。
- 已完成 `03A` 或 `03B` 的基础 pipeline。
- 已有 Jetson 环境基线。项目三 Jetson TensorRT 阶段默认继承项目二 `20260609_jetson_8gb_env_baseline`；该基线已继承项目一 `20260604_jetson_8gb_env_baseline` 的 Jetson TensorRT/CUDA/OpenCV/tegrastats 信息。
- 已准备配置：`projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` 和 `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml`。
- 已准备固定视频源和实时输入源。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- 如新建项目三专属环境基线，必须对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md`；如继承项目一/二基线，run 中必须记录继承的 `environment_baseline_id`，并补充项目三的视频输入、C++ 构建、runtime log 和 monitor log 证据。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| backend | `tensorrt` | 固定字段名 |
| execution_provider | `TensorRT-GPU` 或 `TensorRT-DLA` | 按实际推理路径填写 |
| loader_api | `TensorRT C++ API` | 如使用封装库，按实际填写 |
| backend_artifact_format | `engine` | TensorRT engine |
| precision | `int8_ptq` | 项目三 Jetson 主线固定使用项目二 INT8 PTQ engine |
| input_source | video file + realtime source | 至少一种实时源 |
| monitor | `tegrastats` 或等价工具 | 必须保存日志 |
| benchmark duration | 10 分钟基础，30 分钟稳定性 | 2 小时进入 03H |

Jetson 当前正式实时源口径补充：

- 本轮 Jetson 不再把 `USB` 摄像头或 `RTSP` 作为唯一默认 live-source 占位。
- 当前正式 live-source 选择为 `imx219_csi_001`，即 Jetson CSI IMX219。
- 当前正式主线运行语义必须写清楚：`V4L2 RG10 raw 1280x720@60 (sensor_mode=5) -> fixed_10bit normalize -> RGGB debayer -> TensorRT pipeline`。
- 配置项 `BAYER_PATTERN=RG` 表示常规 `RGGB` 传感器排列，不表示 OpenCV 历史两字母 `COLOR_BayerRG2BGR` 枚举；实现层必须保证 debayer 后输出为 OpenCV `BGR` frame，供预览窗口和后续模型预处理共同使用。
- `fixed_10bit` 在当前 Jetson IMX219 路径里的具体含义也必须写清楚：它不是“把低 10 bit 直接按 `255/1023` 线性缩放”，而是按当前板端 `RG10` 16-bit word 的高位对齐经验，保留高 8 bit 作为 8-bit preview 输入。否则会出现全白预览。
- 当前正式主线默认关闭 gray-world white balance，即 `V4L2_DISABLE_WHITE_BALANCE=1`。
- `20260623_jetson_8gb_yolo11n_tensorrt_imx219_preview_rotate180_rg_bayerfix` 已完成板端视觉有效性复核：方向与颜色恢复正常，且 `runtime_pass_all_postchecks_pass`。因此 `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 可以重新作为 Jetson IMX219 sustained 主线 run 引用。
- 若 IMX219 物理安装方向与默认画面方向不一致，必须通过 `INPUT_ORIENTATION_CORRECTION=clockwise`、`counterclockwise`、`rotate180`（或 `upside_down`）显式校正；不能把朝向问题继续混写成 Bayer 或曝光问题。当前板端现场复核口径收敛为 `rotate180 + RG`，此前 `counterclockwise + GB` / `clockwise + GR` 已被现场结果证伪。
- 摄像头方向修正不能只看 run 记录里的环境变量；runtime log 必须出现 `INPUT_ORIENTATION_CORRECTION: source=/dev/video0 mode=... normalized=...`，否则视为方向修正没有实际生效。
- 当前项目三 Jetson 摄像头实时预览默认使用 `PREVIEW_WINDOW=auto`：
  - 当输入源是实时源且检测到 `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE=x11|wayland` 时，应在屏幕上实时显示检测过程。
  - 预览窗口由主线程执行 `imshow()` / `waitKey()`，并在左上角叠加 `FPS`、`DET` 和检测框标签。
  - headless / systemd / 无图形环境时必须自动禁用，不得因为缺少桌面环境把 runtime run 直接判为失败。
  - 任何带 `PREVIEW_WINDOW=auto|on` 的人工目视复核，都必须在 Jetson 本地桌面会话中执行；普通 SSH 终端不构成“预览已验证”的证据。
- 当前 `mipi_camera + V4L2 raw` 路径的板端 `v4l2-ctl --list-ctrls -L` 已明确只暴露 `gain`、`exposure`、`override_enable` 等手动控制，没有看到标准 ISP 风格的自动曝光 / 自动白平衡开关；当前项目不再开放手动曝光命令入口，只在启动时强制把 `override_enable` 复位到 `0`，避免实验之间互相污染。因此画面观感异常不能再简单按“推理链路问题”归因，必须区分朝向、raw decode 口径和设备控制状态三类问题。
- 仅当 `imx219_csi_001` 板端正式 run 完成后，03D 中“至少一种实时源”才算闭环。
- `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 已作为当前 Jetson IMX219 正式主线 run 留档。
- 项目内允许保留 `imx219_csi_argus_001` 作为诊断入口：
  - 运行语义：`nvarguscamerasrc -> nvvidconv -> videoconvert -> OpenCV appsink -> TensorRT pipeline`
  - 目标：把 raw Bayer normalize / debayer 从 CPU 热路径移到 Jetson ISP / Argus
  - 当前状态口径：`diagnostic_only_blocked_current_board`
  - 当前板端已由 `20260621_..._argus_smoke`、`20260621_..._argus_runtime600`、`20260622_..._argus_simple_ab` 证明其无法建立有效帧，因此不得再写成正式主线候选

## Jetson 当前主线的队列策略口径

Jetson 报告不能只写 `drop_oldest`、`drop_newest`、`block_with_timeout` 这几个名字，必须同时给出满队列时的行为定义。当前仓库主线 app 的解释口径如下：

- 队列策略只在“目标队列已满”时触发；队列未满时直接入队。
- `queue_push_timeout_ms` 等待的是“目标队列出现空位”，不是“TensorRT 推理超时”，也不是“33 ms 内没有整条 pipeline 响应就丢帧”。
- 当前 `video_pipeline_app.cpp` 实现里，`queue_policy` 和 `queue_push_timeout_ms` 会统一作用于 `q_capture`、`q_preprocess`、`q_infer`、`q_result` 四段队列；Jetson 当前主线不是每段不同策略。

| 策略 | 队列满时的 Jetson 实际动作 | 等待方式 | 丢弃语义 | Jetson 报告口径 |
|---|---|---|---|---|
| `drop_oldest` | 弹出队列中最旧元素，再把当前新元素入队 | 不等待 | 丢队列里最旧帧 | 这是默认低延迟主线口径 |
| `drop_newest` | 保持队列不变，直接放弃当前新元素 | 不等待 | 丢当前新帧 | 适合作为对照策略，不代表更低延迟 |
| `block_with_timeout` | 最多等待 `queue_push_timeout_ms` 让目标队列空出一个位置；成功则入队 | 最长等待 `queue_push_timeout_ms` | 超时仍满则丢当前新帧 | `33 ms` 代表“单次入队等待上限 33 ms” |
| `block` / `block_forever` / `no_drop` | 一直等待到有空位或队列关闭 | 无限等待 | 不因 timeout 丢当前新帧 | 只适合 no-drop / 质量链路，不适合作为默认实时显示主线 |

Jetson 执行和报告额外要求：

- 如通过脚本覆盖策略，必须同时记录 `queue_policy_override_requested` 与 `queue_policy_override_effective`。
- 如使用 `block_with_timeout`，必须显式记录 `queue_push_timeout_ms`；不能只在命令里写、报告里不写。
- 如 run_id 中出现 `block_timeout` 等缩写，报告正文必须展开成完整行为解释，不能让读者自己猜。
- 如启用或沿用实时预览能力，run 记录中必须写 `preview_window_requested`；若窗口未弹出，应先检查 runtime log 中的 `PREVIEW_WINDOW_STATUS`，再区分是 `display_env_missing`、`non_realtime_source`、`opencv_highgui_failed` 还是用户主动按键关闭。

## Jetson 单板执行清单

| 项目阶段 | Jetson 任务 | 交付物 | 状态规则 |
|---|---|---|---|
| 阶段 0 | 继承项目二 Jetson 环境基线，补充项目三增量确认：TensorRT/CUDA/OpenCV/GStreamer、`tegrastats`、输入源和 engine 文件 | `configs/boards/jetson_8gb.yaml`、build log、runtime log、monitor log、schema/trace check | 缺继承 baseline id 或项目三增量证据时写 `not_verified` |
| 阶段 1 | 用项目二 Jetson INT8 PTQ engine 跑 C++ 单线程最小链路 | `configs/pipeline/jetson_tensorrt_single_thread.yaml`、single-thread raw/log/output | 只跑项目二单模型 benchmark 不算通过 |
| 阶段 2 | 用项目二 Jetson INT8 PTQ engine 跑多线程 pipeline | `configs/pipeline/jetson_tensorrt_pipeline.yaml`、trace check、queue log | frame_id 或队列证据缺失写 `not_verified` |
| 阶段 3 | 比较 Jetson `drop_oldest`、`drop_newest`、`block_with_timeout`，确认本板卡主线策略，并写清楚每种策略在“队列满”时的动作与 timeout 口径 | queue runs、monitor log、`runtime_benchmark.md` 队列表 | 无内存曲线或无策略语义说明不能写 `pass` |
| 阶段 4 | 固定 TensorRT C++ wrapper 和 GPU 调用证据 | C++ build log、runtime log、`tegrastats`、raw result | 无法证明 TensorRT/GPU 调用写 `not_verified` |
| 阶段 7 | 在 Jetson 做断流、模型路径错误、输入尺寸错误、输出不可写、队列堆积、systemd 启停 | failure JSONL、systemd journal、`failure_and_fallback.md` | 失败隐藏或假运行写 `fail` |
| 阶段 8 | Jetson 10 分钟 smoke、30 分钟 short sustained、2 小时目标测试 | stability raw、monitor CSV/log、`stability_report.md` | 30 分钟未通过写 `fail` 或 `blocked` |
| 阶段 9 | 生成 Jetson 单板 runtime/stability/failure 汇总，并进入全项目状态矩阵 | runtime_summary、stability_summary、excluded_runs | `not_verified` 不进入正式性能结论 |

## Jetson artifact 选择

项目三 Jetson 主线使用项目二产出的 INT8 PTQ TensorRT engine，不使用 FP16 engine 作为主线或默认 fallback。项目二单模型结果只能作为输入资产和质量证据来源，项目三仍必须重新生成 pipeline 级 raw result 和稳定性证据。

| 用途 | artifact | SHA256 | 来源 | 项目三使用规则 |
|---|---|---|---|---|
| 主线 | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` | 项目二 | 默认 Jetson pipeline engine |

项目二的单模型 INT8 结果只能作为 baseline 和质量证据来源，不能直接写成项目三 pipeline 性能。项目三必须重新生成：

```text
benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl
logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log
logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log
projects/03_video_pipeline/runs/<run_id>/run.md
```

## 执行步骤

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_jetson_8gb_yolo11n_tensorrt_cpp_pipeline/run.md
```

### 2. 记录 engine hash

```bash
sha256sum models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine
```

run 和 raw result 必须记录：

```yaml
backend_runtime: tensorrt
execution_provider: TensorRT-GPU # 实际使用 DLA 时写 TensorRT-DLA
loader_api: TensorRT C++ API
backend_artifact_format: engine
backend_artifact_path: models/yolo11n/tensorrt/<engine_file>.engine
backend_artifact_sha256: <64_hex_sha256>
runtime_evidence_path:
accelerator_evidence_path:
cpu_fallback:
fallback_reason:
```

### 3. 构建 TensorRT pipeline

命令模板：

```bash
RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh
```

### 4. 运行 benchmark

命令模板：

```bash
RUN_ID=<yyyymmdd>_jetson_8gb_yolo11n_tensorrt_cpp_pipeline \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### 5. 聚合指标

```bash
python3 projects/03_video_pipeline/scripts/benchmark/aggregate_pipeline_benchmark.py \
  --input benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl \
  --monitor logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log \
  --output benchmark/processed/03_video_pipeline/<run_id>_summary.csv
```

## Jetson Benchmark 指标表

Jetson TensorRT 的项目三结果必须是 pipeline 级结果。下表是 03D 最低指标集合；未执行时在对应报告中保留空值和 `not_executed`，已经执行但证据不完整时写 `not_verified`。

| 指标组 | 指标 | 单位 / 取值 | raw 字段或日志来源 | 必须写入的报告表 |
|---|---|---|---|---|
| 场景 | run_id、target、environment_baseline_id | string | run、raw result | Runtime Summary、Reproducibility |
| 场景 | input_source_id、input_source_type、input_width、input_height、input_fps | string / number | stream config、raw result | Runtime Summary、Scenario |
| 后端 | backend_runtime、execution_provider、loader_api | string | board config、raw result、runtime log | Runtime Summary、Resource/Accelerator |
| 后端 | backend_artifact_path、backend_artifact_sha256、precision_or_quantization | path / sha256 / enum | board config、run、raw result | Artifact Matrix、Reproducibility |
| 性能 | FPS | frame/s | frame timestamp、processed result | Runtime Summary、MLPerf Performance |
| 性能 | p50/p90/p95/p99 end-to-end latency | ms | `end_to_end_latency_ms` | Runtime Summary、MLPerf Performance |
| 分阶段 | capture、decode、preprocess、inference、postprocess、output p50/p95/p99 | ms | `*_ms` | Stage Latency |
| 队列 | queue p50/p95/max per stage | frames | `queue_*_size` | Queue/Buffer |
| 丢帧 | drop_frame_count、drop_frame_rate、dropped_frame_reason | count / ratio / enum | raw result | Queue/Buffer、Failure Impact |
| Buffer | buffer_reuse、buffer_pool_size、gpu_buffer_reuse | boolean / count | pipeline config、run | Queue/Buffer |
| 资源 | memory peak、memory growth | MB、MB/hour | `tegrastats`、processed stability | Resource、Stability |
| 资源 | temperature max、power mode、power avg/peak、throttle events | degC、mode、W、count | `tegrastats`、`nvpmodel`、monitor log | Resource、Stability |
| 加速器证据 | runtime_evidence_path、accelerator_evidence_path、GPU/DLA utilization | path / percent | runtime log、`tegrastats` | Resource/Accelerator |
| fallback | cpu_fallback、fallback_reason | boolean / string/null | raw result、runtime log、failure log | CPU Fallback |
| 质量 | output_valid、detection_count、detection_quality_status | boolean / count / enum | raw result、输出样例、对齐报告 | Quality Gate |
| 质量 | fixed-input alignment、task-level quality、quality_alignment_exemption | enum / object | 项目一/二报告、项目三 run | Quality Gate |
| 稳定性 | stability_tier、target_duration_sec、actual_duration_sec、completed | enum / sec / boolean | stability run、raw result | Stability Summary |
| 稳定性 | restart_count、reconnect_count、crash_count、watchdog_count | count | failure log、service log | Stability Summary、Failure During Stability |
| 可复现 | pipeline_config、stream_config、model_config、board_config、command、raw/log path | path / command | run 记录 | Reproducibility |

## Jetson Benchmark 执行矩阵

| run 类型 | 建议 run_id 后缀 | 输入源 | 时长 / 范围 | 主要目的 | 必须更新的表 |
|---|---|---|---:|---|---|
| env baseline | `env_baseline` | `not_applicable` | `not_applicable` | 固定 Jetson 系统、TensorRT/CUDA、OpenCV/GStreamer、电源、散热、swap 和监控能力 | `video_pipeline.md` 当前状态、`runtime_benchmark.md` Reproducibility |
| single thread | `single_thread_demo` | `video_set_runtime_v1` | 前 300 帧 | 验证最小 C++ TensorRT 链路、前后处理和输出格式 | Runtime Summary、Stage Latency、Quality Gate |
| multithread | `multithread_pipeline` | `video_set_runtime_v1` | 600 sec | 验证线程解耦、frame_id、队列长度和端到端延迟 | Runtime Summary、Stage Latency、Queue/Buffer |
| queue policy | `queue_<policy>` | 高负载视频或实时源 | 600 sec / policy | 比较 `drop_oldest`、`drop_newest`、`block_with_timeout` | Queue/Buffer、Resource |
| TensorRT backend | `tensorrt_cpp_pipeline` | 固定视频 + 至少一种实时源计划 | 600 sec | 证明 TensorRT C++ API 和 GPU/DLA 实际参与推理 | Resource/Accelerator、CPU Fallback |
| INT8 mainline | `tensorrt_int8_mainline` | 同一固定视频 | 600 sec | 验证项目二 INT8 engine 的 pipeline 级性能、质量和尾延迟风险 | Runtime Summary、Artifact Matrix |
| failure/service | `failure_service_test` | 故障注入源 | case by case | 验证断流、模型错误、输出不可写、队列堆积和 systemd 启停 | Failure Cases、CPU Fallback、Service Recovery |
| stability smoke | `stability_smoke` | `video_set_stability_v1` | 600 sec | 确认稳定性配置可跑 | Stability Summary、Resource Trace |
| stability short | `stability_short_sustained` | `video_set_stability_v1` | 1800 sec | 项目三基础稳定性必测 | Stability Summary、Resource Trace、Queue/Drop Trend |
| stability acceptance | `stability_acceptance_sustained` | `video_set_stability_v1` | 7200 sec | 项目验收目标 | Stability Summary、MLPerf-style Summary |

## Jetson 证据矩阵

| 证据 | 最低要求 | 合格状态 | 不合格状态 |
|---|---|---|---|
| engine hash | run、board config、raw result 三处一致 | `pass` | hash 缺失或不一致写 `not_verified` |
| TensorRT 初始化 | runtime log 含 engine 加载、binding、context 或 wrapper 初始化信息 | `pass` | 无 runtime log 写 `not_verified` |
| GPU/DLA 调用 | `tegrastats` 或等价日志能对应 run 时间窗；DLA 未使用时明确写 `TensorRT-GPU` | `pass` / `degraded` | 无法证明加速器参与写 `not_verified` |
| CPU fallback | raw result 与 failure 报告都明确 `cpu_fallback=false`；若为 true 必须说明原因 | `pass` | fallback 被隐藏写 `fail` |
| frame trace | `frame_id`、阶段 timestamp、输出结果可追踪 | `pass` | 缺 frame_id 或乱序不可解释写 `fail` |
| queue evidence | 每阶段队列长度、容量、策略和丢帧原因完整 | `pass` | 队列字段缺失写 `not_verified` |
| resource monitor | 至少有内存、温度、电源模式或功耗、GPU/CPU 利用率 | `pass` / `degraded` | monitor 缺失写 `not_verified` |
| labeled video quality | `bdd100k_mot_mini_v1` 使用 `data/validation/bdd100k_mot_mini_v1/labels/`、`jetson_tensorrt_bdd100k_quality.yaml`，报告必须包含 frame coverage、missing labeled frames、overall AP50/precision/recall/F1、TP/FP/FN 和 per-class gt/pred/tp/fp/fn/AP50/precision/recall/F1/mean IoU | `pass` / `not_verified` | 未制备 BDD100K mini、无 GT 对齐报告、存在 frame gap/drop、缺少 TP/FP/FN/coverage 或只用无标注视频写质量 pass 视为 `fail` |
| quality gate | 复用项目一/二质量 baseline；项目三变更前后处理或 wrapper 时补固定输入和任务级对齐 | `pass` / `not_verified` | 缺质量证据却写 pass 视为 `fail` |
| reproducibility | run、命令、配置、raw、runtime log、monitor log、输出样例路径完整 | `pass` | 任一核心路径缺失写 `not_verified` |

## 记录要求

- engine 路径和 hash 必须记录。
- `backend_artifact_format/path/sha256`、`loader_api`、`execution_provider`、`runtime_evidence_path`、`accelerator_evidence_path`、`cpu_fallback` 必须写入 run 和 raw result。
- `queue_policy`、`queue_capacity`、`queue_push_timeout_ms` 必须写入 run 和 raw result；如存在覆盖，还必须写 `queue_policy_override_requested` 和 `queue_policy_override_effective`。
- Jetson 单板 run 在写入 runtime 或 quality 结论前，必须生成 `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md`，证明项目三的 preprocess / postprocess 仍与项目一/二基线一致；若 consistency check 失败，该 run 直接记为 `fail`，不能继续写 runtime 结论。
- 视频级带标注质量评估必须使用 `bdd100k_mot_mini_v1`；类别映射、忽略类、视频 SHA256、标签 SHA256 和 5 GB 预算检查必须进入 manifest。
- BDD100K MOT mini 质量评估必须使用 no-drop 配置 `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml`，并记录 `TRACE_FAIL_ON_GAPS=1`。若 raw result 中 `drop_frame_count_max > 0` 或 trace check 出现 `frame_id_gaps > 0`，该 run 只能作为实时 pipeline smoke 或队列策略证据，不能作为带标注质量证据。
- BDD100K MOT mini 质量评估必须同时生成详细 CSV、compact summary CSV 和 Markdown 表格；summary 至少包含 `labeled_frame_coverage`、`missing_labeled_frames`、`overall_ap50_weighted`、`overall_precision`、`overall_recall`、`overall_f1`、`total_gt`、`total_pred`、`total_tp`、`total_fp`、`total_fn`。
- BDD100K MOT mini 做 confidence sweep 时必须记录 C++ `model_config` 的 `postprocess.confidence_threshold` 和评估脚本的 `CONFIDENCE_MIN`。如果 raw result 的最小 confidence 已经等于或高于原始 postprocess 阈值，离线降低 `CONFIDENCE_MIN` 不能作为低阈值召回验证；必须重新上板生成低阈值 raw。
- `bdd100k_mot_mini_v1` 已完成下载、筛选、视频制备和标签转换后可以写 `ready`，但质量 `pass` 仍必须等待 Jetson pipeline raw result 和 `evaluate_bdd100k_mot_detection.py` 报告；weather/time/scene coverage 当前只能记录为 `not_verified`，不能作为场景覆盖结论。
- 未实际使用 DLA 时不能写 `TensorRT-DLA`；默认写 `TensorRT-GPU`。
- C++ build 命令必须记录。
- runtime 日志保存到 `logs/runtime/03_video_pipeline/jetson_8gb/`。
- monitor 日志保存到 `logs/monitor/03_video_pipeline/jetson_8gb/`。
- raw result 保存到 `benchmark/raw/03_video_pipeline/jetson_8gb/`。
- 聚合结果保存到 `benchmark/processed/03_video_pipeline/`。

## 输出文件

| 文件 | 要求 |
|---|---|
| `projects/03_video_pipeline/CMakeLists.txt` | C++17/OpenCV/TensorRT 构建入口 |
| `projects/03_video_pipeline/src/video_pipeline_app.cpp` | Jetson TensorRT pipeline 应用入口 |
| `projects/03_video_pipeline/src/inference/tensorrt/*` | TensorRT C++ wrapper |
| `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | Jetson board/runtime/artifact 配置 |
| `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml` | Jetson 多线程 pipeline 配置 |
| `projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml` | BDD confidence rerun 的低阈值模型配置 |
| `projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh` | Jetson TensorRT 构建入口 |
| `projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | Jetson runtime benchmark 入口 |
| `projects/03_video_pipeline/scripts/run/run_jetson_fixed_input_alignment.sh` | Jetson fixed-input 对齐一键入口 |
| `projects/03_video_pipeline/scripts/quality/convert_project1_alignment_to_video_raw.py` | 项目一 baseline 到项目三对齐 raw 的桥接脚本 |
| `projects/03_video_pipeline/scripts/quality/sweep_bdd100k_confidence.py` | BDD raw 离线置信度扫描入口 |
| `benchmark/raw/03_video_pipeline/jetson_8gb/*jetson*tensorrt*.jsonl` | raw result |
| `logs/monitor/03_video_pipeline/jetson_8gb/*jetson*tensorrt*.log` | Jetson 监控 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | Jetson benchmark |
| `projects/03_video_pipeline/reports/stability_report.md` | Jetson 10 分钟、30 分钟、2 小时稳定性状态 |
| `projects/03_video_pipeline/reports/failure_and_fallback.md` | Jetson 异常注入、CPU fallback 和服务恢复 |
| `projects/03_video_pipeline/reports/video_pipeline.md` | Jetson 线程、队列、buffer 和后端链路 |
| `projects/03_video_pipeline/reports/runbook.md` | Jetson 复现步骤 |

fixed-input 对齐如果发现历史项目一 raw 只有 `quality_metric.num_detections`、没有逐框 `detections[]`，必须重新生成 baseline：可以分步执行 `extract_video_alignment_frames.py` + `projects/01_vision_deploy/scripts/benchmark/benchmark_tensorrt.py` + `convert_project1_alignment_to_video_raw.py`，也可以直接使用 `projects/03_video_pipeline/scripts/run/run_jetson_fixed_input_alignment.sh`。在 baseline/current 成对证据出现前，fixed-input alignment 只能写 `pending_board_run` / `not_verified`。

## 验收标准

- pipeline 使用 TensorRT 后端可连续运行。
- 有端到端和分阶段耗时。
- 有 GPU/DLA 调用证据或 TensorRT runtime 证据。
- 温度、功耗或电源模式、降频情况有记录。
- 结果能与项目一/二单模型 benchmark 对照，但不能直接复用单模型 FPS 作为 pipeline FPS。
- raw result、runtime log、monitor log、run 记录和报告结论可以互相追溯。

## 降级和问题库

下面问题必须进入问题库：

- engine 加载失败。
- 显存不足。
- CUDA/TensorRT runtime 错误。
- 温控降频。
- pipeline 性能显著低于单模型 benchmark 且无法解释。
- TensorRT/GPU 调用证据缺失。
- 出现 CPU fallback。
- fixed-input alignment、BDD100K MOT mini 或任务级质量证据不完整却试图写入 `pass`。

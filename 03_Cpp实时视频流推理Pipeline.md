# 03_Cpp实时视频流推理Pipeline

实验结果状态仍以 `projects/03_video_pipeline/reports/` 和各次 `runs/<run_id>/run.md` 为准。

## 当前收口快照（2026-06-25）

- Jetson：`03A / 03B / 03C / 03D / 03G / 03H` 工程证据已闭环。`20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 提供 IMX219 sustained `runtime600` 吞吐证据，`20260623_jetson_8gb_yolo11n_tensorrt_imx219_preview_rotate180_rg_bayerfix` 提供方向、颜色和本地预览有效性证据；Jetson 子项目现可正式收口。
- RK3588：项目三主线已闭环，BDD100K 任务级质量继续按非阻塞失败单独归档。
- RDK X5：`20260624` 已完成项目三 C++ single-thread、600s runtime、600/1800/7200s stability、CLI failure 5/5 和 `systemd_service_test_v2` 的正式上板回填；其中 `20260624_rdk_x5_8gb_systemd_service_test_v2` 已验证 `start=active`、`restart=active`、`stop=inactive`、`health_check=pass`。当前 live-source 已明确收敛为 `imx219_rdkx5_hbn_001`，接入方式是 `mipi_camera_hbn + HBN/srcampy`，并默认按 `PREVIEW_WINDOW=auto` 在检测到图形显示器时实时显示窗口；只剩 IMX219 `input_disconnect` 的正式板端证据待补。

## 定位

本文件是项目三的总规范，面向 Jetson、RK3588、RDK X5 等所有目标开发板共同使用。它根据 `docs/standards/项目选题与作品集.md` 中“C++ 实时视频流推理 pipeline”的选题要求，以及 `docs/standards/项目方案.md` 中项目三的执行方案细化得到；板卡专属差异只在对应 `specs/` 中进一步细化。

项目三是工程化主项目。它承接项目一和项目二的 YOLO11n 端侧部署结果，把“单张图片推理”推进到“可持续运行、可监控、可恢复、可服务化”的 C++ 实时视频流系统。

核心链路：

```text
USB Camera / MIPI Camera / RTSP / video file
-> capture / decode
-> preprocess
-> TensorRT / RKNN / RDK X5 BPU inference
-> decode boxes / NMS
-> render / display / save / report
-> latency / FPS / queue / resource / stability logs
```

项目三的成果不是一段能跑一次的视频 demo，而是一组可复现证据：

- C++ pipeline 代码和构建方式。
- 单线程最小链路、多线程链路、队列限流、buffer 复用。
- 至少一个真实端侧后端的 C++ 集成，目标是 Jetson、RK3588、RDK X5 都有记录。
- 端到端 FPS、p50/p90/p95/p99 延迟、分阶段耗时、队列长度、丢帧率。
- runtime 日志、monitor 日志、failure 日志和 raw result。
- 30 分钟必测、2 小时目标的稳定性实验。
- systemd 或 Docker 服务化复现步骤。
- 问题库和降级策略。

## 总规范对齐

| 来源             | 要求                                                         | 本项目落地方式                                               |
| ---------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 项目选题与作品集 | 摄像头或视频文件输入，capture/preprocess/infer/postprocess/output 多线程解耦 | 固定 C++ pipeline 分层、线程模型和阶段耗时字段               |
| 项目选题与作品集 | 队列限流，避免延迟无限堆积                                   | `03C` 定义队列容量、满队列策略、丢帧策略和 buffer 复用       |
| 项目选题与作品集 | 异常恢复、systemd 或 Docker 部署                             | `03G` 定义错误码、断流重连、服务化部署和异常注入             |
| 项目选题与作品集 | 连续运行 2 小时以上内存和温度曲线                            | `03H` 显式执行稳定性与监控实验                               |
| 项目方案         | 项目三是 P0 工程化主项目                                     | 本项目必须把项目一/二模型变成持续运行的端侧系统              |
| MLPerf 风格规范  | pipeline 报告必须包含 sustained、p95/p99、资源和 raw result  | `runtime_benchmark.md`、`stability_report.md` 必须包含或引用 MLPerf-style Summary |
| 问题库规范       | 断流、队列堆积、后端加载失败、服务化失败必须复盘             | 所有工程问题进入 `projects/03_video_pipeline/reports/troubleshooting.md` |

## 执行自由度与硬性证据约束

项目三的 specs 是执行参考书，不是唯一脚本。执行者可以替换 C++ 框架、日志库、线程模型、队列实现、视频输入库、后端封装、监控工具或服务化方式，但不能替换项目目标。

硬性约束：

- 必须保留环境基线、模型 hash、后端 artifact hash、配置、命令、raw result、runtime 日志、monitor 日志和输出样例。
- 必须统计 capture、decode、preprocess、inference、postprocess、output、end-to-end latency。
- 必须保留 frame_id、timestamp、队列长度、丢帧计数、错误码和状态字段。
- 必须证明真实后端调用，TensorRT、RKNN、BPU、CPU fallback 必须明确区分。
- 必须执行稳定性与监控实验，不能只在文档中声明。
- 必须在执行过程中同步维护 `projects/03_video_pipeline/runs/`、`projects/03_video_pipeline/reports/`、`benchmark/`、`logs/` 和问题库。

如果执行过程和 specs 推荐步骤不同，报告中只需要说明替代方法、替代原因和证据等价性。不能因为步骤不同而省略证据，也不能把单次成功 demo 写成工程化成果。

## 项目边界

包含：

- C++17 / CMake 最小单线程 demo。
- USB/MIPI 摄像头、RTSP、视频文件输入。
- capture、decode、preprocess、infer、postprocess、output 多线程 pipeline。
- 有界队列、丢帧策略、buffer 复用、延迟控制。
- TensorRT、RKNN、RDK X5 BPU 后端 C++ 封装。
- frame_id、timestamp、阶段耗时、队列长度、丢帧率、异常事件日志。
- 10 分钟 smoke、30 分钟稳定性、2 小时验收目标、可选 8 小时压力测试。
- systemd 或 Docker 服务化部署和复现步骤。

不包含：

- 模型量化策略本身，进入项目二。
- 模型压缩训练，进入项目六。
- LLM/VLM 告警解释，进入项目五。
- UI 大屏或复杂 Web 后台。本项目只要求显示、保存或结构化输出可验证。
- 新模型训练。本项目使用项目一、项目二产出的 YOLO11n 端侧模型。

实时显示补充要求：

- 对 `USB camera`、`MIPI camera`、`RTSP`、`OpenNI camera` 这类实时源，项目允许并建议在板端存在图形环境时直接显示实时检测过程。
- 当前共享 C++ app 的正式控制开关为 `PREVIEW_WINDOW=auto|on|off`：`auto` 表示“仅当输入是实时源且检测到 `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE=x11|wayland` 时自动显示”，`off` 表示严格关闭，`on` 表示强制尝试打开。
- 预览窗口必须显示检测框、类别名以及最基本的实时指标，当前正式 HUD 字段为 `FPS` 和 `DET`。
- headless、纯 SSH 终端、systemd 或其他无图形环境场景下，预览必须自动降级为关闭，不能把“没有屏幕”误判成 runtime 失败。
- 该实时显示能力属于项目三自身实现，代码和运行入口必须保留在当前项目内，不得把旧仓库的板级程序直接耦合进来。

## 横向能力引用

- 问题库：输入断流、模型加载失败、后端初始化失败、CPU fallback、队列堆积、内存增长、温控降频、服务化失败、报告无法追溯，都必须记录到 `projects/03_video_pipeline/reports/troubleshooting.md`。
- MLPerf-style Benchmark：`runtime_benchmark.md` 和 `stability_report.md` 必须引用 `docs/standards/MLPerf风格Benchmark规范.md`，包含 scenario、quality gate、performance、resource、reproducibility。
- 边缘设备稳定性与监控系统：该横向能力在项目三中必须真实执行，落地到 `03H_稳定性监控规范.md`、`logs/monitor/03_video_pipeline/` 和 `projects/03_video_pipeline/reports/stability_report.md`。
- 模型变更质量对齐：检测模型 artifact、后端 wrapper、前处理、后处理、输入 shape、输出解析或 NMS 变化后，必须引用 `docs/standards/模型变更质量对齐规范.md`，对齐项目一/二 baseline；纯队列、日志、监控或服务包装变化按豁免规则记录。
- Jetson 单板 run 在写入 runtime 或 quality 结论前，必须生成 `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md`，证明项目三 C++ preprocess / postprocess 仍与项目一/二基线一致；consistency check 失败时，该 run 不允许继续写 runtime 或 quality 结论。

## 核心原则

### 原则 1：必须是真 C++ pipeline

不能把 Python 脚本、单模型 benchmark 或 OpenCV 读帧脚本包装成项目三成果。项目三主链路必须是 C++，Python 只可用于辅助监控、日志分析、schema 校验和报告生成。

唯一例外是板级厂商驱动只提供 Python 绑定、而项目三又必须在当前仓库内保留真实 live-source 接入能力时，可以增加一个**本地输入适配 shim**：例如 RDK X5 的 `HBN/srcampy -> stdout` helper。此时必须同时满足：

- 推理、队列、日志、预览、故障注入和主控制流程仍由当前仓库的 C++ app 负责。
- shim 只能承担“把板级驱动帧送到 C++ app”的职责，不能把推理主链路搬回 Python。
- 该适配层必须随当前项目一起入库、可复现、可审计，并在 run.md / 报告中明确记录。

### 原则 2：每帧必须可追溯

每一帧至少要能追踪：

```text
input_source_id
frame_id
capture_ts
preprocess_ts
infer_start_ts
infer_end_ts
postprocess_ts
output_ts
status
error_code
```

如果发生丢帧，必须能说明是输入断流、队列满丢帧、超时丢帧、后端失败还是输出限速导致。

### 原则 3：队列必须有界

实时系统不能无限堆积帧。所有阶段之间的队列必须有容量、满队列策略和日志字段。

至少比较或说明以下策略：

```text
drop_oldest
drop_newest
block_with_timeout
keep_key_frame
```

当前仓库主线对这些策略的解释必须写成明确行为，不能只写名字：

- 队列策略只在“目标队列已满”时触发；队列未满时直接入队。
- `queue_push_timeout_ms` 等待的是“队列腾出一个空位”，不是“推理响应超时”，也不是“端到端延迟上限”。
- 当前 `src/video_pipeline_app.cpp` 的参考实现里，`queue_policy` 和 `queue_push_timeout_ms` 是 pipeline 级全局参数，会同时作用于 `capture -> preprocess`、`preprocess -> infer`、`infer -> postprocess`、`postprocess -> output` 四段有界队列；当前不是“每段队列各自独立策略”。

| 策略 | 目标队列已满时的实际动作 | 是否等待 | 何时丢当前帧/包 | 当前口径说明 |
|---|---|---|---|---|
| `drop_oldest` | 先移除队列中最旧元素，再把当前新元素入队 | 否 | 不丢当前帧，丢的是队列里最旧帧 | 优先保留最新视图，典型用途是低延迟实时显示 |
| `drop_newest` | 保持当前队列内容不变，直接放弃本次新元素 | 否 | 队列一满就丢当前帧 | 适合“不想覆盖已排队结果”的场景，但更容易保留旧画面 |
| `block_with_timeout` | 最多等待 `queue_push_timeout_ms` 让目标队列出现空位；有空位再入队 | 是，等待上限由 `queue_push_timeout_ms` 决定 | 等到超时后队列仍满，或队列已关闭时 | `33 ms` 的意思是“单次入队最多等 33 ms”，不是“33 ms 没有下游响应就判失败” |
| `block` / `block_forever` / `no_drop` | 一直等待到有空位或队列关闭，再继续 | 是，无超时上限 | 不因 timeout 丢当前帧 | 适合 no-drop / 质量评估路径，不适合把低延迟当第一目标的主线 |
| `keep_key_frame` | 需要业务规则判定哪些帧必须保留 | 视实现而定 | 视实现而定 | 这是规范级可选策略；当前主线 app 尚未实现，不能把它当作已验证策略写进结论 |

最终选择的策略必须由端到端延迟、丢帧率和稳定性证据支撑。

### 原则 4：后端证据必须真实

不能只写“使用 TensorRT/RKNN/BPU”。报告必须给出：

```text
后端模型路径和 hash
runtime 初始化日志
推理调用日志或 wrapper 证据
加速器利用率或不可观测原因
CPU fallback 判断
端到端 raw result
```

### 原则 5：稳定性是项目三的一等成果

30 分钟稳定性是必测项，2 小时稳定性是项目验收目标。稳定性报告必须包含内存曲线、温度曲线、队列长度、丢帧率、异常恢复次数和日志路径。

## 目录结构

本项目按当前仓库结构组织，不额外引入 `deploy/`、`inputs/`、`outputs/` 等新的顶层目录。项目三自己的主文档、specs、代码、配置、脚本、运行记录和人工报告放在 `projects/03_video_pipeline/` 下；跨项目共享的数据、模型、benchmark 原始结果和日志放在仓库已有的全局目录下。

```text
edge-inference-deploy-lab/
  projects/
    03_video_pipeline/
      03_Cpp实时视频流推理Pipeline.md
      specs/
        00_environment_baseline_template.md
        00_run_record_template.md
        03A_单线程最小Demo规范.md
        03B_多线程Pipeline规范.md
        03C_队列限流与Buffer复用规范.md
        03D_Jetson_TensorRT_CppPipeline规范.md
        03E_RK3588_RKNN_CppPipeline规范.md
        03F_RDK_X5_BPU_CppPipeline规范.md
        03G_异常恢复与服务化部署规范.md
        03H_稳定性监控规范.md
        03I_统一RuntimeBenchmark与报告规范.md
      src/
        include/
        common/
        capture/
        preprocess/
        inference/
        postprocess/
        output/
        service/
      scripts/
        build/
        run/
        benchmark/
        monitor/
        service/
      configs/
        pipeline/
        models/
        boards/
        streams/
      runs/
        <run_id>/
          run.md
          outputs/
      reports/
        input_sources.md
        video_pipeline.md
        runtime_benchmark.md
        stability_report.md
        failure_and_fallback.md
        runbook.md
        troubleshooting.md

  data/
    videos/
      video_fixed_v1/
    images/
    validation/

  models/
    yolo11n/
      tensorrt/
      rknn/
      rdk_x5_bpu/
      rdk_x5_bpu_split_head/

  benchmark/
    raw/
      03_video_pipeline/
        jetson_8gb/
        rk3588_8gb/
        rdk_x5_8gb/
    processed/
      03_video_pipeline/
    reports/
      03_video_pipeline/
    schemas/
      video_pipeline_raw_schema.yaml

  logs/
    runtime/
      03_video_pipeline/
    monitor/
      03_video_pipeline/
    failures/
      03_video_pipeline/

  tools/
    collect_env/
    monitor/
    log_parser/
    report_generator/

  shared/
    cpp/
    python/
    metrics/
    schemas/
```

结构说明：

- `projects/03_video_pipeline/src/` 放 C++ 主体代码。`capture/` 管视频接入，`preprocess/` 管 resize/letterbox/normalize，`inference/` 管 TensorRT/RKNN/BPU wrapper，`postprocess/` 管 decode boxes/NMS，`output/` 管显示、保存和结构化输出，`service/` 管服务化入口。
- `projects/03_video_pipeline/configs/` 放项目三配置。`pipeline/` 管线程、队列、输出和日志，`models/` 管模型输入尺寸、类别、阈值，`boards/` 管板卡和后端参数，`streams/` 管视频源。
- `projects/03_video_pipeline/runs/` 放每次实验记录。每个 `run_id` 至少包含运行目的、环境基线、模型、输入、命令、配置、日志路径和结论。输出视频、截图或 JSON 样例优先放在对应 run 的 `outputs/`。
- `projects/03_video_pipeline/reports/` 放人工整理报告和问题库。
- `data/videos/video_fixed_v1/` 放固定测试视频。实时源的设备路径或 RTSP URL 写入 `projects/03_video_pipeline/configs/streams/` 和 run 记录。
- `models/yolo11n/` 放项目一、项目二产出的后端模型或模型索引。大文件是否入库由仓库规则决定，但报告必须记录路径、来源、大小和 hash。
- `benchmark/raw/03_video_pipeline/` 只放逐帧 frame-level 原始 JSONL/CSV，按开发板拆分。每行表示一帧，必须包含 `frame_id`。
- `benchmark/processed/03_video_pipeline/` 放 schema 校验、trace 校验、窗口级指标、runtime 聚合和 stability 聚合结果。
- `logs/runtime/03_video_pipeline/`、`logs/monitor/03_video_pipeline/`、`logs/failures/03_video_pipeline/` 分别保存运行日志、资源监控日志和失败最小复现日志。

判断目录是否合格：

```text
按项目能找到主文档、specs、src、scripts、configs、runs 和 reports。
按 run_id 能追溯到命令、配置、输入源、raw result、runtime 日志、monitor 日志和输出样例。
按开发板能找到板卡配置、后端模型、raw result、runtime 日志和 monitor 日志。
按报告能反向定位到 run、raw result 和问题库条目。
```

## run、环境基线与 schema 统一规则

项目三统一使用目录式 run，不使用平铺 `.md` 文件：

```text
projects/03_video_pipeline/runs/<run_id>/run.md
```

每个 run 可以附带：

```text
projects/03_video_pipeline/runs/<run_id>/outputs/
projects/03_video_pipeline/runs/<run_id>/config_snapshot/
projects/03_video_pipeline/runs/<run_id>/notes.md
```

run 记录模板固定为：

```text
projects/03_video_pipeline/specs/00_run_record_template.md
```

环境基线模板固定为：

```text
projects/03_video_pipeline/specs/00_environment_baseline_template.md
```

环境基线 run 命名：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_<target>_env_baseline/run.md
```

run_id 建议格式：

```text
<yyyymmdd>_<target>_<model>_<backend>_<pipeline_mode_or_stage>
```

示例：

```text
20260602_jetson_8gb_yolo11n_tensorrt_single_thread_demo
20260602_rk3588_8gb_yolo11n_rknn_multithread_pipeline
20260602_rdk_x5_8gb_yolo11n_bpu_stability_2h
20260602_all_yolo11n_video_pipeline_summary
```

raw result schema 固定为：

```text
benchmark/schemas/video_pipeline_raw_schema.yaml
```

failure log schema 固定为：

```text
benchmark/schemas/video_pipeline_failure_schema.yaml
```

`status` 只能使用 `pass`、`fail`、`degraded`、`blocked`、`not_executed`、`not_verified`，语义以 `00_run_record_template.md` 为准。

## 模型与开发板分工

| 开发板     | 主后端          | 模型来源                                     | 本项目目标                                                   |
| ---------- | --------------- | -------------------------------------------- | ------------------------------------------------------------ |
| Jetson 8GB | TensorRT / CUDA | 项目一或项目二产出的 YOLO11n TensorRT engine | 验证 C++ pipeline 与 TensorRT 端到端性能和稳定性             |
| RK3588 8GB | RKNN / RKNPU    | 项目一或项目二产出的 YOLO11n RKNN 模型       | 验证国产 NPU C++ pipeline、RKNPU 调用证据和 CPU fallback 判断 |
| RDK X5 8GB | BPU / split-head bin | 项目二正式量化收口的 YOLO11n INT8 split-head `.bin` 主线模型 | 验证 RDK X5 BPU pipeline、BPU 调用证据、CPU fallback 判断和服务化稳定性 |

如果某块板卡暂不可用，不能删除该项。必须在 `projects/03_video_pipeline/reports/runtime_benchmark.md` 或 `projects/03_video_pipeline/reports/failure_and_fallback.md` 中标记 `not_executed`、`blocked` 或 `degraded`，并说明原因和后续补测计划；该状态只影响对应板卡或后端的结论，不影响其他开发板继续执行。

## 输入资产

| 资产          | 路径或来源                                                   | 要求                                               |
| ------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| 后端模型      | `models/yolo11n/`                                            | 记录来源、格式、大小、hash、项目一/二关联报告      |
| 固定视频源    | `data/videos/video_fixed_v1/`                                | 至少包含短视频、长视频、空场景、密集目标、光照变化 |
| 实时输入源    | USB/MIPI/RTSP                                                | 记录设备路径、URL、分辨率、FPS、是否可长期使用     |
| pipeline 配置 | `projects/03_video_pipeline/configs/pipeline/`               | 线程、队列、丢帧、输出、日志配置                   |
| stream 配置   | `projects/03_video_pipeline/configs/streams/`                | 输入源 ID、类型、URI、分辨率、FPS                  |
| model 配置    | `projects/03_video_pipeline/configs/models/yolo11n.yaml`     | 模型输入、类别、阈值、NMS                          |
| board 配置    | `projects/03_video_pipeline/configs/boards/<target>.yaml`    | 后端模型、runtime、设备参数                        |
| 环境基线      | `projects/03_video_pipeline/runs/<yyyymmdd>_<target>_env_baseline/run.md`，字段对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md` | 每块板和后端都必须有                               |

输入数据建议分组：

| input_source_id          | 场景         | 目的                       |
| ------------------------ | ------------ | -------------------------- |
| `video_long_loop_001`    | 单文件循环回退输入 | 调试、回退或单文件循环复现 |
| `video_set_runtime_v1`   | 20 条 BDD100K playlist | 600 秒 runtime 主线复现 |
| `video_set_stability_v1` | 80 条 BDD100K playlist | 30 分钟和 2 小时 stability |
| `bdd100k_mot_mini_v1`    | 80 条带人工标注道路视频 | 正式视频质量对齐；评估全部 15,631 个标注帧 |
| `imx219_csi_001`         | Jetson CSI IMX219（V4L2 raw） | 正式 live-source；验证真实采集链路和 `input_disconnect` |
| `imx219_rdkx5_hbn_001`   | RDK X5 IMX219（HBN/srcampy） | RDK X5 正式 live-source；通过本仓库内 helper 把 NV12 连续帧送入共享 C++ pipeline，并用于 `input_disconnect` |
| `imx219_csi_argus_001`   | Jetson CSI IMX219（Argus/ISP） | 仅保留为板端诊断入口；当前板端 `Argus` 路径无法建立有效帧，不得作为正式主线候选 |
| `rtsp_stream_001`        | RTSP 实时源  | 检查断流、重连和端到端延迟 |
| `astra_s_openni_001`     | RK3588 Astra S（OpenNI2 / liborbbec） | RK3588 正式 live-source；验证真实采集链路、`input_disconnect` 和 camera service |
| `usb_camera_001`         | 通用 USB UVC 摄像头占位 | 仅作候选输入源占位；不得替代 Astra S 已验证结论 |

RK3588 的正式验收是双 source 口径，不是只保留一种输入：

- 视频集持续回放 source：`video_set_runtime_v1` / `video_set_stability_v1`，用于可复现 runtime、稳定性、视频集 service。
- 真实摄像头 source：当前登记为 `astra_s_openni_001`，技术口径为 `input_source_type=openni_camera`、selector `2bc5/0402`，默认 color stream 为 `640x480 RGB888 @ 30 FPS`，用于真实 live capture、`input_disconnect` 和 camera service。

视频集虽可持续循环，但技术口径仍是 file/playlist source，不得用它替代 live-source 断流证据。

RK3588 Astra S 还必须记录一个权限前提：板端需具备 OpenNI2 runtime（`libOpenNI2.so` + `liborbbec.so`），并通过 udev 规则把 USB 设备 `2bc5:0402` 赋给 `plugdev`，否则 non-root CLI 和 systemd camera service 只能以 `Access denied` 失败，不能算 live-source 已闭环。

输入源必须有 manifest。主线配置为：

```text
projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml
projects/03_video_pipeline/reports/input_sources.md
```

每个输入源至少记录：

```text
input_source_id
input_source_type
uri
video_sha256
codec
width
height
fps
duration_sec
frame_count
bitrate
loop_mode
timestamp_source
availability
```

固定视频必须记录 SHA256；实时源不能计算 SHA256 时写 `null`，但必须记录设备或 URL、分辨率、FPS 和可用状态。所有 run 必须引用 `input_source_id`，不能只写临时文件名。

## 输出资产

| 资产             | 路径                                                         | 用途                                          |
| ---------------- | ------------------------------------------------------------ | --------------------------------------------- |
| C++ 源码         | `projects/03_video_pipeline/src/`                            | pipeline、后端 wrapper、队列、日志、服务入口  |
| 构建脚本         | `projects/03_video_pipeline/scripts/build/`                  | CMake 配置和构建                              |
| 运行脚本         | `projects/03_video_pipeline/scripts/run/`                    | 单线程、多线程、分板运行                      |
| benchmark 脚本   | `projects/03_video_pipeline/scripts/benchmark/`              | schema 校验、聚合、trace 检查                 |
| 监控脚本         | `projects/03_video_pipeline/scripts/monitor/`                | 资源采集和进程监控                            |
| 服务脚本         | `projects/03_video_pipeline/scripts/service/`                | systemd 或 Docker 配置生成和验证              |
| run 记录         | `projects/03_video_pipeline/runs/<run_id>/run.md`            | 单次实验复现入口                              |
| raw result       | `benchmark/raw/03_video_pipeline/<target>/<run_id>.jsonl` 或 `.csv` | 原始逐帧 frame-level 指标                     |
| processed result | `benchmark/processed/03_video_pipeline/`                     | window、runtime、stability 聚合指标和检查报告 |
| runtime 日志     | `logs/runtime/03_video_pipeline/<target>/<run_id>.log`       | pipeline 运行日志                             |
| monitor 日志     | `logs/monitor/03_video_pipeline/<target>/<run_id>.csv`       | CPU/GPU/NPU/BPU、内存、温度、功耗             |
| failure 日志     | `logs/failures/03_video_pipeline/<target>/<run_id>.jsonl`    | 异常注入和故障日志                            |
| pipeline 报告    | `projects/03_video_pipeline/reports/video_pipeline.md`       | 架构、线程、队列、模块接口                    |
| benchmark 报告   | `projects/03_video_pipeline/reports/runtime_benchmark.md`    | 性能和端到端指标                              |
| 稳定性报告       | `projects/03_video_pipeline/reports/stability_report.md`     | sustained 结果和资源曲线                      |
| 降级报告         | `projects/03_video_pipeline/reports/failure_and_fallback.md` | 异常恢复和服务化策略                          |
| runbook          | `projects/03_video_pipeline/reports/runbook.md`              | 从构建到运行的复现步骤                        |
| 问题库           | `projects/03_video_pipeline/reports/troubleshooting.md`      | 工程问题和修复记录                            |

## 执行入口

| spec                                           | 作用                                                         |
| ---------------------------------------------- | ------------------------------------------------------------ |
| `specs/00_environment_baseline_template.md`    | 项目三环境基线模板，覆盖 C++ 构建、视频输入、runtime、服务化和监控 |
| `specs/00_run_record_template.md`              | 项目三目录式 run 记录模板                                    |
| `specs/03A_单线程最小Demo规范.md`              | 构建 C++ 最小链路，验证输入、推理、后处理、输出和基础指标    |
| `specs/03B_多线程Pipeline规范.md`              | 拆分 capture/preprocess/infer/postprocess/output 多线程链路  |
| `specs/03C_队列限流与Buffer复用规范.md`        | 定义队列限流、丢帧策略、buffer 复用和延迟控制                |
| `specs/03D_Jetson_TensorRT_CppPipeline规范.md` | Jetson TensorRT C++ 后端集成                                 |
| `specs/03E_RK3588_RKNN_CppPipeline规范.md`     | RK3588 RKNN C++ 后端集成                                     |
| `specs/03F_RDK_X5_BPU_CppPipeline规范.md`      | RDK X5 BPU C++ 后端集成                                      |
| `specs/03G_异常恢复与服务化部署规范.md`        | 异常恢复、日志、退出码、systemd/Docker 服务化                |
| `specs/03H_稳定性监控规范.md`                  | 边缘设备稳定性与监控系统实验                                 |
| `specs/03I_统一RuntimeBenchmark与报告规范.md`  | raw result 校验、指标聚合、最终报告和 runbook 汇总           |

## 每次实验的通用动作

每个模型、每块板、每种 pipeline 模式都按同一套动作执行，避免报告口径不一致。

| 顺序 | 动作              | 具体做法                                    | 必须记录                             | 通过条件                 |
| ---: | ----------------- | ------------------------------------------- | ------------------------------------ | ------------------------ |
|    1 | 确认环境基线      | 采集系统、runtime、驱动、电源、散热、swap   | `environment_baseline_id`            | 能找到环境基线记录       |
|    2 | 确认模型资产      | 检查模型来源、格式、文件大小、hash          | `model_file_hash`、项目一/二报告路径 | 模型文件可追溯           |
|    3 | 固定输入          | 选择固定视频、实时源或 RTSP，不临时改输入   | `input_source_id`、配置路径          | 后续可重复运行           |
|    4 | 最小可运行        | 先跑短输入，不开完整 benchmark              | 命令、stdout/stderr、是否加载成功    | 能推理或明确失败         |
|    5 | warmup            | 跑 1-3 次，不计入统计                       | warmup 次数、异常情况                | warmup 后系统稳定        |
|    6 | runtime benchmark | 固定配置重复或持续运行                      | p50/p90/p95/p99、FPS、队列、丢帧     | 有 raw CSV/JSONL         |
|    7 | 资源监控          | benchmark 同时采集资源                      | monitor log 路径                     | 资源数据和推理时间能对齐 |
|    8 | 质量检查          | 对输出视频、JSON、检测框做可用性检查        | 输出样例、空结果、异常帧             | 输出能用于后续项目       |
|    9 | 降级尝试          | 失败时降低分辨率、FPS、输出、队列或后端设置 | 降级前后配置和指标                   | 有明确降级策略           |
|   10 | 写报告            | 更新 reports 和问题库                       | markdown、raw result、log path       | 每个结论可追溯           |

最小粒度：

```text
环境基线 -> 模型资产 -> 输入源 -> 最小样例 -> runtime benchmark -> 资源监控 -> 异常/降级 -> 稳定性 -> 报告汇总
```

## 阶段内按开发板独立推进规则

项目三仍然按阶段推进，但阶段是能力维度，不是开发板之间的串行队列。Jetson、RK3588、RDK X5 在同一阶段内互相独立；只要某块板具备该阶段所需的环境、模型、配置和输入源，就可以直接执行对应任务，不需要等待其他开发板完成。

阶段编号只用于组织文档和报告，不表示跨板卡部署顺序。阶段 4、阶段 5、阶段 6 是三条并列的后端集成路线：

```text
阶段 0 资产和环境：Jetson / RK3588 / RDK X5 独立准备
阶段 1 单线程 demo：任一可用开发板可独立执行
阶段 2 多线程 pipeline：任一可用开发板可独立执行
阶段 3 队列限流和 buffer 复用：任一可用开发板可独立执行
阶段 4 端侧后端集成：Jetson TensorRT
阶段 5 端侧后端集成：RK3588 RKNN
阶段 6 端侧后端集成：RDK X5 BPU
阶段 7 异常恢复和服务化：按可用开发板独立执行
阶段 8 稳定性监控：按可用开发板独立执行
阶段 9 汇总报告：汇总已完成板卡，并显式保留未完成板卡状态
```

单板闭环条件与汇总规则：

| 阶段 | 适用对象 | 单板完成条件 | 跨板卡规则 |
|---|---|---|---|
| 阶段0 | 每块目标板卡 | 环境基线、board 配置、模型 hash、输入源 manifest 可追溯 | 不等待其他板卡；缺硬件或缺模型时只标记该板卡状态 |
| 阶段1 | 每块可用板卡 | 单线程 run、raw result、runtime log、输出样例完整 | 任一板卡完成即可进入该板卡后续阶段 |
| 阶段2 | 每块可用板卡 | 多线程 run、trace check、队列长度、端到端延迟完整 | 多线程链路按单板验证，不要求三板同步 |
| 阶段3 | 每块可用板卡 | 队列策略对比、丢帧率、内存曲线、策略说明完整 | 队列策略可以按板卡资源差异分别选择 |
| 阶段4/5/6 | 对应后端板卡 | 后端 wrapper、artifact hash、加速器调用证据、CPU fallback 判断完整 | 三条后端路线互不作为前置条件，按硬件可用性任意顺序执行 |
| 阶段7 | 每块已跑通 pipeline 的板卡 | 断流、模型加载失败、队列堆积、服务启停证据完整 | 异常恢复按单板闭环，不阻塞其他板卡 |
| 阶段8 | 每块已跑通 pipeline 的板卡 | 10 分钟 smoke、30 分钟 short sustained、2 小时目标状态可追溯 | 稳定性档位可以按板卡进度分别推进 |
| 阶段9 | 汇总报告 | 每个结论可追溯到 run/raw/log/monitor；未完成项状态明确 | 可以先汇总已完成板卡，但不得把未完成板卡写成通过 |

如果任一开发板在某阶段失败，不能在报告中假设通过。必须记录为 `fail`、`blocked`、`degraded` 或 `not_verified`，写入 `projects/03_video_pipeline/reports/troubleshooting.md` 或 `failure_and_fallback.md`。该状态只约束对应开发板或后端的正式结论，不阻塞其他开发板继续执行同阶段或后续单板任务。

## Jetson TensorRT 参考主线内容

Jetson TensorRT 是项目三已经固定的一条参考实现主线，不是 RK3588 或 RDK X5 的前置条件。RK3588 RKNN 与 RDK X5 BPU 应分别参考 `03E`、`03F` 独立执行；Jetson 结果只作为可复用的工程经验和报告格式参考，不能作为其他板卡开始执行的必要条件。

当前 Jetson 路线已固定以下内容：

| 项 | 路径 / 口径 | 状态 |
|---|---|---|
| C++ 构建入口 | `projects/03_video_pipeline/CMakeLists.txt` | ready_for_board_build |
| C++ pipeline 应用 | `projects/03_video_pipeline/src/video_pipeline_app.cpp` | ready_for_board_build |
| Jetson board 配置 | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | ready |
| YOLO11n pipeline 模型配置 | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | ready |
| Jetson 多线程 pipeline 配置 | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml` | ready |
| Jetson 单线程配置 | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_single_thread.yaml` | ready |
| 构建脚本 | `projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh` | ready |
| 运行脚本 | `projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | ready |
| 稳定性脚本 | `projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | ready |
| 监控脚本 | `projects/03_video_pipeline/scripts/monitor/monitor_jetson_tegrastats.sh` | ready |
| systemd 模板 | `projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-jetson.service` | ready |

Jetson 摄像头实时显示当前也已经固定为项目三内部能力：

- 共享 app 通过 `--preview-window auto|on|off` 控制实时预览；Jetson 运行脚本对外暴露为 `PREVIEW_WINDOW` 环境变量。
- `PREVIEW_WINDOW=auto` 时，仅在实时源且图形环境存在时显示窗口；窗口关闭不会影响 raw result、monitor 和 runtime 产物生成。
- 当前正式显示内容包括检测框、英文类别名、`FPS`、`DET`。
- 稳定性、8 小时 mixed、buffer reuse A/B、disconnect 自动化等非交互脚本默认应使用 `PREVIEW_WINDOW=off`，避免 GUI 干扰正式 benchmark。

Jetson 主线 artifact 使用项目二已经通过质量检查的 TensorRT INT8 PTQ engine；项目三 Jetson 路线不再使用 FP16 engine 作为主线输入：

| 字段 | 值 |
|---|---|
| backend artifact | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` |
| SHA256 | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` |
| 上游项目 | `02_quantization` |
| 上游质量状态 | 以 `projects/02_quantization/reports/ptq_report.md` 和对应 raw result 为准 |
| 项目三状态 | 只作为 pipeline 输入资产，不能把项目二单模型 FPS 直接写成项目三 pipeline FPS |
| 使用规则 | Jetson TensorRT pipeline 默认加载该 INT8 engine；FP16 engine 不作为项目三 Jetson 主线或默认 fallback |

Jetson 单板报告更新顺序：

```text
run.md
-> benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl
-> logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log
-> logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log
-> benchmark/processed/03_video_pipeline/<run_id>_summary.csv
-> reports/video_pipeline.md
-> reports/runtime_benchmark.md
-> reports/stability_report.md
-> reports/failure_and_fallback.md
-> reports/runbook.md
```

Jetson Benchmark 表格落点固定如下。上板前可以保留 `not_executed`，但不能删除表格；上板后所有数值必须从项目三 raw result、processed result、runtime log 和 monitor log 聚合得到，不能复用项目一/二单模型吞吐数字。

| 报告或规范 | 必须包含的 Jetson 表格 | 数据来源 | 未执行时状态 |
|---|---|---|---|
| `03D_Jetson_TensorRT_CppPipeline规范.md` | Jetson benchmark 指标矩阵、证据矩阵、验收矩阵 | 03D spec、Jetson 配置、03I 字段要求 | `not_executed` |
| `reports/video_pipeline.md` | Jetson pipeline 阶段、线程、队列、buffer 和后端 wrapper 表 | `configs/pipeline/jetson_tensorrt_pipeline.yaml`、C++ app、run 记录 | `ready_for_board_run` 或 `not_executed` |
| `reports/runtime_benchmark.md` | Runtime Summary、Stage Latency、Queue/Buffer、Resource/Accelerator、Quality Gate、Reproducibility | `benchmark/raw/03_video_pipeline/jetson_8gb/*.jsonl`、`benchmark/processed/03_video_pipeline/*.csv`、runtime/monitor log | `not_executed` |
| `reports/stability_report.md` | Stability Summary、Resource Trace、Queue/Drop Trend、Failure During Stability、MLPerf-style Summary | stability raw、`tegrastats`、failure log、run 记录 | `not_executed` |
| `reports/failure_and_fallback.md` | Failure Cases、CPU Fallback、Service Recovery、Benchmark 影响表 | failure JSONL、runtime log、journal、问题库 | `not_executed` |
| `reports/runbook.md` | Jetson benchmark 执行顺序、命令、输出路径、填表顺序 | 03A/03B/03C/03D/03G/03H/03I | `not_executed` |

## 阶段拆分

### 阶段 0：资产、配置和环境准备

目标：

- 固定模型、视频源、板卡配置和 benchmark schema。
- 确定项目一/二模型如何进入项目三。
- 确定每块板的环境基线和后端可用状态。

任务：

1. 在 `projects/03_video_pipeline/configs/boards/` 准备 `jetson_8gb.yaml`、`rk3588_8gb.yaml`、`rdk_x5_8gb.yaml`。
2. 在 `projects/03_video_pipeline/configs/models/` 准备 `yolo11n.yaml`，记录输入尺寸、类别、阈值、NMS 参数。
3. 在 `projects/03_video_pipeline/configs/streams/` 准备固定视频和实时源配置。
4. 在三块板上采集或继承环境基线，生成或引用唯一 `environment_baseline_id`；继承既有基线时必须补充本项目的视频输入、C++ 构建、runtime log 和 monitor log 增量证据。
5. 准备 `data/videos/video_fixed_v1/` 固定输入集。
6. 定义 `benchmark/schemas/video_pipeline_raw_schema.yaml`。
7. 定义 `benchmark/schemas/video_pipeline_failure_schema.yaml`。
8. 明确 raw result、runtime log、monitor log、failure log 的命名规则。

产出：

- 环境基线记录，或继承基线记录加项目三增量确认证据。
- 模型资产记录。
- 输入源清单。
- raw result schema。
- failure log schema。
- `projects/03_video_pipeline/reports/runbook.md` 初稿。

### 阶段 1：单线程最小 demo

目标：

- 用 C++ 跑通最小链路：capture/decode -> preprocess -> inference -> postprocess -> output。
- 验证模型、输入、预处理、后处理和输出格式一致。

必须记录：

- build 命令和 build 日志。
- run 命令和 runtime 日志。
- 模型路径、hash、后端类型。
- 输入源 ID 和输入文件 hash。
- 每帧 `frame_id`、timestamp、阶段耗时和输出状态。
- 输出视频、截图或 JSON 样例。

验收：

- 能完成至少一个固定视频源的推理。
- raw result 能被 03I schema 校验。
- 输出结果能追溯到输入源和模型文件。

### 阶段 2：多线程 pipeline

目标：

- 将单线程链路拆成 capture、preprocess、infer、postprocess、output 等阶段。
- 保证 frame_id 在多线程间可追踪。
- 记录队列长度和端到端延迟。

必须记录：

- 线程划分。
- 队列容量。
- 队列满策略。
- 每阶段耗时。
- 每阶段输入输出 frame_id。
- 队列长度和丢帧原因。

验收：

- 队列不无限增长。
- 输出顺序可解释。
- 端到端延迟不随运行时间持续恶化。
- 多线程结果与单线程结果的差异有解释。

### 阶段 3：队列限流与 buffer 复用

目标：

- 在高负载输入下控制延迟。
- 明确实时优先、完整帧优先或告警关键帧优先策略。
- 验证 buffer 复用是否降低内存增长或分配压力。

建议比较：

| 策略                 | 目标           | 适用场景             |
| -------------------- | -------------- | -------------------- |
| `drop_oldest`        | 丢最旧帧、保最新帧 | 低延迟实时显示       |
| `drop_newest`        | 丢当前新帧、保队列旧帧 | 不希望覆盖已排队结果 |
| `block_with_timeout` | 最多等超时后再决定是否丢当前帧 | 实时性和保留率折中   |
| `keep_key_frame`     | 仅保留关键帧或异常帧 | 告警触发，需额外实现 |

验收：

- 主线策略有数据支撑。
- 高负载下端到端延迟可控。
- 内存曲线没有持续增长。
- 丢帧率和丢帧原因可解释。

### 阶段 4：Jetson TensorRT C++ pipeline

目标：

- 将项目一/二的 TensorRT engine 接入 C++ pipeline。
- 完成 Jetson 端到端 benchmark 和资源监控。

必须记录：

- TensorRT engine 路径、精度、hash。
- TensorRT runtime 初始化日志。
- CUDA/GPU/DLA 调用证据或不可观测原因。
- `tegrastats` 或等价监控日志。
- 端到端 FPS、p95/p99、分阶段耗时、温度和功耗或电源模式。

验收：

- TensorRT 后端可连续运行。
- 结果能与项目一/二单模型 benchmark 对照。
- 没有把 CPU fallback 写成 TensorRT 成果。

### 阶段 5：RK3588 RKNN C++ pipeline

目标：

- 将 RKNN 模型接入 C++ pipeline。
- 证明 pipeline 实际调用 RKNPU 或清楚说明不可观测原因。

必须记录：

- RKNN 模型路径、hash、量化格式。
- RKNN runtime 日志。
- RKNPU 调用证据、NPU load 或不可读取原因。
- CPU fallback 判断。
- 端到端指标和资源指标。

验收：

- RKNN 后端可连续运行或有明确阻塞原因。
- RKNPU 调用证据完整，或不可读取原因合理。
- 队列和端到端延迟可控。

### 阶段 6：RDK X5 BPU C++ pipeline

目标：

- 直接继承项目二 RDK X5 环境基线和正式主线 artifact。
- 将项目二量化完成的 INT8 split-head `.bin` 模型接入 RDK X5 BPU pipeline。
- 证明 pipeline 实际调用 BPU 或清楚说明不可观测原因。

必须记录：

- 项目二环境基线 ID、项目三 build 命令和运行命令。
- split-head `.bin` 模型路径、hash、量化格式。
- BPU runtime 日志。
- BPU 调用证据、利用率或不可读取原因。
- CPU fallback 判断。
- 端到端指标和资源指标。

验收：

- BPU 后端可连续运行或有明确阻塞原因。
- 端到端延迟、分阶段耗时和资源曲线完整。
- 结果能与项目一/二单模型 benchmark 对照。

RDK X5 首次上板推荐顺序固定为：

1. `build_rdk_x5_bpu.sh`
2. `rdk_x5_bpu_single_thread.yaml` 单线程 smoke
3. `rdk_x5_bpu_pipeline.yaml` 多线程 `600s` runtime
4. `run_rdk_x5_bpu_stability.sh`
5. `run_rdk_x5_failure_injection.sh` 和 `test_rdk_x5_systemd_service.sh`

不要跳过单线程 smoke 直接做多线程 benchmark。单线程阶段的目标是先确认 `hbDNN` 初始化、NV12 输入和 split-head 输出解码，不是正式性能结论。

RDK X5 当前正式主线固定如下：

| 项目 | 固定值 | 说明 |
|---|---|---|
| environment baseline | `20260612_rdk_x5_8gb_env_baseline` | 直接继承项目二环境基线 |
| backend runtime | `bpu` | 项目三 RDK X5 C++ 主线 |
| execution provider | `BPU` | raw result、run、报告口径保持一致 |
| loader API | `Horizon hbDNN C API` | 当前推荐集成方式 |
| artifact path | `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin` | 项目二正式主线 |
| artifact sha256 | `2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c` | 必须与 board config、run、raw result 一致 |
| input contract | `NV12 bytes` | 当前 BPU 路线输入契约 |
| postprocess route | `split_head_external_dfl_nms` | 当前后处理口径 |
| build script | `projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh` | 统一构建入口 |
| runtime script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` | 统一 benchmark 入口 |
| stability script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | 统一稳定性入口 |
| failure / service | `projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh`、`projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh` | 统一异常与服务化入口 |

`2026-06-24` 的 RDK X5 项目三实测回填摘要如下：

| run_id | 类型 | 关键指标 | 当前口径 |
|---|---|---|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | single-thread smoke | `404` 帧 / `60s`、`6.7333 FPS`、`p95=146.5713 ms`、`0` drop、trace `pass` | 最小链路已打通 |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | 600s runtime | `10888` 帧 / `601s`、`18.1165 FPS`、`p95=167.0899 ms`、drop rate `0.3967`、`queue_full` | `drop_oldest` 实时主线可运行，trace `degraded` 但 `0` out-of-order |
| `20260624_rdk_x5_8gb_yolo11n_bpu_stability_acceptance_sustained` | 7200s stability | `133052` 帧 / `7200s`、`18.4794 FPS`、`p95=166.5849 ms`、memory growth `0.3597 MB/h`、temp peak `67.961 C` | 长稳通过，仍是 bounded-queue realtime 口径 |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | CLI failure | `input_open_failed / model_missing / invalid_shape / output_unwritable / queue_overflow = 5/5 pass` | 异常注入主线已建立 |
| `20260624_rdk_x5_8gb_systemd_service_test_v2` | systemd | `start=active`、`restart=active`、`stop=inactive`、`health_check=pass` | service lifecycle 已通过；旧的 placeholder `WORKDIR` / `CHDIR` 失败样本转入排障证据 |

### 阶段 7：异常恢复与服务化

目标：

- 验证 pipeline 不是只能在终端手动跑一次。
- 定义错误码、日志格式、异常注入、systemd 或 Docker 运行方式。

必须覆盖：

| 异常              | 期望                 |
| ----------------- | -------------------- |
| 输入源断流        | 重连或清晰错误       |
| 模型路径错误      | 明确错误码和日志     |
| 后端 runtime 失败 | 退出或降级，不假运行 |
| 输出目录不可写    | 记录错误并按策略退出 |
| 队列堆积          | 丢帧、限流或告警     |
| 服务重启          | 有日志和恢复状态     |

验收：

- 服务可启动、停止、重启。
- 异常注入结果可复现。
- 失败不会被隐藏，必须进入 `failure_and_fallback.md` 和问题库。

### 阶段 8：稳定性与监控实验

目标：

- 执行项目三中的“边缘设备稳定性与监控系统”实验。
- 验证 pipeline 在持续运行时资源是否稳定。

测试档位：

| 档位                 |    时长 | 是否必须     | 作用           |
| -------------------- | ------: | ------------ | -------------- |
| smoke                | 10 分钟 | 必须         | 确认配置可跑   |
| short sustained      | 30 分钟 | 必须         | 基础稳定性     |
| acceptance sustained |  2 小时 | 项目验收目标 | 作品集核心证据 |
| long sustained       |  8 小时 | 条件允许     | 压力验证       |

必须记录：

- 连续运行时长。
- FPS、p95/p99、队列长度、丢帧率。
- 内存峰值和内存增长。
- 温度峰值和降频情况。
- CPU/GPU/NPU/BPU 利用率。
- 异常恢复次数、重连次数、崩溃次数。

验收：

- 30 分钟测试必须通过。
- 2 小时测试作为项目验收目标。
- 稳定性报告包含 MLPerf-style Summary。

### 阶段 9：汇总与作品集报告

目标：

- 校验 raw result。
- 聚合 runtime 和 stability 指标。
- 写出可被他人复现和审查的最终报告。

必须更新：

- `projects/03_video_pipeline/reports/video_pipeline.md`
- `projects/03_video_pipeline/reports/runtime_benchmark.md`
- `projects/03_video_pipeline/reports/stability_report.md`
- `projects/03_video_pipeline/reports/failure_and_fallback.md`
- `projects/03_video_pipeline/reports/runbook.md`
- `projects/03_video_pipeline/reports/troubleshooting.md`

验收：

- 每个报告结论都能反向追溯到 run、命令、配置、raw result、monitor 和日志。
- 未完成项明确标记 `not_executed`、`blocked`、`degraded` 或 `fail`。

## Benchmark 指标

| 类别 | 必须指标 | 单位 / 取值 | 原始来源 | 聚合或报告落点 |
|---|---|---|---|---|
| 性能 | end-to-end FPS | frame/s | frame-level `output_ts`、有效输出帧数、run 时长 | `runtime_benchmark.md` Runtime Summary |
| 性能 | p50/p90/p95/p99 end-to-end latency | ms | `end_to_end_latency_ms` | `runtime_benchmark.md` Runtime Summary、MLPerf-style Summary |
| 性能 | p50/p90/p95/p99 stage latency | ms | `capture_ms`、`decode_ms`、`preprocess_ms`、`inference_ms`、`postprocess_ms`、`output_ms` | `runtime_benchmark.md` Stage Latency |
| Pipeline | queue size p50/p95/max | frame count | `queue_capture_size`、`queue_preprocess_size`、`queue_infer_size`、`queue_postprocess_size` | `runtime_benchmark.md` Queue/Buffer |
| Pipeline | drop frame count / rate / reason | count、ratio、enum | `drop_frame_count`、`drop_frame_rate`、`dropped_frame_reason` | `runtime_benchmark.md` Queue/Buffer、`failure_and_fallback.md` |
| Pipeline | frame trace continuity | pass/fail/not_verified | `frame_id`、trace check report | `video_pipeline.md`、`runtime_benchmark.md` Quality Gate |
| Pipeline | output validity | pass/fail/not_verified | output JSON、输出视频、检测框合法性检查 | `runtime_benchmark.md` Quality Gate |
| 资源 | memory peak / memory growth | MB、MB/hour | monitor log、processed stability summary | `runtime_benchmark.md` Resource、`stability_report.md` |
| 资源 | temperature peak / throttle events | degC、count | `tegrastats` 或等价监控 | `stability_report.md` Resource Trace |
| 资源 | power mode / power avg / power peak | mode、W | `nvpmodel`、`tegrastats`、run 记录 | `runtime_benchmark.md` Resource、MLPerf-style Summary |
| 资源 | CPU/GPU/NPU/BPU utilization | percent 或结构化字符串 | `tegrastats`、runtime/monitor log | `runtime_benchmark.md` Resource/Accelerator |
| 稳定性 | target / actual duration | sec | stability run、raw timestamp、run 记录 | `stability_report.md` Stability Summary |
| 稳定性 | restart / reconnect / crash / watchdog count | count | failure log、runtime log、service log | `stability_report.md`、`failure_and_fallback.md` |
| 稳定性 | sustained FPS / p95 / p99 | frame/s、ms | stability raw result | `stability_report.md` MLPerf-style Summary |
| 后端 | backend artifact path / SHA256 / precision | path、sha256、enum | board config、run、raw result | `runtime_benchmark.md` Reproducibility |
| 后端 | loader API / execution provider | enum | run、raw result、runtime log | `runtime_benchmark.md` Resource/Accelerator |
| 后端 | runtime evidence / accelerator evidence | path | runtime log、`tegrastats` | `runtime_benchmark.md` Resource/Accelerator |
| 后端 | CPU fallback / fallback reason | boolean、string/null | raw result、runtime log、failure log | `runtime_benchmark.md`、`failure_and_fallback.md` |
| 质量 | fixed-input alignment / task-level quality | pass/fail/not_verified/blocked | 项目一/二报告、项目三对齐 run | `runtime_benchmark.md` Quality Gate |
| 可复现 | environment_baseline_id、run_id、config hash、model hash、command、raw/log path | string/path | run 记录、配置快照、hash | `runtime_benchmark.md` Reproducibility |

各板卡首轮都必须至少形成下面这些表。没有实测数据时保留空值并标记 `not_executed`；已经执行但缺少 schema、日志、monitor 或后端证据时标记 `not_verified`，不能写成 `pass`。

| 表格 | 必须字段 | 对应文件 |
|---|---|---|
| Runtime Summary | run_id、target、backend_runtime、execution_provider、input_source_id、pipeline_mode、queue_policy、FPS、p50/p90/p95/p99、drop_frame_rate、CPU fallback、status | `reports/runtime_benchmark.md` |
| Stage Latency | run_id、capture/decode/preprocess/inference/postprocess/output p50/p95/p99、end-to-end p95/p99 | `reports/runtime_benchmark.md` |
| Queue / Buffer | run_id、queue_policy、queue_capacity、buffer_reuse、queue p95/max、drop_count、drop_rate、dropped_frame_reason、memory_growth | `reports/runtime_benchmark.md` |
| Resource / Accelerator | run_id、monitor_log_path、GPU util、CPU util、memory peak、temperature max、power mode/power、throttle events、runtime_evidence_path、accelerator_evidence_path | `reports/runtime_benchmark.md`、`reports/stability_report.md` |
| Labeled Video Quality | run_id、dataset_id、labeled_frames、prediction_frames、labeled_frame_coverage、missing_labeled_frames、AP50、precision、recall、F1、TP、FP、FN、per-class table、status | `reports/runtime_benchmark.md`、`benchmark/processed/03_video_pipeline/*_bdd100k_mot_quality.md` |
| Stability | tier、target_duration_sec、actual_duration_sec、completed、FPS、p95/p99、memory_growth、temperature_max、restart/reconnect/crash/watchdog、status | `reports/stability_report.md` |
| Failure / Fallback | case_id、error_code、expected_behavior、actual_behavior、recovery_action、service_status、cpu_fallback、related_troubleshooting_id、status | `reports/failure_and_fallback.md` |

RDK X5 BPU 当前必须在相应文档中形成的表格落点如下：

| 文档 | RDK X5 必须出现的表格 | 当前口径 |
|---|---|---|
| `specs/03F_RDK_X5_BPU_CppPipeline规范.md` | Benchmark 指标表、执行矩阵、证据矩阵 | RDK X5 单板执行规范 |
| `reports/runtime_benchmark.md` | Runtime Summary、Stage Latency、Queue / Buffer、Resource / Accelerator、Quality Gate、Reproducibility、MLPerf-style Summary | 项目三 runtime benchmark 主表 |
| `reports/stability_report.md` | Stability Summary、Resource Trace、Queue / Drop Trend、Stability Events、MLPerf-style Summary | 10 分钟 / 30 分钟 / 2 小时稳定性主表 |
| `reports/failure_and_fallback.md` | Failure Cases、CPU Fallback、Service Recovery、Benchmark Impact | 异常恢复与降级主表 |
| `reports/video_pipeline.md` | 主线定义、代码 / 配置 / 脚本落点、Benchmark 与证据状态 | RDK X5 路线总览 |
| `reports/runbook.md` | 快速入口、命令矩阵、产物检查表、证据边界表 | RDK X5 复现与填表入口 |

## Raw Result 字段

项目三 raw CSV/JSONL 使用 frame-level 粒度。每一行表示一帧，字段定义以 `benchmark/schemas/video_pipeline_raw_schema.yaml` 为准。窗口级统计、FPS、p50/p90/p95/p99、memory growth、runtime summary、stability summary 写入 `benchmark/processed/03_video_pipeline/`，不写入 raw result 作为替代。

```text
run_id
timestamp
schema_version
project
measurement_scope
board
target
environment_baseline_id
backend_runtime
execution_provider
loader_api
model
model_file_hash
precision_or_quantization
backend_artifact_format
backend_artifact_path
backend_artifact_sha256
input_source_id
input_source_type
input_source_sha256
input_width
input_height
input_fps
pipeline_mode
queue_policy
queue_capacity
buffer_reuse
frame_id
capture_ts
decode_ts
preprocess_ts
infer_start_ts
infer_end_ts
postprocess_ts
output_ts
capture_ms
decode_ms
preprocess_ms
inference_ms
postprocess_ms
output_ms
end_to_end_latency_ms
queue_capture_size
queue_preprocess_size
queue_infer_size
queue_postprocess_size
drop_frame_count
drop_frame_rate
dropped_frame_reason
memory_mb
temperature_c
power_w
power_mode
cpu_gpu_npu_bpu_utilization
runtime_evidence_path
accelerator_evidence_path
cpu_fallback
fallback_reason
output_valid
detection_count
detection_quality_status
error_code
status
runtime_log_path
monitor_log_path
failure_log_path
related_troubleshooting_id
```

不可观测字段不能删除。schema 中允许为空的字段写 `null`，并在 run 记录中说明原因；schema 中不可为空的字符串字段如果确实不可观测，必须写明确状态值或问题标识，并关联 `related_troubleshooting_id`。

派生指标归属：

| 指标                    | 归属                                | 生成来源                                     |
| ----------------------- | ----------------------------------- | -------------------------------------------- |
| FPS                     | processed result                    | 从 frame-level 时间戳和有效输出帧聚合        |
| p50/p90/p95/p99 latency | processed result                    | 从 `end_to_end_latency_ms` 和分阶段耗时聚合  |
| memory_growth_mb        | processed result                    | 从 monitor log 的内存曲线聚合                |
| sustained duration      | processed result / stability report | 从 run 记录、frame 时间戳和 monitor log 聚合 |

最低质量检查：

- 输出 JSON 可解析。
- 空场景可输出空结果。
- 检测框坐标在图像范围内。
- `class_id` 合法。
- `frame_id` 与输出结果一一对应。
- 正式视频质量必须使用带人工标注的数据集；无标注固定视频只能用于 smoke、runtime 或排障，不得进入正式质量门。
- 项目三正式带标注视频质量输入使用 `bdd100k_mot_mini_v1`，来源为 BDD100K MOT；评估类别覆盖 pedestrian/rider/car/bus/truck/train/motorcycle/bicycle 到 YOLO/COCO 类别的映射。
- `bdd100k_mot_mini_v1` 的 manifest 为 `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json`，标签目录为 `data/validation/bdd100k_mot_mini_v1/labels/`；制备后必须记录每个视频和标签的 SHA256，且总量不超过 5 GB。
- 固定输入 baseline/current 对齐与带标注任务质量是两类证据：前者输出 match rate、IoU 和 confidence difference；后者必须使用 BDD100K 标注输出 AP50、precision、recall、F1、TP、FP、FN。延迟 `p50` 不是检测质量指标，不能与 `AP50` 混写。
- BDD100K MOT mini 只在官方标注帧上计算质量指标；未标注帧不能纳入 AP、precision、recall、F1 统计。
- BDD100K MOT mini 质量报告必须记录 labeled/prediction frame coverage、missing labeled frames、overall AP50/precision/recall/F1、TP、FP、FN，以及 per-class 的 gt/pred/tp/fp/fn/AP50/precision/recall/F1/mean IoU。
- BDD100K MOT mini 质量评估必须走目标板对应的 no-drop 配置：Jetson 使用 `jetson_tensorrt_bdd100k_quality.yaml`，RK3588 使用 `rk3588_rknn_bdd100k_quality.yaml`。实时 benchmark 的 `drop_oldest` / `drop_newest` 结果只能用于队列和延迟分析；一旦 raw result 出现 frame gap 或 `drop_frame_count > 0`，该 run 的 AP/recall 不能作为正式质量结论。
- BDD100K MOT mini 的 confidence sweep 必须区分 C++ postprocess 阈值和离线评估阈值。若 raw result 最小 confidence 已被 `model_config` 中的 `postprocess.confidence_threshold` 截断，只调整 `CONFIDENCE_MIN` 不能证明低阈值 recall；必须重新生成 raw，并在 run 记录中写明 `MODEL_CONFIG`、`CONFIDENCE_MIN` 和 sweep 报告路径。
- 项目三若自行维护 C++ 前后处理实现，必须把 `class_agnostic_nms`、`color_format`、`layout`、`pad_value`、`normalize.scale`、`keep_ratio` 等关键字段真正接入运行时；不能只在 YAML 中声明而不在实现中生效。
- 如果 pipeline 中的模型 artifact、runtime、前处理、后处理或输出解析发生变化，必须补充任务级检测质量对齐；只做抽帧固定输入对齐时，模型变更质量状态只能写 `not_verified`。
- 如果本次只修改队列、日志、监控、服务启动或报告聚合，且确认不影响推理输出，必须在 run 中写 `quality_alignment_exemption`，不能默认豁免。

## 报告产出要求

### `video_pipeline.md`

必须包含：

- pipeline 架构图或文字链路。
- C++ 模块拆分。
- 线程模型。
- 队列容量和满队列策略。
- frame_id 和 timestamp 追踪方式。
- 后端 wrapper 接口。
- 输出格式。
- 和项目一/二模型产物的衔接方式。

### `runtime_benchmark.md`

必须包含：

- 分板、分后端、分输入源结果。
- FPS、p50/p90/p95/p99、分阶段耗时。
- 队列长度、丢帧率、CPU fallback。
- TensorRT/RKNN/BPU 后端证据。
- raw result、processed result、runtime log、monitor log 路径。
- MLPerf-style Summary。

### `stability_report.md`

必须包含：

- 10 分钟、30 分钟、2 小时测试状态。
- 内存曲线、温度曲线、利用率曲线。
- 队列长度和丢帧率随时间变化。
- 异常、重连、崩溃、降频记录。
- 未完成测试的原因。
- MLPerf-style Summary。

### `failure_and_fallback.md`

必须包含：

- 输入断流、模型加载失败、后端 runtime 失败、队列堆积、服务重启等异常注入结果。
- 错误码和日志样例。
- 恢复策略或降级策略。
- 对项目五的影响，例如是否能作为告警系统的视频主链路。

### `runbook.md`

必须包含：

- 环境准备。
- 构建命令。
- 单线程运行。
- 多线程运行。
- 分板后端运行。
- benchmark。
- 稳定性测试。
- systemd/Docker 启停。
- 常见问题和日志位置。

## MLPerf-style Summary 模板

`runtime_benchmark.md` 和 `stability_report.md` 必须包含或引用：

```markdown
## MLPerf-style Summary

### Scenario
- Task:
- Board:
- Backend/runtime:
- Model:
- Input source:
- Pipeline mode:
- Batch / concurrency:
- Warmup:
- Repeat / duration:

### Quality Gate
- Detection quality:
- Frame trace:
- Queue policy:
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

### Reproducibility
- Environment baseline:
- Pipeline config:
- Backend artifact:
- Command:
- Raw logs:
- Result CSV/JSON:
- Related run:
- Related troubleshooting:
```

## 问题库触发条件

出现下面任一情况，必须写入 `projects/03_video_pipeline/reports/troubleshooting.md`：

- 输入源打开失败、断流、重连失败。
- 模型加载失败、后端 wrapper 初始化失败。
- 输出错位、frame_id 乱序、检测结果不可追溯。
- 模型、后端 wrapper、前后处理或输出解析变化后，缺少固定输入对齐或任务级质量对齐。
- 队列长度持续增长、端到端延迟持续恶化。
- buffer 泄漏或内存持续增长。
- TensorRT/RKNN/BPU 未调用目标加速器或发生 CPU fallback。
- 30 分钟或 2 小时稳定性测试失败。
- systemd/Docker 服务无法启动、停止、重启或日志不足。
- 报告指标无法追溯到 run、raw result 或日志。

问题记录至少包含：

```text
问题 ID
现象
触发命令
环境基线
模型 hash
输入源 ID
相关 raw result
runtime log
monitor log
根因分析
修复或降级方案
修复前后指标
当前状态
```

## 最终验收标准

- 至少一个真实端侧后端可以在 C++ pipeline 中持续运行；主线目标是 Jetson、RK3588、RDK X5 都有记录。
- pipeline 输出 capture、decode、preprocess、infer、postprocess、output 和 end-to-end 耗时。
- 涉及模型或推理链路输出的变更必须完成固定输入对齐和任务级检测质量对齐；只完成 pipeline 性能或稳定性 benchmark 不能写成质量 `pass`。
- 队列不会无限堆积，丢帧策略明确。
- 摄像头或 RTSP 断流有恢复或清晰错误。
- 30 分钟稳定性测试必须通过，2 小时测试作为项目验收目标。
- `runtime_benchmark.md` 和 `stability_report.md` 包含 raw result、日志路径和 MLPerf-style Summary。
- 至少 3 个工程问题或风险进入 `projects/03_video_pipeline/reports/troubleshooting.md`。
- 结论中的每个数字都能追溯到 `projects/03_video_pipeline/runs/` 和 `benchmark/raw/03_video_pipeline/`。
- 未完成的板卡或后端必须有 `not_executed`、`blocked`、`degraded` 或 `fail` 状态和原因。

## 风险与降级方案

| 风险                     | 降级方案                                                   |
| ------------------------ | ---------------------------------------------------------- |
| 实时源不稳定             | 先用固定视频完成 benchmark，再单独记录实时源断流问题       |
| 后端模型不可用           | 使用项目一/二已有后端模型，失败则标记 blocked 并进入问题库 |
| RKNPU/BPU 利用率不可观测 | 保留 runtime 日志、模型格式、调用栈和不可观测原因          |
| 端到端延迟过高           | 降低输入 FPS、输入尺寸、输出保存频率，调整队列策略         |
| 队列堆积                 | 使用有界队列、drop_oldest、block_with_timeout 或关键帧策略 |
| 内存增长                 | 引入 buffer 复用、对象池，减少重复分配，记录修复前后曲线   |
| 温控降频                 | 降低功耗模式、加散热、减少输入 FPS，记录降频时间点         |
| 服务化失败               | 先保留命令行可复现，再补 systemd/Docker 最小服务           |

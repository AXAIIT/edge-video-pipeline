# 03E_RK3588_RKNN_CppPipeline规范

## 适用范围

本规范用于在 RK3588 8GB 上将 RKNN YOLO11n 模型集成到 C++ pipeline，并完成端到端 benchmark。

本 spec 必须证明 pipeline 中的 RKNN 模型实际调用 RKNPU，不能只记录 CPU 侧视频处理。

## 执行原则

下面的 RKNN wrapper 接口、构建命令和 benchmark 命令是推荐路径，不是唯一实现。可以替换 RKNN C API 封装、输入输出 buffer 管理、日志库或监控工具，但不能降低证据要求：必须保留 RKNN 模型 hash、C++ build 命令、端到端 raw result、RKNPU 调用证据、CPU fallback 判断、资源监控和问题记录。替代路径必须写入对应 `projects/03_video_pipeline/runs/`，并同步更新相关 `projects/03_video_pipeline/reports/`。

## 路径口径

本 spec 使用当前仓库结构：

- RK3588 配置放在 `projects/03_video_pipeline/configs/boards/` 和 `projects/03_video_pipeline/configs/pipeline/`。
- RKNN 模型放在 `models/yolo11n/rknn/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/rk3588_8gb/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/rk3588_8gb/`。
- monitor 日志放在 `logs/monitor/03_video_pipeline/rk3588_8gb/`。
- build 日志放在 `logs/runtime/03_video_pipeline/build/`。

## 前置条件

- 已完成项目一 RKNN 模型，或项目二 RKNN INT8 模型。
- 已完成 pipeline 基础框架。
- 已建立 RK3588 环境基线。
- 已准备配置：`projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml` 和 `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml`。
- 已准备固定视频源和实时输入源。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- 环境基线必须对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md`。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| backend | `rknn` | 固定字段名 |
| execution_provider | `RKNPU` | 只有能证明 RKNPU 推理时填写 |
| loader_api | `RKNN C API` 或实际 API | 按实际填写 |
| backend_artifact_format | `rknn` | RKNN 产物 |
| input_source | video file + realtime source | 至少一种实时源 |
| monitor | RKNPU profiler 或替代日志 | 必须保存证据 |
| benchmark duration | 10 分钟基础，30 分钟稳定性 | 2 小时进入 03H |

## 执行步骤

### RK3588 多核策略口径

本项目明确区分“单 context 多核 mask”和“多 context 分核并行”。两者不能混写为同一种三核方案。正式报告必须写清楚具体采用的是哪一种。

| 项目 | 策略 A：单 context 多核 mask | 策略 B：三 context 分核并行 |
|---|---|---|
| `rknn_context` 数量 | 1 | 3 |
| 推理 worker 数量 | 1 | 3 |
| core 绑定 | 同一 context 设置 `0_1_2` | context 0/1/2 分别绑定 core0/core1/core2 |
| 同时在途视频帧 | 1 | 最多 3 |
| 并行粒度 | 由 RKNN 决定单帧计算图是否跨核调度 | 应用层明确进行帧级并行 |
| 模型/runtime 状态 | 一套 | 每个 context 一套完整状态 |
| 输出完成顺序 | 天然串行 | 可能乱序完成，必须重排后输出 |
| 证据要求 | 不得把 `core_mask=0_1_2` 直接写成“三核并行收益” | 必须提供多 worker、core 绑定、帧序和资源证据 |

策略 A 中的 `rknn_set_core_mask(0_1_2)` 只限定同一个 context 可以使用的 NPU core，不保证多个不同帧自动并发，因此不能直接作为帧级并行证据。若正式路线采用策略 B，必须额外记录每个 worker 的 core 绑定、frame trace 和内存峰值。

### 多 context 帧顺序保证

三颗 core 的完成速度可以不同，程序不得按“谁先完成谁先输出”。当前实现采用以下顺序屏障：

1. worker 从 `q_preprocess` 取帧和分配连续 `inference_sequence` 时共用同一互斥区，序号严格对应推理队列出队顺序。
2. 三个 context 可以并发推理并乱序完成，但完成包先进入阻塞式 `q_infer`，推理完成后不再执行实时丢帧。
3. postprocess 使用 `std::map<int, InferPacket>` 暂存乱序结果，只在 `next_sequence` 到达时处理，并按序号逐一释放。
4. `q_result` 同样使用阻塞策略，防止已重排结果在输出前被丢弃。
5. `check_pipeline_trace.py` 将向前跳号记为 `frame_id_gaps`，将重复或倒序记为 `frame_id_out_of_order`；后者无条件使 run 失败。

实时模式允许在推理前因 `drop_oldest` 产生 `100 -> 102` 这样的缺帧，但禁止 `102 -> 101` 或 `102 -> 102`。正式 3-worker run 必须满足 `frame_id_out_of_order=0`。

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_rk3588_8gb_yolo11n_rknn_cpp_pipeline/run.md
```

### 2. 记录 RKNN 模型 hash

```bash
sha256sum models/yolo11n/rknn/yolo11n_640_rk3588_int8_ptq_calib500.rknn
```

run 和 raw result 必须记录：

```yaml
backend_runtime: rknn
execution_provider: RKNPU
loader_api: RKNN C API
backend_artifact_format: rknn
backend_artifact_path: models/yolo11n/rknn/yolo11n_640_rk3588_int8_ptq_calib500.rknn
backend_artifact_sha256: <64_hex_sha256>
runtime_evidence_path:
accelerator_evidence_path:
cpu_fallback:
fallback_reason:
```

### 3. 构建 RKNN pipeline

命令模板：

```bash
cmake -S projects/03_video_pipeline -B build/03_video_pipeline_rk3588 \
  -DCMAKE_BUILD_TYPE=Release \
  -DPIPELINE_BACKEND=rknn \
  > logs/runtime/03_video_pipeline/build/<run_id>_configure.log 2>&1

cmake --build build/03_video_pipeline_rk3588 --config Release -j \
  > logs/runtime/03_video_pipeline/build/<run_id>_build.log 2>&1
```

### 4. 运行 benchmark

RK3588 必须覆盖两类输入，不能二选一：

| 输入配置 | 性质 | 必测内容 | 结论边界 |
|---|---|---|---|
| `video_set_runtime_v1` / `video_set_stability_v1` | BDD100K 视频集持续回放 source | runtime、稳定性、视频集 systemd 生命周期 | 可复现的 file/playlist source，不得称为真实 live source |
| `astra_s_openni_001`（当前正式） / `usb_camera_001`（候选占位） / 实际登记的 RK3588 摄像头 | 真实摄像头 source | 摄像头采集 smoke、`input_disconnect`、摄像头 systemd 生命周期 | Astra S 当前通过 OpenNI selector `2bc5/0402` 接入，默认 color 为 `640x480 RGB888@30`，必须记录 selector、分辨率、FPS 和权限前提 |

命令模板：

```bash
RUN_ID=<run_id> \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
INFERENCE_WORKERS=3 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

摄像头探测与命令模板：

```bash
python3 projects/03_video_pipeline/scripts/probe/probe_openni2_astra.py \
  --device 2bc5/0402 \
  --json-output benchmark/processed/03_video_pipeline/<run_id>_astra_probe.json

RUN_ID=<camera_disconnect_run_id> \
INPUT_SOURCE_ID=astra_s_openni_001 \
INPUT_SOURCE_TYPE=openni_camera \
INPUT_PATH=2bc5/0402 \
PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_camera_disconnect.sh
```

正式文档必须同时写清楚这两个 source：

- 视频集持续回放 source：`video_set_runtime_v1` / `video_set_stability_v1`
- 真实摄像头 source：Astra S OpenNI，`input_source_id=astra_s_openni_001`、`input_source_type=openni_camera`、`INPUT_PATH=2bc5/0402`

`/dev/video0` 仅保留给通用 UVC 候选。摄像头 service 使用 `edge-video-pipeline-rk3588-camera.service`，不得用视频 playlist 的 service 结果代替。

### 5. 记录 RKNPU 证据

命令模板：

```bash
cat /sys/kernel/debug/rknpu/load 2>/dev/null || true
dmesg | grep -i rknpu | tail -n 50 || true
```

保存到：

```text
logs/monitor/03_video_pipeline/rk3588_8gb/<run_id>_monitor.log
```

如果无法读取 NPU 利用率，必须写明原因，并保留 runtime 日志和 CPU fallback 判断。状态规则：

- RKNPU 调用可由 runtime 日志、RKNN C API 日志或其他证据证明，但利用率不可读：`degraded`。
- 无法证明 RKNPU 调用：`not_verified`，不能进入正式收益结论。
- 明确 CPU fallback：`fail` 或 `degraded`，并进入问题库。

## 记录要求

- RKNN 模型路径和 hash 必须记录。
- `backend_artifact_format/path/sha256`、`loader_api`、`execution_provider`、`runtime_evidence_path`、`accelerator_evidence_path`、`cpu_fallback` 必须写入 run 和 raw result。
- runtime 日志保存到 `logs/runtime/03_video_pipeline/rk3588_8gb/`。
- monitor 日志保存到 `logs/monitor/03_video_pipeline/rk3588_8gb/`。
- raw result 保存到 `benchmark/raw/03_video_pipeline/rk3588_8gb/`。
- CPU fallback 必须明确记录。

## 输出文件

| 文件 | 要求 |
|---|---|
| `projects/03_video_pipeline/src/inference/rknn/*` | RKNN C++ wrapper |
| `benchmark/raw/03_video_pipeline/rk3588_8gb/*rk3588*rknn*.jsonl` | raw result |
| `logs/monitor/03_video_pipeline/rk3588_8gb/*rk3588*rknn*.log` | RKNPU 证据 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | RK3588 benchmark |
| `projects/03_video_pipeline/reports/troubleshooting.md` | RKNN 问题 |

### BDD100K 标注质量口径

RK3588 正式视频质量只使用 `bdd100k_mot_mini_v1`，不得使用无人工标注的固定短视频形成正式质量结论。数据集包含 80 段视频、15,631 个官方标注帧和 230,698 个 GT 框；只在官方标注帧上评估，必须覆盖 manifest 选中的全部序列和全部标注帧。

执行入口为 `run_rk3588_bdd100k_mini.sh`，配置为 `rk3588_rknn_bdd100k_quality.yaml`。Pipeline 必须使用 `block`、容量 32、三独立 RKNN context、`TRACE_FAIL_ON_GAPS=1` 和 `SAVE_OUTPUT_VIDEO=0`。任一序列出现丢帧、frame gap、倒序或 labeled frame coverage 小于 1.0，该序列质量证据无效。

BDD100K 标签坐标固定为显示方向的 `1280x720` 横屏坐标，但 80 个 MOV 的存储像素使用两种相反的 90° `tkhd` track transformation matrix。quality runner 必须使用 `INPUT_ORIENTATION_CORRECTION=container` 逐视频解析矩阵，并将 `input_orientation_requested` / `input_orientation_effective` 写入 batch CSV；不得对全数据集统一强制 clockwise 或 counterclockwise。评估前还必须校验 raw 的 `input_width=1280`、`input_height=720`；出现 `720x1280` 或方向矩阵无法解析时立即失败。若标签映射帧号位于实际解码 EOF 之后，必须单独记录为 `trailing_unavailable_labeled_frames`；它不进入可评估帧 coverage 分母，中间缺帧仍必须使 coverage 失败。

正式报告必须同时生成逐序列报告和全 80 段聚合表。聚合表必须包含 sequence count、overall AP50、precision、recall、F1、TP、FP、FN；逐序列报告必须包含 labeled frame coverage，详细质量表必须包含逐类别 AP50/precision/recall/F1/TP/FP/FN/mean IoU。延迟 `p50/p95/p99` 作为同一 run 的性能上下文单独记录，不能替代检测质量指标。

## 验收标准

- RKNN 后端可在 pipeline 中连续运行。
- 明确是否存在 CPU fallback。
- 队列和端到端延迟可控。
- 有 RKNPU 调用证据或不可读取原因。
- 结果能与项目一/二单模型 benchmark 对照。

## 降级和问题库

下面问题必须进入问题库：

- RKNN 加载失败。
- RKNPU 未调用。
- 后处理差异。
- 性能异常。
- 内存增长或队列堆积。


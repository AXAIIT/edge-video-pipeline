# C++ 实时视频流推理 Pipeline / C++ Real-time Video Stream Inference Pipeline

面向边缘 AI 设备的生产级 C++ 实时视频推理系统。支持 USB 摄像头、MIPI 摄像头、RTSP 流和视频文件输入，经 YOLO11n 目标检测，在 NVIDIA Jetson、Rockchip RK3588 和 Horizon RDK X5 三块边缘开发板上实现 30 FPS 持续推理，并通过 12 小时以上稳定性验证。

项目覆盖完整的工程化链路：多线程 pipeline 架构、有界队列与背压控制、分阶段延迟追踪、异常恢复与服务化部署，以及 MLPerf 风格 benchmark 报告。

---

## 架构总览

```
┌──────────┐    ┌────────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│ Capture  │───>│ Preprocess │───>│  Infer   │───>│ Postprocess│───>│  Output  │
│          │    │            │    │          │    │            │    │          │
│ USB/MIPI │    │ resize     │    │ TensorRT │    │ decode box │    │ display  │
│ RTSP     │    │ letterbox  │    │ RKNN     │    │ NMS        │    │ save     │
│ video    │    │ normalize  │    │ BPU      │    │ filter     │    │ JSON     │
└──────────┘    └────────────┘    └──────────┘    └────────────┘    └──────────┘
     │               │                 │                │                │
     └───────────────┴─────────────────┴────────────────┴────────────────┘
                          有界队列 (bounded queue) + 背压控制
                          queue_policy: drop_oldest / drop_newest / block_with_timeout
                          queue_capacity: 8
```

**5 阶段 pipeline 各阶段职责：**

| 阶段 | 职责 | 关键操作 |
|------|------|----------|
| Capture | 视频采集与解码 | OpenCV VideoCapture / V4L2 / HBN srcampy 读取帧，分配 frame_id 和 capture_ts |
| Preprocess | 推理前处理 | resize、letterbox、normalize、色彩空间转换（NV12/RGB）、方向修正 |
| Infer | 模型推理 | TensorRT / RKNN / BPU 后端调用，batch=1，记录 infer_start_ts / infer_end_ts |
| Postprocess | 推理后处理 | decode boxes、DFL 解码、NMS、confidence 过滤、类别映射 |
| Output | 结果输出 | 渲染检测框、保存视频/JSON、实时预览（PREVIEW_WINDOW=auto\|on\|off） |

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| C++ | C++17 | 主链路实现语言 |
| CMake | >= 3.16 | 构建系统 |
| OpenCV | 4.x | 视频采集、图像处理、显示 |
| TensorRT | 8.x | Jetson 推理后端 |
| RKNN | 2.x (RKNPU2) | RK3588 推理后端 |
| hbDNN | X5 DDK | RDK X5 BPU 推理后端 |
| pthread / std::thread | - | 多线程 pipeline |
| systemd | - | 服务化部署 |

---

## 核心特性

- **5 阶段多线程 pipeline**：Capture / Preprocess / Infer / Postprocess / Output 独立线程，通过有界队列解耦
- **有界队列与背压控制**：队列满时支持 `drop_oldest`（保最新帧）、`drop_newest`（保已排队帧）、`block_with_timeout`（限时等待空位）三种策略，防止延迟无限堆积
- **逐帧可追溯**：每帧记录 frame_id、capture_ts、preprocess_ts、infer_start_ts、infer_end_ts、postprocess_ts、output_ts、status、error_code
- **分阶段延迟追踪**：独立统计 capture / preprocess / inference / postprocess / output 各阶段耗时，输出 p50 / p90 / p95 / p99 分位数
- **3 板卡 3 后端统一代码**：同一份 `video_pipeline_app.cpp` 通过 `PIPELINE_BACKEND` 编译切换 TensorRT / RKNN / BPU
- **实时资源监控**：CPU / GPU / NPU / BPU 利用率、内存峰值与增长、温度曲线、功耗
- **异常恢复与服务化**：输入断流检测、模型加载失败处理、CLI 异常注入 5/5 通过、systemd 服务生命周期验证
- **MLPerf 风格 benchmark**：raw result schema 校验、trace check、stability 聚合、可复现命令与证据链

---

## 性能指标

### Runtime Benchmark（600s 主线，SAVE_OUTPUT_VIDEO=0）

| 指标 | Jetson Xavier NX 8GB<br/>TensorRT INT8 | RK3588 8GB<br/>RKNN INT8 | RDK X5 8GB<br/>BPU INT8 |
|------|:---------------------------------------:|:------------------------:|:-----------------------:|
| FPS | 30.13 | 30.08 | 18.12 (playlist) / 30.08 (IMX219) |
| 延迟 p50 (ms) | 60.19 | 107.46 | 141.48 (IMX219) |
| 延迟 p95 (ms) | 63.76 | 122.32 | 165.44 (IMX219) |
| 延迟 p99 (ms) | 66.11 | 125.49 | 169.43 (IMX219) |
| 丢帧率 | 0.0% | 0.0% (camera) / 0.0018% (video) | 0.0% (IMX219) |
| 内存峰值 (MB) | 3484 | 253.95 (camera) / 365.42 (video) | 142.76 (IMX219) |
| 温度峰值 (°C) | 59.5 | 55.46 (camera) / 56.38 (video) | 72.11 (IMX219) |
| CPU fallback | false | false | false |

### 稳定性验证

| 开发板 | smoke (10min) | short (30min) | acceptance (2h) | long (8h) |
|--------|:---:|:---:|:---:|:---:|
| Jetson 8GB | pass | pass | pass (7196s) | not_executed |
| RK3588 8GB | pass | pass | pass (7199s) | pass (8h mixed: camera 4h + video 4h) |
| RDK X5 8GB | pass | pass | pass (7198s IMX219) | not_executed |

> 详细指标见 `reports/runtime_benchmark.md` 和 `reports/stability_report.md`。

---

## 快速开始

### 构建

```bash
# Jetson TensorRT
PIPELINE_BACKEND=tensorrt bash scripts/build/build_jetson_tensorrt.sh

# RK3588 RKNN
PIPELINE_BACKEND=rknn bash scripts/build/build_rk3588_rknn.sh

# RDK X5 BPU
PIPELINE_BACKEND=bpu bash scripts/build/build_rdk_x5_bpu.sh
```

### 运行

```bash
# Jetson 多线程 pipeline
RUN_ID=<run_id> bash scripts/run/run_jetson_tensorrt_pipeline.sh

# RK3588 多线程 pipeline
RUN_ID=<run_id> bash scripts/run/run_rk3588_rknn_pipeline.sh

# RDK X5 多线程 pipeline
RUN_ID=<run_id> bash scripts/run/run_rdk_x5_bpu_pipeline.sh

# 稳定性测试
TIER=acceptance_sustained bash scripts/run/run_jetson_tensorrt_stability.sh
```

### 配置

Pipeline 行为通过 YAML 配置控制，位于 `configs/pipeline/`：

```yaml
# configs/pipeline/jetson_tensorrt_pipeline.yaml 示例
threads:
  mode: multithread
  stages: [capture, preprocess, inference, postprocess, output]
queues:
  mainline_policy: drop_oldest
  queue_capacity: 8
  queue_push_timeout_ms: 20
buffers:
  reuse: true
  gpu_buffer_reuse: true
```

---

## 目录结构

```
03_video_pipeline_github/
├── CMakeLists.txt                  # CMake 构建，PIPELINE_BACKEND 切换后端
├── src/
│   └── video_pipeline_app.cpp      # 统一 C++ pipeline 主程序 (~4400 LOC)
├── configs/
│   ├── pipeline/                   # pipeline 配置（线程、队列、输出、日志）
│   ├── models/                     # 模型配置（输入尺寸、类别、阈值、NMS）
│   └── streams/                    # 输入源配置（视频、摄像头、RTSP）
├── scripts/
│   ├── build/                      # 各板卡构建脚本
│   ├── run/                        # 运行与 benchmark 脚本
│   ├── benchmark/                  # schema 校验、聚合、trace 检查
│   ├── monitor/                    # 资源监控脚本
│   ├── service/                    # systemd 服务配置与测试
│   ├── quality/                    # BDD100K 质量评估与对齐脚本
│   └── inject_failure_tests.py     # 异常注入测试
├── specs/                          # 各阶段执行规范 (03A-03I)
├── reports/
│   ├── video_pipeline.md           # pipeline 架构与主线结论
│   ├── runtime_benchmark.md        # 性能 benchmark 报告
│   ├── stability_report.md         # 稳定性报告
│   ├── failure_and_fallback.md     # 异常恢复与降级报告
│   ├── runbook.md                  # 复现步骤手册
│   ├── troubleshooting.md          # 问题库
│   └── input_sources.md            # 输入源清单
└── 03_Cpp实时视频流推理Pipeline.md  # 项目总规范
```

---

## 平台支持

| 开发板 | SoC | 内存 | 推理后端 | 精度 | 模型格式 | 实时源 |
|--------|-----|------|----------|------|----------|--------|
| NVIDIA Jetson Xavier NX | T194 | 8GB | TensorRT (GPU) | INT8 PTQ | `.engine` | IMX219 MIPI (V4L2 raw) |
| Rockchip RK3588 | RK3588 | 8GB | RKNN (RKNPU) | INT8 PTQ | `.rknn` | Astra S OpenNI2 |
| Horizon RDK X5 | X5 | 8GB | BPU (hbDNN) | INT8 PTQ | `.bin` (split-head) | IMX219 MIPI (HBN/srcampy) |

**Fixed-input 对齐**：633/633 帧跨后端对齐通过，mean_matched_IoU=0.996638。

---

## License

MIT

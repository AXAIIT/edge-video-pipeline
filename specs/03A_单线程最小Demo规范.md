# 03A_单线程最小Demo规范

## 适用范围

本规范用于实现项目三的 C++ 单线程最小 demo：

```text
input source
-> capture / decode
-> preprocess
-> backend inference
-> postprocess
-> output
```

本阶段只验证最小链路是否正确，不追求最终多线程性能。

## 执行原则

下面的目录结构、命令和脚本接口是推荐路径，不是唯一实现。可以替换视频读取库、日志库、后端 mock、构建命令或输出方式，但不能降低证据要求：必须保留 build 命令、run 命令、配置、日志、raw result、输出样例和问题记录。替代路径必须写入对应 `projects/03_video_pipeline/runs/`，并同步更新 `projects/03_video_pipeline/reports/video_pipeline.md` 和 `projects/03_video_pipeline/reports/runtime_benchmark.md`。

## 路径口径

本 spec 使用当前仓库结构：

- 项目代码、配置、脚本、run 记录和人工报告放在 `projects/03_video_pipeline/`。
- 固定视频输入放在 `data/videos/video_fixed_v1/`。
- 后端模型放在 `models/yolo11n/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/<target>/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/<target>/`。
- build 日志放在 `logs/runtime/03_video_pipeline/build/`。
- 输出视频、截图或 JSON 样例放在对应 `projects/03_video_pipeline/runs/<run_id>/outputs/`。

## 前置条件

- 已有至少一个可运行 YOLO11n 后端模型，优先使用项目一产物。
- 已准备固定视频源：`data/videos/video_fixed_v1/`。
- 已建立目标环境基线。
- 已准备配置：
  - `projects/03_video_pipeline/configs/pipeline/single_thread_demo.yaml`
  - `projects/03_video_pipeline/configs/models/yolo11n.yaml`
  - `projects/03_video_pipeline/configs/boards/<target>.yaml`
  - `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- 已准备 CMake 和 C++17 编译环境。
- 环境基线必须对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md`。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| mode | `single_thread` | 单线程最小链路 |
| input_source_type | `video_file` | 先固定视频文件，再接实时源 |
| input_size | `640x640` | 与项目一一致 |
| batch | `1` | 实时 pipeline 默认 |
| output | display / save / json | 至少一种可验证输出 |
| frame_id | 单调递增 | 每帧都必须有 |
| benchmark | 前 300 帧或完整短视频 | 二选一，必须记录 |

## 执行步骤

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_<target>_yolo11n_<backend>_single_thread_demo/run.md
```

示例：

```text
projects/03_video_pipeline/runs/20260602_jetson_8gb_yolo11n_tensorrt_single_thread_demo/run.md
```

### 2. 构建 demo

命令模板：

```bash
cmake -S projects/03_video_pipeline -B build/03_video_pipeline \
  -DCMAKE_BUILD_TYPE=Release \
  -DPIPELINE_BACKEND=<tensorrt|rknn|bpu|ort_mock>

cmake --build build/03_video_pipeline --config Release -j
```

构建日志保存到：

```text
logs/runtime/03_video_pipeline/build/YYYY-MM-DD_03_single_thread_build.log
```

### 3. 运行单线程 demo

命令模板：

```bash
build/03_video_pipeline/video_pipeline_demo \
  --config projects/03_video_pipeline/configs/pipeline/single_thread_demo.yaml \
  --input-source-id bdd100k_mot_mini_v1_<sequence_id> \
  --input data/videos/bdd100k_mot_mini_v1/<sequence_id>.mov \
  --model-config projects/03_video_pipeline/configs/models/yolo11n.yaml \
  --backend-config projects/03_video_pipeline/configs/boards/<target>.yaml \
  --output-json benchmark/raw/03_video_pipeline/<target>/<run_id>.jsonl \
  --output-video projects/03_video_pipeline/runs/<run_id>/outputs/<run_id>.mp4 \
  > logs/runtime/03_video_pipeline/<target>/<run_id>.log 2>&1
```

### 4. 校验输出

必须检查：

- 是否每帧有 `frame_id` 和 timestamp。
- 是否输出检测框或空结果。
- 是否记录 preprocess、inference、postprocess、output、end-to-end latency。
- 输出视频或 JSON 是否可打开。
- raw result 是否为 frame-level；窗口级统计不能写入 raw 替代逐帧记录。

## 记录要求

- build 命令和 run 命令写入 run。
- build 日志保存到 `logs/runtime/03_video_pipeline/build/`。
- runtime 日志保存到 `logs/runtime/03_video_pipeline/<target>/`。
- raw result 保存到 `benchmark/raw/03_video_pipeline/<target>/`。
- 输出样例保存到 `projects/03_video_pipeline/runs/<run_id>/outputs/`。
- 失败记录进入 `projects/03_video_pipeline/reports/troubleshooting.md`。

## 输出文件

| 文件 | 要求 |
|---|---|
| `build/03_video_pipeline/video_pipeline_demo` | 最小 C++ demo |
| `benchmark/raw/03_video_pipeline/<target>/*single_thread*.jsonl` | 单线程 raw result |
| `projects/03_video_pipeline/runs/<run_id>/outputs/*single_thread*` | 输出视频或 JSON 样例 |
| `projects/03_video_pipeline/reports/video_pipeline.md` | 记录最小链路结构 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | 记录基础性能 |

## 验收标准

- 单线程链路可运行。
- 每帧有 frame_id 或 timestamp。
- 至少输出 FPS、preprocess、inference、postprocess、total latency。
- raw result 字段能被后续 03I 校验。
- 输出结果能追溯到输入源和模型文件。

## 降级和问题库

下面问题必须进入问题库：

- 输入读取失败。
- 模型加载失败。
- 后处理错误。
- 输出异常。
- frame_id 缺失或日志不可追溯。


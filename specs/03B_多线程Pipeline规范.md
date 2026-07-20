# 03B_多线程Pipeline规范

## 适用范围

本规范用于将单线程 demo 拆分为多线程实时 pipeline：

```text
capture thread
-> preprocess thread
-> infer thread
-> postprocess thread
-> output thread
```

本阶段重点验证阶段解耦、frame_id 追踪、队列状态和端到端延迟。

## 执行原则

下面的线程划分和配置字段是推荐路径，不是唯一实现。可以替换线程池、异步 runtime、锁机制、日志库或输出方式，但不能降低证据要求：必须保留 frame_id、阶段耗时、队列长度、丢帧率、端到端延迟、日志和 raw result。替代路径必须写入对应 `projects/03_video_pipeline/runs/`，并同步更新 `projects/03_video_pipeline/reports/video_pipeline.md` 和 `projects/03_video_pipeline/reports/runtime_benchmark.md`。

## 路径口径

本 spec 使用当前仓库结构：

- pipeline 配置放在 `projects/03_video_pipeline/configs/pipeline/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/<target>/`。
- trace 检查和聚合结果放在 `benchmark/processed/03_video_pipeline/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/<target>/`。
- 报告放在 `projects/03_video_pipeline/reports/`。

## 前置条件

- 已完成 `03A_单线程最小Demo规范.md`。
- 已确定队列容量、丢帧策略和线程数。
- 已准备固定视频源和至少一个后端模型。
- 已准备配置：`projects/03_video_pipeline/configs/pipeline/multithread_pipeline.yaml`。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- 环境基线必须对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md`。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| thread stages | capture/preprocess/infer/postprocess/output | 可合并，但必须记录 |
| queue capacity | 每段 4 或 8 | 可替换但必须记录 |
| frame_id | capture 阶段生成 | 后续阶段必须继承 |
| timestamp | 每阶段记录 | 用于计算阶段耗时 |
| benchmark duration | 10 分钟 | 作为多线程基本 benchmark |

## 执行步骤

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_<target>_yolo11n_<backend>_multithread_pipeline/run.md
```

### 2. 配置 pipeline

配置文件必须包含：

```yaml
input:
  input_source_id:
  input_source_sha256:
  type:
  uri:
  fps:
pipeline:
  stages:
  queue_capacity:
  drop_policy:
  thread_affinity:
backend:
  type:
  model_path:
output:
  display:
  save_video:
  json_path:
logging:
  raw_result_path:
  runtime_log_path:
```

### 3. 运行多线程 pipeline

命令模板：

```bash
build/03_video_pipeline/video_pipeline_app \
  --config projects/03_video_pipeline/configs/pipeline/multithread_pipeline.yaml \
  --duration-sec 600 \
  --raw-output benchmark/raw/03_video_pipeline/<target>/<run_id>.jsonl \
  > logs/runtime/03_video_pipeline/<target>/<run_id>.log 2>&1
```

### 4. 校验 frame_id 和队列

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/benchmark/check_pipeline_trace.py \
  --raw benchmark/raw/03_video_pipeline/<target>/<run_id>.jsonl \
  --output benchmark/processed/03_video_pipeline/<run_id>_trace_check.md
```

必须检查：

- frame_id 是否连续或丢帧原因明确。
- 输出顺序是否可解释。
- 每个阶段是否有耗时。
- 队列是否无限增长。
- 输出框数量、`class_id`、空结果和异常帧比例是否与单线程结果可解释地一致。

## 记录要求

- pipeline 配置保存到 `projects/03_video_pipeline/configs/pipeline/`。
- 队列长度、丢帧率、阶段耗时写入 raw result。
- runtime 日志保存到 `logs/runtime/03_video_pipeline/<target>/`。
- trace 检查结果保存到 `benchmark/processed/03_video_pipeline/`。
- trace 检查输出路径必须写入 run 的 `performance.trace_check_path`，供 03I 汇总引用。
- 异常进入 `projects/03_video_pipeline/reports/troubleshooting.md`。

## 输出文件

| 文件 | 要求 |
|---|---|
| `projects/03_video_pipeline/configs/pipeline/multithread_pipeline.yaml` | 多线程配置 |
| `benchmark/raw/03_video_pipeline/<target>/*multithread*.jsonl` | 多线程 raw result |
| `benchmark/processed/03_video_pipeline/*trace_check.md` | frame_id 和队列检查 |
| `projects/03_video_pipeline/reports/video_pipeline.md` | 线程模型说明 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | 多线程性能结果 |

## 验收标准

- 队列不会无限增长。
- 延迟不会随运行时间持续恶化。
- 每阶段耗时可统计。
- 输出结果可追溯到 frame_id。
- 10 分钟 benchmark 有完整 raw result 和日志。

## 降级和问题库

下面问题必须进入问题库：

- 死锁。
- frame_id 乱序且无法解释。
- 队列堆积。
- 内存增长。
- 丢帧异常。
- 多线程结果与单线程结果不一致且无法解释。

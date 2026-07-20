# 03C_队列限流与Buffer复用规范

## 适用范围

本规范用于定义视频 pipeline 的队列限流、丢帧策略、buffer 复用和延迟控制规则。

本阶段重点回答：

```text
当输入 FPS 高于推理能力时，系统如何控制延迟？
队列满时丢旧帧、丢新帧还是阻塞？
buffer 是否持续分配导致内存增长？
```

## 执行原则

下面的队列策略和 buffer 复用实现是推荐路径，不是唯一实现。可以替换有界队列、环形缓冲、内存池或丢帧策略，但不能降低证据要求：必须保留队列长度、丢帧率、端到端延迟、内存曲线和策略解释。替代路径必须写入对应 `projects/03_video_pipeline/runs/`，并同步更新 `projects/03_video_pipeline/reports/runtime_benchmark.md` 和 `projects/03_video_pipeline/reports/failure_and_fallback.md`。

## 路径口径

本 spec 使用当前仓库结构：

- 队列配置放在 `projects/03_video_pipeline/configs/pipeline/`。
- raw result 放在 `benchmark/raw/03_video_pipeline/<target>/`。
- monitor 日志放在 `logs/monitor/03_video_pipeline/<target>/`。
- runtime 日志放在 `logs/runtime/03_video_pipeline/<target>/`。
- 报告放在 `projects/03_video_pipeline/reports/`。

## 前置条件

- 已完成 `03B_多线程Pipeline规范.md`。
- 已记录各阶段平均耗时和 p95/p99。
- 已明确实时优先还是完整帧优先。
- 已准备高负载输入源，例如高 FPS 视频或高分辨率 RTSP。
- run 记录必须对齐 `projects/03_video_pipeline/specs/00_run_record_template.md`。
- 环境基线必须对齐 `projects/03_video_pipeline/specs/00_environment_baseline_template.md`。
- raw result 必须符合 `benchmark/schemas/video_pipeline_raw_schema.yaml`，且每行表示一帧。

## 固定策略

| 场景 | 推荐策略 | 说明 |
|---|---|---|
| 实时显示 | 丢旧帧 | 保持低延迟 |
| 离线分析 | 阻塞或不丢帧 | 保持完整性 |
| 告警触发 | 丢旧帧 + 保留关键帧 | 后续项目五可复用 |
| 输出保存 | 根据磁盘能力限速 | 防止 output 阶段拖垮 pipeline |

## 策略语义口径

文档里不能只写 `drop_oldest`、`drop_newest`、`block_with_timeout` 这些名字，必须同时写清楚“它在队列满时到底做什么”。

统一口径如下：

- 队列策略只在“目标队列已满”时触发；未满时直接入队。
- `queue_push_timeout_ms` 等待的是“目标队列腾出空位”，不是“推理响应超时”，也不是“端到端延迟阈值”。
- 当前参考实现 `src/video_pipeline_app.cpp` 里，`queue_policy` 与 `queue_push_timeout_ms` 是 pipeline 级全局参数，会同时作用于四段内部队列；除非代码另有证据，不能在报告里声称“每段队列已经使用不同策略”。

| 策略 | 队列满时的动作 | 等待行为 | 丢弃语义 | 报告中必须写清楚的解释 |
|---|---|---|---|---|
| `drop_oldest` | 移除队列中最旧元素，再把当前新元素入队 | 不等待 | 丢的是“已排队最旧帧”，不是当前帧 | 这是“保最新画面”的低延迟策略，不是 no-drop 策略 |
| `drop_newest` | 保持队列不变，直接放弃本次新元素 | 不等待 | 丢的是“当前新帧” | 这是“保队列存量”的策略，更容易把旧画面继续送到下游 |
| `block_with_timeout` | 等待最多 `queue_push_timeout_ms` 让队列出现空位；有空位则入队 | 等待上限由 `queue_push_timeout_ms` 决定 | 超时后仍无空位，则丢当前帧 | `33 ms` 表示“单次入队最多等 33 ms”，不能解读成“33 ms 没有整条链路响应就失败” |
| `block` / `block_forever` / `no_drop` | 一直等待到有空位或队列关闭 | 无限等待 | 不因 timeout 丢当前帧 | 更适合 no-drop 对齐或质量评估，不适合作为默认低延迟主线 |
| `keep_key_frame` | 依赖业务规则保关键帧 | 视实现而定 | 视实现而定 | 当前是规范级保留策略；未实现前不能作为已验证策略写结论 |

额外要求：

- 如果通过脚本传参做覆盖，run 和报告必须同时记录“请求的策略名”和“实际生效的策略名”。
- 如果使用 `block_with_timeout`，run、raw result、summary 和报告必须显式写出 `queue_push_timeout_ms`。
- 如果用了 `block`、`block_forever` 或 `no_drop`，必须明确说明为什么允许等待堆积，以及是否会影响实时显示延迟。

## 执行步骤

### 1. 建立 run 记录

新建：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_<target>_yolo11n_<backend>_queue_<policy>/run.md
```

每个 policy 必须单独建 run，不能把多个策略混写到一个 run 中。

### 2. 定义队列配置

配置示例：

```yaml
queues:
  capture_to_preprocess:
    capacity: 4
    full_policy: drop_oldest
  preprocess_to_infer:
    capacity: 4
    full_policy: block_with_timeout
  infer_to_postprocess:
    capacity: 4
    full_policy: block_with_timeout
  postprocess_to_output:
    capacity: 8
    full_policy: drop_oldest
buffers:
  reuse: true
  pool_size: 8
```

上面的 YAML 示例表达的是“设计层允许每段队列有不同配置”。但对当前仓库的参考实现，必须额外注明一条实现口径：

- `queue_capacity` 会按配置作用在各段队列；
- `queue_policy` 和 `queue_push_timeout_ms` 当前按“全局统一策略”生效，而不是每段单独生效；
- 因此，若报告中写“已比较 `drop_oldest` / `drop_newest` / `block_with_timeout`”，其含义应是“对整条 pipeline 的所有内部有界队列统一切换策略后进行对照”。

### 3. 运行策略对比

命令模板：

```bash
for policy in drop_oldest drop_newest block_with_timeout; do
    RUN_ID=<yyyymmdd>_<target>_yolo11n_<backend>_queue_${policy}
    build/03_video_pipeline/video_pipeline_app \
    --config projects/03_video_pipeline/configs/pipeline/queue_${policy}.yaml \
    --duration-sec 600 \
    --raw-output benchmark/raw/03_video_pipeline/<target>/${RUN_ID}.jsonl \
    > logs/runtime/03_video_pipeline/<target>/${RUN_ID}.log 2>&1
done
```

如果使用当前仓库的统一 run 脚本覆盖策略，推荐同时记录：

```bash
QUEUE_POLICY=<policy>
QUEUE_PUSH_TIMEOUT_MS=<timeout_if_any>
```

并在 run / report 中同时写出：

```text
queue_policy_override_requested
queue_policy_override_effective
queue_push_timeout_ms
```

### 4. 采集内存曲线

命令模板：

```bash
python3 projects/03_video_pipeline/scripts/monitor_process.py \
  --pid <pipeline_pid> \
  --interval-sec 1 \
  --output logs/monitor/03_video_pipeline/<target>/<run_id>_memory.csv &
echo $! > logs/monitor/03_video_pipeline/<target>/<run_id>_memory_monitor.pid
```

测试结束后停止监控：

```bash
kill "$(cat logs/monitor/03_video_pipeline/<target>/<run_id>_memory_monitor.pid)"
```

### 5. 聚合对比

```bash
python3 projects/03_video_pipeline/scripts/compare_queue_policies.py \
  --input benchmark/raw/03_video_pipeline/<target> \
  --pattern "*_queue_*.jsonl" \
  --monitor logs/monitor/03_video_pipeline/<target>/*_memory.csv \
  --output projects/03_video_pipeline/reports/runtime_benchmark.md
```

## 记录要求

- 队列配置写入 `projects/03_video_pipeline/configs/pipeline/`。
- 丢帧率、队列长度和阶段耗时写入 raw result。
- `buffer_reuse`、`buffer_pool_size`、`queue_policy`、`queue_capacity` 和 `queue_push_timeout_ms` 必须写入 run；`buffer_reuse`、`queue_policy` 和 `queue_push_timeout_ms` 也必须进入 raw result。
- 如本次 run 通过脚本或命令行覆盖队列策略，必须在 run 中同时写 `queue_policy_override_requested` 和 `queue_policy_override_effective`，避免出现“run_id 写的是一种策略，实际执行的是另一种策略”。
- 内存曲线保存到 `logs/monitor/03_video_pipeline/<target>/`。
- 策略选择原因写入 `projects/03_video_pipeline/reports/video_pipeline.md`。
- 高负载下失败或降级写入 `projects/03_video_pipeline/reports/troubleshooting.md`。

## 输出文件

| 文件 | 要求 |
|---|---|
| `projects/03_video_pipeline/configs/pipeline/queue_*.yaml` | 队列策略配置 |
| `benchmark/raw/03_video_pipeline/<target>/*queue*.jsonl` | 队列策略 raw result |
| `logs/monitor/03_video_pipeline/<target>/*queue_buffer_memory.csv` | 内存曲线 |
| `projects/03_video_pipeline/reports/runtime_benchmark.md` | 队列策略对比 |
| `projects/03_video_pipeline/reports/failure_and_fallback.md` | 高负载降级策略 |

## 验收标准

- 高负载下端到端延迟可控。
- 内存不持续增长。
- 丢帧策略在报告中解释清楚。
- 选定主线策略有数据支撑。
- buffer 复用前后内存或分配次数有对比，无法统计时必须说明原因。

## 降级和问题库

下面问题必须进入问题库：

- buffer 泄漏。
- 延迟堆积。
- 队列策略导致结果不可用。
- 丢帧率异常。
- 内存曲线缺失。

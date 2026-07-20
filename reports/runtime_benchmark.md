# 项目三 Runtime Benchmark

## 当前状态
completed_closed_nonblocking_quality_fails_archived

当前正式默认主线口径已经从“带输出视频主线”切换为“playlist-paced + SAVE_OUTPUT_VIDEO=0”。带输出视频 run 继续保留，但仅作为 output 瓶颈对照证据，不再作为默认实时性基线。

截至 `2026-07-01`，本报告覆盖的 Jetson / RK3588 / RDK X5 三条项目三正式工程主线都已完成收口。当前 remaining items 只包括可选优化，不再包括规范必做项；所有 BDD100K task-level quality fail 都已按 `closed_nonblocking_task_fail` 单独归档。

数据集边界：本报告出现的 `video_short_001` 均为无人工标注的历史诊断或旧 runtime 证据，不参与当前正式质量汇总；`bdd100k_mot_mini_v1` 是包含 80 段视频、15,631 个标注帧和 230,698 个 GT 框的正式数据集。两者不是同一数据集，历史短视频结果不得与 BDD100K 的 AP50、precision、recall、F1 或覆盖率合并。当前及后续离线视频 run 统一使用 `bdd100k_mot_mini_v1` 及其 runtime/stability playlist。

## 2026-06-18 03I 本地汇总进展

2026-06-30 update:
- `schema_check_report.md` 当前为 `pass`。
- 默认 formal scope 已额外排除 ad-hoc preview / visual-debug raw，包括 Jetson IMX219 预览调试 raw、RK3588 Astra 预览 smoke raw，以及新增补入的 RDK X5 IMX219 `preview_*` / ad-hoc `*service*.jsonl`。
- `runtime_summary.csv`、`stability_summary.csv`、`excluded_runs.md` 已按这轮扩展后的 formal scope 完成本地增量重刷；RDK X5 `20260624/20260629/20260630` 相关行已刷新为当前温度/内存/worker 口径。
- `20260630` 的 RDK X5 IMX219 live-source `short_sustained` / `acceptance_sustained` 已通过对应的 `summary.csv`、`stability.csv`、`trace_check.md` 与本地 `schema_check.md` 重验，可先作为 RDK X5 当前权威证据链使用。

- 已生成：
  - `benchmark/processed/03_video_pipeline/runtime_summary.csv`
  - `benchmark/processed/03_video_pipeline/stability_summary.csv`
  - `benchmark/processed/03_video_pipeline/excluded_runs.md`
- 当前已闭环：
  - `benchmark/processed/03_video_pipeline/schema_check_report.md` 对整个 `benchmark/raw/03_video_pipeline/` 在默认 formal scope 下返回 `pass`
  - 默认 formal scope 已排除 13 份非正式 raw：
    - `02_quantization/` 下 11 份 legacy inherited raw
    - 文件名含 `project1_baseline` 的 2 份跨项目 fixed-input 对照 raw
  - `benchmark/processed/03_video_pipeline/excluded_runs.md` 已逐项记录排除原因
- 因此，`03I` 的 Jetson 侧本地回填已经进入可用状态；后续不再是补板端 run 或继续修 scope，而是等待 RK3588 frame-level raw 增量同步，并继续把“规范未闭环的实验项”与“已完成的 video-file 主线证据”分开表述。

## 术语解释

为了避免只靠英文缩写阅读，这里统一说明项目三报告中的常用术语：

- `trace`：逐帧追踪检查，主要看 `frame_id` 和各阶段时间戳是否完整、连续、可追溯。
- `frame gap` / `frame_id_gaps`：`frame_id` 不连续，说明中间有帧没有进入最终 raw result。
- `drop_oldest`：队列满时丢掉最旧的帧，优先保留最新帧，目标是尽量保持实时性。
- `drop_newest`：队列满时丢掉最新到达的帧，优先保留已经排队的旧帧。
- `block` / `no-drop`：队列满时阻塞等待，尽量不丢帧，但更容易增加端到端延迟。
- `p50 / p90 / p95 / p99`：延迟分位数。例如 `p95=63 ms` 表示 95% 的帧延迟不超过 63 ms。
- `TP / FP / FN`：真阳性 / 假阳性 / 漏检，用于说明检测质量。
- `precision / recall / F1`：精确率 / 召回率 / 综合分数。
- `AP50`：IoU=0.50 条件下的平均精度。
- `artifact`：本次运行实际加载的模型文件，例如 TensorRT engine；报告里必须区分“规范要求的 artifact”和“raw 实际记录的 artifact”。

当前 Jetson C++ 主线实现还有一个要特别说明的口径：

- 运行时当前实际消费的是**全局** `mainline_policy` 和 **全局** `queue_capacity`。
- 因此，主线实时 benchmark 的核心行为应以 `mainline_policy` / `queue_capacity` 为准，而不是只看 YAML 里每个阶段的展示性字段。

## Jetson BDD100K Mini No-drop Limit5 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5` 的回传结果。该 run 先通过 `bash -n` 检查 `run_jetson_bdd100k_mini.sh` 和 `run_jetson_tensorrt_pipeline.sh`，随后执行 5 段 BDD100K MOT mini no-drop 质量评估。结论是：5/5 pipeline、schema、trace 均通过且无丢帧，1/5 质量通过，4/5 质量阈值失败。当前问题主要是检测召回不足，不是队列或 frame gap。
| item | value |
|---|---|
| run_prefix | `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision | `fp16` |
| selected_sequences | 5 |
| pipeline_exit | all `0` |
| schema_check | pass for all 5 |
| trace_check | pass for all 5 |
| frame_id_gaps | 0 for all 5 |
| queue_policy | `block` |
| queue_capacity | 32 |
| drop_frame_count_max | 0 for all 5 |
| quality_pass | 1 / 5 |
| quality_failures | 4 |
| strict_failures | 0 |

| runtime metric | value |
|---|---:|
| fps_avg_across_sequences | 30.0128 |
| fps_min | 29.8399 |
| fps_max | 30.1281 |
| p95_latency_avg_ms | 51.0114 |
| p95_latency_min_ms | 48.5862 |
| p95_latency_max_ms | 52.2831 |
| p99_latency_avg_ms | 80.4334 |
| p99_latency_min_ms | 78.7554 |
| p99_latency_max_ms | 83.8656 |
| memory_mb_peak_max | 2432.0 |
| temperature_c_peak_max | 60.0 |

| quality aggregate | value |
|---|---:|
| total_gt | 13742 |
| total_pred | 6118 |
| total_tp | 4189 |
| total_fp | 1929 |
| total_fn | 9553 |
| weighted_ap50_by_gt | 0.280182 |
| overall_precision_from_totals | 0.684701 |
| overall_recall_from_totals | 0.304832 |
| overall_f1_from_totals | 0.421853 |

| sequence_id | frames | fps_estimated | p95_latency_ms | p99_latency_ms | drop_frame_count_max | labeled_frame_coverage | ap50_weighted | precision | recall | f1 | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `02344f0c-d5d916ff` | 1204 | 30.0349 | 52.2831 | 80.4538 | 0 | 0.995050 | 0.136443 | 0.554014 | 0.164363 | 0.253515 | quality_threshold_fail |
| `012a9c41-692c9f06` | 1207 | 30.0149 | 51.7939 | 83.8656 | 0 | 0.995074 | 0.302004 | 0.847561 | 0.312594 | 0.456736 | quality_threshold_fail |
| `01af2f91-3eacda83` | 1204 | 30.0462 | 50.1840 | 78.7554 | 0 | 0.995050 | 0.074009 | 0.374277 | 0.107917 | 0.167529 | quality_threshold_fail |
| `010fc651-19922861` | 1202 | 29.8399 | 52.2100 | 79.1665 | 0 | 0.990148 | 0.325592 | 0.635323 | 0.354633 | 0.455185 | quality_threshold_fail |
| `02097021-05dcbf23` | 1211 | 30.1281 | 48.5862 | 79.9255 | 0 | 0.995074 | 0.548176 | 0.796380 | 0.571058 | 0.665155 | pass |

分布结论：5 段的 `weighted_ap50_by_gt=0.280182` 已超过当前 `0.25` 阈值，但 `overall_recall_from_totals=0.304832` 明显低于 `0.50` 阈值。质量失败不是由 no-drop 链路造成；后续已补做离线 confidence sweep，下一步需要低阈值上板 rerun、难例分层和项目一 / fixed-input 对齐复核，确认是模型能力、阈值口径还是数据集难度导致。
## Jetson BDD100K Mini No-drop Limit5 Confidence Sweep 2026-06-16

本节使用已同步的 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5` raw result 和 BDD labels 做离线置信度扫描。扫描脚本只会在 raw 已经写出的 detections 上调整评估阈值，不能恢复 C++ postprocess 阶段已经被 `confidence_threshold=0.25` 过滤掉的候选框。
| artifact | path |
|---|---|
| sweep_summary | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_confidence_sweep_summary.csv` |
| sweep_details | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_confidence_sweep_details.csv` |
| sweep_report | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_confidence_sweep.md` |
| raw_confidence_distribution | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_raw_confidence_distribution.csv` |

| confidence_min | pass_count | fail_count | total_pred | weighted_ap50_by_gt | precision | recall | f1 | status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0.05 | 1 | 4 | 6118 | 0.280182 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.10 | 1 | 4 | 6118 | 0.280182 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.15 | 1 | 4 | 6118 | 0.280182 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.20 | 1 | 4 | 6118 | 0.280182 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.25 | 1 | 4 | 6118 | 0.280182 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.30 | 1 | 4 | 5447 | 0.280182 | 0.722416 | 0.286348 | 0.410131 | fail |

| sequence_id | raw_detection_count_all_frames_all_classes | min_confidence | max_confidence | `<0.10` | `0.10-0.15` | `0.15-0.20` | `0.20-0.25` | `0.25-0.30` | `>=0.30` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `02344f0c-d5d916ff` | 6859 | 0.250179 | 0.929951 | 0 | 0 | 0 | 0 | 880 | 5979 |
| `012a9c41-692c9f06` | 7340 | 0.250179 | 0.948537 | 0 | 0 | 0 | 0 | 906 | 6434 |
| `01af2f91-3eacda83` | 5425 | 0.250179 | 0.962108 | 0 | 0 | 0 | 0 | 698 | 4727 |
| `010fc651-19922861` | 8618 | 0.250179 | 0.865224 | 0 | 0 | 0 | 0 | 1040 | 7578 |
| `02097021-05dcbf23` | 13812 | 0.250179 | 0.956634 | 0 | 0 | 0 | 0 | 1646 | 12166 |

结论：离线 `confidence_min=0.05-0.25` 的指标完全一致，5 段 raw 的最小 detection confidence 都是 `0.250179`，`0.25` 以下候选框数量为 0。因此当前 raw 上的离线阈值扫描已经穷尽，下一步若要验证低阈值能否提高 recall，必须在 Jetson 上用 `MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml` 重新跑 pipeline，并同步设置 `CONFIDENCE_MIN=0.10` 做评估。
## Jetson BDD100K Mini No-drop Conf010 Limit5 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5` 的回传结果。该 run 在同一 no-drop pipeline 基线上，把 `MODEL_CONFIG` 切到 `projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml`，将 C++ postprocess `confidence_threshold` 从 `0.25` 降到 `0.10`，评估脚本同步使用 `CONFIDENCE_MIN=0.10`。结论是：5/5 pipeline 继续通过，raw 确实新增了 `0.10-0.25` 区间候选框，aggregate recall 和 AP50 明显提升，但 `overall_recall_from_totals=0.372144` 仍低于 `0.50` 门槛，质量状态仍是 `1/5 pass`、`4/5 fail`。
| item | value |
|---|---|
| run_prefix | `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision | `fp16` |
| selected_sequences | 5 |
| pipeline_exit | all `0` |
| schema_check | pass for all 5 |
| trace_check | pass for all 5 |
| frame_id_gaps | 0 for all 5 |
| queue_policy | `block` |
| queue_capacity | 32 |
| model_config | `projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml` |
| evaluation_confidence_min | `0.10` |
| drop_frame_count_max | 0 for all 5 |
| quality_pass | 1 / 5 |
| quality_failures | 4 |
| strict_failures | 0 |

| runtime metric | value |
|---|---:|
| fps_avg_across_sequences | 30.0128 |
| p95_latency_avg_ms | 51.5047 |
| p99_latency_avg_ms | 79.4130 |
| detection_count_mean_avg | 13.0023 |
| memory_mb_peak_max | 2437.0 |
| temperature_c_peak_max | 60.5 |

| quality aggregate | value |
|---|---:|
| total_gt | 13742 |
| total_pred | 10366 |
| total_tp | 5114 |
| total_fp | 5252 |
| total_fn | 8628 |
| weighted_ap50_by_gt | 0.321903 |
| overall_precision_from_totals | 0.493344 |
| overall_recall_from_totals | 0.372144 |
| overall_f1_from_totals | 0.424258 |

| sequence_id | frames | fps_estimated | p95_latency_ms | p99_latency_ms | detection_count_mean | ap50_weighted | precision | recall | f1 | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `02344f0c-d5d916ff` | 1204 | 30.0349 | 50.7089 | 78.7549 | 11.6761 | 0.160882 | 0.395539 | 0.213761 | 0.277534 | quality_threshold_fail |
| `012a9c41-692c9f06` | 1207 | 30.0149 | 51.3008 | 84.0617 | 12.4275 | 0.367680 | 0.621212 | 0.399550 | 0.486314 | quality_threshold_fail |
| `01af2f91-3eacda83` | 1204 | 30.0462 | 51.7807 | 78.5153 | 8.5058 | 0.082617 | 0.244599 | 0.132083 | 0.171537 | quality_threshold_fail |
| `010fc651-19922861` | 1202 | 29.8399 | 55.9205 | 79.6939 | 12.8536 | 0.362674 | 0.459930 | 0.421725 | 0.440000 | quality_threshold_fail |
| `02097021-05dcbf23` | 1211 | 30.1281 | 47.8126 | 76.0390 | 19.5483 | 0.617316 | 0.593100 | 0.674886 | 0.631355 | pass |

| compare_metric | conf025_limit5 | conf010_limit5 | delta |
|---|---:|---:|---:|
| total_pred | 6118 | 10366 | 4248 |
| total_tp | 4189 | 5114 | 925 |
| total_fp | 1929 | 5252 | 3323 |
| total_fn | 9553 | 8628 | -925 |
| weighted_ap50_by_gt | 0.280182 | 0.321903 | 0.041721 |
| overall_precision_from_totals | 0.684701 | 0.493344 | -0.191357 |
| overall_recall_from_totals | 0.304832 | 0.372144 | 0.067312 |
| overall_f1_from_totals | 0.421853 | 0.424258 | 0.002405 |
| fps_avg_across_sequences | 30.0128 | 30.0128 | 0.0000 |
| p95_latency_avg_ms | 51.0114 | 51.5047 | 0.4933 |
| p99_latency_avg_ms | 80.4334 | 79.4130 | -1.0204 |
| detection_count_mean_avg | 6.9718 | 13.0023 | 6.0305 |
| memory_mb_peak_max | 2432.0 | 2437.0 | 5.0 |
| temperature_c_peak_max | 60.0 | 60.5 | 0.5 |

结论：`conf010` 确实改善了质量，但改善幅度不足以穿过当前 recall 门槛。新增 4248 个评估候选框仅换来 925 个 TP，同时引入 3323 个 FP；aggregate F1 只从 `0.421853` 升到 `0.424258`。从类别表现看，`car` recall 有明显改善，但 `bicycle` 和 `train` 仍未召回，说明当前瓶颈不只是简单阈值过高。
## Jetson BDD100K Mini No-drop Conf010 Limit5 Confidence Sweep 2026-06-16

本节在 `conf010` rerun 的 raw 上继续做离线 confidence sweep，确认最佳评估阈值。由于新 raw 的最小 detection confidence 已降到 `0.100172`，离线 `0.10` 以下阈值可以和 `0.25` 基线拉开差异；但 `0.05` 和 `0.10` 结果完全一致，说明当前 raw 仍没有 `<0.10` 的候选框。
| artifact | path |
|---|---|
| sweep_summary | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_confidence_sweep_summary.csv` |
| sweep_details | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_confidence_sweep_details.csv` |
| sweep_report | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_confidence_sweep.md` |
| raw_confidence_distribution | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_raw_confidence_distribution.csv` |

| confidence_min | pass_count | fail_count | total_pred | weighted_ap50_by_gt | precision | recall | f1 | status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0.05 | 1 | 4 | 10366 | 0.321903 | 0.493344 | 0.372144 | 0.424258 | fail |
| 0.10 | 1 | 4 | 10366 | 0.321903 | 0.493344 | 0.372144 | 0.424258 | fail |
| 0.15 | 1 | 4 | 8189 | 0.321903 | 0.577116 | 0.343909 | 0.430988 | fail |
| 0.20 | 1 | 4 | 6963 | 0.321903 | 0.639236 | 0.323898 | 0.429944 | fail |
| 0.25 | 1 | 4 | 6118 | 0.321903 | 0.684701 | 0.304832 | 0.421853 | fail |
| 0.30 | 1 | 4 | 5447 | 0.321903 | 0.722416 | 0.286348 | 0.410131 | fail |

| sequence_id | raw_detection_count_all_frames_all_classes | min_confidence | max_confidence | `<0.10` | `0.10-0.15` | `0.15-0.20` | `0.20-0.25` | `0.25-0.30` | `>=0.30` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `02344f0c-d5d916ff` | 14058 | 0.100172 | 0.929951 | 0 | 3813 | 2092 | 1294 | 880 | 5979 |
| `012a9c41-692c9f06` | 15000 | 0.100172 | 0.948537 | 0 | 4126 | 2176 | 1358 | 906 | 6434 |
| `01af2f91-3eacda83` | 10241 | 0.100172 | 0.962108 | 0 | 2695 | 1289 | 832 | 698 | 4727 |
| `010fc651-19922861` | 15450 | 0.100172 | 0.865224 | 0 | 3349 | 2088 | 1395 | 1040 | 7578 |
| `02097021-05dcbf23` | 23673 | 0.100172 | 0.956634 | 0 | 4946 | 2939 | 1976 | 1646 | 12166 |

结论：新 raw 上的最佳评估阈值是 `0.05/0.10`，aggregate recall 上限目前就是 `0.372144`。这说明 `conf010` 已经把 `0.10-0.25` 区间候选框纳入，但阈值调优本身仍不足以把任务级质量拉到 `recall >= 0.50`。
## Jetson BDD100K Mini No-drop Conf005 Limit5 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5` 的回传结果。该 run 延续同一 no-drop pipeline 基线，将 `MODEL_CONFIG` 切到 `projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml`，把 C++ postprocess `confidence_threshold` 从 `0.10` 继续降到 `0.05`，评估脚本同步使用 `CONFIDENCE_MIN=0.05`。结论是：5/5 pipeline 继续通过、trace 继续无 gaps，但 `conf010 -> conf005` 的新增候选框主要转化成 FP，虽然 recall 继续升高，整体 F1 已开始明显回落，质量状态仍是 `1/5 pass`、`4/5 fail`。

| item | value |
|---|---|
| run_prefix | `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision | `fp16` |
| model_config | `projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml` |
| confidence_min | `0.05` |
| sequences | 5 |
| schema / trace / prepost | 5/5 pass, 5/5 no frame gaps, prepost check emitted for all 5 runs |
| output_video_saved | 0 |
| batch_status | `1_pass_4_quality_threshold_fail` |

| metric | value |
|---|---:|
| total_gt | 13742 |
| total_pred | 15287 |
| total_tp | 5721 |
| total_fp | 9566 |
| total_fn | 8021 |
| weighted_ap50_by_gt | 0.341615 |
| overall_precision_from_totals | 0.374240 |
| overall_recall_from_totals | 0.416315 |
| overall_f1_from_totals | 0.394158 |
| labeled_frame_coverage | 0.994077 |

| compare_metric | `conf010_limit5` | `conf005_limit5` | delta |
|---|---:|---:|---:|
| total_pred | 10366 | 15287 | 4921 |
| total_tp | 5114 | 5721 | 607 |
| total_fp | 5252 | 9566 | 4314 |
| total_fn | 8628 | 8021 | -607 |
| weighted_ap50_by_gt | 0.318622 | 0.341615 | 0.019712 |
| overall_precision_from_totals | 0.493344 | 0.374240 | -0.119104 |
| overall_recall_from_totals | 0.372144 | 0.416315 | 0.044171 |
| overall_f1_from_totals | 0.424258 | 0.394158 | -0.030100 |

| class_name | gt_count | conf025_recall | conf010_recall | conf005_recall | key_reading |
|---|---:|---:|---:|---:|---|
| person | 1383 | 0.138106 | 0.163413 | 0.184382 | 有提升，但提升主要靠大幅增加候选框换来，precision 明显恶化 |
| bicycle | 92 | 0.000000 | 0.000000 | 0.000000 | 即使继续降阈值仍然 0 召回 |
| car | 9915 | 0.392940 | 0.480484 | 0.537771 | 继续降阈值主要还是在救 `car` |
| train | 743 | 0.000000 | 0.000000 | 0.000000 | 即使预测框从 6 增到 25，仍然没有 TP |
| truck | 1308 | 0.064985 | 0.074924 | 0.077982 | 只有边际改善，不足以改变总体结论 |

结论：`conf005` 说明单纯继续降阈值仍能再抬一点 recall，但收益已经明显变差。新增 4921 个候选框只换来 607 个 TP，同时多引入 4314 个 FP，导致 aggregate F1 从 `0.424258` 回落到 `0.394158`。因此“继续靠阈值调优把任务质量拉过线”这一条路线可以认为已经基本跑透，后续重点不应再放在更低阈值，而应转向模型能力或类别/标注口径分析。
## Jetson BDD100K Mini No-drop Prepostfix Limit5 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5` 的回传结果。该 run 使用默认 `projects/03_video_pipeline/configs/models/yolo11n.yaml`，但已经带上前后处理一致性修复，并且 5/5 序列都先产出了 `*_prepost_consistency.md` 且 `status=pass`。结论是：项目三 C++ preprocess / postprocess 漂移问题已经被修正并在 Jetson 上验证通过，但这次 rerun 的 BDD100K MOT 质量指标和修复前 `nodrop_limit5` 基本重合，说明当前主问题仍是 `P3-TRB-20260616-001` 中的召回不足，而不是前后处理实现偏移。
| item | value |
|---|---|
| run_prefix | `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision | `fp16` |
| model_config | `projects/03_video_pipeline/configs/models/yolo11n.yaml` |
| selected_sequences | 5 |
| prepost_consistency | pass for all 5 |
| pipeline_exit | all `0` |
| quality_pass | 1 / 5 |
| quality_failures | 4 |
| strict_failures | 0 |
| evidence_source | Jetson terminal output + synced runtime/monitor logs |
| local_artifact_sync_status | current workspace still lacks this rerun's `benchmark/raw` and `benchmark/processed` files; aggregate totals below are reconstructed from terminal precision/recall plus synced per-sequence `total_gt` |

| aggregate compare_metric | `nodrop_limit5` | `nodrop_prepostfix_limit5` | delta |
|---|---:|---:|---:|
| total_pred | 6118 | 6177 | 59 |
| total_tp | 4189 | 4190 | 1 |
| total_fp | 1929 | 1987 | 58 |
| total_fn | 9553 | 9552 | -1 |
| weighted_ap50_by_gt | 0.280182 | 0.280400 | 0.000218 |
| overall_precision_from_totals | 0.684701 | 0.678323 | -0.006378 |
| overall_recall_from_totals | 0.304832 | 0.304905 | 0.000073 |
| overall_f1_from_totals | 0.421853 | 0.420704 | -0.001149 |

| sequence_id | prepost_consistency | ap50_weighted | delta_ap50 | precision | delta_precision | recall | delta_recall | f1 | delta_f1 | labeled_frame_coverage | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `02344f0c-d5d916ff` | pass | 0.136712 | 0.000269 | 0.556762 | 0.002748 | 0.165834 | 0.001471 | 0.255551 | 0.002036 | 0.995050 | quality_threshold_fail |
| `012a9c41-692c9f06` | pass | 0.302733 | 0.000729 | 0.835507 | -0.012054 | 0.312219 | -0.000375 | 0.454570 | -0.002166 | 0.995074 | quality_threshold_fail |
| `01af2f91-3eacda83` | pass | 0.073933 | -0.000076 | 0.361997 | -0.012280 | 0.108750 | 0.000833 | 0.167254 | -0.000275 | 0.995050 | quality_threshold_fail |
| `010fc651-19922861` | pass | 0.326091 | 0.000499 | 0.635323 | 0.000000 | 0.354633 | 0.000000 | 0.455185 | 0.000000 | 0.990148 | quality_threshold_fail |
| `02097021-05dcbf23` | pass | 0.547925 | -0.000251 | 0.789474 | -0.006906 | 0.569435 | -0.001623 | 0.661640 | -0.003515 | 0.995074 | pass |

结论：这次 board rerun 已经把 `P3-TRB-20260616-002` 从“代码层本地修复待上板”推进到“Jetson 侧验证通过”。但从 aggregate 和 per-sequence delta 看，变化都非常小，无法解释当前 `overall_recall` 长期停留在 `0.30-0.37` 区间的问题。后续排查主线应继续聚焦类别分布、难例分层、fixed-input 对齐和模型能力边界，而不是继续怀疑前后处理实现没有继承项目一 / 二。
## Jetson BDD100K Mini Difficult-case Analysis 2026-06-16

本节基于已同步的 `conf025_limit5` 与 `conf010_limit5` raw / label 结果做难例分层分析，目标是回答两个问题：第一，`person`、`bicycle`、`train` 是否只是样本太少；第二，低召回是否主要集中在小目标、遮挡、截断和 crowd 等困难切片。分析脚本输出：

| artifact | path |
|---|---|
| difficult_case_report | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_conf010_vs_conf025_difficult_case_analysis.md` |
| difficult_case_class_summary | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_conf010_vs_conf025_difficult_case_class_summary.csv` |
| difficult_case_slice_summary | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_conf010_vs_conf025_difficult_case_slice_summary.csv` |

GT 分布先给出直接答案：`person` 和 `train` 不是稀有类，`bicycle` 相对少一些，但也不是 0 或偶发。
| class_name | gt_count | gt_share_among_focus | small | medium | large | occluded | truncated | crowd | difficult |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| person | 1383 | 0.113987 | 751 | 419 | 213 | 870 | 23 | 51 | 1088 |
| bicycle | 92 | 0.007583 | 41 | 50 | 1 | 66 | 14 | 0 | 79 |
| car | 9915 | 0.817193 | 2108 | 4740 | 3067 | 7287 | 1643 | 749 | 9013 |
| train | 743 | 0.061238 | 12 | 122 | 609 | 743 | 311 | 0 | 743 |

`conf010` 相比 `conf025` 的类别级变化如下。结论很清楚：阈值下调主要救回来的是 `car`，对 `person` 只有有限帮助，对 `bicycle` / `train` 基本无效。
| class_name | gt_count | conf025_ap50 | conf010_ap50 | delta_ap50 | conf025_recall | conf010_recall | delta_recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| person | 1383 | 0.119326 | 0.133323 | 0.013998 | 0.138106 | 0.163413 | 0.025307 |
| bicycle | 92 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| car | 9915 | 0.353544 | 0.406425 | 0.052881 | 0.392940 | 0.480484 | 0.087544 |
| train | 743 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

困难切片进一步解释了为什么现在的 recall 很难过线：
| class_name | slice_name | gt_count | conf025_recall | conf010_recall | delta_recall |
|---|---|---:|---:|---:|---:|
| person | size_small | 751 | 0.009321 | 0.015979 | 0.006658 |
| person | occluded_true | 870 | 0.059770 | 0.089655 | 0.029885 |
| person | difficult | 1088 | 0.048713 | 0.072610 | 0.023897 |
| person | size_large | 213 | 0.629108 | 0.708920 | 0.079812 |
| bicycle | all | 92 | 0.000000 | 0.000000 | 0.000000 |
| bicycle | difficult | 79 | 0.000000 | 0.000000 | 0.000000 |
| car | size_small | 2108 | 0.054080 | 0.126186 | 0.072106 |
| car | occluded_true | 7287 | 0.325923 | 0.427199 | 0.101276 |
| car | difficult | 9013 | 0.350605 | 0.442361 | 0.091756 |
| car | size_large | 3067 | 0.769156 | 0.795240 | 0.026084 |
| train | all | 743 | 0.000000 | 0.000000 | 0.000000 |
| train | difficult | 743 | 0.000000 | 0.000000 | 0.000000 |

结论：
- `person` 的问题主要集中在小目标和遮挡；`size_large` recall 已经到 `0.708920`，但 `size_small` 只有 `0.015979`。
- `bicycle` 不是“没有样本”，而是 `92` 个 GT 在 `conf025` / `conf010` 都是 `0` 召回。
- `train` 也不是“样本太少”，5 段里共有 `743` 个 GT，且大部分还是 large box，但当前仍是 `0` 召回，说明这不是简单的小目标问题。
- `car` 是唯一被降阈值明显救回来的大类，但即便如此，`difficult` 切片 recall 也只有 `0.442361`，仍不足以把整体任务级 recall 拉过 `0.50` 门槛。
## Jetson BDD100K Focus-class Domain-gap Analysis 2026-06-16

本节基于 `conf025_limit5`、`conf010_limit5`、`conf005_limit5` 三轮 no-drop 产物，对 `person / bicycle / train` 做一轮更聚焦的“难例 + 类别口径”分析。新脚本 [`analyze_bdd100k_focus_gap.py`](../scripts/quality/analyze_bdd100k_focus_gap.py) 不再只看 same-class recall，而是把未命中 GT 拆成四类：
- `matched_same_class`
- `wrong_class_iou50`
- `coarse_localization_only`（有粗定位，但 IoU 未到 0.50）
- `no_overlap`（没有任何 >=0.10 IoU 的预测框）

产物路径：
- report: `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_focus_gap_analysis.md`
- source summary: `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_focus_gap_source_summary.csv`
- error summary: `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_focus_gap_error_summary.csv`
- wrong-class summary: `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_focus_gap_wrong_class_summary.csv`
- slice summary: `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_focus_gap_slice_summary.csv`

| class_name | source_category | conf025_recall | conf010_recall | conf005_recall |
|---|---|---:|---:|---:|
| person | pedestrian | 0.146029 | 0.170794 | 0.207515 |
| person | rider | 0.094340 | 0.122642 | 0.174528 |
| bicycle | bicycle | 0.000000 | 0.000000 | 0.000000 |
| train | train | 0.000000 | 0.000000 | 0.000000 |

| class_name | gt_count | matched_same_class | wrong_class_iou50 | coarse_localization_only | no_overlap |
|---|---:|---:|---:|---:|---:|
| person | 1383 | 280 (0.202458) | 23 (0.016631) | 335 (0.242227) | 745 (0.538684) |
| bicycle | 92 | 0 (0.000000) | 16 (0.173913) | 37 (0.402174) | 39 (0.423913) |
| train | 743 | 0 (0.000000) | 0 (0.000000) | 15 (0.020188) | 728 (0.979812) |

| focus_class | predicted_class | count | note |
|---|---|---:|---|
| bicycle | person | 11 | `wrong_class_iou50` 主导错类，说明骑行场景存在一部分类别口径冲突 |
| bicycle | car | 5 | 次要错类来源 |
| bicycle | person | 21 | `coarse_localization_only` 最近预测也多为 `person`，仍是骑行场景语义耦合 |
| train | train | 9 | 仅少量 `coarse_localization_only`，说明模型偶尔“看到火车轮廓”，但定位/表征不足 |

结论：
- `person` 的 `rider` recall 确实低于 `pedestrian`，但差距并不大到足以解释整体失败；更大的问题是 `small + difficult + no_overlap`，因此主因不是 `rider -> person` 映射本身。
- `bicycle` 呈现“混合型失败”：一部分是骑行场景下被 `person` 吸走，说明存在类别口径张力；但仍有 `42.39%` GT 落在 `no_overlap`，说明不只是口径问题，模型对 BDD 自行车目标本身也缺少稳定响应。
- `train` 呈现最强的域差信号：`743` 个 GT 里 `728` 个落在 `no_overlap`，`609` 个还是 `large`，同时 `wrong_class_iou50=0`。这更像 COCO 预训练目标分布对 BDD 火车场景覆盖不足，而不是阈值、NMS、trace 或前后处理问题。
- 结合 fixed-input alignment 已通过这一事实，当前可以把“项目三实现漂移”从主因列表中移除；这轮分析已经足够支持“COCO->BDD 域差 / 未微调未重训练”是当前质量不对齐的主要解释。

后续数据集建议（不影响当前项目三主线）：

| dataset | 与 COCO 关系 | 适用价值 | 当前判断 |
|---|---|---|---|
| `YouTube-VIS` | 类别体系和视频目标表达方式与 COCO 更接近 | 适合继续验证视频时序场景下的检测/实例目标可迁移性，域差通常小于 COCO -> BDD | 可作为后续替代性视频质量评估数据集候选 |
| `COCO-VID / ImageNet-VID` | 与 COCO 目标口径更近，视频检测任务链路更直接 | 适合做“保持 COCO 预训练、不做 BDD 微调”条件下的主线视频质量验证 | 可作为后续替代性视频质量评估数据集候选 |

当前处理状态：
- `P3-TRB-20260616-001` 已在问题库中按 `closed_nonblocking_task_fail` 收口。
- 收口结论为“COCO->BDD 域差 / 未微调未重训练”，故本次 BDD100K 任务级质量验证失败，但不影响项目三主线。
- 项目三 Jetson 主线下一步不再是 BDD 质量诊断，而是正式 03D `600` 秒 runtime benchmark 与 03H stability smoke。
## Historical Unlabeled Fixed-input Diagnostic 2026-06-16

fixed-input 对齐链路已经完成板端闭环验证。首轮 `drop_oldest` 误配置导致的 current raw 缺帧已定位并修复，`nodropfix` 重跑已拿到可解释的 baseline/current 成对产物和对齐报告。

| evidence_item | status | detail |
|---|---|---|
| baseline `video_short_001` raw with `detections[]` | historical_unlabeled_verified | 仅为历史诊断证据；已生成 `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_project1_baseline_video_short_001.jsonl` |
| current project3 `video_short_001` raw with `detections[]` | historical_unlabeled_verified | 仅为历史诊断证据；已生成 `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_project3_current.jsonl`，`trace_check` 为 `frames=795`、`frame_id_gaps=0`、`drop_frame_count_max=0` |
| alignment manifest | ready | `data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json` |
| alignment compare script | ready | `projects/03_video_pipeline/scripts/quality/compare_detection_alignment.py` |
| project1 baseline bridge | ready | `projects/03_video_pipeline/scripts/quality/convert_project1_alignment_to_video_raw.py` |
| one-shot board runner | ready_verified | `projects/03_video_pipeline/scripts/run/run_jetson_fixed_input_alignment.sh` 已按 fixed-input no-drop 配置完成抽帧、项目一 baseline、项目三 current 和对齐报告 |
| first board attempt | fail_invalid_current_raw | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_fixed_input_alignment.md` 显示 `payload_issue_count=79`，`current_payload_status=missing_frame` |
| corrected board rerun | pass | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_fixed_input_alignment.md` 显示 `payload_issue_count=0`、`total_matches=633/633`、`mean_matched_iou=0.996638`、`mean_conf_abs_diff=0.001089`；detail CSV 仅剩 `frame_id=600` 有 `unmatched_current_count=1`，属于当前 baseline-centric gate 可接受的轻微残余差异 |
| current status | pass_verified_on_board | fixed-input baseline/current/compare 证据链完整，当前可以明确写入 `fixed_input_alignment=pass` |
## Jetson BDD100K Mini No-drop Limit1 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1` 的回传结果。该 run 使用 `jetson_tensorrt_bdd100k_quality.yaml`、`queue_policy=block`、`SAVE_OUTPUT_VIDEO=0`、`TRACE_FAIL_ON_GAPS=1`，用于验证 BDD100K labeled video quality 的 no-drop 路径。结论是：pipeline / runtime / schema / trace 通过，质量评估有效执行但未达到当前阈值。
| item | value |
|---|---|
| run_id | `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision | `fp16` |
| input_source_id | `bdd100k_mot_mini_v1_02344f0c-d5d916ff` |
| queue_policy | `block` |
| queue_capacity | 32 |
| raw_frames | 1204 |
| pass_frames | 1204 |
| schema_check | pass |
| trace_check | pass, `frame_id_gaps=0` |
| drop_frame_count_max | 0 |
| drop_frame_rate_max | 0.0 |
| output_video_saved | 0 |
| pipeline_exit | 0 |
| evaluate_exit | 1 |
| quality_status | `quality_threshold_fail` |
| runtime_log_status | path recorded in summary; file not present in synchronized local workspace |
| monitor_log_status | synchronized |

| metric | value |
|---|---:|
| fps_estimated | 30.0349 |
| latency_p50_ms | 35.8383 |
| latency_p90_ms | 46.4251 |
| latency_p95_ms | 51.7791 |
| latency_p99_ms | 81.6952 |
| detection_count_mean | 5.6968 |
| memory_mb_peak | 2424.0 |
| temperature_c_peak | 52.5 |
| cpu_util_avg | 48.0556 |
| gpu_util_avg | 47.5333 |
| throttle_events | 30 |

| quality metric | value |
|---|---:|
| labeled_frames | 202 |
| prediction_frames | 1204 |
| labeled_frames_with_predictions | 201 |
| labeled_frame_coverage | 0.995050 |
| missing_labeled_frames | 1 |
| missing_labeled_frame_ids_sample | `02344f0c-d5d916ff:1206` |
| overall_ap50_weighted | 0.136443 |
| overall_precision | 0.554014 |
| overall_recall | 0.164363 |
| overall_f1 | 0.253515 |
| total_gt | 3401 |
| total_pred | 1009 |
| total_tp | 559 |
| total_fp | 450 |
| total_fn | 2842 |
| required_overall_ap50_min | 0.25 |
| required_overall_recall_min | 0.50 |

| class_id | class_name | gt_count | pred_count | tp | fp | fn | ap50 | precision | recall | f1 | mean_matched_iou |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | person | 410 | 25 | 0 | 25 | 410 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1 | bicycle | 20 | 0 | 0 | 0 | 20 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2 | car | 2766 | 966 | 544 | 422 | 2222 | 0.162396 | 0.563147 | 0.196674 | 0.291533 | 0.719165 |
| 3 | motorcycle | 0 | 5 | 0 | 5 | 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 5 | bus | 4 | 1 | 0 | 1 | 4 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 6 | train | 174 | 1 | 0 | 1 | 174 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 7 | truck | 27 | 16 | 15 | 1 | 12 | 0.550124 | 0.937500 | 0.555556 | 0.697674 | 0.713583 |

质量失败不是由队列丢帧导致：本轮 `drop_frame_count_max=0` 且 `frame_id_gaps=0`。主要失败原因是当前 YOLO11n FP16 pipeline 在该 BDD100K MOT 序列上召回不足，尤其是 `person`、`bicycle`、`train` 为 0 召回，`car` 类 GT 密集且大量目标较小、遮挡多，`car` recall 仅 `0.196674`。该 run 可以作为有效的 no-drop BDD quality fail 证据，不能写作 `quality pass`。
## Jetson BDD100K Mini Smoke 2026-06-15

本节记录 `20260615_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_smoke_py38fix` 的同步结果。该 run 证明 Jetson TensorRT C++ pipeline、raw schema、runtime summary 和 BDD 质量评估脚本链路可以跑通，但本轮使用的是实时主线 `drop_oldest` 队列策略，raw result 大量丢帧，因此不得作为 BDD100K labeled video quality 结论。
| item | value |
|---|---|
| run_prefix | `20260615_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_smoke_py38fix` |
| target | `jetson_8gb` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| input_source_type | `video_file` |
| selected_sequences | 5 |
| pipeline_exit | all `0` |
| schema_check | pass for generated raw files |
| runtime_summary | generated for all 5 sequences |
| queue_policy_observed | `drop_oldest` |
| drop_frame_count_max | 1011-1048 |
| drop_frame_rate_max | 0.997567-0.997743 |
| trace_status | degraded due to frame_id gaps |
| quality_status | `quality_threshold_fail` for all 5 sequences |
| quality_evidence_status | invalid_for_labeled_quality_due_to_frame_drops |
| next required run | rebuild with `jetson_tensorrt_bdd100k_quality.yaml`, `TRACE_FAIL_ON_GAPS=1`, `SAVE_OUTPUT_VIDEO=0` |

| sequence_id | raw_frames | fps_estimated | p95_latency_ms | p99_latency_ms | drop_frame_count_max | drop_frame_rate_max | overall_ap50_weighted | overall_recall | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `02344f0c-d5d916ff` | 187 | 30.0349 | 105.3882 | 133.5483 | 1017 | 0.997573 | 0.020949 | 0.021170 | excluded_from_labeled_quality |
| `012a9c41-692c9f06` | 166 | 30.0149 | 121.4065 | 154.6806 | 1041 | 0.997630 | 0.055209 | 0.053223 | excluded_from_labeled_quality |
| `01af2f91-3eacda83` | 161 | 30.0462 | 129.6680 | 148.3392 | 1043 | 0.997625 | 0.014493 | 0.015833 | excluded_from_labeled_quality |
| `010fc651-19922861` | 191 | 29.8399 | 106.5250 | 120.4218 | 1011 | 0.997567 | 0.047672 | 0.050662 | excluded_from_labeled_quality |
| `02097021-05dcbf23` | 163 | 30.1281 | 113.7792 | 159.5954 | 1048 | 0.997743 | 0.084003 | 0.080792 | excluded_from_labeled_quality |

排除原因：BDD 标签帧是源视频帧号 `0, 6, 12, ...`；本轮第一段 raw 只有 187 帧，而 raw / label frame_id 交集只有 25 个标注帧，trace check 出现大量 frame_id gaps。该 AP / recall 主要反映队列丢帧，不反映模型或 TensorRT wrapper 的有效检测质量。
本报告当前包含手工同步分析和 03I 汇总目标表。最终性能表只使用通过 schema 校验、能追溯 run 记录、输入源、后端 artifact、runtime 日志和 monitor 日志的最新有效 run。
Jetson TensorRT 的项目三执行入口已完成，BDD100K no-drop 质量诊断链路、fixed-input alignment 和前后处理一致性复核也已收口。当前结论明确为“COCO->BDD 域差 / 未微调未重训练”，故本次 BDD100K 任务级质量验证失败，但不影响项目三主线；后续不再继续追加同类 BDD 诊断 rerun，主线回到正式 `600` 秒 runtime benchmark 和 stability。最终有效表格必须由 `benchmark/raw/03_video_pipeline/jetson_8gb/*.jsonl`、`benchmark/processed/03_video_pipeline/*.csv`、`logs/runtime/03_video_pipeline/jetson_8gb/*.log` 和 `logs/monitor/03_video_pipeline/jetson_8gb/*_tegrastats.log` 聚合。
## Jetson TensorRT 待执行项

| item | path / value | status |
|---|---|---|
| mainline backend | TensorRT INT8 PTQ | ready |
| backend artifact | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` | ready |
| artifact SHA256 | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` | ready |
| active environment baseline | `20260609_jetson_8gb_env_baseline` inherited from project 2 | ready |
| upstream environment baseline | `20260604_jetson_8gb_env_baseline` from project 1 | ready |
| board config | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | ready |
| model config | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | ready |
| low-confidence model config | `projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml` | executed_quality_still_fail |
| ultra-low-confidence diag config | `projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml` | executed_quality_still_fail |
| pipeline config | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml` | ready |
| single-thread config | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_single_thread.yaml` | ready |
| stream manifest | `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` | ready |
| labeled video stream manifest | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | ready |
| build command | `RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh` | ready |
| runtime command | `RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | ready |
| BDD mini batch command | `RUN_PREFIX=<run_prefix> bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh` | ready |
| stability command | `TIER=<tier> bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | ready |
| raw result | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | runtime600_mainline_available |
| runtime log | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` | runtime600_mainline_path_recorded_not_synced_locally |
| monitor log | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` | runtime600_mainline_path_recorded_not_synced_locally |
| processed summary | `benchmark/processed/03_video_pipeline/<run_id>_summary.csv` | runtime600_mainline_available_local_rebuilt |

## Jetson Mainline Next Step

`20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` 已经执行完成，但当前不能直接作为 03D 正式 `pass` 结论。原因有三点：

- 本地重建后的 `summary / schema_check / trace_check / prepost_consistency` 已可确认该 run 的 pipeline 能持续运行约 `596s`。
- 这次 raw 明确记录的实际 artifact 是 `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_fp16.engine`，而不是 03D 主线规定的 INT8 PTQ engine。
- 本地尚未同步到对应 `runtime_log`、`monitor_log` 和 `runs/<run_id>/outputs/`，且 `trace_fail_on_gaps=0` 下 trace 结果为 `degraded`，存在大量 frame gap。

因此，Jetson 主线下一步应按下面顺序继续，而不是直接把这次 run 写成主线完成：

| order | action | command | expected evidence |
|---:|---|---|---|
| 1 | 核对这次 `runtime600_mainline` 的实际 artifact 与证据链 | 优先同步 `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline.log`、`logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_tegrastats.log`、`projects/03_video_pipeline/runs/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline/` | 确认为什么 raw 记录为 `fp16` / `yolo11n_640_jetson_trt_fp16.engine` |
| 2 | 重新执行 03D 正式 INT8 TensorRT C++ pipeline `600s` runtime benchmark | `cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab && export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline && RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_runtime600_q8_mainline PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml BOARD_CONFIG=projects/03_video_pipeline/configs/boards/jetson_8gb.yaml bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl`、`benchmark/processed/03_video_pipeline/<run_id>_summary.csv`、`logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log`、`logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` |
| 3 | 03H stability smoke `600s` | `cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab && export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline && RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_stability_smoke TIER=smoke bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh` | stability raw/log/monitor，供 `stability_report.md` 汇总 |

说明：
- 第 1 步对应的是历史无标注旧 run，只用于核对既有 artifact 与日志，不得重跑为当前基线；当前新 run 使用 `bdd100k_mot_mini_v1`。
- 第 2 步脚本当前默认使用 `video_set_runtime_v1`，即固定 20 条 BDD100K playlist 的 paced runtime 语义；旧的 `video_long_loop_001` 单文件循环口径只保留作历史对照或回退调试。
- 主线实时配置已把全局 `queue_capacity` 从 `4` 调整到 `8`，同时继续保留 `drop_oldest`，目标是减少极端丢帧，但仍优先保持“最新帧优先”的实时性方向。

## Jetson Runtime600 Mainline 2026-06-16

本节记录 `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` 的当前本地可验证结果。终端输出显示脚本完成，且 `prepost_consistency` 返回 `status=pass`；本地已同步到 raw，并基于仓库脚本重建了 `schema_check / trace_check / summary / prepost_consistency`。结论是：这次 run 证明 Jetson C++ 多线程 pipeline 在 `drop_oldest` 主线配置下可以持续运行约 `596s`，但当前不能作为 03D INT8 主线正式结论，因为实际记录 artifact 为 FP16，且 trace 大量 gap、runtime/monitor 日志尚未本地同步。

该 run 的 `video_short_001` 输入属于无人工标注历史证据，仅保留事实记录；后续复跑必须改用 `bdd100k_mot_mini_v1`，其性能结果也不得冒充 BDD100K 质量结果。

| item | value |
|---|---|
| run_id | `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` |
| environment_baseline_id | `20260609_jetson_8gb_env_baseline` |
| input_source_id | `video_short_001` |
| pipeline_mode | `backend_pipeline` |
| queue_policy / queue_capacity | `drop_oldest` / `4` |
| prepost_consistency | `pass` |
| raw schema | `pass` |
| trace status | `degraded` |
| trace frame_id_gaps | `26573` |
| actual wall duration | `596.0 sec` |
| actual output FPS | `44.7836` |
| p50 / p90 / p95 / p99 latency | `51.1158 / 58.5714 / 63.4315 / 74.1949 ms` |
| drop_frame_count_max | `137352` |
| drop_frame_rate_max | `0.999057` |
| cpu_fallback | `false` |
| actual backend artifact | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_fp16.engine` |
| actual precision_or_quantization | `fp16` |
| runtime_log local sync | `not_synced_locally` |
| monitor_log local sync | `not_synced_locally` |
| local status | `degraded_runtime_pass_artifact_mismatch` |

补充说明：

- 这次本地还顺手修正了 `projects/03_video_pipeline/scripts/benchmark/aggregate_pipeline_benchmark.py` 的时长/FPS 聚合口径。旧逻辑按 `input_fps` 估算时长，会把这次 run 错算成 `2669.1 sec / 10 FPS`；现已改为优先使用 `output_ts` 计算真实持续时长。
- 由于 `TRACE_FAIL_ON_GAPS=0`，脚本本身没有因为 frame gap 退出；但从报告口径看，这次 trace 只能记为 `degraded`，不能写成 `pass_no_frame_gaps`。
- 由于实际 artifact 与 03D 主线规定的 INT8 PTQ 不一致，这次 run 只能先作为“FP16 + drop_oldest 主线配置已跑通”的运行证据，不能直接写成 “Jetson INT8 主线已完成”。

## Jetson runtime benchmark 通过条件
- `raw result` 通过 `benchmark/schemas/video_pipeline_raw_schema.yaml`
- 每帧包含 `capture/decode/preprocess/inference/postprocess/output/end_to_end_latency_ms`
- `execution_provider=TensorRT-GPU` 或实际 DLA 路径，且有 TensorRT runtime log 和 `tegrastats` 证据
- `cpu_fallback=false`；无法证明时状态为 `not_verified`
- p50 / p90 / p95 / p99、FPS、丢帧率、队列长度必须从项目三 raw result 聚合，不能引用项目一 / 二单模型数字
- 模型 artifact、TensorRT wrapper、前处理、后处理或输出解析变化时，必须记录 fixed-input 对齐和任务级质量对齐；只完成性能 benchmark 不能把质量状态写成 `pass`
## 最新有效 run 选择

| group_key | selected_run_id | status | excluded_runs_path | selection_reason |
|---|---|---|---|---|
| `jetson_8gb/tensorrt/video_set_runtime_v1/backend_pipeline/drop_oldest/int8_ptq/runtime600` | `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout` | `selected_default_runtime_baseline` | `benchmark/processed/03_video_pipeline/excluded_runs.md` | 最新 INT8、playlist-paced、`SAVE_OUTPUT_VIDEO=0` 的 600 秒主线；schema / prepost / runtime / monitor 已齐 |
| `jetson_8gb/tensorrt/video_set_runtime_v1/backend_pipeline/drop_newest/int8_ptq/runtime600` | `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_drop_newest_v2` | `selected_queue_policy_contrast` | `benchmark/processed/03_video_pipeline/excluded_runs.md` | override 传参链路修复后的有效 `drop_newest` 对照 |
| `jetson_8gb/tensorrt/video_set_runtime_v1/backend_pipeline/block_with_timeout/int8_ptq/runtime600` | `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_block_timeout_v2` | `selected_queue_policy_contrast` | `benchmark/processed/03_video_pipeline/excluded_runs.md` | override 传参链路修复后的有效 `block_with_timeout(33ms)` 对照 |
| `jetson_8gb/tensorrt/video_set_stability_v1/backend_pipeline/drop_oldest/int8_ptq/short_sustained` | `20260617_jetson_8gb_yolo11n_tensorrt_stability_short_playlist80_noout` | `selected_stability_short_baseline` | `benchmark/processed/03_video_pipeline/excluded_runs.md` | 30 分钟 noout 基线，已完成 `1797 / 1800 sec` |
| `jetson_8gb/tensorrt/video_set_stability_v1/backend_pipeline/drop_oldest/int8_ptq/acceptance_sustained` | `20260617_jetson_8gb_yolo11n_tensorrt_stability_acceptance_playlist80_noout` | `selected_stability_acceptance_baseline` | `benchmark/processed/03_video_pipeline/excluded_runs.md` | 2 小时 noout 基线，已完成 `7196 / 7200 sec` |

## Jetson Benchmark 覆盖矩阵

| spec | run 类型 | target | backend_runtime | precision | pipeline_mode | input_source_id | duration_sec | required evidence | status |
|---|---|---|---|---|---|---|---:|---|---|
| 03A | single-thread minimal demo | jetson_8gb | tensorrt | int8_ptq | single_thread | video_set_runtime_v1 | 600 | `20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo`；`trace/schema/prepost` 全 pass，`frame_id_gaps=0` | pass_board_verified |
| 03B | multithread pipeline | jetson_8gb | tensorrt | int8_ptq | backend_pipeline | video_set_runtime_v1 | 600 | `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline`；`30.13 FPS`、零 gap、零丢帧、可与 03A 显式对照 | pass_board_verified |
| 03C | queue policy `drop_oldest` | jetson_8gb | tensorrt | int8_ptq | queue_buffer | video_set_runtime_v1 | 600 | `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout` | executed_via_playlist20_noout |
| 03C | queue policy `drop_newest` | jetson_8gb | tensorrt | int8_ptq | queue_buffer | video_set_runtime_v1 | 600 | `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_drop_newest_v2` | executed_via_drop_newest_v2 |
| 03C | queue policy `block_with_timeout` | jetson_8gb | tensorrt | int8_ptq | queue_buffer | video_set_runtime_v1 | 600 | `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_block_timeout_v2` | executed_via_block_timeout_v2 |
| 03C | buffer reuse A/B | jetson_8gb | tensorrt | int8_ptq | queue_buffer | video_set_runtime_v1 | 600 | `20260622_jetson_8gb_yolo11n_tensorrt_bufferreuse_on_ab600` / `..._off_ab600` 与 `20260622_jetson_8gb_yolo11n_tensorrt_bufferreuse_ab600.md`；结论 `buffer_reuse_beneficial` | pass_board_verified |
| 03D | TensorRT C++ pipeline | jetson_8gb | tensorrt | int8_ptq | backend_pipeline | video file + realtime source | 600 | INT8 + TensorRT GPU + 600 秒 video-file 主线已验证；但 `20260623` GUI 预览已证明旧版 `fixed_10bit` 会把 IMX219 画面拉成近乎纯白，因此 `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 目前只能保留为吞吐侧历史证据，正式 live-source 需在修正后重验 | int8_video_file_verified_imx219_visual_validity_pending_recheck |

## Runtime Summary

| run_id | target | backend_runtime | execution_provider | loader_api | precision | input_source_id | pipeline_mode | queue_policy | queue_capacity | fps_avg | latency_p50_ms | latency_p90_ms | latency_p95_ms | latency_p99_ms | drop_frame_rate | cpu_fallback | status |
|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | int8_ptq | `imx219_csi_001` | backend_pipeline | drop_oldest | 8 | 47.6711 | 40.3564 | 41.9747 | 43.1277 | 45.5745 | 0.0 | false | throughput_only_pending_visual_validity_recheck |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | int8_ptq | `video_set_runtime_v1` | single_thread | none | 0 | 25.0817 | 40.0760 | 42.1740 | 42.6840 | 48.0968 | 0.0 | false | runtime_pass_all_postchecks_pass |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | int8_ptq | `video_set_runtime_v1` | backend_pipeline | drop_oldest | 8 | 30.1302 | 60.1854 | 62.0441 | 63.7580 | 66.1065 | 0.0 | false | runtime_pass_all_postchecks_pass |
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | fp16 | `video_short_001` | backend_pipeline | drop_oldest | 4 | 44.7836 | 51.1158 | 58.5714 | 63.4315 | 74.1949 | 0.999057 | false | historical_unlabeled_degraded_artifact_mismatch |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | fp16 | `bdd100k_mot_mini_v1_02344f0c-d5d916ff` | backend_pipeline | block | 32 | 30.0349 | 35.8383 | 46.4251 | 51.7791 | 81.6952 | 0.0 | false | runtime_pass_quality_fail |

## Stage Latency

| run_id | capture_p50_ms | capture_p95_ms | capture_p99_ms | decode_p50_ms | decode_p95_ms | preprocess_p50_ms | preprocess_p95_ms | inference_p50_ms | inference_p95_ms | postprocess_p50_ms | postprocess_p95_ms | output_p50_ms | output_p95_ms | e2e_p95_ms | e2e_p99_ms | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` | 20.8059 | 22.5250 | 23.0985 | 0.0 | 0.0 | 2.3446 | 2.9193 | 12.1605 | 12.7183 | 4.3576 | 6.3617 | 0.0368 | 0.0593 | 43.1277 | 45.5745 | trace_pass |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo` | 7.0413 | 8.8150 | 11.2011 | 0.0 | 0.0 | 2.4906 | 3.2718 | 25.2472 | 25.8500 | 5.4990 | 5.7996 | 0.0456 | 0.0664 | 42.6840 | 48.0968 | trace_pass |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` | 33.2902 | 33.3521 | 34.9512 | 0.0 | 0.0 | 2.9794 | 6.7356 | 18.1681 | 18.7209 | 5.7601 | 6.5583 | 0.0380 | 0.0655 | 63.7580 | 66.1065 | trace_pass |
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | 3.4333 | 4.7056 | 10.7128 | 0.0 | 0.0 | 3.9768 | 8.5387 | 18.0730 | 20.6112 | 3.7752 | 5.9637 | 20.4743 | 30.6102 | 63.4315 | 74.1949 | trace_degraded |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | 9.1902 | 24.8191 | 26.3780 | 0.0 | 0.0 | 5.9192 | 13.7201 | 13.1898 | 18.2041 | 3.9631 | 9.1677 | 0.0695 | 0.1120 | 51.7791 | 81.6952 | runtime_pass |

## Queue / Buffer

| run_id | queue_policy | queue_capacity | buffer_reuse | buffer_pool_size | queue_capture_p95 | queue_preprocess_p95 | queue_infer_p95 | queue_postprocess_p95 | queue_max | drop_frame_count | drop_frame_rate | dropped_frame_reason | memory_growth_mb_per_hour | status |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` | drop_oldest | 8 | true | 8 | 0.0 | 0.0 | 0.0 | 0.0 | 5 | 0 | 0.0 |  | 927.5362 | pass_multithread_baseline |
| `20260622_jetson_8gb_yolo11n_tensorrt_bufferreuse_on_ab600` | drop_oldest | 8 | true | 8 | 0.0 | 0.0 | 0.0 | 0.0 | 5 | 0 | 0.0 | none | 1333.3333 | pass_buffer_reuse_on |
| `20260622_jetson_8gb_yolo11n_tensorrt_bufferreuse_off_ab600` | drop_oldest | 8 | false | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 5 | 3 | 0.000166 | queue_full | 1194.2029 | pass_buffer_reuse_off |
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | drop_oldest | 4 | true | 8 | 4.0 | 4.0 | 0.0 | 4.0 | 4 | 137352 | 0.999057 | queue_full |  | high_drop_realtime_mode |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | block | 32 | true | 32 | 32.0 | 32.0 | 0.0 | 0.0 | 32 | 0 | 0.0 |  | -75.0 | no_drop_pass |

## Resource / Accelerator

| run_id | monitor_log_path | memory_mb_peak | memory_growth_mb_per_hour | temperature_c_peak | power_mode | power_w_avg | power_w_peak | cpu_util_avg | gpu_util_avg | throttle_events | runtime_evidence_path | accelerator_evidence_path | status |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|
| `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` | `logs/monitor/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5_tegrastats.log` | 2539.0 | 2473.1942 | 59.0 | not_recorded |  |  | 42.0881 | 46.5609 | 624 | `logs/runtime/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5.log` | same_as_monitor_log | monitor_available |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo` | `logs/monitor/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo_tegrastats.log` | 3306.0 | 5822.5080 | 57.0 | not_recorded |  |  | 27.8909 | 44.0803 | 623 | `logs/runtime/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo.log` | same_as_monitor_log | monitor_available |
| `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` | `logs/monitor/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline_tegrastats.log` | 3484.0 | 927.5362 | 59.5 | not_recorded |  |  | 29.0598 | 42.8280 | 622 | `logs/runtime/03_video_pipeline/jetson_8gb/20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline.log` | same_as_monitor_log | monitor_available |
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_tegrastats.log` |  |  |  | not_recorded |  |  |  |  |  | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_tegrastats.log` | paths_recorded_not_synced_locally |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_tegrastats.log` | 2424.0 | -75.0 | 52.5 | not_recorded |  |  | 48.0556 | 47.5333 | 30 | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_tegrastats.log` | monitor_available_runtime_log_not_synced |

## Artifact Matrix

| role | backend_artifact_path | backend_artifact_sha256 | source_project | source_quality_status | project3_use | project3_status |
|---|---|---|---|---|---|---|
| mainline | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` | `02_quantization` | pass | Jetson INT8 PTQ pipeline 主线 | ready |

## Quality Gate

| run_id | change_type | baseline_artifact | current_artifact | fixed_input_alignment_ref | fixed_input_alignment_status | task_level_quality_ref | task_level_quality_status | quality_alignment_exemption | output_valid | frame_trace_status | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | backend_runtime_pipeline_integration | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_fp16.engine` baseline run | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_fp16.engine` current pipeline run | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_fixed_input_alignment.md` | pass | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_bdd100k_mot_quality.md` | quality_threshold_fail |  | 1.0 | pass_no_frame_gaps | fail |

## Historical Unlabeled Fixed-input Evidence

`video_short_001` 没有人工标注，本节只保存已发生的实现诊断证据，不是当前执行入口，也不能计算正式 AP50。当前正式质量数据集是 `bdd100k_mot_mini_v1`；两者的结果不得混用。

| run_id | input_source_id | source_video | source_sha256 | alignment_manifest | selected_frames | baseline_raw_result | current_raw_result | alignment_report | alignment_details | status |
|---|---|---|---|---|---:|---|---|---|---|---|
| `20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment` | `video_short_001` | `data/videos/video_fixed_v1/video_short_001.avi` | `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf` | `data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json` | 80 | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_project1_baseline_video_short_001.jsonl` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_project3_current.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_fixed_input_alignment.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_fixed_input_alignment.csv` | historical_unlabeled_invalid_first_attempt |
| `20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix` | `video_short_001` | `data/videos/video_fixed_v1/video_short_001.avi` | `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf` | `data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json` | 80 | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_project1_baseline_video_short_001.jsonl` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_project3_current.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_fixed_input_alignment.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_fixed_input_alignment_nodropfix_fixed_input_alignment.csv` | historical_unlabeled_diagnostic_pass |
## Labeled Video Quality Evidence

`bdd100k_mot_mini_v1` is the task-level video quality dataset. It is prepared from BDD100K MOT under a 5 GB storage budget. A `pass` here requires generated video hashes, label hashes, raw pipeline predictions with `detections[]`, and per-class / overall AP50, precision, recall and F1 reports.

| run_id | dataset_id | quality_manifest | sequence_count | labeled_frames | prepared_video_dir | prepared_video_sha256_manifest | labels_dir | label_sha256_manifest | metric | quality_report | quality_details | quality_summary | status |
|---|---|---|---:|---:|---|---|---|---|---|---|---|---|---|
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5` | `bdd100k_mot_mini_v1` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | 5 / 80 | 1013 | `data/videos/bdd100k_mot_mini_v1/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | `data/validation/bdd100k_mot_mini_v1/labels/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | AP50=0.341615, precision=0.374240, recall=0.416315, F1=0.394158 | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_*_bdd100k_mot_quality.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_*_bdd100k_mot_quality.csv` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_*_bdd100k_mot_quality_summary.csv` | 1_pass_4_quality_threshold_fail |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5` | `bdd100k_mot_mini_v1` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | 5 / 80 | 1013 | `data/videos/bdd100k_mot_mini_v1/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | `data/validation/bdd100k_mot_mini_v1/labels/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | AP50=0.321903, precision=0.493344, recall=0.372144, F1=0.424258 | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_*_bdd100k_mot_quality.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_*_bdd100k_mot_quality.csv` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_*_bdd100k_mot_quality_summary.csv` | 1_pass_4_quality_threshold_fail |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5` | `bdd100k_mot_mini_v1` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | 5 / 80 | 1013 | `data/videos/bdd100k_mot_mini_v1/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | `data/validation/bdd100k_mot_mini_v1/labels/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | AP50=0.280400, precision=0.678323, recall=0.304905, F1=0.420704, prepost_consistency=5_pass | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_*_bdd100k_mot_quality.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_*_bdd100k_mot_quality.csv` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_*_bdd100k_mot_quality_summary.csv` | 1_pass_4_quality_threshold_fail_terminal_reconstructed |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5` | `bdd100k_mot_mini_v1` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | 5 / 80 | 1013 | `data/videos/bdd100k_mot_mini_v1/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | `data/validation/bdd100k_mot_mini_v1/labels/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | AP50=0.280182, precision=0.684701, recall=0.304832, F1=0.421853 | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_*_bdd100k_mot_quality.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_*_bdd100k_mot_quality.csv` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit5_*_bdd100k_mot_quality_summary.csv` | 1_pass_4_quality_threshold_fail |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | `bdd100k_mot_mini_v1` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | 1 / 80 | 202 | `data/videos/bdd100k_mot_mini_v1/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | `data/validation/bdd100k_mot_mini_v1/labels/` | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` | AP50=0.136443, precision=0.554014, recall=0.164363, F1=0.253515 | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_bdd100k_mot_quality.md` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_bdd100k_mot_quality.csv` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_bdd100k_mot_quality_summary.csv` | quality_threshold_fail |

## CPU Fallback

| run_id | backend_runtime | execution_provider | loader_api | backend_artifact_path | runtime_evidence_path | accelerator_evidence_path | cpu_fallback | fallback_reason | status |
|---|---|---|---|---|---|---|---|---|---|
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | tensorrt | TensorRT-GPU | TensorRT C++ API | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_fp16.engine` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_tegrastats.log` | false |  | raw_recorded_logs_not_synced_locally |
|  | tensorrt | TensorRT-GPU | TensorRT C++ API | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` |  |  |  |  | not_executed |

## Reproducibility

| run_id | environment_baseline_id | pipeline_config | stream_config | model_config | board_config | command | raw_result_path | processed_result_path | runtime_log_path | monitor_log_path | related_troubleshooting_id | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` | `20260609_jetson_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml` | `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | `RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_runtime600_mainline bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_summary.csv` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline_tegrastats.log` | `P3-TRB-20260616-004` | degraded_runtime_pass_artifact_mismatch |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5` | `20260609_jetson_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml` | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml` | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | `RUN_PREFIX=20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5 PYTHON_BIN=python3 MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml CONFIDENCE_MIN=0.05 LIMIT=5 bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_<sequence_id>.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_<sequence_id>_summary.csv` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_<sequence_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5_<sequence_id>_tegrastats.log` | `P3-TRB-20260616-001` | runtime_pass_quality_fail |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5` | `20260609_jetson_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml` | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml` | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | `RUN_PREFIX=20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5 PYTHON_BIN=python3 MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml CONFIDENCE_MIN=0.10 LIMIT=5 bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_<sequence_id>.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_<sequence_id>_summary.csv` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_<sequence_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5_<sequence_id>_tegrastats.log` | `P3-TRB-20260616-001` | runtime_pass_quality_fail |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5` | `20260609_jetson_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml` | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | `RUN_PREFIX=20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5 PYTHON_BIN=python3 LIMIT=5 bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_<sequence_id>.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_<sequence_id>_summary.csv` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_<sequence_id>.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_prepostfix_limit5_<sequence_id>_tegrastats.log` | `P3-TRB-20260616-001`, `P3-TRB-20260616-002` | runtime_pass_quality_fail_prepost_verified_terminal |
| `20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff` | `20260609_jetson_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml` | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | `projects/03_video_pipeline/configs/boards/jetson_8gb.yaml` | `RUN_PREFIX=20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1 PYTHON_BIN=python3 LIMIT=1 bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh` | `benchmark/raw/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff.jsonl` | `benchmark/processed/03_video_pipeline/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_summary.csv` | `logs/runtime/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff.log` | `logs/monitor/03_video_pipeline/jetson_8gb/20260616_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_limit1_02344f0c-d5d916ff_tegrastats.log` |  | runtime_pass_quality_fail |

## 辅助结果

engine_only、runtime_only 或工具级初测只能作为辅助说明，不能替代完整 pipeline raw result。
| run_id | scope | target | backend_runtime | metric | value | evidence_path | notes |
|---|---|---|---|---|---:|---|---|
|  | auxiliary | jetson_8gb | tensorrt |  |  |  |  |

## RK3588 RKNN 03E Benchmark Plan

本节是 RK3588 03E 的正式填表位置。当前已经补齐 C++ RKNN wrapper、YOLO11 official split-head DFL 解码、配置和执行脚本，并已在 RK3588 板端完成 600 秒实时 runtime、COCO2017 artifact 复检和 BDD100K full80 带标注质量评估。对应 frame-level raw、processed summary、schema/trace、runtime log 和 RKNPU monitor log 均已同步到当前工作区。项目二单模型 benchmark 只作为 artifact 来源证据，不替代本节的 C++ video pipeline benchmark。

### RK3588 Source Baseline

| item | value |
|---|---|
| inherited_environment_baseline_id | `20260611_rk3588_8gb_env_baseline` |
| source_project2_run | `20260611_rk3588_8gb_yolo11n_rknnopt_int8_int8_ptq_calib500_benchmark` |
| source_project2_backend | RKNN / RKNPU |
| source_project2_model | `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn` |
| source_project2_sha256 | `ced0b0d4feea9b6df7326441323af5c99ad0a9e1af794434716ea581b1dc9de5` |
| selected_project3_sha256 | `40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c` |
| current_workspace_and_board_sha256 | `40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c` |
| model_hash_status | `project3_selected_hash_aligned_full_coco2017_pass` |
| source_project2_quality | `mAP50_95=0.3814960637396267`, `accuracy_drop=0.00500393626`, `pass` |
| source_project2_runtime | `p50=53.1932 ms`, `p95=57.3990 ms`, `FPS=18.6151` |
| project3_rknn_postprocess | C++ `DecodeRknnOfficialYolo11`，9 输出 split-head + DFL + NMS |
| project3_status | `runtime_pass_mixed_8h_camera4h_video4h_realtime_with_negligible_drop_bdd100k_quality_fail` |

### RK3588 Runtime Summary

| run_id | target | backend_runtime | execution_provider | input_source_id | pipeline_mode | queue_policy | FPS | p50_latency_ms | p90_latency_ms | p95_latency_ms | p99_latency_ms | drop_frame_rate | CPU fallback | status |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | rk3588_8gb | rknn | RKNPU | `video_set_runtime_v1` | backend_pipeline | drop_oldest | 23.7238 | 91.4538 | 107.5226 | 109.0495 | 111.4993 | 0.209996 | false | degraded_raw_hash_metadata_mismatch_and_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120` | rk3588_8gb | rknn | RKNPU | `video_set_runtime_v1` | backend_pipeline | drop_oldest | 23.3917 | 92.5728 | 108.1598 | 109.8213 | 112.9087 | 0.221359 | false | baseline_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120` | rk3588_8gb | rknn | RKNPU | `video_set_runtime_v1` | backend_pipeline | drop_oldest | 30.0417 | 103.9390 | 117.5812 | 119.6984 | 125.2233 | 0.000000 | false | realtime_target_pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | rk3588_8gb | rknn | RKNPU | `video_set_runtime_v1` | backend_pipeline | drop_oldest | 30.0800 | 103.3005 | 118.1683 | 120.0783 | 124.8260 | 0.000000 | false | runtime600_pass_quality_alignment_pending |
| `20260621_rk3588_8gb_yolo11n_rknn_astra_openni_nonsudo_smoke` | rk3588_8gb | rknn | RKNPU | `astra_s_openni_001` | backend_pipeline | drop_oldest | 29.6500 | 101.6480 |  | 120.6580 |  | 0.000000 | false | historical_smoke_pass |
| `20260622_rk3588_8gb_yolo11n_rknn_astra_openni_nonsudo_smoke_v2` | rk3588_8gb | rknn | RKNPU | `astra_s_openni_001` | backend_pipeline | drop_oldest | 29.6033 | 101.8440 | 118.6470 | 122.0018 | 127.4686 | 0.000000 | false | live_source_smoke_pass |
| `20260617_rk3588_8gb_yolo11n_rknn_rtsp` | rk3588_8gb | rknn | RKNPU | `rtsp_stream_001` | backend_pipeline | drop_oldest |  |  |  |  |  |  |  | not_executed |

### RK3588 Astra S Live Source Validation

RK3588 当前正式摄像头 live source 已从泛化 `usb_camera_001` 收敛为 `astra_s_openni_001`。实现路径不是 V4L2 `/dev/video0`，而是 OpenNI2 + `liborbbec.so`：应用通过 `input_source_type=openni_camera`、device selector `2bc5/0402` 直接打开 Astra S color stream，再把 RGB888 帧送入现有 RKNN C++ pipeline。这样做的原因很直接：板端已具备 Astra S 的 OpenNI2 runtime 和驱动，但没有稳定可用的 `/dev/video0` UVC 节点；如果继续沿用旧的 `usb_camera_001` 假设，live-source、断流和 camera service 证据都无法成立。

| run_id | source | open_mode | inference_workers | source_fps_basis | fps_estimated | latency_p50_ms | latency_p95_ms | capture_p50_ms | preprocess_p50_ms | inference_p50_ms | postprocess_p50_ms | drop_frame_count_total_estimated | output_valid_rate | memory_mb_peak | temperature_c_peak | status |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260621_rk3588_8gb_yolo11n_rknn_astra_openni_nonsudo_smoke` | `astra_s_openni_001` | OpenNI2 selector `2bc5/0402` | 3 | openni_stream_mode `640x480@30` | 29.6500 | 101.6480 | 120.6580 | 34.8860 | 2.5281 | 58.3728 | 5.6643 | 0 | 1.0000 | 215.11 | 51.77 | historical_pass |
| `20260622_rk3588_8gb_yolo11n_rknn_astra_openni_nonsudo_smoke_v2` | `astra_s_openni_001` | OpenNI2 selector `2bc5/0402` | 3 | openni_stream_mode `640x480@30` | 29.6033 | 101.8440 | 122.0018 | 34.8700 | 2.5167 | 58.6752 | 5.2496 | 0 | 1.0000 | 224.95 | 51.77 | pass |

板端 probe 结果确认 Astra S 可读的传感器为 `color/depth/ir`，其中 color 默认模式为 `640x480 RGB888 @ 30 FPS`。正式 smoke 使用非 root 账号直接运行，说明 udev 权限已经闭环；若缺少 `/etc/udev/rules.d/99-orbbec-astra.rules`，同一路径在板端会以 `Access denied (insufficient permissions)` 失败。

| run_id | check_type | input_source_id | expected_behavior | observed_result | status |
|---|---|---|---|---|---|
| `20260622_rk3588_8gb_yolo11n_rknn_astra_disconnect_appfault_v2` | input_disconnect | `astra_s_openni_001` | 应用记录 `FAULT_INJECTED_DISCONNECT` 和 `INPUT_DISCONNECTED`，并以 exit `11` 清晰退出 | 历史回归样本：exit `139`，仅保留问题追溯 | historical_fail |
| `20260622_rk3588_8gb_yolo11n_rknn_astra_disconnect_appfault_v3` | input_disconnect | `astra_s_openni_001` | 应用记录 `FAULT_INJECTED_DISCONNECT` 和 `INPUT_DISCONNECTED`，并以 exit `11` 清晰退出 | 已验证，wrapper `disconnect_status=pass` | pass |
| `20260622_rk3588_8gb_astra_camera_systemd_service_test_v2` | camera systemd lifecycle | `astra_s_openni_001` | `start/restart/stop = active/active/inactive` | 历史回归样本：`activating/activating/inactive`，仅保留问题追溯 | historical_fail |
| `20260622_rk3588_8gb_astra_camera_systemd_service_test_v3` | camera systemd lifecycle | `astra_s_openni_001` | `start/restart/stop = active/active/inactive` | 已验证 | pass |

因此，Astra S 当前已经满足 RK3588 在项目三里的 live-source 最低验收要求：真实采集、非 root 运行、断流清晰失败、camera service 生命周期可复现。它不替代 BDD100K playlist 的可复现 runtime/stability 数据集角色；两者在正式报告里必须并行保留。

更新说明：`2026-06-22` 的第一次复测曾出现 `disconnect v2 exit=139` 和 `camera service v2 = activating/activating/inactive`。这两条旧样本现在只保留给问题追溯；同日的 `disconnect v3` 与 `camera systemd service v3` 已重新通过，因此 Astra S live-source 当前可以恢复为闭环状态。

### RK3588 NPU Core Mask A/B

保持模型、视频、`drop_oldest`、queue capacity、pacing 和输出设置不变，只改变 RKNN core mask。正式比较先执行 120 秒 A/B，三核胜出且无本轮新增 RKNPU timeout 后，再执行 600 秒 clean runtime。

| run_id | core_mask | duration_sec | inference_p50_ms | inference_p95_ms | FPS | drop_rate | new_rknpu_timeout_count | status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `20260618_rk3588_8gb_yolo11n_rknn_core0_ab120` | `core0` | 120 | 43.1292 | 44.6689 | 22.9835 | 0.228571 | 0 | baseline |
| `20260618_rk3588_8gb_yolo11n_rknn_core012_ab120` | `0_1_2` | 120 | 43.4985 | 45.2455 | 23.0083 | 0.234119 | 0 | no_material_improvement |

结论：单 RKNN context 设置 `0_1_2` 相比 `core0` 仅提升 `0.1082%` FPS，推理 P50 反而增加 `0.8563%`，不能解决约 30 FPS 输入下的持续丢帧。实时优化转入三个独立 context 分别绑定 core 0/1/2 的并行 worker 路线。

### RK3588 Multi-context Realtime

| run_id | inference_workers | core_binding | duration_sec | FPS | inference_p50_ms | inference_p95_ms | drop_rate | frame_trace | RKNPU anomaly | status |
|---|---:|---|---:|---:|---:|---:|---:|---|---|---|
| `20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120` | 1 | `core0` | 120 | 23.3917 | 42.7544 | 44.2983 | 0.221359 | degraded: 788 gaps, 0 out-of-order | 0 | baseline_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120` | 3 | `core0,core1,core2` | 120 | 30.0417 | 56.8197 | 62.3937 | 0.000000 | pass: 0 gaps, 0 out-of-order | 0 | realtime_target_pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | 3 | `core0,core1,core2` | 600 | 30.0800 | 56.7945 | 61.9567 | 0.000000 | pass: 0 gaps, 0 out-of-order | 0 | runtime600_pass |

三 context 方案相对单 context 的 FPS 提升 `28.4289%`，总体丢帧率下降 `22.1359` 个百分点，并完整保留 `frame_id=0..3604`。三个 worker 的 core 绑定日志和 raw 元数据均通过核验，顺序屏障使 `frame_id_out_of_order=0`。代价是资源竞争下单帧 inference P50 增加 `32.899%`，端到端 P95 增加 `8.992%`；因此该方案是吞吐优化，不是单帧延迟优化。120 秒实时门通过，但仍需 600 秒 clean runtime 和后续稳定性测试。

### RK3588 Artifact COCO2017 Recheck

该表验证项目三选定的 `40bce507...` RKNN artifact 是否达到项目二同口径质量门。必须重新执行完整 5000 张 val2017，不能复用 `ced0b0d4...` 的历史 COCOeval JSON。

| run_id | artifact_sha256 | images | mAP50_95 | mAP50 | mAP75 | accuracy_drop_vs_fp32 | delta_vs_ced0 | threshold | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `20260618_rk3588_8gb_yolo11n_rknn_40bce_coco2017_recheck` | `40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c` | 5000 | 0.381496063740 | 0.536142820425 | 0.416985806384 | 0.005003936260 | 0.000000000000 | `accuracy_drop <= 0.03` | pass |

### RK3588 Stage Latency

| run_id | capture_p50_ms | capture_p95_ms | capture_p99_ms | decode_p50_ms | decode_p95_ms | decode_p99_ms | preprocess_p50_ms | preprocess_p95_ms | preprocess_p99_ms | inference_p50_ms | inference_p95_ms | inference_p99_ms | postprocess_p50_ms | postprocess_p95_ms | postprocess_p99_ms | output_p50_ms | output_p95_ms | output_p99_ms | end_to_end_p95_ms | end_to_end_p99_ms | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | 33.3105 | 33.4630 | 34.9386 | 0.0000 | 0.0000 | 0.0000 | 8.5652 | 10.6715 | 13.9536 | 42.0705 | 43.6218 | 46.6158 | 6.2113 | 24.2288 | 24.5957 | 0.0583 | 0.1015 | 0.1495 | 109.0495 | 111.4993 | executed_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120` | 33.3102 | 33.4543 | 34.9665 | 0.0000 | 0.0000 | 0.0000 | 8.5733 | 10.2560 | 12.9622 | 42.7544 | 44.2983 | 47.3851 | 6.4168 | 24.7009 | 25.0192 | 0.0612 | 0.1026 | 0.1391 | 109.8213 | 112.9087 | baseline_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120` | 33.3131 | 33.4201 | 34.9697 | 0.0000 | 0.0000 | 0.0000 | 6.6443 | 7.7769 | 10.3822 | 56.8197 | 62.3937 | 69.1283 | 4.8614 | 21.6402 | 22.0610 | 0.0391 | 0.0641 | 0.0895 | 119.6984 | 125.2233 | realtime_target_pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | 33.3125 | 33.4210 | 34.9562 | 0.0000 | 0.0000 | 0.0000 | 6.4218 | 7.9405 | 11.5499 | 56.7945 | 61.9567 | 68.1328 | 4.8497 | 21.7400 | 22.2801 | 0.0385 | 0.0665 | 0.0948 | 120.0783 | 124.8260 | runtime600_pass |

### RK3588 Queue / Buffer

| run_id | queue_policy | queue_capacity | buffer_reuse | queue_capture_p95 | queue_capture_max | queue_preprocess_p95 | queue_preprocess_max | queue_infer_p95 | queue_infer_max | queue_postprocess_p95 | queue_postprocess_max | drop_count | drop_rate | dropped_frame_reason | memory_growth_mb_per_hour | status |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | drop_oldest | 8 | true | 0.0 | 2 | 8.0 | 8 | 0.0 | 0 | 0.0 | 0 | 3790 | 0.209996 | queue_full | not_recorded | executed_high_drop_rate |
| `20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120` | drop_oldest | 8 | true | 0.0 | 4 | 8.0 | 8 | 0.0 | 0 | 0.0 | 0 | 798 | 0.221359 | queue_full | not_recorded | baseline_high_drop |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120` | drop_oldest | 8 | true | 0.0 | 1 | 0.0 | 5 | 0.0 | 1 | 0.0 | 0 | 0 | 0.000000 | none | not_recorded | realtime_target_pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | drop_oldest | 8 | true | 0.0 | 3 | 0.0 | 8 | 0.0 | 2 | 0.0 | 0 | 0 | 0.000000 | none | 72.2559 | runtime600_pass_growth_requires_stability_recheck |
| `20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_on_ab600` | drop_oldest | 8 | true | 0.0 | 0 | 0.0 | 4 | 0.0 | 1 | 0.0 | 0 | 0 | 0.000000 | none | 77.0451 | pass_buffer_reuse_on |
| `20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_off_ab600` | drop_oldest | 8 | false | 0.0 | 0 | 0.0 | 4 | 0.0 | 1 | 0.0 | 0 | 0 | 0.000000 | none | 86.3143 | pass_buffer_reuse_off |
| `20260617_rk3588_8gb_yolo11n_rknn_drop_newest_ab` | drop_newest | 8 | true |  |  |  |  |  |  |  |  |  |  |  |  | not_executed |
| `20260617_rk3588_8gb_yolo11n_rknn_block_timeout_ab` | block_with_timeout | 8 | true |  |  |  |  |  |  |  |  |  |  |  |  | not_executed |

#### RK3588 Buffer Reuse A/B（2026-06-22）

`buffer_reuse` 在 RK3588 侧已经不是“配置存在但未证实”的状态。`20260622` 的板端日志明确显示 3 个独立 RKNN context 都完成了 `input_io_mem=true` 和 `output_prealloc=true` 初始化，且运行日志中没有出现 `RKNN_BUFFER_REUSE_SKIP`。这意味着当前实现确实复用了输入 IO memory，并为输出走了预分配路径，而不是退回到逐帧临时分配。

需要单独收紧一个交付口径：当前共享 C++ app 只实际读取并消费了 `buffers.reuse`，没有把 `buffers.pool_size` 解析成通用对象池/通用 buffer pool 运行时机制。因此，本节验证通过的范围是“RKNN backend buffer reuse 已落地”，不是“通用 buffer pool 已落地”。配置文件中的 `pool_size` 目前只能视为规范/配置占位，不能拿来充当运行时对象池证据。

| duration_sec | decision | fps_gain | inference_p50_reduction | latency_p95_reduction | memory_peak_reduction | memory_growth_reduction | drop_rate_delta | evidence |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 120 | `buffer_reuse_no_material_difference` | 0.000000 | not_material | not_material | not_material | not_material | 0.000000 | `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_ab120.md` |
| 600 | `buffer_reuse_beneficial` | 0.000000 | -0.003821 | 0.000050 | 0.025685 | 0.107388 | 0.000000 | `benchmark/processed/03_video_pipeline/20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_ab600.md` |

| run_id | mode | frames | FPS | inference_p50_ms | inference_p95_ms | latency_p95_ms | drop_rate | memory_peak_mb | memory_growth_mb_per_hour | frame_id_gaps | frame_id_out_of_order | new_rknpu_anomaly_lines | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_on_ab600` | `reuse_on` | 18048 | 30.0800 | 56.9946 | 62.1430 | 118.1660 | 0.000000 | 328.88 | 77.0451 | 0 | 0 | 0 | beneficial_runtime600 |
| `20260622_rk3588_8gb_yolo11n_rknn_bufferreuse_off_ab600` | `reuse_off` | 18048 | 30.0800 | 56.7777 | 62.0675 | 118.1720 | 0.000000 | 337.55 | 86.3143 | 0 | 0 | 0 | baseline_runtime600 |

结论按 600 秒结果收口：吞吐不变，但 `buffer_reuse=true` 将进程峰值内存从 337.55 MB 降到 328.88 MB，内存增长从 86.31 MB/h 降到 77.05 MB/h；同时零丢帧、零乱序、零新增 RKNPU timeout/reset。对 RK3588 而言，03C 的 RKNN backend buffer reuse 子项可以视为已闭环；通用 buffer pool（`pool_size`）仍未落地。

### RK3588 Resource / Accelerator

| run_id | monitor_log_path | RKNPU util | CPU util | memory_peak_mb | temperature_max_c | power_mode | power_avg_w | power_peak_w | throttle_events | runtime_evidence_path | accelerator_evidence_path | status |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_rknpu.log` | avg=100%, peak=100% | not_recorded | 1096.87 (system used peak) | 50.85 | not_recorded | not_observable | not_observable | historical dmesg event, not attributable | `logs/runtime/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_rknpu.log` | monitor_pass_runtime_dmesg_boundary_missing |
| `20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_1worker_ab120_rknpu.log` | sampled=100%@1GHz | not_recorded | 1080.27 (system used peak) | 50.85 | not_recorded | not_observable | not_observable | 0 | runtime log | monitor log | pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_ab120_rknpu.log` | sampled=100%@1GHz | not_recorded | 1103.93 (system used peak) | 52.69 | not_recorded | not_observable | not_observable | 0 | runtime log | monitor log | pass_120s |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean_rknpu.log` | sampled=100%@1GHz | not_recorded | 329.40 process VmHWM | 55.46 | not_recorded | not_observable | not_observable | 0 | runtime log | monitor log | runtime600_pass |

#### RK3588 Mixed 8h Update (2026-06-23)

`20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h` 已完成正式 mixed 8h 收口。当前应把它解释为“camera 4h + video 4h 的长稳组合证据”，而不是继续停留在 2h acceptance 口径：

| run_id | input_source_id | duration_sec | fps_estimated | drop_frame_count_total_estimated | drop_frame_rate_total_estimated | frame_order | status |
|---|---|---:|---:|---:|---:|---|---|
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_astra4h` | `astra_s_openni_001` | 14400.0 | 29.6003 | 0 | 0.0 | 0 gaps / 0 out-of-order | pass |
| `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h_video4h` | `video_set_stability_v1` | 14400.0 | 30.0521 | 8 | 0.0000184861 | strict trace 5 gap events / 0 out-of-order | pass_realtime_with_negligible_drop |

结论：在“不要求严格 zero-gap、按实时策略收口”的前提下，RK3588 当前正式主线状态应以 mixed 8h 为准；BDD100K 任务质量仍单独保留为非阻塞失败。

### RK3588 Labeled Video Quality

| run_id | dataset_id | labeled_frames | prediction_frames | labeled_frame_coverage | missing_labeled_frames | AP50 | precision | recall | F1 | TP | FP | FN | per_class_table | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2` | `bdd100k_mot_mini_v1` | 15631 (15572 evaluable) | 95946 | 1.000000 (80/80) | 0 | 0.351213 | 0.373474 | 0.445810 | 0.406449 | 102460 | 171883 | 127369 | `benchmark/processed/03_video_pipeline/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_bdd100k_mot_quality_aggregate.md` | fail_recall_below_0.50 |

#### RK3588 full80 Confidence Sweep

该扫描使用同一 full80 raw；C++ 已在 0.05 截断候选框，因此只能验证 0.05 及以上 operating point。0.05 的 Recall 最高，提高阈值只会继续降低 Recall，质量子任务据此按非阻塞失败收口。

| confidence | AP50 | precision | recall | F1 | status |
|---:|---:|---:|---:|---:|---|
| 0.05 | 0.351213 | 0.373474 | 0.445810 | 0.406449 | fail_recall |
| 0.10 | 0.351213 | 0.490456 | 0.406515 | 0.444558 | fail_recall |
| 0.15 | 0.351213 | 0.564754 | 0.378947 | 0.453559 | fail_recall |
| 0.20 | 0.351213 | 0.623896 | 0.353250 | 0.451092 | fail_recall |
| 0.25 | 0.351213 | 0.669513 | 0.329593 | 0.441728 | fail_recall |
| 0.30 | 0.351213 | 0.705467 | 0.308325 | 0.429108 | fail_recall |

证据：`benchmark/processed/03_video_pipeline/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_confidence_sweep_summary.csv`；问题记录：`P3-TRB-20260620-012`。

### RK3588 Quality Gate

| run_id | fixed_input_alignment | task_level_quality | frame_trace | output_validity | schema_check | prepost_consistency | model_hash_status | pass_fail | status |
|---|---|---|---|---|---|---|---|---|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | not_executed | inherited_project2_pass_not_project3_verified | degraded_3719_frame_id_gaps | pass_1.0 | pass_14258_records | pass | actual_hash_pass_raw_metadata_mismatch | fail_until_alignment_and_clean_runtime | degraded_not_verified |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | not_executed | artifact_coco2017_pass_pipeline_alignment_pending | pass_0_gaps_0_out_of_order | pass_1.0 | pass_18048_records | pass | pass_40bce | not_verified_until_fixed_input_alignment | runtime_pass_quality_pending |
| `20260618_rk3588_8gb_yolo11n_rknn_int8_fixed_input_alignment_project3_current` | fail_626_of_630_matches_unmatched_baseline_4_unmatched_current_6 | artifact_coco2017_pass | pass_795_frames_0_gaps_0_out_of_order | pass_1.0 | pass_795_records | false_pass_static_checker_did_not_model_rknn_pad | pass_40bce | fail_preprocess_pad_114_vs_0 | root_cause_fixed_pending_rerun |
| `20260619_rk3588_8gb_yolo11n_rknn_int8_fixed_input_alignment_pad0_project3_current` | diagnostic_630_of_630_bidirectional_80_frames | artifact_coco2017_pass_map50_95_0.381496 | pass_795_frames_0_gaps_0_out_of_order | pass_1.0 | pass_795_records | pass_effective_pad_0 | pass_40bce | not_formal_quality_evidence | diagnostic_only_superseded_by_bdd100k |
| `20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2` | diagnostic_superseded | fail_AP50_0.351213_recall_0.445810 | pass_80_sequences_0_pipeline_failures | pass_80_of_80_coverage_1.0 | pass_80_of_80 | pass | pass_40bce | fail_recall_below_0.50 | closed_nonblocking_task_fail_proceed_stability |

### RK3588 BDD100K Orientation-invalid Run 2026-06-19

`20260619_rk3588_8gb_yolo11n_rknn_bdd100k_full80_*` 不能作为质量证据。已同步的 73 个 raw 全部记录 `input_width=720`、`input_height=1280`，而 BDD100K 标签和同序列 Jetson raw 均为 `1280x720`。首个序列实际输出 1,958 个检测、1,204/1,204 帧均非空，但坐标位于旋转后的竖屏空间，导致 TP=0、AP50/precision/recall/F1 全为 0；这不是 RKNN 模型无输出。

根因是 80 个 MOV 同时存在两种相反的 90° `tkhd` track matrix，且 RK3588 OpenCV 无法稳定暴露可用的 orientation metadata。仅关闭 orientation auto 或统一强制 clockwise 都不足够。当前 runner 使用 `container` 模式逐视频解析矩阵，并使用 `1280x720` 尺寸门禁。旧方向无效 raw 已从 formal aggregation scope 排除。

标签 coverage 的另一个独立现象是部分标签映射帧位于视频实际 EOF 之后，例如首个序列 raw 最大帧号为 1203、最后标签帧号为 1206。评估器现将其明确记录为 `trailing_unavailable_labeled_frames`，只对视频实际存在的标注帧计算 coverage；任何视频范围内缺帧仍判失败。

### RK3588 Reproducibility

| run_id | environment_baseline_id | pipeline_config | stream_config | model_config | board_config | command | raw_result_path | processed_result_path | runtime_log_path | monitor_log_path | related_troubleshooting_id | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` | `20260611_rk3588_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml` | `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | `projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml` | `RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline.jsonl` (板端生成，本地尚未同步) | `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_summary.csv` | `logs/runtime/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_rknpu.log` | `P3-TRB-20260618-RK3588-003`, `P3-TRB-20260618-RK3588-004` | degraded_raw_not_synced_locally |
| `20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean` | `20260611_rk3588_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml` | `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n.yaml` | `projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml` | `INFERENCE_WORKERS=3 DURATION_SEC=600 TRACE_FAIL_ON_GAPS=1 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean.jsonl` | `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean_summary.csv` | `logs/runtime/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean_rknpu.log` | `P3-TRB-20260618-RK3588-005`, `P3-TRB-20260618-RK3588-006` | runtime600_pass_quality_pending |
| `20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2` | `20260611_rk3588_8gb_env_baseline` | `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_bdd100k_quality.yaml` | `projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml` | `projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml` | `projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml` | `RUN_PREFIX=20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2 START_INDEX=0 LIMIT=0 CONTINUE_ON_ERROR=1 INPUT_ORIENTATION_CORRECTION=container CONFIDENCE_MIN=0.05 EVALUATE_STRICT=0 bash projects/03_video_pipeline/scripts/run/run_rk3588_bdd100k_mini.sh` | `benchmark/raw/03_video_pipeline/rk3588_8gb/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_<sequence_id>.jsonl` | `benchmark/processed/03_video_pipeline/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_bdd100k_mot_quality_aggregate.csv` | `logs/runtime/03_video_pipeline/rk3588_8gb/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_<sequence_id>.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260619_rk3588_8gb_yolo11n_rknn_bdd100k_container_full80_v2_<sequence_id>_rknpu.log` | `P3-TRB-20260619-011` | reproducible_quality_fail_recall |

### RK3588 MLPerf-style Summary

#### Scenario

- Task: C++ realtime video inference pipeline
- Board: RK3588 8GB
- Backend/runtime: RKNN
- Execution provider: RKNPU
- Loader API: RKNN C API
- Model: YOLO11n
- Backend artifact: `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn`
- Backend artifact SHA256: `40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c`; COCO2017 artifact quality pass，BDD100K full80 quality fail（recall below 0.50）
- Input source: `video_set_runtime_v1`
- Pipeline mode: backend_pipeline
- Queue policy: drop_oldest mainline
- Batch / concurrency: batch=1, concurrency=3，三个独立 RKNN context 分别绑定 core0/core1/core2
- Warmup: 30 frames in config
- Repeat / duration: 600 sec completed

#### Quality Gate

| item | value |
|---|---|
| Detection quality | artifact COCO2017 pass: mAP50-95=0.381496；BDD100K full80 AP50=0.351213, precision=0.373474, recall=0.445810, F1=0.406449 |
| Historical diagnostic alignment | 80 帧 630/630 双向匹配，仅用于 pad 漂移修复，不进入正式质量门 |
| Task-level quality | fail: BDD100K recall 0.445810 < 0.50；AP50 0.351213 >= 0.25 |
| Frame trace | pass: 18048 frames, 0 gaps, 0 out-of-order |
| Queue policy | drop_oldest, capacity=8, drop_rate=0% |
| Output validity | pass: 18048/18048，valid rate=1.0 |
| Pass / Fail | runtime_pass_mixed_8h_camera4h_video4h_realtime_with_negligible_drop_bdd100k_task_quality_fail |

#### Performance

| metric | value |
|---|---:|
| p50 end-to-end latency | 103.3005 ms |
| p90 end-to-end latency | 118.1683 ms |
| p95 end-to-end latency | 120.0783 ms |
| p99 end-to-end latency | 124.8260 ms |
| FPS | 30.0800 |
| drop frame rate | 0% (0 / 18048 input frames) |

#### Resource

| metric | value |
|---|---:|
| memory peak | 329.40 MB process VmHWM |
| memory growth | runtime600 初估 72.26 MB/h；30 分钟复核 12.62 MB/h；2 小时 acceptance 进一步降至 3.96 MB/h |
| temperature max | 55.46 C |
| power mode / power | not_recorded / not_observable |
| CPU/GPU/NPU/BPU utilization | CPU not recorded / GPU N/A / RKNPU avg=100%, peak=100% |
| CPU fallback | false |
| accelerator runtime anomaly | 0 new timeout/reset during bounded 600 sec run |

#### Reproducibility

- Environment baseline: `20260611_rk3588_8gb_env_baseline`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn`
- Command: `RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean INFERENCE_WORKERS=3 DURATION_SEC=600 TRACE_FAIL_ON_GAPS=1 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh`
- Raw result: `benchmark/raw/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean.jsonl`
- Processed result: `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean_summary.csv`
- Runtime logs: `logs/runtime/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean.log`
- Monitor logs: `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_3worker_runtime600_clean_rknpu.log`
- Related troubleshooting: `P3-TRB-20260618-RK3588-005`, `P3-TRB-20260618-RK3588-006`

## MLPerf-style Summary

### Scenario

- Task: C++ realtime video inference pipeline
- Board: Jetson 8GB
- Backend/runtime: TensorRT
- Execution provider: TensorRT-GPU
- Loader API: TensorRT C++ API
- Model: YOLO11n
- Backend artifact: `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine`
- Backend artifact SHA256: `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d`
- Input source: `video_set_runtime_v1`
- Pipeline mode: backend_pipeline
- Queue policy: `drop_oldest` mainline；已另行对照 `drop_newest` 与 `block_with_timeout(33ms)`
- Batch / concurrency: batch=1, concurrency=1
- Warmup: 30 frames in config
- Repeat / duration: 600 sec runtime benchmark target；当前选中 run 实测 `596.0 sec`

### Quality Gate

| item | value |
|---|---|
| Detection quality | `quality_threshold_fail` |
| Fixed-input alignment | pass |
| Fixed-input alignment manifest | `data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json` |
| Labeled video quality dataset | `bdd100k_mot_mini_v1` |
| Labeled video quality manifest | `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json` |
| Task-level quality | `quality_threshold_fail` |
| Quality alignment exemption | `not_applicable` |
| Frame trace | `degraded_startup_gap_only` |
| Queue policy | `drop_oldest_runtime_baseline`; `drop_newest` / `block_with_timeout(33ms)` 已完成对照 |
| Output validity | `pass_1.0` |
| Pass / Fail | `runtime_pass_quality_gate_fail_imx219_live_source_capture_bottleneck` |

### Performance

| metric | value |
|---|---:|
| p50 end-to-end latency | 49.19645 |
| p90 end-to-end latency | 51.11239 |
| p95 end-to-end latency | 52.23789 |
| p99 end-to-end latency | 54.837118 |
| FPS | 30.087248 |
| drop frame rate | 0.0064273 |

### Resource

| metric | value |
|---|---:|
| memory peak | 2221.0 MB |
| memory growth | not_recorded_in_runtime_summary |
| temperature max | 57.0 C |
| power mode / power | not_recorded |
| CPU/GPU/NPU/BPU utilization | cpu_avg=25.3058, gpu_avg=22.3566 |
| CPU fallback | false |

### Reproducibility

- Environment baseline: `20260609_jetson_8gb_env_baseline`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine`
- Command: `RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh`
- Raw result: `benchmark/raw/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout.jsonl`
- Processed result: `benchmark/processed/03_video_pipeline/20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout_summary.csv`
- Runtime logs: `logs/runtime/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout.log`
- Monitor logs: `logs/monitor/03_video_pipeline/jetson_8gb/20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout_tegrastats.log`
- Failure logs: not_applicable
- Related run: `projects/03_video_pipeline/runs/20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout/run.md`
- Related troubleshooting: `P3-TRB-20260617-005`, `P3-TRB-20260617-006`, `P3-TRB-20260617-007`

## 2026-06-17 Update: Jetson INT8 Q8 Mainline

本节用于更正上文仍停留在 `20260616` 的临时结论。`20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_q8_mainline` 已经完成并同步回本地，说明 `P3-TRB-20260616-004` 中的 artifact mismatch 已被实际修正：本轮 raw 与 `run.md` 都明确记录了 INT8 PTQ engine，而不是 FP16 engine。

### 本轮确认事实

| item | value |
|---|---|
| run_id | `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_q8_mainline` |
| precision_or_quantization | `int8_ptq` |
| backend_artifact_path | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` |
| backend_artifact_sha256 | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` |
| execution_provider | `TensorRT-GPU` |
| cpu_fallback | `false` |
| queue_policy / queue_capacity | `drop_oldest` / `8` |
| schema_check | `pass` |
| prepost_consistency | `pass` |
| trace_check | `degraded` |
| frame_id_gaps | `26348` |
| duration_sec_estimated | `596.0` |
| fps_estimated | `45.8859` |
| latency_p50 / p95 / p99 | `45.6490 / 59.1164 / 68.7150 ms` |
| drop_frame_count_max | `135764` |
| drop_frame_rate_max | `0.999133` |
| output_valid_rate | `1.0` |
| memory_mb_peak | `2153.0` |
| temperature_c_peak | `71.0` |
| cpu_util_avg / gpu_util_avg | `92.6775% / 51.3719%` |
| throttle_events | `648` |

### 口径更正

- 这轮 run 可以作为“Jetson INT8 TensorRT C++ 主线已跑通”的证据。
- 这轮 run 不能作为“no-drop / no-gap 已通过”的证据。
- 原因不是时间戳缺失，而是主线策略本身就是 `drop_oldest + queue_capacity=8`，会在拥塞时主动丢弃旧帧，优先保留最新帧。
- 因此，`trace=degraded` 在这里应解读为“实时低延迟主线证据”，而不是“逐帧完整性证据”。

### 对 20260616 记录的修正

- `20260616_jetson_8gb_yolo11n_tensorrt_runtime600_mainline` 仍保留为历史对照 run。
- 但 03D 主线是否真正使用 INT8 的问题，已经由 `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_q8_mainline` 解决。
- 从这一刻起，artifact mismatch 不再是 Jetson 主线 blocker；剩余未完成项转为稳定性验证和可选的 no-drop / 队列策略对比。

### 当前推荐下一步

1. 跑 03H stability smoke，验证当前 INT8 q8 主线在更长时间窗口下的稳定性。
2. 如需补 no-gap 证据，使用 fixed-input 或 no-drop 专用配置，不复用这条 `drop_oldest` 主线。
3. 如需补 03C 队列对比，再增加 `drop_newest` / `block_with_timeout` 对照 run。

## 2026-06-18 Update: 03C Queue Policy Contrast Verified

在同步代码修复并重新 build Jetson app 后，03C 的两轮补充对照已经有效完成：

- `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_drop_newest_v2`
- `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_block_timeout_v2`

它们与默认 noout 主线 `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout` 的对比如下：

| run_id | queue_policy | queue_push_timeout_ms | fps_estimated | drop_frame_count_total_estimated | drop_frame_rate_total_estimated | frame_keep_rate_estimated | latency_p50_ms | latency_p95_ms | queue_max | trace_gap_count | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout` | drop_oldest | 20 | 30.0872 | 116 | 0.00643 | 0.99357 | 49.1965 | 52.2379 | 7 | 1 | `baseline_noout_mainline` |
| `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_drop_newest_v2` | drop_newest | 20 | 30.0772 | 122 | 0.00676 | 0.99324 | 50.7239 | 52.8154 | 7 | 1 | `valid_queue_policy_contrast` |
| `20260618_jetson_8gb_yolo11n_tensorrt_int8_runtime600_block_timeout_v2` | block_with_timeout | 33 | 30.0771 | 92 | 0.00510 | 0.99490 | 50.6659 | 52.4287 | 8 | 3 | `valid_queue_policy_contrast` |

### 当前解读

- 这次 `v2` 两轮已经真正生效，不再是之前“名义切换、实际仍按 `drop_oldest` 执行”的无效对照。
- `drop_newest` 在这组 600 秒 noout runtime 里没有带来优势：
  - 丢帧总数 `122`，略差于 `drop_oldest` 的 `116`
  - p50/p95 延迟也略高
- `block_with_timeout(33ms)` 是这组三策略里保留率最好的：
  - 总丢帧 `92`，优于 `drop_oldest` 的 `116`
  - keep rate `0.99490`，三者最高
  - FPS 与默认主线几乎一致
- 但 `block_with_timeout` 也带来了更明显的背压痕迹：
  - `queue_capture_max=8`
  - `queue_preprocess_max=8`
  - trace gap 从 `1` 增加到 `3`

### 当前结论

- 就这组 `playlist-paced + SAVE_OUTPUT_VIDEO=0 + runtime600` 结果而言：
  - **`drop_newest` 不值得替代默认主线**
  - **`block_with_timeout(33ms)` 值得作为候选策略保留**
- 但当前证据仍不足以直接把默认主线从 `drop_oldest` 切到 `block_with_timeout`，因为：
  - 这只是 `600s` 文件播放语义下的对照
  - 还没有更长时长或 live-source 场景的背压稳定性验证

## 2026-06-18 Update: `block_with_timeout(33ms)` Stability Smoke Contrast

`20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` 已完成，说明 `block_with_timeout(33ms)` 不再只有 `runtime600 + video_set_runtime_v1` 一组证据，而是已经进入 `video_set_stability_v1` 的 80 视频 smoke 复核。

与默认 noout smoke 基线 `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` 的对比如下：

| run_id | queue_policy | queue_push_timeout_ms | fps_estimated | drop_frame_count_total_estimated | drop_frame_rate_total_estimated | latency_p50_ms | latency_p95_ms | queue_max | trace_gap_count | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke_playlist80_noout` | drop_oldest | 20 | 30.1091 | 103 | 0.00571 | 50.6552 | 52.7732 | 7 | 1 | `smoke_noout_baseline` |
| `20260618_jetson_8gb_yolo11n_tensorrt_stability_smoke_block_timeout` | block_with_timeout | 33 | 30.1023 | 107 | 0.00593 | 49.0913 | 51.9486 | 8 | 3 | `smoke_block_timeout_candidate` |

这轮 smoke 说明：

- `block_with_timeout(33ms)` 在 `video_set_stability_v1` 上没有延续 `runtime600` 那种“总体丢帧更少”的优势。
- 它的延迟略低，但总丢帧、`queue_max` 和 trace gap 都略差于 `drop_oldest` smoke 基线。
- 因此，当前关于 `block_with_timeout` 的结论应修正为：
  - **值得保留为候选策略**
  - **但证据已呈现 mixed result，默认主线暂不切换**

如果后续还要继续补队列策略验证，优先级应是：

1. `short_sustained` 档位下的 `block_with_timeout(33ms)` 复核。
2. 至少一种真实 live-source 输入，而不是仅文件 playlist。

## 2026-06-17 Update: Stability Smoke First Attempt

`20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke` 已执行并同步回本地，但这轮结果不能直接当作“paced 真实实时流稳定性结论”。

### 本轮确认事实

| item | value |
|---|---|
| run_id | `20260617_jetson_8gb_yolo11n_tensorrt_stability_smoke` |
| input_source_id | `video_long_loop_001` |
| precision_or_quantization | `int8_ptq` |
| queue_policy / queue_capacity | `drop_oldest` / `8` |
| schema_check | `pass` |
| prepost_consistency | `pass` |
| trace_check | `degraded` |
| frame_id_gaps | `25856` |
| duration_sec_estimated | `596.0` |
| fps_estimated | `44.5520` |
| drop_frame_count_max | `136198` |
| drop_frame_rate_max | `0.999242` |
| memory_mb_peak | `2134.0` |
| temperature_c_peak | `71.0` |
| cpu_util_avg / gpu_util_avg | `94.4020% / 51.6763%` |
| throttle_events | `624` |
| runtime_log_size | `0 bytes` |

### 为什么这轮不能当作 paced 结论

- raw 中最终写出 `26553` 帧，但最大 `frame_id` 到了 `162750`
- 保留率只有 `26553 / 162750 ≈ 16.3%`
- 若按 `596 sec` 粗算，采集侧节奏仍接近 `162750 / 596 ≈ 273 FPS`
- 这明显不符合 `video_long_loop_001` / `video_short_001` 在 stream manifest 中声明的 `10 FPS`，也进一步说明旧 smoke 结果不能代表新的 playlist-paced 语义

因此，这轮 `stability_smoke` 说明：

- 板端这次执行仍然体现出旧的“离线文件高速灌流”语义
- pacing 修复尚未在这轮 smoke 上形成可确认的板端证据
- 这轮结果可以作为 stress 模式下的稳定运行证据，但不能当作真实实时流稳定性结论

### 对 03H 结论的修正

- 03H 不能再写成 `not_executed`
- 也不能写成“真实实时流 stability smoke 已通过”
- 当前最准确状态应为：`executed_old_file_stress_semantics`

### 下一步

在确认 Jetson 已同步 pacing 修复并完成重新 build 后，重新执行：

```bash
cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline

RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_stability_smoke_paced \
TIER=smoke \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh
```

期望在新一轮 runtime log 中看到 `INPUT_PACING` 记录，并且 `max_frame_id` 不再以数百 FPS 的速度推进。

## 2026-06-17 Update: Playlist-paced Runtime Mainline Verified

`20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_mainline` 已同步回本地，并且可以确认这轮不是旧的离线高速灌流语义，而是真正的 playlist-paced runtime 主线。

### 本轮确认事实

| item | value |
|---|---|
| run_id | `20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_mainline` |
| input_source_id | `video_set_runtime_v1` |
| input_source_type | `video_playlist` |
| runtime_log | `INPUT_PACING: ... input_source_type=video_playlist ... pacing_mode=source_timestamps_with_fps_fallback ... playlist_items=20` |
| duration_sec_estimated | `596.0` |
| fps_estimated | `25.1158` |
| frame_id_max | `18047` |
| input_frames_estimated | `18048` |
| drop_frame_count_total_estimated | `3079` |
| drop_frame_rate_total_estimated | `0.1706` |
| frame_keep_rate_estimated | `0.8294` |
| frame_id_gaps | `2888` |
| drop_frame_rate_max | `0.99187` |
| output_p50_ms | `38.4636` |
| inference_p50_ms | `9.7640` |
| queue_postprocess_p95 / max | `8.0 / 8` |
| dropped_frame_reason | `queue_full` |

### 结论

- playlist + pacing 修复已经在板端验证通过，`frame_id` 推进速度已恢复到约 `30 FPS` 的真实播放语义。
- 当前主线仍然有丢帧，但已经不是旧的“输入灌流过快”问题。
- 当前主要瓶颈位于 output 阶段，而不是 TensorRT inference：
  - `output_p50_ms ≈ 38.5 ms` 已超过 `30 FPS` 的单帧预算 `33.3 ms`
  - `inference_p50_ms ≈ 9.8 ms`
  - `queue_postprocess_p95=8` 说明输出前的最后一级队列持续打满

### 不要把 `drop_frame_rate_max` 当成整轮丢帧率

- 从这一轮开始，整轮总体丢帧应优先看：
  - `drop_frame_count_total_estimated`
  - `drop_frame_rate_total_estimated`
  - `frame_keep_rate_estimated`
- `drop_frame_rate_max` 仅表示“逐帧瞬时累计丢帧率最大值”，不能再直接解读为整轮总体丢帧率，更不能直接读成“这一轮丢了 99% 帧”。

## 2026-06-17 Update: No-output Runtime A/B Confirmed

`20260617_jetson_8gb_yolo11n_tensorrt_int8_runtime600_playlist20_noout` 已同步回本地，用于和保存输出视频版本做单变量对照。

### 对照结果

| metric | `playlist20_mainline` | `playlist20_noout` | delta |
|---|---:|---:|---:|
| fps_estimated | 25.1158 | 30.0872 | +4.9714 |
| drop_frame_rate_total_estimated | 0.1706 | 0.00643 | -0.1642 |
| frame_keep_rate_estimated | 0.8294 | 0.9936 | +0.1642 |
| frame_id_gaps | 2888 | 1 | -2887 |
| output_p50_ms | 38.4636 | 0.0369 | -38.4267 |
| output_p95_ms | 50.5263 | 0.0526 | -50.4737 |
| latency_p50_ms | 88.9517 | 49.1965 | -39.7552 |
| queue_postprocess_p95 | 8.0 | 0.0 | -8.0 |

### 结论

- 关闭视频输出后，主线已经回到接近 `30 FPS` 的播放语义处理能力。
- 这轮 A/B 对照基本已经坐实：当前 playlist-paced 主线的主要瓶颈在 output video writer，而不是 inference。
- 因此，后续如果目标是“尽量减少实时流下的丢帧”，优先级应是优化输出路径，而不是继续怀疑 TensorRT 算力不足。
- 从当前版本开始，Jetson 主线运行脚本默认 `SAVE_OUTPUT_VIDEO=0`；保存输出视频改为显式 opt-in。

## RDK X5 BPU 当前口径

`2026-06-24` 的 playlist runtime/stability/failure/service 产物与 `2026-06-29` 的 IMX219 live-source 性能优化产物已经同步回仓库。这里必须把两条证据链分开写清楚：

- `20260624` 这批 run 仍是当前可复现的 playlist 长时 runtime/stability 证据；回传时使用的旧 schema 仍把 `video_playlist` 视为非法 `input_source_type`，所以板端 `run.md` 保留了历史 `schema_check_exit_code=1`。
- 当前仓库中的 `benchmark/schemas/video_pipeline_raw_schema.yaml` 已允许 `video_playlist`；我已用当前 schema 对这批 RDK X5 raw 重新执行本地校验，`single_thread / cpp_pipeline / stability` 的 schema check 现均为 `pass`。
- `20260629` 这批 run 是当前 IMX219 live-source 的性能优化回填，不是 600 秒 playlist soak，而是 `PREVIEW_WINDOW=off` 下的本地摄像头 no-preview 性能对照。当前最佳组合是 `INFERENCE_WORKERS=2 + POSTPROCESS_WORKERS=2`。
- `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` 则把这条 `2 infer / 2 postprocess` live-source 主线延长到了 `1798.0s`，并保持 `30.3921 FPS / 0 gap / 0 drop / trace pass`，说明当前正式性能主线已经具备 `30 分钟` 级稳定性补证。
- `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` 又把同一条 live-source 主线延长到了 `7198.0s`，并保持 `30.3865 FPS / 0 gap / 0 drop / trace pass`；同步回当前仓库后，这轮 `schema_check.md` 也已按现行 schema 本地重验为 `pass`。
- `20260624_rdk_x5_8gb_systemd_service_test_v2` 已把 systemd 生命周期补齐为 `pass`；`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` 又把真实 live-source `input_disconnect` 正式补齐到 `disconnect_status=pass`。
- `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` 的 80/80 raw 已同步回当前仓库；虽然板端 batch.csv 仍因旧 postcheck 保留 `pipeline_exit=3` / `evaluate_status=not_run`，但当前仓库已基于同一批 raw 本地补齐正式 aggregate 与 confidence sweep，RDK X5 的 BDD100K 任务级质量结论现已闭环。

### RDK X5 Artifact / Baseline

| item | value | status | notes |
|---|---|---|---|
| environment_baseline_id | `20260612_rdk_x5_8gb_env_baseline` | inherited_ready | 项目三直接继承项目二环境基线 |
| backend_runtime | `bpu` | ready_for_cpp_board_run | 项目三主线要求为 C++ hbDNN BPU runtime |
| execution_provider | `BPU` | ready_for_cpp_board_run | 正式写入前仍需项目三 C++ runtime log 证明 |
| loader_api | `Horizon hbDNN C API` | ready_for_cpp_board_run | 项目二参考为 `hobot_dnn.pyeasy_dnn`，项目三主线改为 C API |
| backend_artifact_path | `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin` | mainline_selected | 继承项目二正式 split-head 主线 |
| backend_artifact_sha256 | `2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c` | mainline_selected | 与项目二正式 run 一致 |
| source_project2_run | `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | reference_available | 只能作为 reference，不能替代项目三 C++ runtime |
| project3_single_thread_run | `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | board_run_synced | 单线程 smoke，schema 已按当前规则重验通过 |
| project3_playlist_runtime_run | `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | board_run_synced | 600s playlist runtime，queue policy=`drop_oldest` |
| project3_live_source_perf_run | `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | mainline_selected | 当前 IMX219 live-source 正式性能主线 |
| project3_live_source_short_sustained_run | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` | mainline_sustained_verified | 当前 IMX219 live-source `30 分钟` 稳定性补证 |
| project3_live_source_acceptance_sustained_run | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` | mainline_acceptance_verified | 当前 IMX219 live-source `2 小时` 验收稳定性补证 |
| project3_bdd100k_full80_run | `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` | local_quality_aggregate_completed | 80/80 raw 已同步；当前仓库已补齐正式 aggregate 与 confidence sweep |
| mainline_realtime_source | `imx219_rdkx5_hbn_001` | fixed | `mipi_camera_hbn + HBN/srcampy` |
| mainline_orientation | `INPUT_ORIENTATION_CORRECTION=rotate180` | fixed | 板端窗口和 raw trace 均按该朝向口径解释 |
| mainline_workers | `inference=2 / postprocess=2` | fixed | `20260629` 优化回填后确定 |

### RDK X5 Runtime Summary

| run_id | input_source_id | duration_sec | workers | queue_policy | fps_avg | p50_latency_ms | p90_latency_ms | p95_latency_ms | p99_latency_ms | drop_frame_rate | frame_trace | evidence_scope | status | notes |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | `coco2017_val2017_images` | n/a | reference_only | `not_applicable` | 6.5725 | 141.3216 | 185.7790 | 207.6517 | 264.9066 | 0.0000 | `not_video_pipeline_trace` | reference_from_project2_only | reference_from_project2_only | Python `hobot_dnn.pyeasy_dnn`，不是项目三 C++ video pipeline |
| `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | `video_set_runtime_v1` | 60.0 | `1 infer / 1 postprocess` | `none` | 6.7333 | 144.8215 | 146.1858 | 146.5713 | 147.6431 | 0.0000 | `pass_404_frames_0_gap` | project3_cpp_board_run_synced_back | pass_smoke | 单线程最小链路 smoke，`buffer_reuse=false` |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | `video_set_runtime_v1` | 601.0 | `1 infer / 1 postprocess` | `drop_oldest` | 18.1165 | 149.9730 | 163.1606 | 167.0899 | 173.0053 | 0.3967 | `degraded_6894_gaps_queue_full_0_ooo` | project3_cpp_board_run_synced_back | pass_with_drop_oldest_degraded_trace | 当前 playlist 长时 runtime 基线，长稳证据仍引用这条链路 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2` | `imx219_rdkx5_hbn_001` | 59.0 | `1 infer / 1 postprocess` | `drop_oldest` | 20.0169 | 138.5720 | 140.6200 | 141.9370 | 158.2030 | 0.3346 | `degraded_594_gaps_queue_full_0_ooo` | live_source_perf_backfill | correctness_recovered_but_not_mainline | 正确性恢复，但仍存在明显 queue drop |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1` | `imx219_rdkx5_hbn_001` | 59.0 | `2 infer / 1 postprocess` | `drop_oldest` | 19.9322 | 138.8360 | 141.6505 | 150.7385 | 162.6418 | 0.3375 | `degraded_599_gaps_queue_full_0_ooo` | live_source_perf_backfill | postprocess_bottleneck_rejected | 单 `postprocess` worker 成为瓶颈 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `imx219_rdkx5_hbn_001` | 59.0 | `2 infer / 2 postprocess` | `drop_oldest` | 30.0847 | 141.6540 | 162.2392 | 165.1727 | 168.6542 | 0.0000 | `pass_1775_frames_0_gap` | live_source_perf_backfill | live_source_perf_mainline_selected | 当前 IMX219 no-preview 正式性能主线；相对 `opt2` 吞吐提升约 `50.3%` |

### RDK X5 Optimization Walkthrough

这轮优化的核心不是“把某个阶段 p95 压得更低”，而是把 live-source pipeline 从持续积压状态拉回到 `30 FPS` 输入下的稳定实时态。诊断路径如下：

| 阶段 | 目标 | 关键证据 | 解释 | 决策 |
|---|---|---|---|---|
| live-source bring-up | 先把 IMX219 HBN 采集链路、窗口方向和 helper 流口径固定 | `mipi_camera_hbn + HBN/srcampy` 可正常出帧；`rotate180` 后画面方向正确 | 如果输入链路、helper 或朝向不稳定，后续性能对照没有意义 | 将 `imx219_rdkx5_hbn_001 + rotate180` 固定为正式输入口径 |
| benchmark decouple | 把视觉确认与性能测试拆开 | 正式 benchmark 统一 `PREVIEW_WINDOW=off` | SSH / GUI 预览会掺入显示链路开销，不应混入 BPU pipeline 吞吐结论 | 只保留 no-preview run 进入正式性能表 |
| `opt2` baseline | 建立 live-source 单 worker 基线 | `20.0169 FPS`、drop `0.3346`、`594` gap；`inference_p50=49.4599 ms`，`postprocess_p50=49.7171 ms` | 功能正确，但 1/1 worker 无法在 30 FPS 输入下维持零积压 | 保留为正确性恢复基线，不作为主线 |
| `opt3_i2_p1` | 验证瓶颈是否主要在 infer | `19.9322 FPS`、drop `0.3375`、`598` gap；`queue_infer_p95=8.0` | 只加 infer worker 后没有吞吐提升，说明瓶颈已经转移到 infer 之后的消费阶段 | 明确拒绝 `2 infer / 1 postprocess` |
| `opt3_i2_p2` | 同步提升 infer 与 postprocess 吞吐，并复核 trace | `30.0847 FPS`、drop `0.0`、`0` gap、`queue_max=1`、trace `pass` | 虽然 `p95` 高于 `opt2`，但流水线不再积压，输出顺序和 trace 也保持正确 | 接受为正式主线 |

这里必须强调一个容易被误读的点：

- `opt3_i2_p2` 的 `latency_p95_ms=165.1727` 高于 `opt2` 的 `141.9370`，但它仍然是正式主线。
- 原因不是放宽标准，而是项目三这里追求的是“30 FPS 输入下可持续吞吐、零 gap、零 drop、零乱序”的实时 pipeline 行为。
- `opt2` 虽然尾延迟更低，但实际已经长期 queue 积压并发生大量丢帧，因此不能作为正式主线。

### RDK X5 Stage Latency

| run_id | capture_p50_ms | capture_p95_ms | decode_p50_ms | decode_p95_ms | preprocess_p50_ms | preprocess_p95_ms | inference_p50_ms | inference_p95_ms | postprocess_p50_ms | postprocess_p95_ms | output_p50_ms | output_p95_ms | end_to_end_p95_ms | end_to_end_p99_ms | note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | 33.3096 | 33.3811 | 0.0000 | 0.0000 | 10.9038 | 27.7084 | 54.3953 | 58.0318 | 50.3984 | 53.2948 | 0.0669 | 0.1107 | 167.0899 | 173.0053 | playlist 长时 runtime 基线 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2` | 33.1024 | 33.9176 | 0.0000 | 0.0000 | 6.2304 | 8.4812 | 49.4599 | 50.6287 | 49.7171 | 50.4348 | 0.0519 | 0.0836 | 141.9370 | 158.2030 | 正确性恢复，但单 worker 有明显上游拥塞 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1` | 32.9805 | 34.1226 | 0.0000 | 0.0000 | 6.1765 | 9.8495 | 49.4050 | 50.8571 | 50.2740 | 51.0308 | 0.0238 | 0.0709 | 150.7385 | 162.6418 | 推理并行度提升，但单 postprocess worker 仍卡住队列 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | 32.8727 | 34.5667 | 0.0000 | 0.0000 | 6.9702 | 12.0148 | 50.0817 | 74.5031 | 50.9454 | 52.5113 | 0.0664 | 0.0959 | 165.1727 | 168.6542 | 当前 live-source 正式性能主线；吞吐提升来自消除 postprocess 瓶颈而不是缩短单帧时延 |

说明：

- 项目二 reference 只显式给出 pipeline latency 与 inference latency；capture/decode/preprocess/postprocess/output 分阶段字段必须等待项目三 C++ frame-level raw。
- 项目三正式 `pass` 必须来自 `video_pipeline_app.cpp` 输出的 `*_ms` 字段聚合，不能用项目二 reference 填充。

### RDK X5 Queue / Buffer

| run_id | workers | queue_policy | queue_capacity | queue_push_timeout_ms | buffer_reuse | queue_capture_p95 | queue_preprocess_p95 | queue_infer_p95 | queue_postprocess_p95 | queue_max | drop_frame_count | drop_frame_rate | dropped_frame_reason | memory_growth_mb_per_hour | status |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | `1 / 1` | `none` | 0 | 20 | false | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0000 | `not_applicable` | 212.5227 | pass_smoke |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | `1 / 1` | `drop_oldest` | 8 | 20 | true | 0.0 | 8.0 | 0.0 | 0.0 | 8 | 7160 | 0.3967 | `queue_full` | 42.2360 | playlist_runtime_degraded_trace |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2` | `1 / 1` | `drop_oldest` | 8 | 20 | true | 0.0 | 8.0 | 2.0 | 0.0 | 8 | 594 | 0.3346 | `queue_full` | 920.7628 | single_worker_not_mainline |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1` | `2 / 1` | `drop_oldest` | 8 | 20 | true | 0.0 | 8.0 | 8.0 | 0.0 | 8 | 599 | 0.3375 | `queue_full` | -83.8800 | infer_scaled_but_postprocess_blocked |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `2 / 2` | `drop_oldest` | 8 | 20 | true | 0.0 | 1.0 | 0.0 | 0.0 | 1 | 0 | 0.0000 | `none` | 269.5286 | live_source_perf_mainline_selected |

### RDK X5 Resource / Accelerator

| run_id | monitor_log_path | memory_mb_peak | memory_growth_mb_per_hour | temperature_c_peak | power_mode | cpu_util_avg | bpu_devfreq_mhz | ddr_devfreq_mhz | gpu_devfreq_mhz | bpu_load | runtime_evidence_path | accelerator_evidence_path | cpu_fallback | note |
|---|---|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | `logs/monitor/02_quantization/rdk_x5_8gb/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor_resource_monitor.jsonl` | 1146.219 system / 443.75 process_hwm |  | 57.067 | `performance / fixed fan if available` | 16.748267 | 996.0 | 4266.0 | 996.0 | `not_readable` | `projects/02_quantization/runs/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor/run.md` | same_as_monitor_log | false | 项目二 Python reference |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline_bpu.log` | 239.223 | 42.2360 | 67.423 | `not_recorded` | `not_recorded` | 996.0 | 4266.0 | 996.0 | `not_readable (bpu_load_path=not_found)` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline_bpu.log` | false | playlist 长时 runtime 基线 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_bpu.log` | 127.219 | 269.5286 | 69.182 | `not_recorded` | `not_recorded` | 996.0 | 4266.0 | 996.0 | `not_readable (bpu_load_path=not_found)` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_bpu.log` | false | 当前 live-source 正式性能主线；温度峰值来自 monitor log 实测最大值 |

### RDK X5 Quality Gate

| run_id | fixed_input_alignment | task_level_quality | frame_trace | output_valid | task_dataset | overall_metric | evidence_scope | status | notes |
|---|---|---|---|---|---|---|---|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | `project2_python_reference_only` | `pass_with_resource_note` | `not_video_pipeline_trace` | `schema_pass_predictions_5000_of_5000` | `coco2017_val2017` | `mAP50_95=0.36855805289535165`, `accuracy_drop=0.02433295452` | reference_from_project2_only | reference_from_project2_only | 这是任务级质量参考，不是项目三 C++ video pipeline quality gate |
| `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` | `prepost_pass` | `not_assessed_smoke_only` | `pass_404_frames_0_gap` | `pass_1.0` | `video_set_runtime_v1` | `detection_count_mean=7.0322` | project3_cpp_board_run_synced_back | pass_smoke | 该 run 只用于最小链路验证，不作为正式任务级质量结论 |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | `prepost_pass` | `reference_from_project2_only` | `degraded_6894_gaps_queue_full_0_ooo` | `pass_1.0` | `video_set_runtime_v1` | `detection_count_mean=5.8399` | project3_cpp_board_run_synced_back | playlist_runtime_pass_task_quality_pending | 该 run 继续只承担 playlist runtime/stability 证据；正式任务级质量已由 `20260701_..._bdd100k_mini_full80_v2` 单独收口 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `prepost_pass` | `reference_from_project2_only` | `pass_1775_frames_0_gap` | `pass_1.0` | `imx219_rdkx5_hbn_001` | `detection_count_mean=0.8496` | live_source_perf_backfill | runtime_pass_live_source_mainline_task_quality_pending | 这是 `59s` no-preview live-source 性能主线；真实 `input_disconnect` 已由 `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` 补齐，BDD100K 任务级质量则由 full80 路径单独归档 |
| `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` | `not_executed_prepost_pass_local_schema_reval_pass` | `fail_AP50_0.273229_recall_0.312393` | `pass_80_sequences_raw_synced_legacy_postcheck_locally_reaggregated` | `pass_80_of_80_raw_synced` | `bdd100k_mot_mini_v1` | `AP50=0.273229, precision=0.681076, recall=0.312393, F1=0.428324, pass=3/80` | project3_bdd100k_full80_local_reaggregation | closed_nonblocking_task_fail | 板端 batch.csv 仍保留 `pipeline_exit=3` / `evaluate_status=not_run`；当前仓库已基于 80/80 raw 补齐 aggregate 与 confidence sweep，raw 最低 confidence=`0.250007` |

### RDK X5 BDD100K Full80

`20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` 的板端 batch.csv 仍保留历史 `pipeline_exit=3` / `evaluate_status=not_run`。这不表示 80 条序列没有执行完成，而是板端 wrapper 仍按旧 postcheck 口径把 `final_exit=3` 记成 `pipeline_fail`。80/80 raw、summary、trace 与 label 路径已经完整同步，当前仓库已据此补齐正式 aggregate。

| run_id | dataset | sequence_count | pass_count | fail_count | total_gt | total_pred | total_tp | total_fp | total_fn | AP50 | precision | recall | F1 | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` | `bdd100k_mot_mini_v1` | 80 | 3 | 77 | 229829 | 105417 | 71797 | 33620 | 158032 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail_recall_below_0.50 |

#### RDK X5 Full80 Confidence Sweep

该扫描使用同一批 full80 raw。板端质量 run 的 C++ 输出已经在 `0.25` 左右截断候选框，因此这里验证的是“离线降低评估阈值是否还能从现有 raw 中拉回 Recall”。结果表明不能。

| confidence_min | pass_count | fail_count | AP50 | precision | recall | F1 | status |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.01 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.03 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.05 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.10 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.15 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.20 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |
| 0.25 | 3 | 77 | 0.273229 | 0.681076 | 0.312393 | 0.428324 | fail |

直接扫描 80 份 full80 raw 的 `676254` 条预测可见：最小 `confidence=0.250007`，`<0.25` 的候选数为 `0`。因此 `0.01-0.25` 全部等值不是 sweep 脚本失效，而是当前 C++ raw 已经没有更低置信度候选。若还要继续拉 Recall，只能重新上板降低 C++ postprocess 的 confidence floor 后重跑 full80；单靠离线评估阈值无法继续挽回。

### RDK X5 Reproducibility

| item | value |
|---|---|
| board_config | `projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml` |
| single_thread_pipeline_config | `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml` |
| pipeline_config | `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml` |
| build_script | `projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh` |
| runtime_script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` |
| stability_script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` |
| bdd100k_batch_script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bdd100k_mini.sh` |
| failure_script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh` |
| monitor_script | `projects/03_video_pipeline/scripts/monitor/monitor_rdk_x5_bpu.sh` |
| service_test_script | `projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh` |
| systemd_template | `projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-rdkx5.service` |
| single_thread_run_id | `20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo` |
| playlist_runtime_run_id | `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` |
| live_source_perf_run_id | `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` |
| live_source_short_sustained_run_id | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` |
| live_source_acceptance_sustained_run_id | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` |
| bdd100k_full80_run_prefix | `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` |
| single_thread_raw | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo.jsonl` |
| playlist_runtime_raw | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline.jsonl` |
| live_source_perf_raw | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2.jsonl` |
| live_source_short_sustained_raw | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained.jsonl` |
| live_source_acceptance_sustained_raw | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained.jsonl` |
| bdd100k_full80_batch_csv | `benchmark/processed/03_video_pipeline/20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2_batch.csv` |
| bdd100k_full80_aggregate_csv | `benchmark/processed/03_video_pipeline/20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2_bdd100k_mot_quality_aggregate.csv` |
| bdd100k_full80_aggregate_md | `benchmark/processed/03_video_pipeline/20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2_bdd100k_mot_quality_aggregate.md` |
| bdd100k_full80_sweep_detail_csv | `benchmark/processed/03_video_pipeline/20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2_bdd100k_mot_quality_per_sequence.csv` |
| single_thread_schema_check | `benchmark/processed/03_video_pipeline/20260624_rdk_x5_8gb_yolo11n_bpu_single_thread_demo_schema_check.md` |
| playlist_runtime_schema_check | `benchmark/processed/03_video_pipeline/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline_schema_check.md` |
| live_source_perf_schema_check | `benchmark/processed/03_video_pipeline/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_schema_check.md` |
| live_source_trace_check | `benchmark/processed/03_video_pipeline/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_trace_check.md` |
| live_source_short_sustained_schema_check | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained_schema_check.md` |
| live_source_short_sustained_trace_check | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained_trace_check.md` |
| live_source_short_sustained_stability | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained_stability.csv` |
| live_source_acceptance_sustained_schema_check | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_schema_check.md` |
| live_source_acceptance_sustained_trace_check | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_trace_check.md` |
| live_source_acceptance_sustained_stability | `benchmark/processed/03_video_pipeline/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained_stability.csv` |
| current_mainline_command | `RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2 INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 SRCAMPY_VIDEO_IDX=0 SRCAMPY_WIDTH=640 SRCAMPY_HEIGHT=640 SRCAMPY_SENSOR_WIDTH=1920 SRCAMPY_SENSOR_HEIGHT=1080 SRCAMPY_FPS=30 SRCAMPY_WARMUP=10 DURATION_SEC=60 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` |
| current_short_sustained_command | `RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained TIER=short_sustained INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 SRCAMPY_VIDEO_IDX=0 SRCAMPY_WIDTH=640 SRCAMPY_HEIGHT=640 SRCAMPY_SENSOR_WIDTH=1920 SRCAMPY_SENSOR_HEIGHT=1080 SRCAMPY_FPS=30 SRCAMPY_WARMUP=10 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` |
| current_acceptance_sustained_command | `RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained TIER=acceptance_sustained INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 SRCAMPY_VIDEO_IDX=0 SRCAMPY_WIDTH=640 SRCAMPY_HEIGHT=640 SRCAMPY_SENSOR_WIDTH=1920 SRCAMPY_SENSOR_HEIGHT=1080 SRCAMPY_FPS=30 SRCAMPY_WARMUP=10 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` |
| current_bdd100k_full80_command | `RUN_PREFIX=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2 PYTHON_BIN=python3 START_INDEX=0 LIMIT=0 INPUT_ORIENTATION_CORRECTION=container EVALUATE_STRICT=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bdd100k_mini.sh` |
| revalidation_note | `2026-06-24` 的 `video_playlist` 与 `2026-06-30` 的 `mipi_camera_hbn` 当前都已按现行 schema 重新校验通过；板端历史 `schema_check_exit_code=1` 只保留为旧 postcheck 证据 |

### RDK X5 MLPerf-style Summary

#### Scenario

- Task: C++ realtime video inference pipeline
- Board: RDK X5 8GB
- Backend/runtime: BPU
- Execution provider: BPU
- Loader API: Horizon hbDNN C API
- Model: YOLO11n split-head INT8 PTQ
- Backend artifact: `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin`
- Backend artifact SHA256: `2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c`
- Input source: `imx219_rdkx5_hbn_001`
- Input type / path: `mipi_camera_hbn` / `srcampy://video_idx0`
- Orientation correction: `rotate180`
- Pipeline mode: `backend_pipeline`
- Queue policy: `drop_oldest` mainline
- Workers: `2 infer / 2 postprocess`
- Batch / concurrency: batch=1, concurrency=1
- Warmup: 30 frames in config
- Repeat / duration: 当前正式性能主线为 `59s` no-preview live-source run：`20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2`
- Soak reference: `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` 继续保留为 600 秒 playlist runtime 与长时 stability 证据
- Live-source sustained references: `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained`（`1798.0s`）与 `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained`（`7198.0s`）

#### Quality Gate

| item | value |
|---|---|
| Detection quality | `COCO2017 reference pass + BDD100K full80 fail`：COCO2017 `mAP50_95=0.36855805289535165`；BDD100K full80 `AP50=0.273229`, `precision=0.681076`, `recall=0.312393`, `F1=0.428324` |
| Fixed-input alignment | `prepost_pass`；未单独执行 fixed-input run |
| Task-level quality | `closed_nonblocking_task_fail`；full80 `pass_count=3/80`，`0.01-0.25` confidence sweep 无增益 |
| Frame trace | `pass_1775_frames_0_gap` |
| Queue policy | `drop_oldest` realtime bounded queue |
| Output validity | `pass_1.0` |
| Pass / Fail | `runtime_pass_live_source_mainline_acceptance_sustained_disconnect_pass_bdd100k_quality_fail_closed_nonblocking` |

#### Performance

| metric | value |
|---|---:|
| p50 end-to-end latency | 141.6540 |
| p90 end-to-end latency | 162.2392 |
| p95 end-to-end latency | 165.1727 |
| p99 end-to-end latency | 168.6542 |
| FPS | 30.0847 |
| drop frame rate | 0.0000 |
| frame gap | 0 |
| relative uplift vs `perf_opt2` | +50.3% |

#### Resource

| metric | value |
|---|---:|
| memory peak | 127.219 process_hwm MB |
| memory growth | 269.5286 MB/hour |
| temperature max | 69.182 C |
| power mode / power | not_recorded |
| CPU/GPU/NPU/BPU utilization | `bpu_devfreq=996 MHz`, `ddr=4266 MHz`, `gpu=996 MHz`, `bpu_load_path=not_found` |

#### Reproducibility

- Environment baseline: `20260612_rdk_x5_8gb_env_baseline`
- Single-thread smoke config: `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml`
- Pipeline config: `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml`
- Stream config: `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml`
- Model config: `projects/03_video_pipeline/configs/models/yolo11n.yaml`
- Backend artifact: `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin`
- Command: `RUN_ID=20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2 INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 SRCAMPY_VIDEO_IDX=0 SRCAMPY_WIDTH=640 SRCAMPY_HEIGHT=640 SRCAMPY_SENSOR_WIDTH=1920 SRCAMPY_SENSOR_HEIGHT=1080 SRCAMPY_FPS=30 SRCAMPY_WARMUP=10 DURATION_SEC=60 SAVE_OUTPUT_VIDEO=0 bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh`
- Raw result: `benchmark/raw/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2.jsonl`
- Processed result: `benchmark/processed/03_video_pipeline/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_summary.csv`
- Trace check: `benchmark/processed/03_video_pipeline/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_trace_check.md`
- Runtime logs: `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2.log`
- Monitor logs: `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2_bpu.log`
- Related run: `projects/03_video_pipeline/runs/20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2/run.md`
- Playlist soak reference: `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline`


# 项目三视频 Pipeline 总报告

## Jetson 子项目收口结论（2026-06-23）

可以收口，但口径必须写准确：

1. 当前对话范围内，**Jetson 工程子项目已完成收口**，闭环范围包括 `03A / 03B / 03C / 03D / 03G / 03H`。
2. 正式工程主线结论是：`INT8 TensorRT + video playlist 主线 + IMX219 live-source + 异常恢复 + 稳定性` 均已形成板端证据。
3. `BDD100K MOT mini` 的任务级质量没有通过门限，但它已经按 `closed_nonblocking_task_fail` 单独归档，**不再阻塞 Jetson 子项目收口**。
4. 因此当前不能写成“Jetson 性能与质量双通过”，但可以写成“**Jetson 工程主线收口完成，质量问题已按非阻塞失败归档**”。
5. 剩余事项只属于可选优化，不再属于本轮 Jetson 必做项：
   - 默认队列策略是否从 `drop_oldest` 切换到其它策略
   - 输出视频保存路径的实时性优化
   - IMX219 在修正 `fixed_10bit` 高位对齐实现后，重新验证“图像有效 + 吞吐”的正式 live-source 口径

## 2026-06-19 规范重审

按 [03_Cpp实时视频流推理Pipeline.md](../03_Cpp实时视频流推理Pipeline.md) 和 [03D_Jetson_TensorRT_CppPipeline规范.md](../specs/03D_Jetson_TensorRT_CppPipeline规范.md) 在 `2026-06-19` 当时状态重查后，**当时不能写成“所有实验都完成了”**。下面这张表保留的是那次规范审计时的历史判断，用于说明后续为什么还需要继续补板端正式证据。

| 审计项 | 规范要求 | 当前判定 | 现有证据 | 剩余缺口 |
|---|---|---|---|---|
| 03A 单线程 demo | 需要正式单线程 run、raw/log/output | 已完成 | `20260622_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo` 已完成正式上板 run；`trace/schema/prepost` 全 pass，`frame_id_gaps=0` | 无 |
| 03B 多线程 pipeline | 需要正式 03B run、trace、队列证据，且前置 03A 完成 | 已完成 | `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` 已完成正式命名 run；`30.13 FPS`、`frame_id_gaps=0`、`drop_frame_rate_total_estimated=0.0`，且可与 03A 显式对照 | 无 |
| 03C 队列策略 | `drop_oldest` / `drop_newest` / `block_with_timeout` 对照 | 已完成 | `20260617` / `20260618` 的 runtime600 noout 与 smoke block timeout 已完成 | 无 |
| 03C buffer 复用 | 要求 `buffer_reuse` 前后内存或分配压力对比，无法统计时必须说明原因 | 已完成（backend-level） | RK3588 与 Jetson 均已于 `20260622` 完成 `buffer_reuse=true/false` A/B；当前共享 app 已实证的是 backend 级 buffer reuse。RK3588 侧对应 RKNN `input_io_mem + output_prealloc`，Jetson 侧对应 TensorRT 预分配 device buffer 路径；Jetson 600 秒对照结论为 `buffer_reuse_beneficial`，表现为 `inference_p50` 从 `20.9316 ms` 降到 `18.1851 ms`、`latency_p95` 从 `64.6967 ms` 降到 `62.0564 ms`、`memory_peak` 从 `3512 MB` 降到 `3504 MB`，FPS 基本持平 | `memory_growth_mb_per_hour` 基于单轮 `600s` 样本波动较大，只作辅助指标，不单独作为 blocker；`pool_size` 当前仍为配置占位，不能单独宣称“通用 buffer pool 已落地” |
| 03D Jetson 主线 | INT8、TensorRT GPU、600 秒 pipeline benchmark、至少一种实时源 | 已完成 | INT8 artifact、TensorRT GPU、playlist-paced + noout 的 600 秒 video-file 主线已验证；IMX219 正式 live-source、4h 稳定性与 `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 都已留证 | Argus 路径当前板端已确认不可作为正式主线，但这不再阻塞 03D 收口 |
| 03G 异常恢复 | `input_disconnect` 需真实 live-source 补证 | 已闭环 | CLI 5 case + systemd 生命周期 + `20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_appfault` 已完成 | `driver_unbind` SSH 断开风险转入问题库，不再阻塞 03G 主线 |
| 03H 稳定性 | 30 分钟必测，2 小时为验收目标 | 已完成 Jetson noout 基线 | `short_sustained=1797s`、`acceptance_sustained=7196s` 均达到完成阈值 | `long_sustained` 仍未执行，但不是必测项 |
| 任务级视频质量 | 变更 C++ pipeline 后应有任务级质量结论 | 已执行未通过且已按非阻塞失败归档 | BDD100K MOT mini no-drop 路径已跑 | 当前结论是 `quality_threshold_fail`，不能写质量 `pass`；但该项已按 `closed_nonblocking_task_fail` 收口，不再阻塞后续 Jetson 子任务 |
| 摄像头要求 | 总规范要求摄像头或 RTSP 断流可恢复或清晰报错 | Jetson 与 RK3588 均已闭环 | Jetson IMX219 已完成 `INPUT_DISCONNECTED -> exit 11`；RK3588 Astra S OpenNI 已完成板端 probe、non-root smoke、`input_disconnect` 和 camera service 生命周期 | Astra S 权限依赖 `/etc/udev/rules.d/99-orbbec-astra.rules`；若更换 USB 端口需复查 selector 与权限 |

关于“摄像头是不是必须”这里要写清楚：

- **是，至少一种实时源在规范层面是必须的**。03D 固定参数里明确写了 `input_source = video file + realtime source`，并要求“至少一种实时源”；总规范最终验收里也要求“摄像头或 RTSP 断流有恢复或清晰错误”。
- **当前 Jetson 正式 live-source 已切换为 IMX219**。原因不是“偏好摄像头名”，而是当前代码已经补入了 IMX219 所需的 `RG10 raw -> debayer -> white balance` 专用链路，能和项目三主 app 的多线程/单线程/报告链路统一落证。
- **当前 IMX219 实现是项目三内部独立实现**。代码位于 `projects/03_video_pipeline/src/video_pipeline_app.cpp`，运行入口位于 `projects/03_video_pipeline/scripts/run/`；当前没有对旧仓库的源码、脚本或构建产物形成运行时依赖。
- **当前实时预览能力也已经接入共享主线**。共享 C++ app 通过 `PREVIEW_WINDOW=auto|on|off` 控制：当输入源属于 `mipi_camera` / `mipi_camera_hbn` / `mipi_camera_argus` / `usb_camera` / `openni_camera` / `rtsp`，且板端存在 `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE=x11|wayland` 时，会在屏幕上实时显示检测框、英文类别名、`FPS` 和 `DET`。
- **非交互正式 benchmark 默认不应开预览**。`stability`、`8h_mixed`、`bufferreuse_ab`、`imx219_disconnect` 已统一按 `PREVIEW_WINDOW=off` 处理；需要人工观察摄像头画面时，应使用单次 `run_jetson_tensorrt_pipeline.sh + PREVIEW_WINDOW=auto`，不要把长时 benchmark 当作现场预览入口。

## 当前主线队列策略口径

这里必须明确写清楚，不能只看缩写猜意思：

- 队列策略只在“目标队列已满”时触发；未满时直接入队。
- `queue_push_timeout_ms` 等待的是“队列空位”，不是“下游推理响应”。
- 当前主线实现里，`queue_policy` 与 `queue_push_timeout_ms` 会同时作用于四段内部有界队列，而不是每段各自不同。

| 策略 | 当前主线里队列满时的实际动作 | 文档解释 |
|---|---|---|
| `drop_oldest` | 丢掉队列里最旧帧，再让当前新帧入队 | 低延迟优先，保最新视图 |
| `drop_newest` | 丢掉当前新帧，队列里旧帧继续保留 | 保留已排队结果，但更容易延后最新画面 |
| `block_with_timeout(33ms)` | 最多等 `33 ms` 看队列是否腾出空位；等到就入队，等不到就丢当前新帧 | 这里的 `33 ms` 是“单次入队等待上限”，不是“33 ms 无响应整条链路失败” |
| `block` / `no_drop` | 一直等到有空位才继续 | 适合 no-drop / 质量路径，不适合默认实时显示主线 |

## Jetson 主线结论

### 最新主线 run

| item | value |
|---|---|
| run_id | `20260622_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline` |
| target | `jetson_8gb` |
| backend_runtime | `tensorrt` |
| execution_provider | `TensorRT-GPU` |
| precision_or_quantization | `int8_ptq` |
| backend_artifact_path | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` |
| backend_artifact_sha256 | `1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d` |
| queue_policy | `drop_oldest` |
| queue_capacity | `8` |
| schema_check | `pass` |
| prepost_consistency | `pass` |
| trace_check | `pass` |
| cpu_fallback | `false` |
| output_valid_rate | `1.0` |

### 关键指标

| metric | value |
|---|---:|
| duration_sec_estimated | 599.0 |
| fps_estimated | 30.1302 |
| latency_p50_ms | 60.1854 |
| latency_p95_ms | 63.7580 |
| latency_p99_ms | 66.1065 |
| frame_id_gaps | 0 |
| drop_frame_count_total_estimated | 0 |
| drop_frame_rate_total_estimated | 0.0 |
| output_p50_ms | 0.0380 |
| memory_mb_peak | 3484.0 |
| temperature_c_peak | 59.5 |
| cpu_util_avg | 29.0598 |
| gpu_util_avg | 42.8280 |
| throttle_events | 622 |

### 正确解读

- 这轮 run 是 **INT8 + playlist-paced + 默认 noout 多线程主线已正式闭环** 的证据。
- 这轮 run 在 `600s` 内达到了 `30.13 FPS`、`18048` 帧、`0` gap、`0` out-of-order、`0` missing_stage_timestamps。
- 对照 `03A` 的单线程正式 run，可见 Jetson 在当前主线配置下，多线程路径相对单线程把吞吐从 `25.08 FPS` 提高到 `30.13 FPS`，同时保持全链路 trace 完整。
- 因此，这轮结果的正确标签应更新为：`runtime_pass_all_postchecks_pass_multithread_mainline`。

## 质量与证据链

### 2026-06-18 03I 本地汇总进展

- 已生成：
  - `benchmark/processed/03_video_pipeline/runtime_summary.csv`
  - `benchmark/processed/03_video_pipeline/stability_summary.csv`
  - `benchmark/processed/03_video_pipeline/excluded_runs.md`
- 已确认：
  - `aggregate_stability.py` 需要直接使用 raw 中记录的 `monitor_log_path`，不能把监控目录作为 `--monitor` 参数传入
- 当前已闭环项：
  - `benchmark/processed/03_video_pipeline/schema_check_report.md` 对全量 raw root 在默认 formal scope 下已是 `pass`
  - 默认 formal scope 已自动排除 13 份非正式 raw：
    - `02_quantization/` 下 11 份 legacy inherited raw
    - 文件名含 `project1_baseline` 的 2 份跨项目 fixed-input 对照 raw
  - `excluded_runs.md` 已明确记录上述排除原因，不再是空模板

## RK3588 子项目收口结论

可以收口，但口径必须写准确：

1. 当前对话范围内，**RK3588 工程子项目已可正式收口**。闭环范围包括：`03E` RKNN C++ realtime pipeline 主线、Astra S live-source、`03G` 异常注入 / 服务化、`03H` short/acceptance/8h mixed 稳定性，以及 COCO2017 artifact 复检与 BDD100K task-level quality 执行链路。
2. 正式工程主线结论应写为：`runtime_pass_mixed_8h_camera4h_video4h_realtime_with_negligible_drop_bdd100k_quality_fail`。其中 `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h` 已形成 camera 4h + video 4h 的组合长稳证据；camera 段零 gap/零 drop，video 段仅丢 `8 / 432758` 帧，且全程零乱序、零新增 RKNPU timeout/reset。
3. `BDD100K MOT mini` 的任务级质量没有通过门限，但它已经按**非阻塞失败**单独归档，因此不能写成“RK3588 性能与任务质量双通过”，但可以写成“**RK3588 工程主线收口完成，任务级质量问题已归档且不阻塞当前交付**”。
4. `03C` 这边当前可交付的准确表述是：**RKNN backend buffer reuse 已完成**，也就是 `input_io_mem + output_prealloc` 的 A/B 与证据已经闭环；`pool_size` 仍是配置占位，不能写成通用 buffer pool 已落地。队列策略正式对照当前以 Jetson 侧为主，RK3588 formal 主线保留 `drop_oldest` baseline。
5. 因此，**RK3588 当前不再有必须补跑的板端实验**。后续若继续投入，只属于可选专项优化，例如重开 BDD100K recall 提升、补做 RK3588 自身的 `drop_newest / block_with_timeout` 对照，或真正实现通用 buffer pool；这些都不再构成当前切换到下一块开发板前的 blocker。

## 下一步

项目三当前**没有剩余必做项**。若后续继续投入，只属于可选专项优化，不再影响本项目收口：

1. 重新上板降低 Jetson / RK3588 / RDK X5 的 C++ postprocess confidence floor，再重跑 BDD100K full80，验证 Recall 是否还有可挖空间。
2. 继续优化 live-source 采集与后处理效率，例如 IMX219 采集侧、颜色处理、输出路径或 writer 异步化。
3. 如需对默认实时主线队列策略做产品化决策，再补 `block_with_timeout` 或其它策略的更长时长对照实验。

## 2026-06-17 Update: Playlist-paced Mainline And Stability

### 当前最重要的运行口径

- 输入侧已恢复到接近 `30 FPS`：
  - runtime600：`frame_id_max=18047`，约 `30.3 FPS`
  - acceptance：`frame_id_max=216401`，约 `30.1 FPS`
- 输出侧只能稳定在约 `25-26 FPS`
- 当前主要瓶颈：
  - `output_p50_ms ≈ 37-38 ms`
  - `inference_p50_ms ≈ 9.7 ms`
  - `queue_postprocess_p95 = 8`

### 当前一句话总结

项目三 Jetson 端已经完成 **playlist-paced 真实播放语义下的 INT8 TensorRT 主线与 sustained 验证**；当前剩余核心问题不是输入节流，也不是推理算力，而是 **输出视频路径过慢，导致 `drop_oldest` 主线在 30 FPS 输入下稳定丢掉约 13%-17% 帧**。

补充说明：

- 关闭 `SAVE_OUTPUT_VIDEO` 后，runtime600 和 smoke 都恢复到约 `30.1 FPS`
- 总体丢帧率降到约 `0.6%`
- `output_p50_ms` 从约 `38 ms` 下降到约 `0.04 ms`

因此，当前最准确的工程判断是：

- Jetson 板端 TensorRT 推理本身足以跟上这组约 `30 FPS` 的视频输入
- 真正拉低主线实时性的，是“保存输出视频”这条附加路径
- 当前仓库默认已切换为：主线 / stability 默认不保存输出视频，视频保存只在明确需要时手动开启

## 2026-06-18 Update: RK3588 RKNN 03E 落地状态

RK3588 路线现在已经完成三 context 600 秒 runtime、1800 秒 short sustained、7199 秒 acceptance sustained，以及 `20260622_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h` 的正式 8h mixed。该 8h mixed 先执行 Astra S 4h，再执行 video playlist 4h：camera 段达到 `29.6003 FPS`，`426245` 帧、零 gap、零乱序、零 drop，`memory_peak=253.95 MB`、`temperature_c_peak=55.46 C`；video 段达到 `30.0521 FPS`，`432750` 帧、严格 trace 下有 5 个 gap event、共 8 帧，`frame_id_out_of_order=0`、丢帧率仅 `1.8486e-05`、`dropped_frame_reason=queue_full`，`memory_peak=365.42 MB`、`temperature_c_peak=56.38 C`。runtime log 已补同步并确认无 error、timeout/reset、OOM 或 CPU fallback，monitor log 无新增 RKNPU dmesg 异常；因此当前应按“8h mixed 实时稳定性通过，严格 zero-gap trace 失败证据单独保留”收口。BDD100K 任务质量仍按非阻塞 fail 独立保留。

| item | value |
|---|---|
| inherited_environment_baseline_id | `20260611_rk3588_8gb_env_baseline` |
| source_project2_run | `20260611_rk3588_8gb_yolo11n_rknnopt_int8_int8_ptq_calib500_benchmark` |
| source_project2_quality | `mAP50_95=0.3814960637396267`, `accuracy_drop=0.00500393626`, `pass` |
| project3_board_config | `projects/03_video_pipeline/configs/boards/rk3588_8gb.yaml` |
| project3_pipeline_config | `projects/03_video_pipeline/configs/pipeline/rk3588_rknn_pipeline.yaml` |
| build_script | `projects/03_video_pipeline/scripts/build/build_rk3588_rknn.sh` |
| run_script | `projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh` |
| stability_script | `projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh` |
| monitor_script | `projects/03_video_pipeline/scripts/monitor/monitor_rk3588_rknpu.sh` |
| backend_wrapper | `projects/03_video_pipeline/src/video_pipeline_app.cpp` 中 `PIPELINE_BACKEND_RKNN` / `RknnBackend` |
| rknn_postprocess | `DecodeRknnOfficialYolo11`，对齐项目一/二 RKNN official-path 的 9 输出 split-head + DFL 后处理 |
| bdd100k_full80_quality | AP50=0.351213, precision=0.373474, recall=0.445810, F1=0.406449, TP/FP/FN=102460/171883/127369 |
| current_status | `runtime_pass_mixed_8h_camera4h_video4h_realtime_with_negligible_drop_bdd100k_quality_fail` |

2026-06-18 artifact 决策：项目三改用 PC 与 RK3588 板端一致的 `40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c`。该 artifact 已在 RK3588 上完成完整 5000 张 COCO2017 复检，`mAP50_95=0.381496063740`、相对 FP32 baseline 掉点 `0.005003936260`，状态 `pass`；项目三正式 labeled-video 质量由 BDD100K MOT mini 单独评估。

RK3588 的模型 hash blocker 已在板端解除：`2026-06-18` 在 `&lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab` 执行下面命令，输出与项目二正式记录一致：

```bash
sha256sum models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn
```

```text
40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c  models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn
```

构建 blocker 已解除：2026-06-18 板端显式传入 RKNN header 和 runtime library 后，`build/03_video_pipeline_rk3588/video_pipeline_app` 已成功生成。

```bash
RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_build \
RKNN_INCLUDE_DIR=&lt;BOARD_USER_HOME&gt;/rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/include \
RKNNRT_LIBRARY=/usr/lib/librknnrt.so \
  bash projects/03_video_pipeline/scripts/build/build_rk3588_rknn.sh
```

运行状态：

| item | value |
|---|---|
| run_id | `20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline` |
| prepost_consistency | pass |
| hash_status | pass |
| final_exit | 0 |
| final_status | `not_verified_until_fixed_input_alignment_and_report_pass` |
| raw_result | `benchmark/raw/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline.jsonl` |
| processed_summary | `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_summary.csv` |
| schema_check | `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_schema_check.md` |
| trace_check | `benchmark/processed/03_video_pipeline/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_trace_check.md` |
| runtime_log | `logs/runtime/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline.log` |
| monitor_log | `logs/monitor/03_video_pipeline/rk3588_8gb/20260618_rk3588_8gb_yolo11n_rknn_cpp_pipeline_rknpu.log` |

### RDK X5 代码 / 配置 / 脚本落点

| 类型 | 路径 | 作用 |
|---|---|---|
| board config | `projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml` | 固定环境继承、artifact、BPU evidence 字段 |
| single-thread pipeline config | `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml` | 首次上板最小链路、hbDNN 初始化、NV12 输入和 split-head decode 验证 |
| pipeline config | `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml` | 固定线程、队列、日志和 benchmark 口径 |
| build script | `projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh` | 统一 `PIPELINE_BACKEND=bpu` 构建入口 |
| runtime script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` | 统一 C++ runtime benchmark 入口 |
| stability script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | smoke/short/acceptance sustained 入口 |
| failure script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh` | CLI failure schema JSONL 入口 |
| live disconnect script | `projects/03_video_pipeline/scripts/run/run_rdk_x5_input_disconnect.sh` | `imx219_rdkx5_hbn_001` 的真实 live-source `input_disconnect` 入口；默认 `PREVIEW_WINDOW=auto`，当前 IMX219 默认朝向修正为 `rotate180` |
| monitor script | `projects/03_video_pipeline/scripts/monitor/monitor_rdk_x5_bpu.sh` | devfreq / thermal / process memory / optional `hrut_somstatus` |
| service test | `projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh` | systemd 生命周期入口 |
| systemd template | `projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-rdkx5.service` | RDK X5 service 模板 |

### RDK X5 Benchmark 与证据状态

| 证据项 | 当前状态 | 说明 |
|---|---|---|
| artifact 选型 | pass | split-head `.bin` 已固定 |
| 项目二质量参考 | pass_with_resource_note | COCO2017 `mAP50_95=0.36855805289535165`，但仅限 reference |
| 项目二资源参考 | pass_with_resource_note | system memory max `1146.219 MB`、process HWM max `443.75 MB`、max temp `57.067 C` |
| 项目三 C++ runtime raw | pass_playlist_runtime_board_verified | `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline`：`600s` playlist runtime，`18.12 FPS`，`p95=167.09 ms`，`drop_frame_rate=0.3967`，`queue_full` 可解释 |
| 项目三 live-source 性能主线 | pass_live_source_perf_mainline_selected | `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2`：`59s` IMX219 no-preview，`30.08 FPS`，`p95=165.17 ms`，`drop_frame_rate=0.0`，`frame_id_gaps=0`，当前正式 workers=`2 infer / 2 postprocess` |
| 项目三 C++ stability | pass_playlist_stability_board_verified | smoke / short / acceptance 三档都已回填；`7200s` acceptance 为 `18.48 FPS`、`p95=166.58 ms`、memory growth `0.3597 MB/h` |
| 项目三 03G failure wrapper | pass_cli_5of5 | `input_open_failed / model_missing / invalid_shape / output_unwritable / queue_overflow` 全部通过 |
| 项目三 03G service lifecycle | pass_board_verified | `20260624_rdk_x5_8gb_systemd_service_test_v2` 已验证 `start=active`、`restart=active`、`stop=inactive`、`health_check=pass`；旧 placeholder fail 样本保留作排障证据 |
| 项目三 live-source | runtime_pass_perf_mainline_acceptance_disconnect_pass | 当前正式口径为 `imx219_rdkx5_hbn_001`（`mipi_camera_hbn + HBN/srcampy`）；`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` 已在该 source 上完成 `7198s / 30.3865 FPS / 0 gap / 0 drop / trace pass` 的 2 小时验收稳定性补证，`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` 则完成真实 `INPUT_DISCONNECTED -> exit 11` 板端闭环 |
| 项目三 BDD100K full80 任务质量 | closed_nonblocking_task_fail | `20260701_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini_full80_v2` 的 80/80 raw 已同步；当前仓库已补齐 aggregate 与 confidence sweep，正式结果为 `AP50=0.273229`、`precision=0.681076`、`recall=0.312393`、`F1=0.428324`、`pass_count=3/80`；`0.01-0.25` sweep 完全一致，说明现有 raw 中没有 `<0.25` 的候选框，无法靠离线降评估阈值继续拉回 Recall |
